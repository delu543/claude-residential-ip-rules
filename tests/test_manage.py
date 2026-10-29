import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import manage
import clients

class SafetyTests(unittest.TestCase):
    def test_private_write_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'settings.json';manage.save(p,'{}')
            if sys.platform != 'win32': self.assertEqual(p.stat().st_mode & 0o777,0o600)
            manage.save(p,'{"updated":true}')
            self.assertTrue(manage.read(p)['updated'])

    def test_reject_unreviewed_settings(self):
        o=manage.read(manage.ROOT/'examples/settings.example.json')
        with self.assertRaises(ValueError): manage.validate_options(o)
        o.pop('_template',None);o.update(port=19080,expectedIp='192.0.2.20',country='US',residential={'type':'vless'})
        o['ordinaryProvider']['url']='https://provider.example/sub'
        o['claudePaths']=['/Applications/Claude.app/'];manage.validate_options(o)
        o['proxyServerNameservers']=['https://resolver.example/dns-query#住宅']
        with self.assertRaises(ValueError): manage.validate_options(o)

    def test_client_merge_and_no_proxy(self):
        o={'port':17897}
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);lib=home/'Library/Application Support/Claude-3p/configLibrary'
            manage.save(lib/'_meta.json','{"appliedId":"test-profile"}')
            manage.save(lib/'test-profile.json','{"existing":"keep","egressProxyPacUrl":"old"}')
            manage.save(home/'.claude/settings.json','{"permissions":{"allow":[]},"env":{"OTHER":"keep","NO_PROXY":"*"}}')
            d,c=[x[1] for x in clients.targets(o,home)]
            self.assertEqual(d['existing'],'keep');self.assertNotIn('egressProxyPacUrl',d)
            self.assertEqual(c['env']['OTHER'],'keep');self.assertEqual(c['env']['NO_PROXY'],'')
            self.assertIn('permissions',c)

    def test_unknown_desktop_does_not_create_guessed_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):clients.targets({'port':17897},Path(tmp))
            self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_preflight_wrong_ip_and_groups(self):
        o={'port':17897,'expectedIp':'192.0.2.1','country':'US'}
        good={'all':['住宅固定节点'],'now':'住宅固定节点'}
        responses=[{'mode':'rule'},{'proxies':{'Claude 固定出口':good,'ChatGPT 住宅出口':good}}]
        with patch.object(manage,'api',side_effect=responses),patch.object(manage.subprocess,'check_output',return_value=b'ip=192.0.2.2\nloc=US\n'):
            with self.assertRaisesRegex(ValueError,'egress'):manage.preflight(o)
        with patch.object(manage,'api',return_value={'mode':'global'}):
            with self.assertRaisesRegex(ValueError,'rule mode'):manage.preflight(o)

    def plan_fixture(self, root):
        plan=root/'plan';plan.mkdir()
        targets=[root/'script.js',root/'runtime.json']
        for i,p in enumerate(targets):
            manage.save(p,'old-'+str(i));manage.save(plan/f'before-{i}',p.read_bytes())
        manage.save(root/'profiles.json','{}')
        for n in ['routing.js','runtime.json']:manage.save(plan/n,'new-'+n)
        manage.save(plan/'settings.json','{}')
        manage.save(plan/'plan.json',manage.dump({'targets':list(map(str,targets)),
            'before':[manage.digest(p) for p in targets],
            'candidate':[manage.digest(plan/n) for n in ['routing.js','runtime.json']],
            'profileIndex':str(root/'profiles.json'),'profileHash':manage.digest(root/'profiles.json')}))
        return SimpleNamespace(plan=plan), targets

    def test_failed_apply_restores_both_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,targets=self.plan_fixture(Path(tmp))
            with patch.object(manage,'api') as api,patch.object(manage,'preflight',side_effect=ValueError('bad egress')):
                with self.assertRaisesRegex(ValueError,'restored'):manage.apply(a)
                self.assertEqual(api.call_count,2)
            self.assertEqual([p.read_text(encoding='utf-8') for p in targets],['old-0','old-1'])

    def test_apply_rollback_and_later_edit_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,targets=self.plan_fixture(Path(tmp))
            with patch.object(manage,'api'),patch.object(manage,'preflight'):
                manage.apply(a)
                self.assertEqual(targets[0].read_text(encoding='utf-8'),'new-routing.js')
                manage.save(targets[0],'later user edit')
                with self.assertRaisesRegex(ValueError,'Later edits'):manage.rollback(a)
                self.assertEqual(targets[0].read_text(encoding='utf-8'),'later user edit')
                manage.save(targets[0],'new-routing.js');manage.rollback(a)
            self.assertEqual([p.read_text(encoding='utf-8') for p in targets],['old-0','old-1'])

    def test_prepare_hash_guard_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,targets=self.plan_fixture(Path(tmp)); manage.save(targets[0],'concurrent edit')
            with patch.object(manage,'api') as api:
                with self.assertRaisesRegex(ValueError,'changed since prepare'):manage.apply(a)
                api.assert_not_called()
            self.assertEqual(targets[1].read_text(encoding='utf-8'),'old-1')

if __name__=='__main__':unittest.main()
