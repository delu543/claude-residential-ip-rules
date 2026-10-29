#!/usr/bin/env python3
"""Read-only prerequisite checks: do not enable TUN to install routing."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from manage import ROOT, read, api, dump, save
from platform_support import powershell


def ordinary_proxy(runtime):
    port=runtime.get('mixed-port') or runtime.get('port')
    if type(port)!=int or not 1<=port<=65535:
        raise ValueError('No ordinary HTTP/mixed listener found; keep working system proxy and inspect Verge first')
    return f'http://127.0.0.1:{port}'


def http_probe(url, proxy):
    # No credentials or query data; bounded small request, never a speed test.
    cmd=['curl','--silent','--output','NUL' if sys.platform=='win32' else '/dev/null',
         '--max-time','8','--connect-timeout','4','--write-out','%{http_code}', '--head']
    cmd+=['--noproxy','','--proxy',proxy] if proxy else ['--noproxy','*']
    r=subprocess.run(cmd+[url],capture_output=True,text=True,timeout=10)
    return r.returncode==0 and r.stdout.strip().isdigit() and 200<=int(r.stdout.strip())<400


def windows_diagnostics():
    # Descriptions and routes only; no subscription credentials or browser content.
    script="""@{adapters=@(Get-NetAdapter | Select-Object Name,InterfaceIndex,Status,InterfaceDescription);
      routes=@(Get-NetRoute -AddressFamily IPv4 | Where-Object {$_.DestinationPrefix -eq '0.0.0.0/0'} | Select-Object InterfaceIndex,NextHop,RouteMetric);
      dns=@(Get-DnsClientServerAddress | Select-Object InterfaceIndex,AddressFamily,ServerAddresses);
      services=@(Get-Service | Where-Object {$_.Name -match 'verge|clash'} | Select-Object Name,Status);
      proxy=(Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' | Select-Object ProxyEnable,ProxyServer)} | ConvertTo-Json -Depth 5 -Compress"""
    return json.loads(powershell(script))


def check(o, runtime, require_system=True):
    result={'ordinaryProxyReachable':http_probe(o.get('healthUrl','https://www.gstatic.com/generate_204'),ordinary_proxy(runtime)),
            'tunEnabled':bool(runtime.get('tun',{}).get('enable')), 'systemProxyConfirmed':False}
    if sys.platform=='win32':
        diag=windows_diagnostics();result['diagnostics']=diag
        p=diag.get('proxy') or {};port=ordinary_proxy(runtime).rsplit(':',1)[1]
        endpoints=[x.split('=',1)[-1].strip() for x in (p.get('ProxyServer') or '').split(';')]
        result['systemProxyConfirmed']=p.get('ProxyEnable')==1 and any(x in (f'127.0.0.1:{port}',f'localhost:{port}') for x in endpoints)
    result['ready']=result['ordinaryProxyReachable'] and (not require_system or result['systemProxyConfirmed'])
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--settings',type=Path,default=ROOT/'.private/settings.json')
    p.add_argument('--verge-dir',type=Path)
    p.add_argument('--output',type=Path,default=ROOT/'.private/bootstrap.json')
    a=p.parse_args()
    o=read(a.settings) if a.settings.exists() else {}
    if a.verge_dir is not None:runtime=read(a.verge_dir/'clash-verge.yaml')
    elif o:runtime=api(o,'/configs')
    else:raise ValueError('Pass actual --verge-dir before initialization')
    r=check(o,runtime,require_system=sys.platform=='win32');save(a.output,dump(r))
    print(dump({k:v for k,v in r.items() if k!='diagnostics'}))
    if not r['ready']:raise ValueError('Baseline not ready: keep/recover working system proxy first; do not enable TUN or disable browser DoH')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('Stopped: '+(str(e) if isinstance(e,ValueError) else type(e).__name__),file=sys.stderr);sys.exit(1)
