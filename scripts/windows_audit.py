#!/usr/bin/env python3
"""Read-only Windows route/DNS evidence. Does not claim browser or account success."""
import argparse
import ipaddress
import json
from pathlib import Path
import sys
from manage import ROOT, api, read, save, dump, preflight
from platform_support import powershell


def collect(o):
    preflight(o)
    cfg = api(o, '/configs');tun=cfg.get('tun',{})
    checks = {'ruleMode':cfg.get('mode')=='rule', 'tunEnabled':tun.get('enable') is True,
              'autoRoute':tun.get('auto-route') is True, 'strictRoute':tun.get('strict-route') is True}
    queries = {}
    for label, extra in [('systemUDP',''),('systemTCP','-TcpOnly'),('externalUDP','-Server 223.5.5.5'),('externalTCP','-Server 223.5.5.5 -TcpOnly')]:
        try:
            result=json.loads(powershell("@(Resolve-DnsName -Name claude.ai -Type A -DnsOnly " + extra + " | Where-Object {$_.IPAddress} | Select-Object -ExpandProperty IPAddress) | ConvertTo-Json -Compress") or '[]')
            ips=result if isinstance(result,list) else [result]
            passed=bool(ips) and all(ipaddress.ip_address(ip) in ipaddress.ip_network('198.18.0.0/15') for ip in ips)
            queries[label]={'answers':ips,'fakeIp':passed}
        except Exception: queries[label]={'fakeIp':False,'error':'DNS query failed; inspect locally'}
    checks['dnsSamplesCaptured']=all(v['fakeIp'] for v in queries.values())
    connections=api(o,'/connections').get('connections',[])
    summary=[{'process':Path(c.get('metadata',{}).get('processPath','')).name,
              'host':c.get('metadata',{}).get('host'), 'chain':c.get('chains'), 'rule':c.get('rule')}
             for c in connections if any(x in c.get('metadata',{}).get('host','') for x in ('claude','anthropic','openai','chatgpt'))]
    return {'checks':checks,'dns':queries,'connections':summary,
            'manualRequired':['effective browser policy','STUN IPv4/IPv6 and DNS page','Claude UI/agent/download routes','isolated fault tests'],
            'fullyVerified':False}


def main():
    if sys.platform!='win32': raise ValueError('Run audit in native Windows, not WSL')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--settings',type=Path,default=ROOT/'.private/settings.json')
    p.add_argument('--output',type=Path,default=ROOT/'.private/windows-audit.json')
    a=p.parse_args();r=collect(read(a.settings));save(a.output,dump(r))
    print(dump(r['checks']));print('Saved private evidence. Browser and client acceptance remains required.')
    if not all(r['checks'].values()): raise ValueError('Network checks incomplete; do not mark protection verified')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('Stopped: '+(str(e) if isinstance(e,ValueError) else type(e).__name__),file=sys.stderr);sys.exit(1)
