import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import browser_privacy as bp
import manage

class PrivacyTests(unittest.TestCase):
    def test_apply_preserves_prior_and_refuses_backup_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'backup.json'
            with patch.object(bp,'read_policy',side_effect=['default',bp.VALUE]),patch.object(bp,'write_policy') as w:
                bp.apply(p);w.assert_called_once_with(bp.VALUE)
            self.assertEqual(json.loads(p.read_text())['before'],'default')
            with patch.object(bp,'read_policy',return_value='default'),patch.object(bp,'write_policy') as w:
                with self.assertRaises(FileExistsError):bp.apply(p)
                w.assert_not_called()
    def test_rollback_refuses_later_changes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'b.json';p.write_text(json.dumps({'platform':sys.platform,'before':None,'after':bp.VALUE}))
            with patch.object(bp,'read_policy',return_value='default'),patch.object(bp,'write_policy') as w:
                with self.assertRaises(ValueError):bp.rollback(p)
                w.assert_not_called()
    def test_mac_installer_rejects_windows_before_operation(self):
        with patch.object(manage.sys,'platform','win32'):
            with self.assertRaisesRegex(ValueError,'macOS only'):manage.require_macos()
    def test_policy_unknown_platform(self):
        with patch.object(bp.sys,'platform','linux'):
            with self.assertRaises(ValueError):bp.platform_check()

if __name__=='__main__':unittest.main()
