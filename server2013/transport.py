"""Original, limited RakNet-compatible transport for the owned 2013 experiment.

This is a loopback research host, not a game engine. Unknown Roblox application
messages are recorded as metadata and are never treated as successful admission.
Wire-layout reference: facebookarchive/RakNet Source/RakPeer.cpp and
Source/ReliabilityLayer.cpp; independently implemented here in Python.
"""
from collections import OrderedDict
import hashlib
import ipaddress
import secrets
import socket
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'hosting2013'))
from transport_trace import MAGIC, Trace, frames, u24


def triad(value):
    if not 0<=value<1<<24:raise ValueError('Sequence outside uint24 range')
    return value.to_bytes(3,'little')


def address(value):
    host,port=value
    return b'\x04'+bytes(x^255 for x in ipaddress.IPv4Address(host).packed)+struct.pack('>H',port)


def acknowledge(sequence):
    return b'\xc0\x00\x01\x01'+triad(sequence)


def acknowledgements(data):
    if len(data)<3 or data[0]&0xc0!=0xc0:raise ValueError('Invalid acknowledgement')
    count=int.from_bytes(data[1:3],'big')
    if count>128:raise ValueError('Acknowledgement range budget exceeded')
    offset=3;result=[]
    for _ in range(count):
        if offset>=len(data):raise ValueError('Truncated ACK range')
        single=data[offset];offset+=1
        if single not in (0,1):raise ValueError('Invalid ACK flag')
        low=u24(data[offset:offset+3]);offset+=3
        high=low if single else u24(data[offset:offset+3])
        if not single:offset+=3
        if high<low or high-low>4096:raise ValueError('ACK range too wide')
        result.append((low,high))
    if offset!=len(data):raise ValueError('Trailing ACK bytes')
    return result


def encapsulate(payload,sequence,reliable_index=None,order_index=None,channel=0):
    if not 0<len(payload)<=1200:raise ValueError('Payload outside unsplit frame budget')
    reliability=3 if order_index is not None else 2 if reliable_index is not None else 0
    header=bytes([reliability<<5])+struct.pack('>H',len(payload)*8)
    if reliable_index is not None:header+=triad(reliable_index)
    if order_index is not None:header+=triad(order_index)+bytes([channel])
    return b'\x84'+triad(sequence)+header+payload


