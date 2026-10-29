#!/usr/bin/env python3
"""Pin supported Windows Claude Desktop to a fixed HTTP proxy via official policy."""
import argparse
import json
from pathlib import Path
import re
import sys
from manage import ROOT, read, preflight
from platform_support import powershell, process_inventory
import windows_policy as policy

PATH = r'SOFTWARE\Policies\Claude'
MIN_VERSION = (1, 44121, 1)


def version_of(exe):
    if not exe.is_file() or exe.name.lower() != 'claude.exe':
        raise ValueError('Pass the actual installed Claude.exe path from inspect')
    # JSON data over stdin would be ideal; here a single-quoted literal doubles quotes.
    literal = str(exe).replace("'", "''")
    info = json.loads(powershell("$f=Get-Item -LiteralPath '" + literal + "'; @{version=$f.VersionInfo.ProductVersion; signature=(Get-AuthenticodeSignature -LiteralPath $f.FullName).Status.ToString()} | ConvertTo-Json -Compress"))
    nums = re.match(r'^(\d+)\.(\d+)\.(\d+)', info.get('version') or '')
    if not nums or tuple(map(int, nums.groups())) < MIN_VERSION or info['signature'] != 'Valid':
        raise ValueError('Unrecognized/old/unsigned Claude build; verify official build before policy apply')
    return info['version']


def ensure_closed():
    if any(x['Name'].lower() == 'claude.exe' for x in process_inventory()):
        raise ValueError('Claude is running; save work and exit normally before changing desktop policy')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['plan','apply','check','rollback'])
    p.add_argument('--settings', type=Path, default=ROOT/'.private/settings.json')
    p.add_argument('--exe', type=Path)
    p.add_argument('--backup', type=Path, default=ROOT/'.private/windows-desktop.json')
    a = p.parse_args(); policy.registry()
    if a.command == 'rollback':
        ensure_closed();policy.rollback(a.backup);return
    o = read(a.settings)
    values = {'egressProxyUrl':f"http://127.0.0.1:{o['port']}", 'egressProxyPacUrl':None}
    if a.command == 'check':
        ok = not policy.machine_present(PATH) and policy.snapshot(PATH, values) == values
        print(json.dumps({'configured':ok,'clientBehaviorVerified':False}))
        if not ok: raise ValueError('Desktop fixed proxy policy not configured or overridden')
        return
    if a.exe is None: raise ValueError('--exe is required; do not guess Windows installation path')
    version_of(a.exe)
    if policy.machine_present(PATH): raise ValueError('Machine Claude policy present; administrator must review effective policy')
    print('Plan: set current-user fixed HTTP proxy, remove overriding PAC key, preserve other policies. Version checked.')
    if a.command == 'apply':
        ensure_closed();preflight(o);policy.apply(PATH, values, a.backup)
        print('Policy saved. Next normal launch required; verify actual app and agent connections. This is not an OS firewall.')

if __name__ == '__main__':
    try: main()
    except Exception as e:
        print('Stopped: '+(str(e) if isinstance(e,ValueError) else type(e).__name__),file=sys.stderr);sys.exit(1)
