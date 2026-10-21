"""Embed measured public API IDs/names and explicit owned feature settings.

This generates original C++ data, never packets or proprietary engine code.
The JSON provenance and exact Player hash stay in the source tree.
"""
import argparse
import hashlib
import json
from pathlib import Path


def generate(source):
    tables=source['tables']
    if [t['count'] for t in tables]!=[288,814,244,159]:
        raise ValueError('Unexpected exact-build schema')
    lines=['// Generated from descriptor-0.130.0.40915.json API names/IDs.',
           '// Original data initializer; no Roblox engine code or captured packet.',
           '#pragma once','#include "../protocol/DescriptorWriter.hpp"',
           'namespace rcc2013 {','inline BitWriter ownedSchema() {',
           '    const std::vector<Dictionary> tables={']
    for table in tables:
        entries=table['entries']
        if sorted(e['id'] for e in entries)!=list(range(table['count'])):raise ValueError('ID identity mismatch')
        lines.append('        {')
        for e in entries:
            if not e['name'].isascii():raise ValueError('Non-ASCII API name')
            lines.append('            {'+str(e['id'])+','+json.dumps(e['name'])+'},')
        lines.append('        },')
    lines+=['    };','    return DescriptorWriter().schema(tables,{']
    # These are non-secret boolean feature settings. Verify our explicit false
    # against the observed length/hash; the reference did not export raw values.
    names=['InfiniteTerrain','DisableGuidStringCompression','AllowPhysicsPacketCompression']
    if [p['name'] for p in source['configuration']]!=names:raise ValueError('Configuration identity mismatch')
    for pair in source['configuration']:
        if pair['value_length']!=5 or pair['value_sha256']!=hashlib.sha256(b'false').hexdigest():
            raise ValueError('Explicit owned feature settings differ from observation')
        lines.append('        {'+json.dumps(pair['name'])+',"false"},')
    lines+=['    });','}','}']
    return '\n'.join(lines)+'\n'

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    source=json.loads(Path(__file__).with_name('descriptor-0.130.0.40915.json').read_text())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(generate(source),encoding='ascii')
