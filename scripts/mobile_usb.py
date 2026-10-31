#!/usr/bin/env python3
"""Windows/macOS -> trusted USB iPhone documents. No private-container fallback.

Does not activate a VPN/profile, edit preferences, collect backups, or read other
apps. File transfer success is not network acceptance. Optional dependency is
installed by the operator in a separate venv; nothing is installed at runtime.
"""
import argparse
import asyncio
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
from pathlib import Path, PurePosixPath
import re
import ssl
import subprocess
import sys
import uuid

import mobile

BUNDLE = 'com.liguangming.Shadowrocket'  # Apple's public app-id 932747118 lookup
DEPENDENCY_VERSION = '11.48.0'
LIMIT = 8 * 1024 * 1024


def fingerprint(serial):
    return hashlib.sha256(serial.encode()).hexdigest()[:16]


def select_device(devices, wanted=None):
    usb = [d for d in devices if d.is_usb and (wanted is None or fingerprint(d.serial) == wanted)]
    if len(usb) != 1:
        raise ValueError('Need exactly one selected USB device; unlock/connect it or pass --device from devices')
    return usb[0]


def document_path(relative):
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise ValueError('Use a relative document path from probe, not a container/system path')
    if any(x in ('..', '.', '') for x in relative.split('/')) or any(ord(c) < 32 for c in relative):
        raise ValueError('Unsafe document path')
    p = PurePosixPath(relative)
    if p.is_absolute() or p.suffix.lower() not in ('.conf', '.json'):
        raise ValueError('Only explicit .conf/.json documents may be exported')
    return '/Documents/' + p.as_posix()


async def checked_read(service, relative):
    path = document_path(relative)
    if (await service.stat('/Documents'))['st_ifmt'] != 'S_IFDIR':
        raise ValueError('No regular Documents directory')
    cursor = '/Documents'
    for part in relative.split('/')[:-1]:
        cursor += '/' + part
        if (await service.stat(cursor))['st_ifmt'] != 'S_IFDIR':
            raise ValueError('Directory symlink/non-directory refused')
    info = await service.stat(path)
    if info['st_ifmt'] != 'S_IFREG' or not 0 <= int(info['st_size']) <= LIMIT:
        raise ValueError('Only bounded regular documents may be exported')
    data = await service.get_file_contents(path)
    if len(data) > LIMIT:
        raise ValueError('Document grew beyond export limit')
    return data


async def stage(service, settings, output, target):
    mobile.check(settings, output)
    receipt_path = Path(output) / 'usb-transfer.json'
    if receipt_path.exists():
        raise ValueError('Bundle already has a transfer receipt; inspect it before another transfer')
    o = json.loads(mobile.read(settings))
    if o.get('schema') == 2:
        if o['target']['adapter'] != 'shadowrocket':
            raise ValueError('This USB bridge only stages Shadowrocket; use the selected app official import path')
        o = {'shadowrocketVersion':o['target']['version'], 'iosVersion':o['target']['osVersion']}
    actual = target.get('shadowrocketVersion', '')
    expected = re.match(r'\d+\.\d+\.\d+', o['shadowrocketVersion'])
    if not expected or expected.group() != actual or o['iosVersion'] != target.get('iosVersion'):
        raise ValueError('Target versions differ from plan; regenerate using probe versions')
    build = re.search(r'\((\d+)\)', o['shadowrocketVersion'])
    if build and build.group(1) != str(target.get('shadowrocketBuild')):
        raise ValueError('Shadowrocket build differs from plan')
    if (await service.stat('/Documents'))['st_ifmt'] != 'S_IFDIR':
        raise ValueError('No regular Documents directory')
    name = 'ClaudeRouting-' + uuid.uuid4().hex + '.conf'
    if name in await service.listdir('/Documents'):
        raise ValueError('Unexpected filename collision; nothing written')
    data = (Path(output) / 'shadowrocket.conf').read_bytes()
    if len(data) > LIMIT:
        raise ValueError('Candidate exceeds transfer size limit')
    receipt = {'schema':1, 'status':'write-pending', 'device':target['device'],
               'bundle':BUNDLE, 'document':name, 'sha256':hashlib.sha256(data).hexdigest(),
               'activated':False, 'networkVerified':False}
    # Persist intent before any phone mutation, including partial/disconnected writes.
    mobile.save_new(receipt_path, json.dumps(receipt, indent=2)+'\n')
    await service.set_file_contents('/Documents/' + name, data)
    if await checked_read(service, name) != data:
        raise ValueError('USB readback mismatch; candidate must not be activated')
    result = dict(receipt, status='transferred-readback-matched')
    mobile.save_new(Path(output)/'usb-readback.json', json.dumps(result, indent=2)+'\n')
    return result


def load_backend():
    if sys.platform not in ('darwin', 'win32'):
        raise ValueError('Use native Windows or macOS for USB; WSL is not supported')
    if sys.version_info < (3, 11) or not ssl.OPENSSL_VERSION.startswith('OpenSSL '):
        raise ValueError('Use Python 3.11+ built with OpenSSL in the optional USB venv')
    try:
        installed = version('pymobiledevice3')
    except PackageNotFoundError:
        raise ValueError('Install requirements-mobile.txt into the optional Python 3.11+ USB venv') from None
    if installed != DEPENDENCY_VERSION:
        raise ValueError('USB dependency version changed; review adapter before use')
    from pymobiledevice3 import usbmux
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.installation_proxy import InstallationProxyService
    from pymobiledevice3.services.house_arrest import HouseArrestService
    return usbmux, create_using_usbmux, InstallationProxyService, HouseArrestService


