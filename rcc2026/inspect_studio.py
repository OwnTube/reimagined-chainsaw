"""Read-only PE evidence and historical signature comparison; never patches a binary."""
import argparse
import bisect
import hashlib
import json
import re
from pathlib import Path

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64


def positions(data, pattern):
    tokens = pattern.split()
    if not tokens or any(not re.fullmatch(r'[0-9A-Fa-f]{2}|\?\??', t) for t in tokens):
        raise ValueError('Invalid byte pattern')
    values = [None if t.startswith('?') else int(t, 16) for t in tokens]
    runs = []
    start = 0
    while start < len(values):
        if values[start] is None:
            start += 1
            continue
        end = start
        while end < len(values) and values[end] is not None:
            end += 1
        runs.append((start, bytes(values[start:end])))
        start = end
    if not runs:
        raise ValueError('Pattern needs at least one literal byte')
    offset, anchor = max(runs, key=lambda r: len(r[1]))
    cursor = 0
    while True:
        found = data.find(anchor, cursor)
        if found < 0:
            break
        candidate = found - offset
        if candidate >= 0 and candidate + len(values) <= len(data):
            if all(v is None or data[candidate+i] == v for i, v in enumerate(values)):
                yield candidate
        cursor = found + 1


def inspect(path, patterns):
    raw = path.read_bytes()
    pe = pefile.PE(data=raw, fast_load=True)
    if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20b:
        raise ValueError('Expected an AMD64 PE32+ image')
    pe.parse_data_directories(directories=[0, 2, 3])
    sections = []
    for s in pe.sections:
        start, size = s.PointerToRawData, s.SizeOfRawData
        if start + size > len(raw):
            raise ValueError('Section extends beyond file')
        sections.append((s, raw[start:start+size]))
    functions = sorted((e.struct.BeginAddress, e.struct.EndAddress)
                       for e in getattr(pe, 'DIRECTORY_ENTRY_EXCEPTION', []))
    begins = [f[0] for f in functions]
    md = Cs(CS_ARCH_X86, CS_MODE_64)

    def location(section, offset):
        rva = section.VirtualAddress + offset
        idx = bisect.bisect_right(begins, rva) - 1
        fn = functions[idx] if idx >= 0 and rva < functions[idx][1] else None
        return {'section': section.Name.rstrip(b'\0').decode(errors='replace'),
                'file_offset': section.PointerToRawData + offset,
                'rva': rva, 'preferred_va': pe.OPTIONAL_HEADER.ImageBase + rva,
                'unwind_function_range': list(fn) if fn else None}

    results = []
    for item in patterns:
        matches = []
        for section, data in sections:
            if not section.Characteristics & 0x20000000:
                continue
            for offset in positions(data, item['pattern']):
                hit = location(section, offset)
                hit['instructions_at_pattern'] = [
                    {'preferred_va': i.address, 'bytes': i.bytes.hex(),
                     'mnemonic': i.mnemonic, 'operands': i.op_str}
                    for i in md.disasm(data[offset:offset+48], hit['preferred_va'], count=8)]
                matches.append(hit)
        results.append({**item, 'match_count': len(matches), 'matches': matches,
                        'interpretation': 'candidate_only' if len(matches) == 1 else
                        ('ambiguous' if matches else 'not_found'),
                        'runtime_validated': False})

    strings = {}
    for key in ('StartServer', 'RunScript', '-runScriptFile', '-quitAfterExecution',
                'DebugLocalRccServerConnection', 'ThumbnailGenerator',
                'StudioCaptureService', 'ProtectedStringBytecode'):
        strings[key] = {}
        for encoding in ('ascii', 'utf-16le'):
            needle = key.encode(encoding)
            offsets = []
            cursor = 0
            while (offset := raw.find(needle, cursor)) >= 0:
                offsets.append(offset)
                cursor = offset + 1
            strings[key][encoding+'_substring_offsets'] = offsets
    version_strings = {}
    for group in getattr(pe, 'FileInfo', []):
        for info in group:
            for table in getattr(info, 'StringTable', []):
                for k, v in table.entries.items():
                    if k in (b'FileVersion', b'ProductVersion', b'OriginalFilename'):
                        version_strings[k.decode()] = v.decode(errors='replace')
    return {'artifact': {'name': path.name, 'bytes': len(raw),
                        'sha256': hashlib.sha256(raw).hexdigest()},
            'pe': {'machine': 'amd64', 'timestamp': pe.FILE_HEADER.TimeDateStamp,
                   'size_of_image': pe.OPTIONAL_HEADER.SizeOfImage,
                   'image_base': pe.OPTIONAL_HEADER.ImageBase,
                   'version_strings': version_strings,
                   'exports': [(e.name or b'').decode(errors='replace') for e in
                               getattr(getattr(pe, 'DIRECTORY_ENTRY_EXPORT', None), 'symbols', [])]},
            'historical_patterns': results, 'string_observations': strings,
            'limitations': ['Historical byte matches do not establish function identity or ABI.',
                            'Unwind ranges may describe only a function fragment.',
                            'String absence is not proof that a feature is absent.',
                            'No executable bytes changed; no target code was executed.',
                            'No render or client-join test has run.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    patterns = json.loads(Path(__file__).with_name('historical-patterns.json').read_text())
    result = inspect(args.binary, patterns)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'artifact': result['artifact'], 'pe': result['pe'],
                      'matches': {p['id']:p['match_count'] for p in result['historical_patterns']}}, indent=2))
