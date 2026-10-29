#!/usr/bin/env python3
"""Stage Windows routing, browser protection and clients with resumable receipts.
Initialization still requires locally reviewed subscription IDs and expected exit IP.
"""
import argparse
from pathlib import Path
import subprocess
import sys
from manage import ROOT, read, save, dump
from windows_desktop import ensure_closed
from platform_support import default_verge_dir


def run(script, args):
    subprocess.run([sys.executable,str(ROOT/'scripts'/script),*map(str,args)],check=True)


def steps(a):
    common=['--settings',a.settings]
    result=[('routing','manage.py',['apply','--plan',a.plan],['rollback','--plan',a.plan])]
    selected=a.clients if a.clients is not None else (['desktop','code'] if a.exe else ['code'])
    if 'desktop' in selected:
        result.append(('desktop','windows_desktop.py',['apply',*common,'--exe',a.exe,'--backup',a.plan/'desktop-policy.json'],['rollback','--backup',a.plan/'desktop-policy.json']))
    if 'code' in selected:
        result.append(('code','clients.py',['apply',*common,'--code-only','--backup',a.plan/'code'],['rollback',*common,'--backup',a.plan/'code']))
    for browser in a.browsers:
        for policy in ('webrtc',):
            base=['--browser',browser,'--policy',policy,'--settings',a.settings,'--backup',a.plan/f'{browser}-{policy}.json']
            result.append((f'{browser}-{policy}','browser_privacy.py',['apply',*base],['rollback',*base]))
    return result


def main():
    if sys.platform!='win32': raise ValueError('Windows setup must run on native Windows')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','apply','check','rollback'])
    p.add_argument('--settings',type=Path,default=ROOT/'.private/settings.json')
    p.add_argument('--plan',type=Path,default=ROOT/'.private/windows-plan')
    p.add_argument('--verge-dir',type=Path,default=default_verge_dir())
    p.add_argument('--full',action='store_true',help='Require TUN/DNS acceptance after separately validated TUN')
    p.add_argument('--mihomo',type=Path)
    p.add_argument('--exe',type=Path)
    p.add_argument('--clients',nargs='*',choices=['desktop','code'],help='Optional client scope; empty list configures routing/browser only')
    p.add_argument('--browsers',nargs='+',choices=['chrome','edge'],default=['chrome'])
    a=p.parse_args()
    a.settings=a.settings.resolve();a.plan=a.plan.resolve()
    receipt=a.plan/'workflow.json'
    if a.command=='prepare':
        if a.clients is not None and 'desktop' in a.clients and not a.exe:
            raise ValueError('Desktop scope requires the actual --exe')
        run('bootstrap.py',['--settings',a.settings,'--verge-dir',a.verge_dir])
        if a.exe and (a.clients is None or 'desktop' in a.clients):
            run('windows_desktop.py',['plan','--settings',a.settings,'--exe',a.exe])
        args=['prepare','--settings',a.settings,'--plan',a.plan]
        if a.verge_dir:args+=['--verge-dir',a.verge_dir]
        if a.mihomo:args+=['--mihomo',a.mihomo]
        run('manage.py',args)
        save(receipt,dump({'steps':steps(a),'completed':[],'pending':None,'settings':str(a.settings)}))
        print('Prepared; review candidate and run isolated tests before apply. No production changes.');return
    state=read(receipt)
    if a.command=='check':
        run('manage.py',['check','--settings',state['settings']])
        run('bootstrap.py',['--settings',state['settings'],'--output',a.plan/'baseline-check.json'])
        if a.full:run('windows_audit.py',['--settings',state['settings'],'--output',a.plan/'audit.json'])
        else:print('System-proxy stage checked. TUN/DNS interception is not certified; use --full only after separate TUN validation.')
        return
    ensure_closed()
    if a.command=='rollback':
        if state.get('pending'): raise ValueError('An interrupted step requires receipt review before rollback; see WINDOWS.md')
        for name,script,_,undo in reversed(state['steps']):
            if name in state['completed']:
                # Already-correct browser settings produce no receipt and need no undo.
                if script=='browser_privacy.py' and not Path(undo[undo.index('--backup')+1]).exists():
                    state['completed'].remove(name);save(receipt,dump(state));continue
                run(script,undo);state['completed'].remove(name);save(receipt,dump(state))
        return
    if state.get('pending'): raise ValueError('Previous step interrupted: inspect its backup before continuing, do not blindly replay')
    for name,script,do,_ in state['steps']:
        if name in state['completed']:continue
        state['pending']=name;save(receipt,dump(state))
        run(script,do)
        state['completed'].append(name);state['pending']=None;save(receipt,dump(state))
    run('bootstrap.py',['--settings',state['settings'],'--output',a.plan/'baseline-check.json'])
    print('Configuration written. Run check, reload browser policies and verify real clients. No claim of complete isolation.')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('Stopped: '+(str(e) if isinstance(e,ValueError) else type(e).__name__)+'; inspect workflow.json; completed stages remain recorded.',file=sys.stderr);sys.exit(1)
