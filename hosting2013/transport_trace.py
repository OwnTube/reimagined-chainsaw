"""Bounded metadata tracing of our synthetic, loopback-only RakNet experiment.

No packet replay, public connections, credentials, or application payload dumps.
Transport control bytes may be retained to determine this build's wire layout.
Allowlisted symbol observations of server ID 0x82 contain no replayable body.
"""
import hashlib
import json
from pathlib import Path
import select
import socket
import threading
import time

MAGIC = bytes.fromhex('00ffff00fefefefefdfdfdfd12345678')


def u24(data):
    if len(data)!=3:raise ValueError('Expected a 24-bit integer')
    return int.from_bytes(data,'little')


def frames(data):
    """Decode byte-aligned RakNet 4 frame headers; fail on unknown/truncated data."""
    if not data or data[0]&0x80==0 or data[0]&0x60:return []
    if len(data)<4:raise ValueError('Truncated datagram header')
    offset, result = 4, []
    while offset<len(data):
        if len(result)>=256:raise ValueError('Too many frames')
        start=offset
        if offset+3>len(data):raise ValueError('Truncated frame header')
        flags=data[offset];reliability=flags>>5;split=bool(flags&16)
        bits=int.from_bytes(data[offset+1:offset+3],'big');offset+=3
        if bits==0 or reliability>4:raise ValueError('Unsupported frame layout')
        record={'reliability':reliability,'bits':bits}
        if reliability in (2,3,4):
            record['reliable_index']=u24(data[offset:offset+3]);offset+=3
        if reliability in (1,4):
            record['sequence_index']=u24(data[offset:offset+3]);offset+=3
        if reliability in (1,3,4):
            record['order_index']=u24(data[offset:offset+3]);offset+=3
            if offset>=len(data):raise ValueError('Truncated order channel')
            record['channel']=data[offset];offset+=1
        if split:
            if offset+10>len(data):raise ValueError('Truncated split header')
            record.update(split_count=int.from_bytes(data[offset:offset+4],'big'),
                          split_id=int.from_bytes(data[offset+4:offset+6],'big'),
                          split_index=int.from_bytes(data[offset+6:offset+10],'big'))
            offset+=10
        length=(bits+7)//8
        if offset+length>len(data):raise ValueError('Truncated frame body')
        record['payload']=data[offset:offset+length]
        record['offset']=start
        offset+=length
        result.append(record)
    return result


class Trace:
    def __init__(self):
        self.started=time.monotonic();self.records=[];self.count=0;self.errors=[]
        self.splits={};self.messages=[];self.schema_observations=[];self.globals_observations=[]

    def message(self,direction,payload,**header):
        record={'direction':direction,'id':payload[0] if payload else None,
                'length':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),**header}
        # Connection request can contain an application password: never export it.
        # The accepted/new-incoming address tables and pings are transport data.
        if payload and payload[0] in (0,3,16,19):record['control_hex']=payload.hex()
        if len(self.schema_observations)<2:
            from schema_observer import observe
            observation=observe(direction,payload)
            if observation and not any(o.get('sha256')==observation.get('sha256') for o in self.schema_observations):
                self.schema_observations.append(observation)
        if len(self.globals_observations)<2 and not any(o['sha256']==record['sha256'] for o in self.globals_observations):
            from globals_observer import observe_globals
            observation=observe_globals(direction,payload,header.get('bits',len(payload)*8))
            if observation and not any(o['sha256']==observation['sha256'] for o in self.globals_observations):
                self.globals_observations.append(observation)
        if len(self.messages)<2048:self.messages.append(record)

    def packet(self,direction,data):
        self.count+=1
        if len(self.records)>=4096:return
        row={'t':round(time.monotonic()-self.started,6),'direction':direction,
             'id':data[0] if data else None,'length':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        if len(data)>=18 and data[0] in (5,6,7,8) and data[1:17]==MAGIC:
            row['offline_hex']=data[:64].hex()
            if data[0]==5:row['protocol']=data[17]
        self.records.append(row)
        try:
            for frame in frames(data):
                payload=frame.pop('payload')
                if 'split_count' not in frame:self.message(direction,payload,**frame);continue
                count,index=frame['split_count'],frame['split_index']
                if not 0<=index<count<=1024:raise ValueError('Invalid bounded split count/index')
                key=(direction,frame['split_id'])
                if key not in self.splits:
                    if len(self.splits)>=16:raise ValueError('Split assembly budget reached')
                    self.splits[key]={'count':count,'chunks':{}}
                assembly=self.splits[key]
                if assembly['count']!=count:raise ValueError('Split count changed')
                assembly['chunks'][index]=payload
                if sum(map(len,assembly['chunks'].values()))>2*1024*1024:raise ValueError('Split body budget reached')
                if len(assembly['chunks'])==count:
                    self.message(direction,b''.join(assembly['chunks'][i] for i in range(count)),split_count=count)
                    del self.splits[key]
        except ValueError as error:
            if len(self.errors)<32:self.errors.append({'packet':self.count,'error':str(error)})

    def report(self):
        return {'scope':'synthetic owned fixture on numeric loopback only','datagrams':self.count,
                'application_payloads_exported':False,'packets':self.records,'messages':self.messages,
                'schema_observations':self.schema_observations,'globals_observations':self.globals_observations,
                'decode_errors':self.errors,'incomplete_split_messages':len(self.splits)}


class LoopbackRelay:
    def __init__(self,target_port,output):
        self.front=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.front.bind(('127.0.0.1',0));self.port=self.front.getsockname()[1]
        self.back=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.back.bind(('127.0.0.1',0));self.back.connect(('127.0.0.1',target_port))
        self.output=Path(output);self.trace=Trace();self.stop=threading.Event();self.client=None
        self.thread=threading.Thread(target=self.run,daemon=True)

    def start(self):self.thread.start()

    def run(self):
        while not self.stop.is_set():
            for stream in select.select([self.front,self.back],[],[],0.1)[0]:
                try:data,address=stream.recvfrom(65535)
                except OSError:continue
                if stream is self.front:
                    if address[0]!='127.0.0.1' or self.client not in (None,address):continue
                    self.client=address;self.trace.packet('client_to_server',data);self.back.send(data)
                elif self.client:
                    self.trace.packet('server_to_client',data);self.front.sendto(data,self.client)

    def close(self):
        self.stop.set();self.thread.join(timeout=2)
        self.front.close();self.back.close()
        result=self.trace.report()
        self.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        return {'path':self.output.name,'datagrams':result['datagrams'],'messages':len(result['messages']),
                'decode_errors':len(result['decode_errors']),'application_payloads_exported':False}