class ResearchHost:
    def __init__(self,port,internal_addresses=10,time_bytes=8):
        if not 0<=port<=65535:raise ValueError('Invalid port')
        if internal_addresses not in (10,20) or time_bytes not in (4,8):raise ValueError('Unsupported transport layout')
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.socket.bind(('127.0.0.1',port));self.socket.settimeout(0.1)
        self.port=self.socket.getsockname()[1]
        self.guid=secrets.token_bytes(8);self.peer=None;self.phase='listening';self.mtu=1200
        self.internal_addresses=internal_addresses;self.time_bytes=time_bytes
        self.sequence=0;self.reliable=0;self.order=0;self.pending=OrderedDict()
        self.seen=OrderedDict();self.received=OrderedDict();self.trace=Trace();self.events=[]
        self.connected=False;self.application_messages=[]

    def event(self,name,**values):
        if len(self.events)<256:self.events.append({'event':name,**values})

    def send(self,data):
        self.trace.packet('server_to_client',data)
        self.socket.sendto(data,self.peer)

    def message(self,data,reliable=False,ordered=False):
        sequence=self.sequence;self.sequence=(sequence+1)&0xffffff
        packet=encapsulate(data,sequence,self.reliable if reliable or ordered else None,self.order if ordered else None)
        if reliable or ordered:
            self.reliable=(self.reliable+1)&0xffffff
            if len(self.pending)>=64:raise ValueError('Reliable send budget exceeded')
            self.pending[sequence]={'packet':packet,'sent':time.monotonic(),'retries':0}
        if ordered:self.order=(self.order+1)&0xffffff
        self.send(packet)

    def accepted(self,request_time):
        now=int(time.monotonic()*1000)&((1<<(8*self.time_bytes))-1)
        packet=(b'\x10'+address(self.peer)+b'\x00\x00'+
                address(('127.0.0.1',self.port))+
                address(('0.0.0.0',0))*(self.internal_addresses-1)+request_time+
                now.to_bytes(self.time_bytes,'big'))
        self.message(packet,ordered=True)
        self.phase='accept_sent';self.event('connection_accept_sent',bytes=len(packet),time_bytes=self.time_bytes)

    def application(self,payload):
        record={'id':payload[0],'length':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}
        if len(self.application_messages)<64:self.application_messages.append(record)
        self.event('unimplemented_application_message',**record)

    def dispatch(self,payload):
        if not payload:return
        kind=payload[0]
        if kind==9:
            if self.phase not in ('offline_ready','accept_sent'):raise ValueError('Connection request outside negotiated phase')
            if len(payload)<1+8+self.time_bytes+1:raise ValueError('Truncated connection request')
            # No application password is exported. This peer is the one owned
            # loopback Player on a disposable test runner; no public admission.
            security=payload[1+8+self.time_bytes]
            if security:raise ValueError('Secure RakNet connections are not implemented')
            self.event('connection_request_received',bytes=len(payload))
            if self.phase=='offline_ready':self.accepted(payload[9:9+self.time_bytes])
        elif kind==19:
            if self.phase not in ('accept_sent','connected'):raise ValueError('New incoming connection before acceptance')
            self.phase='connected';self.connected=True;self.event('new_incoming_connection',bytes=len(payload))
        elif kind==0:
            if len(payload)!=1+self.time_bytes:raise ValueError('Unexpected connected ping time width')
            now=int(time.monotonic()*1000)&((1<<(8*self.time_bytes))-1)
            self.message(b'\x03'+payload[1:]+now.to_bytes(self.time_bytes,'big'))
        elif kind in (3,4):pass
        elif kind==21:self.phase='disconnected';self.event('peer_disconnected')
        else:self.application(payload)

    def receive(self,data,peer):
        if peer[0]!='127.0.0.1' or self.peer not in (None,peer):return
        if not data or len(data)>1500:return
        self.trace.packet('client_to_server',data)
        kind=data[0]
        if kind==5 and len(data)>=18 and data[1:17]==MAGIC:
            if self.phase not in ('listening','offline_1') or data[17]!=5:return
            self.peer=peer;self.phase='offline_1';self.mtu=min(1492,max(576,len(data)+28))
            self.event('open_request_1',protocol=data[17],mtu=self.mtu)
            self.send(b'\x06'+MAGIC+self.guid+b'\x00'+struct.pack('>H',self.mtu));return
        if peer!=self.peer:return
        if kind==7 and data[1:17]==MAGIC:
            if self.phase not in ('offline_1','offline_ready') or len(data)!=34:raise ValueError('Unexpected open request 2 layout')
            mtu=int.from_bytes(data[24:26],'big')
            if not 576<=mtu<=1492:raise ValueError('MTU outside allowed range')
            self.mtu=mtu;self.phase='offline_ready';self.event('open_request_2',mtu=mtu)
            self.send(b'\x08'+MAGIC+self.guid+address(peer)+struct.pack('>H',mtu)+b'\x00');return
        if kind&0xc0==0xc0:
            for low,high in acknowledgements(data):
                for sequence in list(self.pending):
                    if low<=sequence<=high:del self.pending[sequence]
            return
        if kind&0xe0==0xa0:
            self.event('negative_ack_received');return
        parsed=frames(data)
        if not parsed:return
        sequence=u24(data[1:4]);self.send(acknowledge(sequence))
        if sequence in self.seen:return
        self.seen[sequence]=True
        if len(self.seen)>4096:self.seen.popitem(last=False)
        for frame in parsed:
            if 'split_count' in frame:raise ValueError('Split application reassembly is not implemented in the host')
            index=frame.get('reliable_index')
            if index is not None:
                if index in self.received:continue
                self.received[index]=True
                if len(self.received)>4096:self.received.popitem(last=False)
            self.dispatch(frame['payload'])

    def tick(self):
        now=time.monotonic()
        for record in self.pending.values():
            if now-record['sent']<0.5:continue
            if record['retries']>=8:raise ValueError('Reliable control message was not acknowledged')
            self.send(record['packet']);record['sent']=now;record['retries']+=1

    def report(self):
        return {'implementation':'original Python research host; no Roblox engine loaded',
                'bind_address':'127.0.0.1','port':self.port,'phase':self.phase,
                'transport_handshake_observed':self.connected,'game_join_validated':False,
                'world_replication_implemented':False,'lua_engine_implemented':False,
                'events':self.events,'application_messages':self.application_messages,
                'trace':self.trace.report()}
