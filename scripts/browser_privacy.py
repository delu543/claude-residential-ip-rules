#!/usr/bin/env python3
"""Set one official Chrome WebRTC policy; no extensions, certificates or routing changes.
macOS defaults / Windows current-user policy. Verify chrome://policy and a real STUN test.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

KEY = 'WebRtcIPHandling'
VALUE = 'disable_non_proxied_udp'
DOMAIN = 'com.google.Chrome'
REGPATH = r'Software\Policies\Google\Chrome'
BROWSER = 'chrome'

def platform_check():
    if sys.platform not in ('darwin', 'win32'):
        raise ValueError('Only macOS and Windows Chrome policy are supported')

def read_policy():
    platform_check()
    if sys.platform == 'darwin':
        q = subprocess.run(['defaults','read',DOMAIN,KEY], capture_output=True, text=True)
        return q.stdout.strip() if q.returncode == 0 else None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGPATH) as key:
            value, kind = winreg.QueryValueEx(key, KEY)
        if kind != winreg.REG_SZ: raise ValueError('Existing policy is not a string; review manually')
        return value
    except FileNotFoundError:
        return None

def write_policy(value):
    platform_check()
    if sys.platform == 'darwin':
        cmd = ['defaults','delete',DOMAIN,KEY] if value is None else ['defaults','write',DOMAIN,KEY,'-string',value]
        subprocess.run(cmd,check=True,capture_output=True)
    else:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGPATH) as key:
            if value is None: winreg.DeleteValue(key,KEY)
            else: winreg.SetValueEx(key,KEY,0,winreg.REG_SZ,value)

def apply(path):
    before=read_policy()
    if before == VALUE:
        print('Already configured locally; effective browser policy and STUN result still require verification.'); return
    # Exclusive creation: never overwrite the only recovery record.
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump({'platform':sys.platform,'browser':BROWSER,'key':KEY,'before':before,'after':VALUE},f)
    write_policy(VALUE)
    if read_policy()!=VALUE: raise ValueError('Policy readback failed; keep backup for recovery')
    print(f'Saved. In {BROWSER}://policy reload policies and verify {KEY} status OK.')
    print('Edge WebRTC policy requires a normal browser restart and may not apply to Microsoft-account profiles. ' if BROWSER=='edge' else '')
    print('Run actual STUN and DNS tests. Web calls may require TCP relays or fail. No browser restart was forced.')

def rollback(path):
    r=json.loads(path.read_text(encoding='utf-8'))
    if r['platform']!=sys.platform or r.get('browser','chrome')!=BROWSER or r.get('key','WebRtcIPHandling')!=KEY or r['after']!=VALUE or read_policy()!=VALUE:
        raise ValueError('Platform or later policy edit differs; refuse overwrite')
    write_policy(r['before'])
    print('Previous policy restored. Reload Chrome policies. Backup retained.')

def main():
    global KEY, VALUE, DOMAIN, REGPATH, BROWSER
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['check','apply','rollback'])
    p.add_argument('--backup',type=Path)
    p.add_argument('--browser',choices=['chrome','edge'],default='chrome')
    p.add_argument('--policy',choices=['webrtc','dns'],default='webrtc')
    p.add_argument('--settings',type=Path,default=Path(__file__).resolve().parents[1]/'.private/settings.json')
    a=p.parse_args();platform_check()
    BROWSER=a.browser;KEY='WebRtcIPHandling';VALUE='disable_non_proxied_udp';DOMAIN='com.google.Chrome';REGPATH=r'Software\Policies\Google\Chrome'
    if a.browser=='edge':
        DOMAIN='com.microsoft.Edge';REGPATH=r'Software\Policies\Microsoft\Edge';KEY='WebRtcLocalhostIpHandling'
    if a.policy=='dns':
        KEY='DnsOverHttpsMode';VALUE='off'
    if a.backup is None:
        name='browser-policy.json' if a.browser=='chrome' and a.policy=='webrtc' else f'{a.browser}-{a.policy}-policy.json'
        a.backup=Path(__file__).resolve().parents[1]/'.private'/name
    if a.command=='apply' and sys.platform=='win32':
        from windows_policy import machine_present
        if machine_present(REGPATH): raise ValueError('Machine browser policy present; review effective policy before writing HKCU')
    if a.command=='apply' and a.policy=='dns':
        from manage import read, api, preflight
        o=read(a.settings);preflight(o)
        tun=api(o,'/configs').get('tun',{})
        if not tun.get('enable') or not tun.get('auto-route') or (sys.platform=='win32' and not tun.get('strict-route')):
            raise ValueError('DNS policy requires verified active TUN, auto-route and Windows strict-route first')
        if sys.platform=='win32':
            from windows_audit import collect
            if not all(collect(o)['checks'].values()):
                raise ValueError('Windows DNS queries are not captured; leave browser DoH unchanged and repair TUN first')
        print('Browser DoH will defer to the system/TUN resolver. Test DNS after apply; do not claim protection if Clash is off.')
    if a.command=='check': print(json.dumps({KEY:read_policy(),'effectiveBrowserVerified':False}))
    elif a.command=='apply': apply(a.backup)
    else: rollback(a.backup)

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('Stopped: '+(str(e) if isinstance(e,ValueError) else type(e).__name__),file=sys.stderr);sys.exit(1)