def windows_host():
    # No registry writes, driver installs, service restarts, full device IDs or
    # network adapter changes. The mux protocol probe is the source of readiness.
    script = """[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new();
    $ErrorActionPreference='Stop';
    @{services=@(Get-Service | Where-Object {$_.Name -match 'Apple.*Mobile.*Device|AppleMobileDevice'} |
       ForEach-Object {@{name=$_.Name;status=$_.Status.ToString()}});
      appleDevicesInstalled=@(Get-AppxPackage -Name AppleInc.AppleDevices).Count -gt 0;
      appleUsb=@(Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
        Where-Object {$_.InstanceId -like 'USB\\VID_05AC*'} |
        ForEach-Object {@{status=$_.Status;class=$_.Class}})} | ConvertTo-Json -Depth 4 -Compress"""
    raw = subprocess.check_output(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], timeout=20)
    return json.loads(raw.decode('utf-8-sig'))


async def doctor():
    report = {'host':sys.platform, 'python':'.'.join(map(str, sys.version_info[:3])),
              'openssl':ssl.OPENSSL_VERSION, 'networkChanged':False,
              'phoneModified':False, 'trustGranted':'not-tested', 'readyForUSB':False}
    if sys.platform == 'win32':
        try:
            report['appleHost'] = windows_host()
        except Exception as exc:
            report['appleHost'] = {'status':'diagnostic-unavailable', 'errorType':type(exc).__name__}
    try:
        mux, *_ = load_backend()
    except ValueError as exc:
        return dict(report, status='host-prerequisite-missing', next=str(exc))
    except Exception as exc:
        return dict(report, status='backend-import-failed', errorType=type(exc).__name__,
                    next='Check the pinned USB venv; do not replace drivers or change networking')
    try:
        devices = await asyncio.wait_for(mux.list_devices(), timeout=10)
    except Exception as exc:
        return dict(report, status='usbmux-unreachable', errorType=type(exc).__name__,
                    next='Windows: check official Apple Devices/iTunes service and data cable; macOS: check USB. Do not enable hotspot, TUN or a developer tunnel')
    usb = [{'device':fingerprint(d.serial)} for d in devices if d.is_usb]
    return dict(report, readyForUSB=True, usbDevices=usb,
                status='usb-detected' if usb else 'no-usb-device',
                next='Select the intended USB device; unlock and trust only when pairing' if usb else
                'Connect and unlock the iPhone with a data cable. Existing desktop setup is preserved')


async def run(a):
    if a.action == 'doctor':
        return await doctor()
    usbmux, connect, Installation, House = load_backend()
    devices = await usbmux.list_devices()
    if a.action == 'devices':
        return {'usbDevices':[{'device':fingerprint(d.serial)} for d in devices if d.is_usb],
                'trustGranted': 'not-tested'}
    device = select_device(devices, a.device)
    lockdown = await connect(serial=device.serial, connection_type='USB',
                             autopair=a.action == 'pair', pair_timeout=20)
    try:
        if a.action == 'pair':
            return {'device':fingerprint(device.serial), 'paired':True,
                    'note':'Pairing is not app file sharing or VPN approval'}
        async with Installation(lockdown=lockdown) as installation:
            apps = await installation.get_apps(bundle_identifiers=[BUNDLE])
        app = apps.get(BUNDLE)
        if not app:
            raise ValueError('Shadowrocket not installed on the selected iPhone')
        if lockdown.all_values.get('DeviceClass') != 'iPhone':
            raise ValueError('Selected USB device is not an iPhone')
        target = {'device':fingerprint(device.serial), 'iosVersion':lockdown.all_values.get('ProductVersion'),
                  'shadowrocketVersion':app.get('CFBundleShortVersionString'),
                  'shadowrocketBuild':app.get('CFBundleVersion'),
                  'fileSharingDeclared':app.get('UIFileSharingEnabled') is True,
                  'vpnActivated':False, 'networkVerified':False}
        if not target['fileSharingDeclared']:
            if a.action == 'probe':
                return dict(target, status='file-sharing-unavailable',
                            next='Use the app export/import UI. Never request VendContainer or a full backup')
            raise ValueError('App does not expose document sharing; use explicit app export/import')
        # Never replace this with VendContainer on failure.
        async with await House.create(lockdown, BUNDLE, documents_only=True) as service:
            if a.action == 'probe':
                entries = await service.listdir('/Documents')
                return dict(target, status='document-sharing-readable',
                            documents=[p for p in entries if PurePosixPath(p).suffix.lower() in ('.conf','.json')])
            if a.action == 'pull':
                if not a.document or not a.destination:
                    raise ValueError('pull requires an explicit document and private local destination')
                data = await checked_read(service,a.document)
                mobile.save_new(a.destination,data.decode('utf-8-sig'))
                return {'status':'exported-local-private-copy','bytes':len(data),'networkVerified':False}
            return await stage(service,a.settings,a.output,target)
    finally:
        await lockdown.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['doctor','devices','pair','probe','pull','stage'])
    p.add_argument('--device',help='Opaque device fingerprint from devices; required if multiple phones attached')
    p.add_argument('--document')
    p.add_argument('--destination',type=Path)
    p.add_argument('--settings',type=Path,default=Path('.private/mobile-settings.json'))
    p.add_argument('--output',type=Path,default=Path('.private/mobile-plan'))
    a=p.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        result=asyncio.run(asyncio.wait_for(run(a),timeout=45))
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception as exc:
        # Device metadata/exceptions can contain serials, names, paths or secrets.
        reason=str(exc) if type(exc) is ValueError else type(exc).__name__
        print('USB step stopped: '+reason+'; no activation command issued; inspect transfer receipts for partial writes.',file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':sys.exit(main())
