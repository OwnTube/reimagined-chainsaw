"""Read a bounded API property list from the exact disposable 2013 Player.

No scanning, writes, hooks, credentials or raw memory export. Only the pinned
StringValue ClassDescriptor's property vector and named reflection fields are
read. This research diagnostic does not create a world or validate replication.
"""
import argparse
import ctypes
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import struct

PLAYER_SHA256='30502f062f428d3d808e7119ddb991865c91eb4beeed9f2c6b983198c007ea41'

def observe(pid,original):
    if hashlib.sha256(Path(original).read_bytes()).hexdigest()!=PLAYER_SHA256:
        raise ValueError('Exact Player profile required')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.ReadProcessMemory.argtypes=[w.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
    kernel.ReadProcessMemory.restype=w.BOOL
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    kernel.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];kernel.CreateToolhelp32Snapshot.restype=w.HANDLE
    class Module(ctypes.Structure):
        _fields_=[('size',w.DWORD),('id',w.DWORD),('pid',w.DWORD),('global_count',w.DWORD),('process_count',w.DWORD),
                  ('base',ctypes.c_void_p),('bytes',w.DWORD),('handle',w.HMODULE),('name',w.WCHAR*256),('path',w.WCHAR*260)]
    kernel.Module32FirstW.argtypes=[w.HANDLE,ctypes.POINTER(Module)];kernel.Module32FirstW.restype=w.BOOL
    snapshot=kernel.CreateToolhelp32Snapshot(0x18,pid)
    if snapshot==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    try:
        module=Module();module.size=ctypes.sizeof(Module)
        if not kernel.Module32FirstW(snapshot,ctypes.byref(module)):raise ctypes.WinError(ctypes.get_last_error())
        if module.name.lower()!='robloxplayerbeta.exe':raise ValueError('Unexpected main module')
        base=module.base
    finally:kernel.CloseHandle(snapshot)
    process=kernel.OpenProcess(0x1010,False,pid)
    if not process:raise ctypes.WinError(ctypes.get_last_error())
    total=0
    def read(address,count):
        nonlocal total
        if not 0x10000<=address<0x100000000 or not 0<count<=4096 or total+count>32768:
            raise ValueError('Reflection read bound')
        total+=count;buffer=ctypes.create_string_buffer(count);got=ctypes.c_size_t()
        if not kernel.ReadProcessMemory(process,ctypes.c_void_p(address),buffer,count,ctypes.byref(got)) or got.value!=count:
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.raw
    def uint(address):return struct.unpack('<I',read(address,4))[0]
    def name(interned):
        # Exact x86 MSVC Name wrapper + std::string object fields.
        data=read(interned+8,24);length,capacity=struct.unpack_from('<II',data,16)
        if not 1<=length<=128 or capacity<length:raise ValueError('Reflection name length')
        raw=read(struct.unpack_from('<I',data)[0],length) if capacity>=16 else data[:length]
        text=raw.decode('ascii')
        if not text.replace('_','').isalnum():raise ValueError('Reflection name alphabet')
        return text
    try:
        descriptor=base+0xa21618
        start,end=struct.unpack('<II',read(descriptor+0x14,8))
        if end<start or (end-start)%4 or not 1<=(end-start)//4<=64:raise ValueError('Property vector shape')
        properties=[]
        for pointer in struct.unpack('<'+'I'*((end-start)//4),read(start,end-start)):
            row=read(pointer,0x24)
            prop_name=name(struct.unpack_from('<I',row,0xc)[0])
            flags=struct.unpack_from('<I',row,0x1c)[0]
            type_holder=struct.unpack_from('<I',row,0x20)[0]
            type_descriptor=uint(type_holder+0x10)
            properties.append({'name':prop_name,'flags':flags,'replicated':bool(flags&4),
                               'boolean':type_descriptor==base+0xa16a24})
        return {'profile_sha256':PLAYER_SHA256,'class_name':'StringValue','properties':properties,
                'read_only':True,'bytes_read':total,'raw_memory_exported':False,
                'new_instance_replication_validated':False,'game_join_validated':False}
    finally:kernel.CloseHandle(process)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pid',required=True,type=int)
    p.add_argument('--original-player',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();result=observe(a.pid,a.original_player)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
