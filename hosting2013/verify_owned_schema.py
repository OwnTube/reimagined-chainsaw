"""Verify original C++ schema fields with the independent Python decoder."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from descriptor_codec import read_tables

OWNED_SCHEMA_SHA256='7f12d60aa1491cefdd0dba70884f71daa9de4a8553072b519fdaa7166c72676b'

def verify_encoding(executable):
    expected=json.loads(Path(__file__).resolve().parents[1].joinpath('server2013/protocol/descriptor-0.130.0.40915.json').read_text())
    with tempfile.TemporaryDirectory(prefix='rcc-owned-schema-') as temporary:
        output=Path(temporary)/'schema.bin'
        result=subprocess.run([str(Path(executable).resolve()),str(output)],check=True,capture_output=True,text=True,timeout=10)
        data=output.read_bytes();metadata=json.loads(result.stdout)
    actual=read_tables(data,table_count=4,include_configuration=True)
    if not actual['schema_complete'] or actual['remaining_bits'] or metadata!={'bits':320080,'bytes':40010}:
        raise ValueError('Incomplete original schema encoding')
    for a,e in zip(actual['tables'],expected['tables']):
        if a['count']!=e['count'] or a['entries']!=e['entries']:raise ValueError('Schema ID/name identity differs')
    if actual['configuration']!=expected['configuration']:raise ValueError('Feature settings differ')
    digest=hashlib.sha256(data).hexdigest()
    if digest!=OWNED_SCHEMA_SHA256:raise ValueError('Original canonical schema hash differs')
    return {'field_roundtrip_validated':True,'bytes':len(data),'bits':actual['consumed_bits'],
            'sha256':digest,'reference_packet_replayed':False,'game_join_validated':False}

def verify_delivery(server):
    delivery=server.get('schema_delivery',{})
    valid=(delivery.get('queued') is True and delivery.get('all_fragments_acked') is True
           and delivery.get('bits')==320080 and delivery.get('bytes')==40010
           and delivery.get('sha256')==OWNED_SCHEMA_SHA256)
    return {'transport_delivery_validated':valid,'application_acceptance_validated':False,
            'world_replication_validated':False,'game_join_validated':False,
            'limitation':'ACKs verify datagram delivery only; engine schema application needs a separate proof'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--encoder',required=True,type=Path)
    args=parser.parse_args();print(json.dumps(verify_encoding(args.encoder),indent=2))
