"""Verify original C++ schema fields with the independent Python decoder."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from descriptor_codec import read_tables,Bits,compressed_string

OWNED_SCHEMA_SHA256='7f12d60aa1491cefdd0dba70884f71daa9de4a8553072b519fdaa7166c72676b'

def verify_encoding(executable):
    expected=json.loads(Path(__file__).resolve().parents[1].joinpath('server2013/protocol/descriptor-0.130.0.40915.json').read_text())
    with tempfile.TemporaryDirectory(prefix='rcc-owned-schema-') as temporary:
        output=Path(temporary)/'schema.bin'
        result=subprocess.run([str(Path(executable).resolve()),str(output)],check=True,capture_output=True,text=True,timeout=10)
        data=output.read_bytes();metadata=json.loads(result.stdout)
    # Independent read of the new exact-build property hypothesis, including
    # non-byte-aligned GUID/property ID/cache string and compact terminator.
    with tempfile.TemporaryDirectory(prefix='rcc-owned-property-') as temporary:
        output=Path(temporary)/'property.bin'
        result=subprocess.run([str(Path(executable).resolve()),'--property',str(output)],check=True,capture_output=True,text=True,timeout=10)
        wire=output.read_bytes();bits=Bits(wire);info=json.loads(result.stdout)
    if bits.uint(8)!=0x83 or bits.uint(2)!=3 or bits.uint(8)!=1:raise ValueError('Property item/reference framing')
    index=int.from_bytes(bytes(bits.uint(8) for _ in range(4)),'little')
    property_id=bits.uint(8)|(bits.uint(2)<<8)
    if index!=0x23456789 or property_id!=404 or bits.uint(1)!=0 or bits.uint(8)!=0x81:raise ValueError('Property ID/control/cache framing')
    length=bits.uint(32);value=compressed_string(bits,128)
    if length!=len(value) or value!=b'RCC2013_0123456789abcdef0123456789abcdef' or bits.uint(6)!=0:raise ValueError('Property string/terminator framing')
    if bits.offset!=info['bits'] or bits.remaining>7:raise ValueError('Property consumption mismatch')
    with tempfile.TemporaryDirectory(prefix='rcc-owned-instance-') as temporary:
        output=Path(temporary)/'instance.bin'
        result=subprocess.run([str(Path(executable).resolve()),'--instance',str(output)],check=True,capture_output=True,text=True,timeout=10)
        bits=Bits(output.read_bytes());info=json.loads(result.stdout)
    def guid():
        if bits.uint(8)!=1:raise ValueError('Owned instance GUID scope')
        return int.from_bytes(bytes(bits.uint(8) for _ in range(4)),'little')
    if bits.uint(8)!=0x83 or bits.uint(2)!=2 or guid()!=0x23456789:raise ValueError('New-instance header')
    class_id=bits.uint(8)|(bits.uint(1)<<8)
    if class_id!=250 or bits.uint(1)!=0:raise ValueError('New-instance class/control')
    for cache,expected_value in [(0x82,b'RccServerToken'),(0x81,b'RCC2013_0123456789abcdef0123456789abcdef')]:
        if bits.uint(1)!=0 or bits.uint(8)!=cache:raise ValueError('New-instance string framing')
        length=bits.uint(32);value=compressed_string(bits,128)
        if length!=len(value) or value!=expected_value:raise ValueError('New-instance string value')
    if bits.uint(1)!=1 or bits.uint(1)!=0 or guid()!=0x3456789a or bits.uint(6)!=0:raise ValueError('New-instance booleans/parent/end')
    if bits.offset!=info['bits'] or bits.remaining>7:raise ValueError('New-instance consumption')
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

def verify_property(server,client_lines):
    import re
    probe=server.get('property_probe',{})
    nonce=probe.get('nonce','')
    observed=set()
    for line in client_lines:
        match=re.search(r'\|SERVICE_NAME\|TestService\|(RCC2013_[0-9a-f]{32})(?:\s|$)',line)
        if match:observed.add(match.group(1))
    valid=(probe.get('sent') is True and probe.get('class_name')=='TestService'
           and probe.get('property_name')=='Instance:Name' and re.fullmatch(r'RCC2013_[0-9a-f]{32}',nonce) is not None
           and nonce in observed)
    return {'property_replication_validated':valid,'schema_property_route_validated':valid,
            'subject':'TestService.Name','server_only_nonce_observed':valid,
            'world_replication_validated':False,'game_join_validated':False,
            'limitation':'One existing service string property; no new instances, character or playable world'}

def verify_instance(server,client_lines):
    import re
    probe=server.get('owned_instance_probe',{})
    nonce=probe.get('nonce','');index=probe.get('index',0);parent=probe.get('parent_index',0)
    observed=set()
    for line in client_lines:
        match=re.search(r'\|OWNED_STRINGVALUE\|Workspace\|StringValue\|RccServerToken\|(RCC2013_[0-9a-f]{32})\|([0-9]+)(?:\s|$)',line)
        if match:observed.add((match.group(1),int(match.group(2))))
    parents=[b['index'] for b in server.get('globals_bindings',[]) if b['class_name']=='Workspace']
    valid=(probe.get('sent') is True and probe.get('class_name')=='StringValue' and probe.get('name')=='RccServerToken'
           and re.fullmatch(r'RCC2013_[0-9a-f]{32}',nonce) is not None
           and 0x20000000<=index<=0x3fffffff and parents==[parent] and index!=parent
           and nonce!=server.get('property_probe',{}).get('nonce') and (nonce,index) in observed)
    return {'new_instance_replication_validated':valid,'server_only_nonce_observed':valid,
            'native_class_name_parent_guid_validated':valid,'subject':'Workspace.RccServerToken (StringValue)',
            'playable_world_validated':False,'game_join_validated':False,
            'limitation':'One owned StringValue instance; geometry, character, simulation and bidirectional updates unimplemented'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--encoder',required=True,type=Path)
    args=parser.parse_args();print(json.dumps(verify_encoding(args.encoder),indent=2))
