"""Bounded 2013 descriptor-table research codec; no engine code or packet replay.

Huffman interoperability follows the public BSD-licensed RakNet reference:
Source/{StringCompressor,DS_HuffmanEncodingTree,BitStream}.cpp. The English
frequency data and its notices are in raknet_reference/. 2013 table framing
is an exact-build hypothesis until checked against owned native traffic.
"""
from bisect import bisect_left
import hashlib
import json
from pathlib import Path
import re


class Bits:
    def __init__(self, data):
        self.data, self.offset = data, 0

    @property
    def remaining(self):
        return len(self.data)*8-self.offset

    def uint(self, count):
        if not 0 <= count <= 32 or count > self.remaining:
            raise ValueError('Truncated or oversized field')
        value=0
        for _ in range(count):
            value=(value<<1)|((self.data[self.offset//8]>>(7-self.offset%8))&1)
            self.offset+=1
        return value

    def compressed_u32(self, endian='big'):
        raw=bytearray(4)
        for index in (3,2,1):
            if self.uint(1):
                continue
            for i in range(index+1):raw[i]=self.uint(8)
            return int.from_bytes(raw,endian)
        raw[0]=self.uint(4 if self.uint(1) else 8)
        return int.from_bytes(raw,endian)


def huffman_tree():
    frequencies=json.loads(Path(__file__).with_name('raknet_reference').joinpath('english_frequencies.json').read_text())
    nodes=[]
    def insert(weight,node):
        index=bisect_left([item[0] for item in nodes],weight)
        nodes.insert(index,(weight,node))
    for symbol,weight in enumerate(frequencies):insert(max(1,weight),symbol)
    while len(nodes)>1:
        left,right=nodes.pop(0),nodes.pop(0)
        insert(left[0]+right[0],(left[1],right[1]))
    return nodes[0][1]


TREE=huffman_tree()


def compressed_string(stream, maximum=255, endian='big'):
    bit_count=stream.compressed_u32(endian)
    if bit_count > 8192 or bit_count > stream.remaining:
        raise ValueError('Compressed string bit bound')
    output=bytearray();node=TREE
    for _ in range(bit_count):
        node=node[stream.uint(1)]
        if isinstance(node,int):
            output.append(node);node=TREE
            if len(output)>maximum:raise ValueError('Decoded string bound')
    # RakNet pads with an incomplete codeword, so node need not equal TREE.
    return bytes(output)


def read_tables(payload, endian='big', table_count=3, include_configuration=False):
    if not payload or payload[0]!=0x82 or len(payload)>128*1024:
        raise ValueError('Expected bounded ID 0x82')
    stream=Bits(payload);stream.uint(8);tables=[]
    for table_index in range(table_count):
        count=stream.uint(32)
        if count>4096:raise ValueError(f'Table {table_index} count {count} exceeds bound at bit {stream.offset}')
        entries=[];seen=set()
        for _ in range(count):
            wire_id=stream.uint(32);length=stream.uint(32)
            if wire_id>65535 or wire_id in seen or not 1<=length<=255:
                raise ValueError(f'Table {table_index} entry {len(entries)} ID {wire_id} length {length} exceeds bound at bit {stream.offset}')
            name=compressed_string(stream,255,endian)
            if len(name)!=length or not re.fullmatch(rb'[A-Za-z_][A-Za-z0-9_ .:/()\-]{0,254}',name):
                raise ValueError(f'Table {table_index} entry {len(entries)} name framing mismatch: expected {length}, decoded {len(name)}, bit {stream.offset}')
            entries.append({'id':wire_id,'name':name.decode('ascii')});seen.add(wire_id)
        tables.append({'index':table_index,'count':count,'entries':entries,'end_bit':stream.offset})
    configuration = []
    if include_configuration:
        count=stream.uint(16)
        if count>512:raise ValueError('Configuration pair count bound')
        for _ in range(count):
            pair=[]
            for field in range(2):
                length=stream.uint(16)
                if length>2048:raise ValueError('Configuration string bound')
                stream.offset=(stream.offset+7)//8*8
                if stream.remaining<length*8:raise ValueError('Truncated configuration string')
                value=bytes(stream.uint(8) for _ in range(length))
                pair.append(value)
            name,value=pair
            if not re.fullmatch(rb'[A-Za-z_][A-Za-z0-9_]{0,254}',name):
                raise ValueError('Configuration name framing mismatch')
            configuration.append({'name':name.decode('ascii'),'value_length':len(value),
                                  'value_sha256':hashlib.sha256(value).hexdigest()})
    return {'tables':tables,'configuration':configuration,
            'configuration_decoded':include_configuration,
            'consumed_bits':stream.offset,'remaining_bits':stream.remaining,
            'compressed_integer_endian':endian,'table_framing_decoded':True,
            'schema_complete':include_configuration and stream.remaining<=7,
            'application_handshake_implemented':False}
