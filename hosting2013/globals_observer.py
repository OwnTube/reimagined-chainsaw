"""Bounded field-only hypotheses for exact-build 2013 globals; no raw body export."""
import hashlib
import re
from descriptor_codec import Bits, compressed_string


def read_globals(payload, valid_bits, header_flags):
    if not payload or payload[0]!=0x81 or not 8<=valid_bits<=len(payload)*8 or len(payload)>4096:
        raise ValueError('Expected bounded ID 0x81 and valid bit length')
    stream=Bits(payload);stream.uint(8)
    flags=[stream.uint(1) for _ in range(header_flags)]
    scopes={};references=[]
    while stream.offset<valid_bits:
        if len(references)>=128:raise ValueError('Globals reference count bound')
        code=stream.uint(8);cache_id=code&127
        if code==0:
            references.append({'null':True});continue
        if code&128:
            length=stream.uint(32)
            if not 1<=length<=128:raise ValueError('Scope length bound')
            scope=compressed_string(stream,128)
            if len(scope)!=length or not re.fullmatch(rb'[A-Za-z0-9_.:{}\-]{1,128}',scope):
                raise ValueError('Scope framing mismatch')
            scopes[cache_id]={'length':length,'sha256':hashlib.sha256(scope).hexdigest()}
            source='literal'
        elif cache_id not in scopes:
            raise ValueError('Undefined scope cache slot')
        else:source='cached'
        # ReadBits into a uint32 copies four wire bytes into little-endian x86
        # storage, unlike the descriptor integer helper's endian conversion.
        index=int.from_bytes(bytes(stream.uint(8) for _ in range(4)),'little')
        references.append({'null':False,'scope_cache_id':cache_id,'scope_source':source,
                           'scope_sha256':scopes[cache_id]['sha256'],'index':index})
    if stream.offset!=valid_bits or not scopes or not references:
        raise ValueError('Globals did not consume the exact valid bit count')
    return {'header_flag_count':header_flags,'flags':flags,'index_bits':32,
            'consumed_bits':stream.offset,'remaining_bits':0,'references':references,
            'scopes':[{'cache_id':key,**value} for key,value in scopes.items()],
            'field_framing_decoded':True,'service_names_identified':False,
            'custom_host_globals_implemented':False}


def observe_globals(direction,payload,valid_bits):
    if direction!='server_to_client' or not payload or payload[0]!=0x81:return None
    result={'id':129,'length':len(payload),'bits':valid_bits,
            'sha256':hashlib.sha256(payload).hexdigest(),'body_exported':False,
            'scope_values_exported':False,'candidates':[],'errors':{}}
    for header_flags in (1,2):
        try:result['candidates'].append(read_globals(payload,valid_bits,header_flags))
        except ValueError as error:result['errors'][str(header_flags)]=str(error)
    return result
