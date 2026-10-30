import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, AsyncMock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import clients
import mobile_usb as usb
import windows_phone as flow
import windows_setup as setup
import browser_privacy as browser
import manage


class WindowsPhoneTests(unittest.TestCase):
    def test_doctor_missing_backend_and_unreachable_mux_are_distinct(self):
        with patch.object(usb.sys,'platform','win32'),patch.object(usb,'windows_host',return_value={}),patch.object(usb,'load_backend',side_effect=ValueError('missing pinned venv')):
            r=asyncio.run(usb.doctor())
        self.assertEqual(r['status'],'host-prerequisite-missing');self.assertFalse(r['phoneModified'])
        mux=SimpleNamespace(list_devices=AsyncMock(side_effect=OSError('private machine info')))
        with patch.object(usb.sys,'platform','win32'),patch.object(usb,'windows_host',return_value={}),patch.object(usb,'load_backend',return_value=(mux,)):
            r=asyncio.run(usb.doctor())
        self.assertEqual(r['status'],'usbmux-unreachable')
        self.assertNotIn('private machine info',json.dumps(r));self.assertFalse(r['readyForUSB'])

    def test_doctor_no_phone_is_not_pairing_or_installer(self):
        mux=SimpleNamespace(list_devices=AsyncMock(return_value=[]))
        with patch.object(usb.sys,'platform','win32'),patch.object(usb,'windows_host',return_value={}),patch.object(usb,'load_backend',return_value=(mux,)):
            r=asyncio.run(usb.doctor())
        self.assertEqual(r['status'],'no-usb-device');self.assertTrue(r['readyForUSB'])
        self.assertFalse(r['networkChanged']);self.assertEqual(r['trustGranted'],'not-tested')

    def test_doctor_fingerprints_usb_and_ignores_wifi(self):
        mux=SimpleNamespace(list_devices=AsyncMock(return_value=[SimpleNamespace(serial='secret-usb',is_usb=True),SimpleNamespace(serial='secret-wifi',is_usb=False)]))
        with patch.object(usb,'load_backend',return_value=(mux,)),patch.object(usb,'windows_host',return_value={}):
            r=asyncio.run(usb.doctor())
        self.assertEqual(r['usbDevices'],[{'device':usb.fingerprint('secret-usb')}])
        self.assertNotIn('secret-',json.dumps(r))

    def test_backend_platform_guard_supports_windows_before_dependencies(self):
        for platform in ('darwin','win32'):
            with patch.object(usb.sys,'platform',platform),patch.object(usb.sys,'version_info',(3,12,0)),patch.object(usb.ssl,'OPENSSL_VERSION','OpenSSL 3'),patch.object(usb,'version',return_value='wrong'):
                with self.assertRaisesRegex(ValueError,'dependency version'):usb.load_backend()
        with patch.object(usb.sys,'platform','linux'):
            with self.assertRaisesRegex(ValueError,'WSL'):usb.load_backend()

    def test_code_check_requires_every_proxy_variable_including_no_proxy(self):
        with tempfile.TemporaryDirectory() as t:
            home=Path(t);o={'port':19111};path=home/'.claude/settings.json'
            self.assertFalse(clients.check_code(o,home))
            env=clients.proxy_env(o);env['OTHER']='preserved'
            manage.save(path,manage.dump({'env':env}))
            self.assertTrue(clients.check_code(o,home))
            env['NO_PROXY']='*';manage.save(path,manage.dump({'env':env}))
            self.assertFalse(clients.check_code(o,home))

    def state(self,p):
        s=p/'settings.json';s.write_text('{}')
        return {'settings':str(s),'completed':['routing','desktop','code','chrome-webrtc'],'pending':None,
                'steps':[['routing','manage.py',[],[]],['desktop','windows_desktop.py',[],[]],
                         ['code','clients.py',[],[]],['chrome-webrtc','browser_privacy.py',
                          ['apply','--browser','chrome','--policy','webrtc'],[]]]}

    def test_verify_checks_all_components_and_does_not_claim_ui_or_phone(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);state=self.state(p)
            with patch.object(setup,'run') as run:r=setup.verify(state,p)
            commands=run.call_args_list
            self.assertEqual([x.args[0] for x in commands],['manage.py','bootstrap.py','windows_desktop.py','clients.py','browser_privacy.py'])
            self.assertIn('--require-configured',commands[-1].args[1])
            self.assertTrue(r['configurationChecked']);self.assertFalse(r['fullyVerified'])
            self.assertEqual(r['dnsInterception'],'not-requested')

    def test_failed_or_partial_desktop_check_invalidates_old_success(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);state=self.state(p);state['pending']='code'
            with patch.object(setup,'run') as run:
                with self.assertRaises(ValueError):setup.verify(state,p)
                run.assert_not_called()
            state['pending']=None
            with patch.object(setup,'run',side_effect=[None,None,subprocess.CalledProcessError(1,'test')]):
                with self.assertRaises(subprocess.CalledProcessError):setup.verify(state,p)
            r=manage.read(p/'verification.json');self.assertFalse(r['configurationChecked'])
            self.assertEqual(r['checks']['desktop'],'failed')

    def args(self,p,action='devices'):
        exe=p/'USB interpreter.exe';exe.write_text('fixture')
        return SimpleNamespace(action=action,desktop_plan=p,usb_python=exe,device=None,
                               document=None,destination=None,settings=p/'mobile.json',output=p/'mobile-plan')

    def test_coordinator_fresh_desktop_failure_prevents_any_phone_operation(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'.private';p.mkdir();a=self.args(p,'stage')
            with patch.object(flow.sys,'platform','win32'),patch.object(flow,'check_desktop',side_effect=ValueError('desktop failed')),patch.object(flow.subprocess,'run') as run:
                with self.assertRaises(ValueError):flow.execute(a)
                run.assert_not_called()

    def test_coordinator_safe_args_new_receipt_and_no_success_claim(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'.private';p.mkdir();a=self.args(p)
            with patch.object(flow.sys,'platform','win32'),patch.object(flow,'check_desktop',return_value={'configurationChecked':True}) as check,patch.object(flow.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='{"usbDevices":[]}')) as run:
                result=flow.execute(a)
            check.assert_called_once();self.assertFalse(result['fullyVerified'])
            self.assertEqual(run.call_args.args[0][0],str(a.usb_python));self.assertNotIn('shell',run.call_args.kwargs)
            self.assertEqual(run.call_args.kwargs['encoding'],'utf-8')
            self.assertEqual(len(list((p.parent/'phone-events'/p.name).glob('*.json'))),1)

    def test_doctor_before_desktop_prepare_does_not_create_plan(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'.private';p.mkdir();a=self.args(p,'doctor');a.desktop_plan=p/'new-plan'
            with patch.object(flow.sys,'platform','win32'),patch.object(flow,'check_desktop') as check,patch.object(flow.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='{"status":"no-usb-device"}')):
                flow.execute(a)
            check.assert_not_called();self.assertFalse(a.desktop_plan.exists())
            self.assertEqual(len(list((p/'phone-events'/'new-plan').glob('*.json'))),1)

    @unittest.skipUnless(sys.platform=='win32','PowerShell parser runs in native Windows CI')
    def test_real_powershell_parser_accepts_host_diagnostic(self):
        import base64
        with patch.object(usb.subprocess,'check_output',return_value=b'{}') as call:usb.windows_host()
        encoded=base64.b64encode(call.call_args.args[0][-1].encode('utf-8')).decode('ascii')
        script="$s=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded+"')); $t=$null;$e=$null;[void][System.Management.Automation.Language.Parser]::ParseInput($s,[ref]$t,[ref]$e); if($e.Count -gt 0){exit 1}"
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],check=True,timeout=15)

    def test_mac_coordinator_refuses_before_any_call(self):
        with patch.object(flow.sys,'platform','darwin'),patch.object(flow.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'target native Windows'):flow.execute(SimpleNamespace())
            run.assert_not_called()

    def test_chrome_check_detects_absent_and_machine_policy(self):
        for value,machine in [(None,False),('disable_non_proxied_udp',True)]:
            with patch.object(browser.sys,'platform','win32'),patch.object(browser.sys,'argv',['browser_privacy.py','check','--require-configured']),patch.object(browser,'read_policy',return_value=value),patch('windows_policy.machine_present',return_value=machine):
                with self.assertRaises(ValueError):browser.main()


if __name__=='__main__':unittest.main()
