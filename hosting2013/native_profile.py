"""Read a few pinned data fields from an owned disposable test process.

No writes, injection, code export, or raw handshake value is performed.
"""
import ctypes
from ctypes import wintypes
import hashlib
import struct


def inspect(process, expected_executable, player=False):
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    class Module(ctypes.Structure):
        _fields_ = [('size',wintypes.DWORD),('module_id',wintypes.DWORD),('pid',wintypes.DWORD),
                    ('global_usage',wintypes.DWORD),('process_usage',wintypes.DWORD),
                    ('base',ctypes.c_void_p),('bytes',wintypes.DWORD),('module',wintypes.HMODULE),
                    ('name',wintypes.WCHAR*256),('path',wintypes.WCHAR*260)]
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD,wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Module32FirstW.argtypes = [wintypes.HANDLE,ctypes.POINTER(Module)]
    kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.ReadProcessMemory.argtypes = [wintypes.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(0x18,process.pid)
    if snapshot == ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    try:
        module = Module();module.size = ctypes.sizeof(Module)
        if not kernel.Module32FirstW(snapshot,ctypes.byref(module)):raise ctypes.WinError(ctypes.get_last_error())
        from pathlib import Path
        if Path(module.path).resolve()!=expected_executable.resolve():raise ValueError('Unexpected owned process module')
        base = module.base
    finally:kernel.CloseHandle(snapshot)
    handle = kernel.OpenProcess(0x410,False,process.pid)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    def read(address,size):
        buffer = ctypes.create_string_buffer(size);actual = ctypes.c_size_t()
        if not kernel.ReadProcessMemory(handle,address,buffer,size,ctypes.byref(actual)) or actual.value!=size:
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.raw
    try:
        value = read(base+(0xa2038c if player else 0xbf8510),28)
        length,capacity = struct.unpack_from('<II',value,20)
        if not 0<length<=128 or capacity<length:raise ValueError('Unexpected pinned native string shape')
        data = read(struct.unpack_from('<I',value,4)[0],length) if capacity>=16 else value[4:4+length]
        flag = read(base+(0xa2dd87 if player else 0xc1ee5f),1)[0]
        return {'handshake_value_sha256':hashlib.sha256(data).hexdigest(),'handshake_value_bytes':length,
                'local_rcc_flag_native_byte':flag,'memory_writes':False}
    finally:kernel.CloseHandle(handle)
