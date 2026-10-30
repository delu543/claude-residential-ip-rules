import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import adapt, manage, bootstrap, tun_trial, windows_setup

class AdaptTests(unittest.TestCase):
    def test_auto_port_and_occupied_override(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1',0));port=occupied.getsockname()[1]
            runtime={'mixed-port':port}
            self.assertNotEqual(adapt.choose_port(runtime),port)
            with self.assertRaises(ValueError):adapt.choose_port(runtime,port)
            with self.assertRaises(ValueError):adapt.choose_port({},port)
    def test_reuse_only_recognized_managed_listener(self):
        r={'listeners':[{'name':'claude-only-http','type':'http','listen':'127.0.0.1','port':19081,'proxy':'住宅固定节点'}]}
        self.assertEqual(adapt.choose_port(r),19081)
        r['mixed-port']=19081
        with self.assertRaises(ValueError):adapt.choose_port(r)
    def test_local_source_and_no_codex_required(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ordinary.json';manage.save(p,'{"proxies":[]}')
            provider=adapt.provider_options({'type':'local'},p,{'type':'http','url':'stale','proxy':'DIRECT','interval':3600})
            self.assertEqual(provider['type'],'file');self.assertNotIn('url',provider)
            o=manage.read(manage.ROOT/'examples/settings.example.json');o.pop('_template')
            o.update(expectedIp='192.0.2.2',country='JP',port=19081,scope='domains-only',ordinaryProvider=provider,residential={'type':'ss'})
            manage.validate_options(o)
    def test_system_proxy_false_blocks_baseline(self):
        with patch.object(bootstrap.sys,'platform','win32'),patch.object(bootstrap,'http_probe',return_value=True),patch.object(bootstrap,'windows_diagnostics',return_value={'proxy':{'ProxyEnable':0,'ProxyServer':'127.0.0.1:7890'}}):
            r=bootstrap.check({}, {'mixed-port':7890,'tun':{'enable':False}})
            self.assertFalse(r['ready'])
    def test_windows_default_stages_do_not_change_dns_or_enable_tun(self):
        a=SimpleNamespace(settings=Path('s.json'),plan=Path('plan'),exe=None,clients=[],browsers=['chrome'])
        result=windows_setup.steps(a)
        self.assertEqual([x[0] for x in result],['routing','chrome-webrtc'])
        self.assertNotIn('dns',str(result))
    def test_existing_healthy_tun_is_preserved_without_requiring_proxy_toggle(self):
        with patch.object(bootstrap.sys,'platform','win32'),patch.object(bootstrap,'http_probe',side_effect=[True,True]) as probe,patch.object(bootstrap,'windows_diagnostics',return_value={'proxy':{'ProxyEnable':0}}):
            r=bootstrap.check({}, {'mixed-port':7890,'tun':{'enable':True}})
        self.assertTrue(r['ready']);self.assertEqual(r['connectivityMode'],'existing-tun')
        self.assertIsNone(probe.call_args_list[-1].args[1])
        with patch.object(bootstrap.sys,'platform','win32'),patch.object(bootstrap,'http_probe',side_effect=[True,False]),patch.object(bootstrap,'windows_diagnostics',return_value={'proxy':{'ProxyEnable':0}}):
            self.assertFalse(bootstrap.check({}, {'mixed-port':7890,'tun':{'enable':True}})['ready'])
    def test_watchdog_restores_without_online_agent(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);manage.save(p/'baseline.json','{"tun":{"enable":false}}')
            manage.save(p/'settings.json','{}');manage.save(p/'trial.json',manage.dump({'baselineHash':manage.digest(p/'baseline.json'),'seconds':0.01}))
            with patch.object(tun_trial,'api',side_effect=[None,{'tun':{'enable':False}}]) as api:
                tun_trial.watchdog(p)
                self.assertEqual(api.call_args_list[0].args[1],'/configs?force=false')
                self.assertTrue((p/'restored.json').exists())
    def test_restore_rejects_changed_backup(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);manage.save(p/'baseline.json','{}');manage.save(p/'trial.json','{"baselineHash":"wrong"}')
            with patch.object(tun_trial,'api') as api:
                with self.assertRaises(ValueError):tun_trial.restore(p)
                api.assert_not_called()
    def test_init_adapts_provider_protocol_port_country_and_missing_codex(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);profiles=base/'profiles'
            res={'name':'private-fixed','type':'ss','server':'192.0.2.10','port':5678,'password':'test-only'}
            manage.save(profiles/'r.json',manage.dump({'proxies':[res]}))
            manage.save(profiles/'n.json','{"proxies":[{"name":"JP","type":"http","server":"127.0.0.1","port":80}]}')
            manage.save(base/'profiles.yaml',manage.dump({'current':'r','items':[{'uid':'r','type':'remote','file':'r.json'},{'uid':'n','type':'local','file':'n.json'}]}))
            manage.save(base/'clash-verge.yaml',manage.dump({'mixed-port':7890,'tun':{'enable':False},'dns':{'default-nameserver':['1.1.1.1']}}))
            a=SimpleNamespace(verge_dir=base,settings=base/'settings.json',residential_uid='r',ordinary_uid='n',node='private-fixed',expected_ip='192.0.2.20',country='JP',scope='domains-only',direct_country=['NONE'])
            with patch.object(manage,'discover_paths',return_value=([],[])),patch.object(manage,'controller_options',return_value={'apiPipe':r'\\.\pipe\test'}),patch.object(manage.sys,'platform','win32'):
                manage.init_settings(a)
            o=manage.read(a.settings)
            self.assertEqual(o['residential']['type'],'ss');self.assertEqual(o['residential']['port'],5678)
            self.assertEqual(o['country'],'JP');self.assertEqual(o['ordinaryProvider']['type'],'file')
            self.assertEqual(o['directCountries'],[]);self.assertEqual(o['codexPaths'],[])
            self.assertFalse(o['windowsTun']);self.assertGreater(o['port'],1023)

if __name__=='__main__':unittest.main()
