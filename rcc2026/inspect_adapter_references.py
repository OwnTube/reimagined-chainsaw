"""Read-only x64 reference inventory for the exact pinned Studio image.

Reports locations and boundary checks, not decompiled code or hook targets.
"""
import argparse
import bisect
import hashlib
import json
from pathlib import Path
import re
import struct

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

from windows_probe import STUDIO_SHA256

ANCHORS = {
    'trust_failure': b'Trust check failed',
    'http_request_untrusted': b'HttpRequest.Url is not trusted',
    'image_url_untrusted': b'Image Url is not trusted',
    'cookie_cache_message': b'[FLog::StudioCookieManager] Security cookie is cached so we proceed saving now.',
}
CANDIDATE_RVA = 0x04DDD610


def relative_references(data, section_rva, targets, memory=True, branches=True):
    """Find selected encodings, including overlaps; boundaries are checked later."""
    if memory:
        pattern = rb'(?=([\x48\x4c][\x8d\x8b][\x05\x0d\x15\x1d\x25\x2d\x35\x3d]....))'
        for match in re.finditer(pattern, data, re.DOTALL):
            at = section_rva + match.start()
            target = at + 7 + struct.unpack_from('<i', match.group(1), 3)[0]
            if target in targets:
                yield {'rva': at, 'target_rva': target, 'bytes': 7, 'kind': 'rip_relative_memory'}
    if branches:
        for opcode, kind in ((b'\xe8', 'direct_call'), (b'\xe9', 'direct_jump')):
            cursor = 0
            while (offset := data.find(opcode, cursor)) >= 0:
                cursor = offset + 1
                if offset + 5 > len(data):
                    continue
                at = section_rva + offset
                target = at + 5 + struct.unpack_from('<i', data, offset + 1)[0]
                if target in targets:
                    yield {'rva': at, 'target_rva': target, 'bytes': 5, 'kind': kind}


def instruction_sizes(data, start_rva):
    return {ins.address: ins.size for ins in Cs(CS_ARCH_X86, CS_MODE_64).disasm(data, start_rva)}


def inspect(path):
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != STUDIO_SHA256:
        raise ValueError('Expected the exact examined Studio executable')
    pe = pefile.PE(data=raw, fast_load=True)
    if pe.FILE_HEADER.Machine != 0x8664:
        raise ValueError('Expected AMD64')
    pe.parse_data_directories(directories=[3])
    ranges = sorted((e.struct.BeginAddress, e.struct.EndAddress)
                    for e in pe.DIRECTORY_ENTRY_EXCEPTION)
    starts = [a for a, _ in ranges]
    executable = [(s.VirtualAddress, raw[s.PointerToRawData:s.PointerToRawData+s.SizeOfRawData])
                  for s in pe.sections if s.Characteristics & 0x20000000]
    cache = {}

    def owner(rva):
        idx = bisect.bisect_right(starts, rva) - 1
        return ranges[idx] if idx >= 0 and rva < ranges[idx][1] else None

    def verify(reference):
        extent = owner(reference['rva'])
        reference['unwind_range'] = list(extent) if extent else None
        if extent is None or extent[1] - extent[0] > 1024 * 1024:
            reference['boundary_verified'] = None
            return reference
        if extent not in cache:
            cache[extent] = instruction_sizes(pe.get_data(extent[0], extent[1]-extent[0]), extent[0])
        reference['boundary_verified'] = cache[extent].get(reference['rva']) == reference['bytes']
        return reference

    anchors = {}
    for label, needle in ANCHORS.items():
        cursor = 0
        while (offset := raw.find(needle, cursor)) >= 0:
            cursor = offset + 1
            # A substring is not itself necessarily the referenced literal.
            start = raw.rfind(b'\0', max(0, offset-256), offset) + 1
            end = raw.find(b'\0', offset, offset+512)
            if end < 0 or end-start > 512 or not all(32 <= b < 127 for b in raw[start:end]):
                continue
            rva = pe.get_rva_from_offset(start)
            item = anchors.setdefault(rva, {'rva': rva, 'labels': [],
                'literal_sha256': hashlib.sha256(raw[start:end]).hexdigest(),
                'literal_bytes': end-start})
            if label not in item['labels']:
                item['labels'].append(label)
    memory_refs = [verify(ref) for base, data in executable
                   for ref in relative_references(data, base, set(anchors), branches=False)]
    owners = {ref['unwind_range'][0] for ref in memory_refs
              if ref['boundary_verified'] and ref['unwind_range']}
    targets = owners | {CANDIDATE_RVA}
    branches = [verify(ref) for base, data in executable
                for ref in relative_references(data, base, targets, memory=False)]
    candidate_range = owner(CANDIDATE_RVA)
    outgoing = []
    if candidate_range:
        decoder = Cs(CS_ARCH_X86, CS_MODE_64)
        decoder.detail = True
        from capstone.x86 import X86_OP_IMM
        for ins in decoder.disasm(pe.get_data(candidate_range[0], candidate_range[1]-candidate_range[0]), candidate_range[0]):
            if (ins.mnemonic == 'call' or ins.mnemonic.startswith('j')) and ins.operands and ins.operands[0].type == X86_OP_IMM:
                outgoing.append({'rva': ins.address, 'kind': ins.mnemonic,
                                 'target_rva': ins.operands[0].imm})
    return {'artifact_sha256': digest, 'candidate_rva': CANDIDATE_RVA,
            'candidate_unwind_range': list(candidate_range) if candidate_range else None,
            'candidate_direct_outgoing_edges': outgoing,
            'anchors': list(anchors.values()), 'anchor_references': memory_refs,
            'incoming_direct_branches': branches,
            'runtime_validated': False, 'hooks_installed': False,
            'limitations': [
                'Selected x64 encodings only; indirect references and UTF-16 anchors are not covered.',
                'Linear instruction boundaries from unwind starts are not proof of reachability.',
                'Unwind ranges may be fragments, not complete functions.',
                'String relationships and byte matches do not establish semantic identity or ABI.',
                'No code bytes, routing, authentication, or runtime state were changed.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.binary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'anchors': len(result['anchors']),
                      'anchor_references': len(result['anchor_references']),
                      'verified_anchor_references': sum(r['boundary_verified'] is True for r in result['anchor_references']),
                      'direct_branch_references': len(result['incoming_direct_branches']),
                      'runtime_validated': False}, indent=2))
