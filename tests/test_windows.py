import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import manage
import clients
import platform_support as ps
import windows_policy as wp
import windows_audit as wa
import windows_desktop as wd


class WindowsTests(unittest.TestCase):
    def test_windows_paths_and_controller(self):
        with patch.object(ps.sys,'platform','win32'), patch.dict(os.environ,{'APPDATA':'C:/Users/Test/AppData/Roaming'}):
            self.assertIn('Roaming',str(ps.default_verge_dir()))
            self.assertEqual(ps.controller_options({'external-controller-pipe':r'\\.\pipe\verge-test'})['apiPipe'],r'\\.\pipe\verge-test')
            with self.assertRaises(ValueError):ps.controller_options({'external-controller':'0.0.0.0:9090'})
        with self.assertRaises(ValueError):ps.ipc_api(r'\\remote\pipe\service','/configs')

    def test_drive_paths_validated_no_blanket_node(self):
        o=manage.read(manage.ROOT/'examples/settings.example.json')
        o.pop('_template',None);o.update(port=19080,expectedIp='192.0.2.20',country='US',residential={'type':'vless'})
        o.update(claudePaths=[r'C:\Users\Tester\Claude\claude.exe'],codexPaths=[r'C:\Apps\Codex\codex.exe'])
        o['ordinaryProvider']['url']='https://ordinary.example/sub'
        manage.validate_options(o)
        o['claudePaths']=['Claude.exe']
        with self.assertRaises(ValueError):manage.validate_options(o)

    def test_code_independent_and_preserves_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);manage.save(home/'.claude/settings.json','{"permissions":{"deny":["x"]},"env":{"OTHER":"keep","NO_PROXY":"*"}}')
            rows=clients.targets({'port':17897},home,True)
            self.assertEqual(len(rows),1);c=rows[0][1]
            self.assertEqual(c['permissions']['deny'],['x'])
            self.assertEqual(c['env']['NO_PROXY'],'');self.assertEqual(c['env']['OTHER'],'keep')

    def test_policy_partial_write_rolls_back(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(wp,'machine_present',return_value=False),patch.object(wp,'snapshot',return_value={'proxy':None}),patch.object(wp,'write',side_effect=[OSError('fail'),None]) as write:
                with self.assertRaises(OSError):wp.apply('TEST',{'proxy':'fixed'},Path(d)/'b.json')
                self.assertEqual(write.call_args_list[-1].args,('TEST',{'proxy':None}))

    def test_policy_refuses_machine_and_later_changes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'b.json'
            with patch.object(wp,'machine_present',return_value=True),patch.object(wp,'write') as w:
                with self.assertRaises(ValueError):wp.apply('TEST',{'proxy':'fixed'},p)
                self.assertFalse(p.exists());w.assert_not_called()
            p.write_text(json.dumps({'path':'TEST','before':{'proxy':None},'after':{'proxy':'fixed'}}))
            with patch.object(wp,'machine_present',return_value=False),patch.object(wp,'snapshot',return_value={'proxy':'new'}),patch.object(wp,'write') as w:
                with self.assertRaises(ValueError):wp.rollback(p)
                w.assert_not_called()

    def test_running_client_stops_changes(self):
        with patch.object(wd,'process_inventory',return_value=[{'Name':'Claude.exe'}]):
            with self.assertRaises(ValueError):wd.ensure_closed()

    def test_dns_audit_does_not_call_real_ip_success(self):
        cfg={'mode':'rule','tun':{'enable':True,'auto-route':True,'strict-route':True}}
        with patch.object(wa,'preflight'),patch.object(wa,'api',side_effect=[cfg,{'connections':[]}]),patch.object(wa,'powershell',side_effect=['["198.18.0.4"]','["198.18.0.4"]','["203.0.113.1"]','["198.18.0.4"]']):
            result=wa.collect({});self.assertFalse(result['checks']['dnsSamplesCaptured']);self.assertFalse(result['fullyVerified'])

    @unittest.skipUnless(sys.platform=='win32','Native Windows CI only')
    def test_real_registry_isolated_test_key_and_rollback(self):
        import uuid, winreg
        key='Software\\ClaudeResidentialRulesTests\\'+uuid.uuid4().hex
        try:
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'receipt.json'
                wp.write(key,{'keep':'original'})
                wp.apply(key,{'fixed':'value','pac':None},p)
                self.assertEqual(wp.snapshot(key,['fixed','keep']),{'fixed':'value','keep':'original'})
                wp.rollback(p)
                self.assertEqual(wp.snapshot(key,['fixed','keep']),{'fixed':None,'keep':'original'})
        finally:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key)

if __name__=='__main__':unittest.main()
