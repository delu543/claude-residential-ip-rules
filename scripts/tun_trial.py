#!/usr/bin/env python3
"""Optional bounded Windows TUN experiment; an independent local process ALWAYS restores baseline.
No system proxy, browser policies, profile scripts or user data are changed.
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import time
from manage import ROOT, api, read, save, dump, digest, preflight
from platform_support import default_verge_dir
from bootstrap import check
from windows_audit import collect


def restore(plan):
    state=read(plan/'trial.json')
    if digest(plan/'baseline.json')!=state['baselineHash']:
        raise ValueError('Baseline backup changed; restoration refused')
    o=read(plan/'settings.json')
    last=None
    for _ in range(3):
        try:
            api(o,'/configs?force=false','PUT',{'path':str(plan/'baseline.json')})
            cfg=api(o,'/configs')
            if cfg.get('tun',{}).get('enable'):raise ValueError('TUN still enabled after restore')
            save(plan/'restored.json',dump({'restored':True,'time':time.time()}));return
        except Exception as e:
            last=e;time.sleep(1)
    save(plan/'restore-error.json',dump({'restored':False,'error':type(last).__name__}))
    raise ValueError('Local core did not accept baseline; use Verge system-proxy mode manually')


def watchdog(plan):
    state=read(plan/'trial.json')
    save(plan/'armed.json','{}')
    deadline=time.monotonic()+state['seconds']
    while time.monotonic()<deadline and not (plan/'restore-request.json').exists():
        time.sleep(0.2)
    restore(plan)


def trial(a):
    if sys.platform!='win32':raise ValueError('Live TUN trial is Windows-only; never run this on the healthy Mac')
    o=read(a.settings);runtime=read(a.verge_dir/'clash-verge.yaml')
    live=api(o,'/configs')
    if live.get('tun',{}).get('enable') or runtime.get('tun',{}).get('enable'):
        raise ValueError('Trial requires a known working TUN-off baseline; do not toggle a healthy running TUN')
    if runtime.get('mode') != live.get('mode') or any(runtime.get(k) != live.get(k) for k in ('mixed-port','port') if k in runtime and k in live):
        raise ValueError('Runtime file differs from live core; reconcile baseline before a TUN trial')
    baseline=check(o,live)
    if not baseline['ready']:raise ValueError('System proxy baseline is not ready; do not test TUN')
    preflight(o)
    a.plan.mkdir(parents=True,exist_ok=False)
    save(a.plan/'settings.json',dump(o));save(a.plan/'baseline.json',dump(runtime));save(a.plan/'baseline-check.json',dump(baseline))
    candidate=copy.deepcopy(runtime)
    candidate['tun']={**candidate.get('tun',{}),'enable':True,'auto-route':True,'strict-route':True,
                      'auto-detect-interface':True,'dns-hijack':['any:53','tcp://any:53']}
    candidate['dns']={**candidate.get('dns',{}),'enable':True,'enhanced-mode':'fake-ip','fake-ip-range':'198.18.0.1/16'}
    save(a.plan/'candidate.json',dump(candidate))
    q=subprocess.run([str(a.mihomo),'-t','-d',str(a.verge_dir),'-f',str(a.plan/'candidate.json')],capture_output=True,timeout=30)
    save(a.plan/'syntax.log',q.stdout+q.stderr)
    if q.returncode:raise ValueError('Candidate syntax rejected; production unchanged')
    save(a.plan/'trial.json',dump({'seconds':a.seconds,'baselineHash':digest(a.plan/'baseline.json')}))
    with (a.plan/'watchdog.log').open('wb') as log:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'_watch','--plan',str(a.plan)],
            stdout=log,stderr=log,stdin=subprocess.DEVNULL,close_fds=True,
            creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP)
    for _ in range(50):
        if (a.plan/'armed.json').exists():break
        if child.poll() is not None:raise ValueError('Recovery process failed to start; production unchanged')
        time.sleep(0.1)
    else:raise ValueError('Recovery process did not arm; production unchanged')
    if child.poll() is not None:raise ValueError('Recovery process exited before trial; production unchanged')
    error=None
    try:
        api(o,'/configs?force=false','PUT',{'path':str(a.plan/'candidate.json')})
        # Explicit proxy works is insufficient: verify plain requests captured by TUN too.
        from bootstrap import http_probe
        r=collect(o)
        r['checks']['ordinaryProxy']=check(o,api(o,'/configs'))['ready']
        r['checks']['tunPlainHttp']=http_probe(o.get('healthUrl','https://www.gstatic.com/generate_204'),None)
        save(a.plan/'result.json',dump(r))
        if not all(r['checks'].values()):raise ValueError('TUN trial failed; inspect private diagnostics')
    except Exception as e:error=e
    finally:
        save(a.plan/'restore-request.json','{}')
        try:child.wait(timeout=65)
        except subprocess.TimeoutExpired:
            # The watchdog may be stuck in a local API call; make no cloud-dependent decision.
            error=ValueError('Recovery not yet confirmed; check watchdog log and switch Verge to system proxy')
        if not (a.plan/'restored.json').exists():
            if child.poll() is not None:restore(a.plan)
            else:raise ValueError('Restoration not confirmed; use Verge system proxy manually')
    recovered=check(o,api(o,'/configs'))
    save(a.plan/'recovered-check.json',dump(recovered))
    if not recovered['ready']:raise ValueError('Baseline reload succeeded but connectivity needs local investigation')
    print('Baseline restored; TUN remains OFF. Trial results are private. No persistent TUN enablement performed.')
    if error:raise error


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['run','restore','_watch'])
    p.add_argument('--settings',type=Path,default=ROOT/'.private/settings.json')
    p.add_argument('--plan',type=Path,default=ROOT/'.private/tun-trial')
    p.add_argument('--verge-dir',type=Path,default=default_verge_dir())
    p.add_argument('--mihomo',type=Path)
    p.add_argument('--seconds',type=int,default=60)
    a=p.parse_args();a.plan=a.plan.resolve()
    if not 30<=a.seconds<=120:raise ValueError('Recovery deadline must be 30–120 seconds')
    if a.command=='_watch':watchdog(a.plan)
    elif a.command=='restore':restore(a.plan)
    else:
        if a.mihomo is None or not a.mihomo.is_file():raise ValueError('Pass actual installed --mihomo executable')
        trial(a)

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('Stopped: '+(str(e) if isinstance(e,ValueError) else type(e).__name__),file=sys.stderr);sys.exit(1)
