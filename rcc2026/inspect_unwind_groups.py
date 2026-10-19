"""Read-only chained-unwind groups and control-flow metadata for pinned Studio.

Layout reference: https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64
No instruction bytes, plaintext literals, hooks, or decompiled code are emitted.
"""
import argparse
from collections import Counter
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import struct

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_GRP_CALL, CS_GRP_JUMP
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

from windows_probe import STUDIO_SHA256

SEEDS = (0x04DDD610, 0x040B1F60)
SERVICE_ERROR = b'HttpRbxApiService::isHttpCallAllowedToUrl HttpRbxApiService is not initialized.'


def parse_unwind_info(data):
    """Decode only the documented V1 header and optional chained RUNTIME_FUNCTION."""
    if len(data) < 4:
        raise ValueError('Truncated unwind header')
    unwind_version, flags, count = data[0] & 7, data[0] >> 3, data[2]
    if unwind_version != 1:
        raise ValueError('Unsupported unwind version')
    if flags & ~7 or flags & 4 and flags & 3:
        raise ValueError('Invalid or unsupported unwind flags')
    tail = 4 + ((count + 1) & ~1) * 2
    needed = tail + (12 if flags & 4 else 4 if flags & 3 else 0)
    if len(data) < needed:
        raise ValueError('Truncated unwind codes or trailer')
    return {'version': unwind_version, 'flags': flags, 'code_slots': count,
            'chain': struct.unpack_from('<III', data, tail) if flags & 4 else None}


def resolve_root(entry, parents, entries, max_depth=32):
    """Reject cycles, absent chain records, and excessive nesting, not just stop."""
    seen = set()
    for _ in range(max_depth):
        if entry not in entries:
            raise ValueError('Chained RUNTIME_FUNCTION is absent from the exception table')
        if entry in seen:
            raise ValueError('Cycle in unwind chain')
        seen.add(entry)
        parent = parents[entry]
        if parent is None:
            return entry
        entry = parent
    raise ValueError('Unwind chain depth limit exceeded')


def inspect(path):
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != STUDIO_SHA256:
        raise ValueError('Expected the exact pinned Studio executable')
    pe = pefile.PE(data=raw, fast_load=True)
    if pe.FILE_HEADER.Machine != 0x8664:
        raise ValueError('Expected AMD64')
    directory = pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
    table = pe.get_data(directory.VirtualAddress, directory.Size)
    if len(table) != directory.Size or len(table) % 12:
        raise ValueError('Invalid exception directory size')
    entries = set(struct.iter_unpack('<III', table))
    by_start = {e[0]: e for e in entries}
    if len(by_start) != len(entries) or any(a >= b for a, b, _ in entries):
        raise ValueError('Duplicate or invalid runtime-function ranges')
    headers, parents, unsupported = {}, {}, set()
    for entry in entries:
        unwind_rva = entry[2]
        if unwind_rva not in headers:
            try:
                # V1's byte count limits codes + trailer to at most 528 bytes.
                headers[unwind_rva] = parse_unwind_info(pe.get_data(unwind_rva, 528))
            except ValueError:
                headers[unwind_rva] = None
        header = headers[unwind_rva]
        if header is None:
            unsupported.add(entry)
        else:
            parents[entry] = header['chain']
    roots, unresolved = {}, Counter()
    for entry in sorted(entries):
        try:
            roots[entry] = resolve_root(entry, parents, entries)
        except (KeyError, ValueError) as exc:
            unresolved[type(exc).__name__] += 1
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    groups = []
    for seed in SEEDS:
        seed_entry = by_start[seed]
        root = roots[seed_entry]  # Unsupported seed metadata must fail closed.
        members = sorted(e for e, primary in roots.items() if primary == root)
        ranges = [(a, b) for a, b, _ in members]
        instructions, direct, indirect, literals, returns = {}, [], [], [], []
        for start, end in ranges:
            if end-start > 1024*1024:
                raise ValueError('Unexpectedly large selected unwind range')
            body = pe.get_data(start, end-start)
            decoded = list(decoder.disasm(body, start))
            if sum(i.size for i in decoded) != end-start:
                raise ValueError('Selected unwind range did not decode completely')
            for ins in decoded:
                instructions[ins.address] = ins.size
                if ins.mnemonic.startswith('ret'):
                    returns.append(ins.address)
                if ins.group(CS_GRP_CALL) or ins.group(CS_GRP_JUMP):
                    if ins.operands and ins.operands[0].type == X86_OP_IMM:
                        target = ins.operands[0].imm
                        direct.append({'rva': ins.address, 'kind': ins.mnemonic,
                                       'target_rva': target,
                                       'target_in_group': any(a <= target < b for a, b in ranges)})
                    else:
                        indirect.append({'rva': ins.address, 'kind': ins.mnemonic})
                for operand in ins.operands:
                    if operand.type == X86_OP_MEM and operand.mem.base == X86_REG_RIP:
                        target = ins.address + ins.size + operand.mem.disp
                        if pe.get_data(target, len(SERVICE_ERROR)+1) == SERVICE_ERROR+b'\0':
                            literals.append({'rva': ins.address, 'target_rva': target,
                                'label': 'http_service_uninitialized',
                                'literal_sha256': hashlib.sha256(SERVICE_ERROR).hexdigest()})
        for edge in direct:
            edge['target_boundary_in_group'] = edge['target_rva'] in instructions if edge['target_in_group'] else None
        groups.append({'seed_rva': seed, 'primary_runtime_function': list(root),
            'members': [list(e) for e in members], 'total_code_bytes': sum(b-a for a,b in ranges),
            'instruction_count': len(instructions), 'direct_edges': direct,
            'indirect_edges': indirect, 'return_sites': returns, 'named_literal_references': literals})
    return {'artifact_sha256': digest, 'exception_table_entries': len(entries),
        'unsupported_unwind_entries': len(unsupported), 'unresolved_chains': dict(unresolved),
        'decoder_distribution': 'capstone=='+version('capstone'), 'groups': groups,
        'runtime_validated': False, 'hooks_installed': False,
        'limitations': ['Chained unwind membership is not a complete control-flow or function-identity proof.',
            'Linear decoding does not establish branch feasibility, argument layouts, or runtime values.',
            'Indirect targets and exception-handler paths are not resolved.',
            'Only V1 unwind records are supported; selected seeds fail closed if unresolved.',
            'No code, authentication, URL routing, or runtime state was modified.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.binary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'groups': [{k: g[k] for k in ('seed_rva', 'total_code_bytes', 'instruction_count')}
                                  for g in result['groups']],
                      'runtime_validated': False}, indent=2))
