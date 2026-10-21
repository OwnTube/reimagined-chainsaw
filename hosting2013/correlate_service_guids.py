"""Correlate reference GUID indices with independent API observations on both peers."""
import argparse
import json
from pathlib import Path
import re


def correlate(trace, result):
    by_role={}
    for role in ('host','client'):
        observations={}
        for line in result.get('peers',{}).get(role,{}).get('engine_marker_lines',[]):
            match=re.search(r'\|SERVICE_GUID_INDEX\|([A-Za-z][A-Za-z0-9_]*)\|(\d+)(?:\s|$)',line)
            if match:observations.setdefault(int(match[2]),set()).add(match[1])
        by_role[role]=observations
    candidates=[c for o in trace.get('globals_observations',[]) for c in o.get('candidates',[])
                if c.get('remaining_bits')==0 and c.get('cpp_encoder',{}).get('native_wire_validated')]
    if len(candidates)!=1:raise ValueError('Expected one completely decoded, C++-verified globals message')
    candidate=candidates[0];rows=[]
    for position,reference in enumerate(candidate['references']):
        index=reference.get('index');host=by_role['host'].get(index,set());client=by_role['client'].get(index,set())
        matched=len(host)==1 and host==client
        rows.append({'position':position,'observed_index':index,'host_classes':sorted(host),
                     'client_classes':sorted(client),'class_name_verified':matched,
                     'class_name':next(iter(host)) if matched else None})
    return {'scope':'owned reference connection only; no custom host world',
            'references':rows,'all_service_classes_identified':bool(rows) and all(r['class_name_verified'] for r in rows),
            'matched_count':sum(r['class_name_verified'] for r in rows),
            'reference_count':len(rows),'globals_encoder_wire_validated':True,
            'game_join_validated':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace',required=True,type=Path)
    parser.add_argument('--result',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    result=correlate(json.loads(args.trace.read_text()),json.loads(args.result.read_text()))
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
