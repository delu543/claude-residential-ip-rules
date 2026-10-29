import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import browser_privacy as bp
import manage
import platform_support as ps

class PrivacyTests(unittest.TestCase):
    def test_apply_preserves_prior_and_refuses_backup_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'backup.json'
            with patch.object(bp,'read_policy',side_effect=['default',bp.VALUE]),patch.object(bp,'write_policy') as w:
                bp.apply(p);w.assert_called_once_with(bp.VALUE)
            self.assertEqual(json.loads(p.read_text(encoding='utf-8'))['before'],'default')
            with patch.object(bp,'read_policy',return_value='default'),patch.object(bp,'write_policy') as w:
                with self.assertRaises(FileExistsError):bp.apply(p)
                w.assert_not_called()
    def test_rollback_refuses_later_changes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'b.json';p.write_text(json.dumps({'platform':sys.platform,'before':None,'after':bp.VALUE}))
            with patch.object(bp,'read_policy',return_value='default'),patch.object(bp,'write_policy') as w:
                with self.assertRaises(ValueError):bp.rollback(p)
                w.assert_not_called()
    def test_installer_platform_dispatch(self):
        for platform in ('darwin','win32'):
            with patch.object(ps.sys,'platform',platform): ps.require_platform()
        with patch.object(ps.sys,'platform','linux'):
            with self.assertRaises(ValueError): ps.require_platform()
    def test_policy_unknown_platform(self):
        with patch.object(bp.sys,'platform','linux'):
            with self.assertRaises(ValueError):bp.platform_check()

if __name__=='__main__':unittest.main()

class BrowserSelectionTests(unittest.TestCase):
    def test_default_windows_chrome_and_edge_is_opt_in(self):
        with patch.object(bp.sys,'argv',['browser_privacy.py','apply']),patch.object(bp.sys,'platform','win32'),patch('windows_policy.machine_present',return_value=False),patch.object(bp,'apply') as apply:
            bp.main();self.assertEqual(bp.BROWSER,'chrome');self.assertEqual(bp.KEY,'WebRtcIPHandling')
            self.assertIn('browser-policy.json',str(apply.call_args.args[0]))
    def test_dns_cannot_disable_doh_without_active_tun(self):
        with patch.object(bp.sys,'argv',['browser_privacy.py','apply','--policy','dns']),patch.object(bp.sys,'platform','win32'),patch('windows_policy.machine_present',return_value=False),patch.object(manage,'read',return_value={}),patch.object(manage,'preflight'),patch.object(manage,'api',return_value={'tun':{'enable':False}}),patch.object(bp,'apply') as apply:
            with self.assertRaisesRegex(ValueError,'requires verified'):bp.main()
            apply.assert_not_called()
        bp.KEY='WebRtcIPHandling';bp.VALUE='disable_non_proxied_udp'
