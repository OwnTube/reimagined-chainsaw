"""Launch our independent loopback host. Roblox world replication is unfinished."""
import argparse
import json
import os
from pathlib import Path
import time
from transport import ResearchHost


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--duration',type=int,default=60)
    parser.add_argument('--internal-addresses',type=int,choices=(10,20),default=10)
    parser.add_argument('--time-bytes',type=int,choices=(4,8),default=8)
    args=parser.parse_args()
    if not 1<=args.duration<=180:parser.error('Duration must be 1..180 seconds')
    args.output.mkdir(parents=True,exist_ok=True)
    host=ResearchHost(args.port,args.internal_addresses,args.time_bytes)
    def write():
        result=host.report();result['pid']=os.getpid()
        temporary=args.output/'server-result.tmp'
        temporary.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        temporary.replace(args.output/'server-result.json')
    write()
    print('CUSTOM_RCC_TRANSPORT_READY|'+str(host.port),flush=True)
    deadline=time.monotonic()+args.duration
    try:
        while time.monotonic()<deadline:
            try:data,peer=host.socket.recvfrom(65535)
            except TimeoutError:pass
            else:
                try:host.receive(data,peer)
                except ValueError as error:host.event('protocol_error',reason=str(error))
                write()
            host.tick()
    except Exception as error:
        host.event('host_error',reason=str(error));write();raise
    finally:write();host.socket.close()
    return 0


if __name__=='__main__':raise SystemExit(main())
