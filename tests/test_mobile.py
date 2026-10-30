import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import mobile


class MobileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name) / '.private'
        self.base.mkdir()
        self.res = '[Proxy]\nFixed = vless,192.0.2.10,443,password=test-only,tls=true,peer=example.com\n'
        self.normal = '[Proxy]\nJP normal = trojan,192.0.2.11,443,password=fake\nUS normal = ss,192.0.2.12,443,password=fake,method=aes-128-gcm\n'
        self.baseline = '[General]\nipv6 = false\n[Rule]\nDOMAIN-SUFFIX,qq.com,DIRECT\nDOMAIN-SUFFIX,youtube.com,PROXY\nIP-CIDR,192.168.0.0/16,DIRECT\nGEOIP,CN,DIRECT\nFINAL,PROXY\n'
        for name, text in [('r.conf', self.res), ('n.conf', self.normal), ('base.conf', self.baseline)]:
            (self.base / name).write_text(text, encoding='utf-8')
        self.o = {'schema':1,'residentialFile':'r.conf','ordinaryFile':'n.conf','baselineFile':'base.conf',
                  'residentialNode':'Fixed','ordinaryNodes':['JP normal','US normal'],
                  'expectedIp':'192.0.2.123','country':'US','iosVersion':'test-fixture',
                  'shadowrocketVersion':'2.2.93 (3488)', 'directDns':['https://1.1.1.1/dns-query'], 'extraClaudeDomains':[]}
        self.settings = self.base / 'settings.json'

    def build(self, o=None):
        self.settings.write_text(json.dumps(o or self.o), encoding='utf-8')
        return mobile.build(self.settings)

    def test_routes_and_payment_boundaries(self):
        conf, report = self.build()
        s = mobile.sections(conf)
        self.assertEqual(s['Proxy Group'][0], 'CR_CLAUDE = select,CR_RESIDENTIAL')
        self.assertNotIn('CR_RESIDENTIAL', s['Proxy Group'][1])
        self.assertNotIn('DIRECT', s['Proxy Group'][1])
        self.assertNotIn('PROXY', ','.join(s['Rule']))
        self.assertTrue(s['Rule'][-1] == 'FINAL,CR_NORMAL')
        self.assertLess(conf.index('DOMAIN-SUFFIX,claude.ai,CR_CLAUDE'), conf.index('GEOIP,CN,DIRECT'))
        self.assertIn('DOMAIN-SUFFIX,chatgpt.com,CR_NORMAL', conf)
        self.assertIn('CR_NORMAL_001 = ss, 192.0.2.12', conf)
        self.assertFalse(report['fullyVerified'])
        self.assertTrue(all(v['status']=='pending' for v in report['phoneAcceptance'].values()))

    def test_dns_no_system_fallback_or_fake_stun_and_no_resolve(self):
        conf, _ = self.build()
        self.assertIn('fallback-dns-server = https://1.1.1.1/dns-query#no-h3',conf)
        self.assertIn('dns-fallback-system = false',conf)
        self.assertIn('GEOIP,CN,DIRECT,no-resolve',conf)
        self.assertNotIn('stun-response-ip',conf)
        self.assertNotIn('compatibility-mode',conf)
        self.assertNotIn('skip-proxy',conf)
        self.assertIn('udp-policy-not-supported-behaviour = REJECT',conf)

    def test_renamed_fixed_node_does_not_choose_alternative(self):
        self.o['residentialNode'] = 'missing'
        with self.assertRaisesRegex(ValueError,'missing/renamed'): self.build()

    def test_overlap_rejected_even_if_renamed(self):
        (self.base/'n.conf').write_text(self.normal.replace('192.0.2.11','192.0.2.10'),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'overlaps'): self.build()

    def test_duplicate_names_unknown_options_chains_insecure(self):
        bad = [self.res+'Fixed = ss,192.0.2.15,443,password=x\n',
               self.res.replace('tls=true','proxy=somewhere'),
               self.res.replace('tls=true','allowInsecure=1'),
               self.res.replace('tls=true','unknown=1'),
               self.res.replace('vless,','unsupported,')]
        for text in bad:
            with self.subTest(text=text), self.assertRaises(ValueError): mobile.nodes(text)

    def test_credentials_preserved_without_base64_damage(self):
        result = mobile.nodes(self.res.replace('test-only','YWJjZA=='))
        self.assertIn('password=YWJjZA==',result['Fixed']['definition'])

    def test_export_without_nodes_stops(self):
        with self.assertRaisesRegex(ValueError,'No \[Proxy\]'): mobile.nodes(self.baseline)

    def test_unknown_baseline_features_stop_not_disappear(self):
        bad = [self.baseline+'[Script]\nx = remote.js\n',
               self.baseline+'[Host]\nclaude.ai = 192.0.2.100\n',
               self.baseline.replace('DOMAIN-SUFFIX,qq.com,DIRECT','RULE-SET,https://example.com/a,DIRECT'),
               self.baseline.replace('FINAL,PROXY','FINAL,MyGroup'),
               self.baseline.replace('ipv6 = false','include = other.conf')]
        for text in bad:
            with self.subTest(text=text), self.assertRaises(ValueError): mobile.baseline_rules(text, [])

    def test_default_localhost_mapping_retained(self):
        (self.base/'base.conf').write_text(self.baseline+'[Host]\nlocalhost = 127.0.0.1\n',encoding='utf-8')
        conf,_=self.build()
        self.assertEqual(mobile.sections(conf)['Host'],['localhost = 127.0.0.1'])
        self.assertIn('DOMAIN,localhost,DIRECT',conf)

    def test_template_missing_role_and_untrusted_dns(self):
        changes = [{'_template':True}, {'ordinaryFile':'r.conf'}, {'ordinaryNodes':[]},
                   {'directDns':['system']}, {'directDns':['https://dns.example/dns-query']},
                   {'directDns':['https://1.1.1.1/dns-query#proxy=CR_RESIDENTIAL']},
                   {'extraClaudeDomains':['com']}, {'extraClaudeDomains':['openai.com']},
                   {'iosVersion':''}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError): self.build(dict(self.o, **change))

    def test_additional_download_domain_and_domestic_override(self):
        self.o['extraClaudeDomains']=['download.example.com']
        conf, _ = self.build()
        self.assertIn('DOMAIN-SUFFIX,download.example.com,CR_CLAUDE',conf)
        self.assertNotIn('DOMAIN-SUFFIX,example.com,CR_CLAUDE',conf)
        self.assertIn('DOMAIN-SUFFIX,qq.com,DIRECT',conf)

    def test_bundle_integrity_drift_and_no_overwrite(self):
        self.build()
        out = self.base/'bundle'
        mobile.prepare(self.settings,out)
        self.assertEqual(mobile.check(self.settings,out)['offlineIntegrity'],'pass')
        self.assertFalse(mobile.check(self.settings,out)['phoneVerified'])
        with self.assertRaises(ValueError): mobile.prepare(self.settings,out)
        (out/'shadowrocket.conf').write_text('changed',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'changed'): mobile.check(self.settings,out)

    def test_input_changes_invalidate_bundle(self):
        self.build(); out = self.base/'bundle';mobile.prepare(self.settings,out)
        (self.base/'r.conf').write_text(self.res.replace('test-only','changed'),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'changed'): mobile.check(self.settings,out)

    def test_public_path_and_symlink_write_refused(self):
        with self.assertRaises(ValueError): mobile.save_new(Path(self.tmp.name)/'public.conf','secret')
        p=self.base/'saved';mobile.save_new(p,'first')
        with self.assertRaises(FileExistsError): mobile.save_new(p,'second')
        self.assertEqual(p.read_text(),'first')
        if os.name != 'nt': self.assertEqual(p.stat().st_mode & 0o777,0o600)

    def test_shared_desktop_mobile_policy(self):
        js = "const {build}=require('./src/routing.js');const o={residential:{},ordinaryProvider:{},usPattern:'US',port:12345,proxyServerNameservers:[]};console.log(JSON.stringify(build({},o).rules))"
        r=json.loads(subprocess.check_output(['node','-e',js],cwd=mobile.ROOT,text=True))
        conf,_=self.build()
        for d in mobile.POLICY['claudeDomains']:
            self.assertIn(f'DOMAIN-SUFFIX,{d},Claude 固定出口',r)
            self.assertIn(f'DOMAIN-SUFFIX,{d},CR_CLAUDE',conf)

    def test_cli_never_claims_phone_access(self):
        r=json.loads(subprocess.check_output([sys.executable,str(mobile.ROOT/'scripts/mobile.py'),'capabilities'],text=True))
        self.assertFalse(r['phoneReadWriteAdapter'])
        self.assertFalse(r['automaticOSPermission'])


if __name__=='__main__': unittest.main()
