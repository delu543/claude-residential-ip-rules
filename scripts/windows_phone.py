#!/usr/bin/env python3
"""Continue from a verified Windows plan into the supported iPhone USB workflow.

This coordinator reuses the existing installers. It never applies desktop
settings, enables TUN/hotspot, imports a phone profile, or approves permissions.
Every phone operation rechecks desktop configuration; stale receipts are not a gate.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import uuid

import mobile

ROOT = Path(__file__).resolve().parents[1]


def check_desktop(plan):
    if not (plan/'workflow.json').is_file():
        raise ValueError('Finish the Windows setup first; see docs/WINDOWS-IPHONE.md. Do not overwrite old plans')
    result = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT/'scripts/windows_setup.py'),
                             'check', '--plan', str(plan)],
                            capture_output=True, text=True, encoding='utf-8', timeout=180)
    if result.returncode:
        raise ValueError('Windows configuration check failed; inspect verification.json and run windows_setup.py check locally. Phone not touched')
    receipt = json.loads(mobile.read(plan/'verification.json'))
    if receipt.get('configurationChecked') is not True:
        raise ValueError('Windows configuration check did not produce a passing receipt')
    return {'configurationChecked':True, 'checkedAt':receipt['checkedAt'],
            'fullyVerified':False, 'manualRequired':receipt['manualRequired']}


def usb_command(a):
    args=[str(a.usb_python), '-X', 'utf8', str(ROOT/'scripts/mobile_usb.py'), a.action]
    if a.device: args+=['--device',a.device]
    if a.action=='pull':
        if not a.document or not a.destination:
            raise ValueError('pull requires an explicit document and a new .private destination')
        args+=['--document',a.document,'--destination',str(a.destination.resolve())]
    if a.action=='stage':
        args+=['--settings',str(a.settings.resolve()),'--output',str(a.output.resolve())]
    return args


def execute(a):
    if sys.platform!='win32':
        raise ValueError('This two-device coordinator runs on the target native Windows PC only')
    a.desktop_plan=a.desktop_plan.resolve()
    if '.private' not in a.desktop_plan.parts:
        raise ValueError('Use a private desktop plan')
    if not a.usb_python.is_file():
        raise ValueError('Pass the actual Python in the optional Windows USB venv; see docs/WINDOWS-IPHONE.md')
    # Validate command inputs before any pairing or transfer can start.
    command=usb_command(a)
    desktop=None if a.action=='doctor' else check_desktop(a.desktop_plan)
    result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=75)
    if result.returncode:
        # The child sanitizes errors; avoid printing interpreter args/paths/data.
        raise ValueError('USB step failed; run mobile_usb.py doctor and inspect existing transfer receipts. No activation command issued')
    usb=json.loads(result.stdout)
    report={'schema':1,'at':datetime.now(timezone.utc).isoformat(), 'action':a.action,
            'desktop':desktop,'usb':usb,'fullyVerified':False}
    # doctor may run before prepare; do not create its exclusive desktop plan.
    mobile.save_new(a.desktop_plan.parent/'phone-events'/a.desktop_plan.name/f'{uuid.uuid4().hex}.json',
                    json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['doctor','devices','pair','probe','pull','stage'])
    p.add_argument('--desktop-plan',type=Path,default=ROOT/'.private/windows-plan')
    p.add_argument('--usb-python',type=Path,default=ROOT/'.private/mobile-tools/Scripts/python.exe')
    p.add_argument('--device')
    p.add_argument('--document')
    p.add_argument('--destination',type=Path)
    p.add_argument('--settings',type=Path,default=ROOT/'.private/mobile-settings.json')
    p.add_argument('--output',type=Path,default=ROOT/'.private/mobile-plan')
    a=p.parse_args()
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    try:
        print(json.dumps(execute(a),ensure_ascii=False,indent=2))
    except Exception as exc:
        reason=str(exc) if type(exc) is ValueError else type(exc).__name__
        print('Stopped: '+reason,file=sys.stderr);return 1
    return 0


if __name__=='__main__':sys.exit(main())
