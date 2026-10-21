"""Compare our C++ encoder's output with a fresh reference prefix hash, not replay."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def encode_observation(executable, trace, require_wire_hash=True):
    candidates=[c for o in trace.get('schema_observations',[]) for c in o.get('descriptor_candidates',[])
                if c.get('schema_complete') and len(c.get('tables',[]))==4]
    if len(candidates)!=1:raise ValueError('Expected one complete schema candidate')
    candidate=candidates[0]
    lines=[]
    for table in candidate['tables']:
        lines.append(str(table['count']))
        for entry in table['entries']:
            if '\n' in entry['name'] or '\t' in entry['name']:raise ValueError('Unexpected delimiter')
            lines.append(str(entry['id'])+'\t'+entry['name'])
    with tempfile.TemporaryDirectory(prefix='rcc-owned-codec-') as temporary:
        root=Path(temporary);input_file=root/'descriptors.tsv';output=root/'encoded.bin'
        input_file.write_text('\n'.join(lines)+'\n',encoding='ascii',newline='\n')
        process=subprocess.run([str(Path(executable).resolve()),str(input_file),str(output)],
                               capture_output=True,text=True,timeout=10,check=True)
        metadata=json.loads(process.stdout)
        encoded=output.read_bytes()
    prefix_bits=candidate['tables'][-1]['end_bit']
    if metadata!={'bits':prefix_bits,'bytes':len(encoded)} or len(encoded)!=(prefix_bits+7)//8:
        raise ValueError('C++ encoded bit/byte counts differ from native framing')
    from descriptor_codec import read_tables
    decoded=read_tables(encoded,table_count=4)
    if decoded['tables']!=candidate['tables']:
        raise ValueError('C++ encoded dictionary fields differ from decoded native fields')
    digest=hashlib.sha256(encoded).hexdigest()
    wire_hash=candidate.get('dictionary_prefix_sha256')
    if require_wire_hash and (candidate.get('dictionary_prefix_bits')!=prefix_bits or wire_hash!=digest):
        raise ValueError('C++ output differs from actual native wire prefix hash')
    return {'field_roundtrip_validated':True,'native_wire_prefix_validated':wire_hash==digest,
            'bits':prefix_bits,'bytes':len(encoded),'sha256':digest,
            'source':'original portable C++ encoder from decoded fields; no packet replay',
            'custom_host_world_implemented':False,'game_join_validated':False}


def encode_globals(executable,payload,valid_bits,flags,scope,indices):
    if len(scope)>128 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in scope):
        raise ValueError('Unexpected scope shape for bounded C++ comparison')
    with tempfile.TemporaryDirectory(prefix='rcc-owned-globals-') as temporary:
        root=Path(temporary);input_file=root/'globals.tsv';output=root/'encoded.bin'
        lines=[''.join(map(str,flags)),scope,str(len(indices))]+list(map(str,indices))
        input_file.write_text('\n'.join(lines)+'\n',encoding='ascii',newline='\n')
        process=subprocess.run([str(Path(executable).resolve()),'--globals',str(input_file),str(output)],
                               capture_output=True,text=True,timeout=10,check=True)
        metadata=json.loads(process.stdout);encoded=output.read_bytes()
    expected=bytearray(payload)
    if valid_bits%8:expected[-1]&=(255<<(8-valid_bits%8))&255
    if metadata!={'bits':valid_bits,'bytes':len(encoded)} or encoded!=expected:
        raise ValueError('C++ globals bits differ from the actual native wire')
    return {'native_wire_validated':True,'bits':valid_bits,'bytes':len(encoded),
            'masked_sha256':hashlib.sha256(encoded).hexdigest(),'scope_value_exported':False,
            'game_join_validated':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--encoder',required=True,type=Path)
    parser.add_argument('--trace',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    result=encode_observation(args.encoder,json.loads(args.trace.read_text()))
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
