"""Validate a fresh pinned native observation against reviewed descriptor fields."""
import argparse
import json
from pathlib import Path


def verify(trace, fixture):
    if trace.get('decode_errors') or not trace.get('datagrams'):
        raise ValueError('Reference trace has no traffic or has frame decode errors')
    candidates=[]
    for observation in trace.get('schema_observations',[]):
        if observation.get('sha256')!=fixture['message_sha256']:
            continue
        if observation.get('length')!=fixture['message_bytes']:
            raise ValueError('Pinned descriptor message length changed')
        candidates.extend(observation.get('descriptor_candidates',[]))
    for candidate in candidates:
        if (not candidate.get('schema_complete') or not candidate.get('configuration_decoded')
                or candidate.get('remaining_bits') != fixture['remaining_bits']
                or candidate.get('consumed_bits') != fixture['consumed_bits']
                or candidate.get('consumed_bits',0)+candidate.get('remaining_bits',0) != fixture['message_bytes']*8):
            continue
        if candidate.get('compressed_integer_endian')!=fixture['compressed_integer_endian']:
            continue
        if len(candidate['tables'])!=len(fixture['tables']):
            continue
        for got,want in zip(candidate['tables'],fixture['tables']):
            # ID is the identity. Some event names occur twice (overloads).
            entries=sorted(got['entries'],key=lambda e:e['id'])
            if entries!=want['entries'] or got['count']!=want['count']:
                raise ValueError('Observed descriptor fields changed')
        return {'validated':True,'scope':'exact pinned reference message only',
                'schema_complete':True,'counts':[t['count'] for t in candidate['tables']],
                'game_join_validated':False,'custom_host_world_implemented':False}
    raise ValueError('No complete pinned descriptor observation matched the reviewed fixture')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace',type=Path)
    parser.add_argument('--fixture',type=Path,default=Path(__file__).resolve().parents[1]/'server2013/protocol/descriptor-0.130.0.40915.json')
    args=parser.parse_args()
    print(json.dumps(verify(json.loads(args.trace.read_text()),json.loads(args.fixture.read_text())),indent=2))
