import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import universal as u
import mobile
import surge_adapter
import manage


class UniversalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'.private';self.root.mkdir()
        self.manifest=self.root/'manifest.json'

    def source(self,name,content):
        path=self.root/name;path.write_text(content,encoding='utf-8')
        return {'path':str(path),'sha256':u.sha(path.read_bytes())}

    def fixture(self,adapter='mihomo',target='windows'):
        fmt=u.ADAPTERS[adapter]['format']
        if fmt=='mihomo':
            r=json.dumps({'proxies':[{'name':'Fixed','type':'http','server':'192.0.2.1','port':443}]})
            n=json.dumps({'proxies':[{'name':'US','type':'http','server':'192.0.2.2','port':443},{'name':'JP','type':'http','server':'192.0.2.3','port':443}]})
            base=json.dumps({'mixed-port':7897,'tun':{'enable':False},'rules':['MATCH,DIRECT'],'dns':{}})
        else:
            r='[Proxy]\nFixed = trojan,192.0.2.1,443,password=fixture\n'
            n='[Proxy]\nUS = trojan,192.0.2.2,443,password=fixture\nJP = trojan,192.0.2.3,443,password=fixture\n'
            base='[Rule]\nDOMAIN-SUFFIX,qq.com,DIRECT\nGEOIP,CN,DIRECT\nFINAL,PROXY\n'
        s1=dict(self.source('fixed.src',r),id='fixed',format=fmt,usage='claude-only')
        s2=dict(self.source('ordinary.src',n),id='normal',format=fmt,usage='ordinary')
        o={'schema':2,'target':{'adapter':adapter,'platform':target,'client':'fixture-client','version':'2.2.93 (3488)','osVersion':'18.0','scope':'domains-only'},
           'sources':[s1,s2],'baseline':self.source('base.src',base),'reviewedPolicyReplacement':True,
           'roles':{'claude':{'source':'fixed','node':'Fixed','expectedIp':'192.0.2.10','country':'US'},'ordinary':[{'source':'normal','node':'US'},{'source':'normal','node':'JP'}]},
           'policy':{'preferredPattern':'(?i)US','directCountries':['CN'],'directGeosites':[],'directDomains':[],'extraClaudeDomains':[]},
           'privacy':{'webRTC':'client-stun' if fmt!='mihomo' else 'browser-policy','browser':'chrome','directResolvers':['https://1.1.1.1/dns-query'],'proxiedResolvers':['https://1.1.1.1/dns-query'],'bootstrapResolvers':['https://1.1.1.1/dns-query']},
           'port':19684,'claudePaths':[],'codexPaths':[]}
        return o

    def put(self,o):
        self.manifest.write_text(json.dumps(o),encoding='utf-8');return self.manifest

    def prepare(self,o):
        with patch.object(u,'choose_port',return_value=o.get('port',19684)):
            u.prepare(self.put(o),self.root/'plan')
        return u.load(self.root/'plan/receipt.json')

    def test_multi_source_and_ordinary_only_reachability(self):
        o=self.fixture()
        third=dict(self.source('third.json',json.dumps({'proxies':[{'name':'US third','type':'socks5','server':'192.0.2.8','port':443}]})),id='third',format='mihomo',usage='ordinary')
        o['sources'].append(third);o['roles']['ordinary'].append({'source':'third','node':'US third'})
        r=self.prepare(o);c=u.load(self.root/'plan/mihomo.json')
        self.assertEqual(r['sourceCount'],3);self.assertEqual(r['ordinaryNodeCount'],3)
        self.assertEqual(set(c['proxy-providers']),{'ordinary-normal','ordinary-third'})
        self.assertEqual(c['proxy-groups'][0]['proxies'],['住宅固定节点'])
        self.assertEqual(c['tun'],{'enable':False})
        self.assertFalse(r['fullyVerified']);self.assertTrue(u.check(self.manifest,self.root/'plan'))

    def test_single_source_distinct_nodes_explicit_mixed(self):
        o=self.fixture();a=manage.read(o['sources'][0]['path']);b=manage.read(o['sources'][1]['path'])
        o['sources']=[dict(self.source('all.json',json.dumps({'proxies':a['proxies']+b['proxies']})),id='all',usage='mixed',format='mihomo')]
        o['roles']['claude']['source']='all'
        for n in o['roles']['ordinary']:n['source']='all'
        r=self.prepare(o);self.assertEqual(r['sourceCount'],1)
        payload=u.load(self.root/'plan/settings.json')['ordinaryProviders']['ordinary-all']['payload']
        self.assertEqual(len(payload),2);self.assertNotIn('192.0.2.1',json.dumps(payload))

    def test_single_node_requires_ack_and_rejects_ordinary(self):
        o=self.fixture();o['sources']=o['sources'][:1];o['roles']['ordinary']=[]
        with self.assertRaisesRegex(ValueError,'No ordinary'):u.context(self.put(o))
        o['roles']['ordinaryUnavailableAccepted']=True;self.prepare(o)
        c=u.load(self.root/'plan/mihomo.json');self.assertEqual(c['proxy-providers'],{})
        self.assertTrue(all(g.get('proxies')==['REJECT'] and not g.get('use') for g in c['proxy-groups'][3:]))

    def test_no_auto_role_guess_and_hash_drift(self):
        o=self.fixture();o['roles']['claude']=None
        with self.assertRaises(ValueError):u.context(self.put(o))
        o=self.fixture();Path(o['sources'][0]['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'Source changed'):u.context(self.put(o))

    def test_alias_overlap_and_exclusive_source_rejected(self):
        for mutate in (lambda o:o['roles']['ordinary'].append({'source':'fixed','node':'Fixed'}),
                       lambda o:o['sources'][1].update(usage='claude-only')):
            o=self.fixture();mutate(o)
            with self.assertRaises(ValueError):u.context(self.put(o))
        o=self.fixture();b=manage.read(o['sources'][1]['path']);b['proxies'][0]['server']='192.0.2.1'
        s=self.source('normal-alias.json',json.dumps(b));o['sources'][1].update(s)
        with self.assertRaisesRegex(ValueError,'overlaps'):u.context(self.put(o))

    def test_empty_role_source_duplicate_ref_and_unknown_client_fail(self):
        mutations=[lambda o:o['sources'][0].update(usage='unassigned'),
                   lambda o:o['roles']['ordinary'].append(o['roles']['ordinary'][0]),
                   lambda o:o['target'].update(adapter='sing-box'),
                   lambda o:o['sources'][0].update(format='shadowrocket'),
                   lambda o:o.update(reviewedPolicyReplacement=False)]
        for mutate in mutations:
            o=self.fixture();mutate(o)
            with self.assertRaises(ValueError):u.context(self.put(o))

    def test_node_security_chain_and_missing_fixed_identity(self):
        for extra in ({'skip-cert-verify':True},{'dialer-proxy':'DIRECT'},{'type':'direct'},{'routing-mark':7}):
            n={'name':'fake','server':'192.0.2.1','port':443,'type':'vless',**extra}
            with self.assertRaises(ValueError):u.validate_mihomo_node(n)
        o=self.fixture();o['roles']['claude']['node']='missing'
        with self.assertRaisesRegex(ValueError,'missing'):u.context(self.put(o))

    def test_mobile_mihomo_no_desktop_policy_and_udp_requires_consent(self):
        o=self.fixture(target='android')
        with self.assertRaisesRegex(ValueError,'WebRTC'):u.context(self.put(o))
        o['privacy']['webRTC']='reject-udp'
        with self.assertRaisesRegex(ValueError,'UDP rejection'):u.context(self.put(o))
        o['privacy']['udpImpactAccepted']=True;self.prepare(o)
        c=u.load(self.root/'plan/mihomo.json');self.assertEqual(c['rules'][0],'NETWORK,udp,REJECT')
        self.assertFalse(c['tun']['enable'])

    def test_no_plaintext_or_ambiguous_dns_and_conflicting_direct(self):
        for dns in (['system'],['https://dns.example/dns-query'],['https://1.1.1.1/dns-query#DIRECT'],[]):
            o=self.fixture();o['privacy']['directResolvers']=dns
            with self.assertRaises(ValueError):u.context(self.put(o))
        o=self.fixture();o['policy']['directDomains']=['claude.ai']
        with self.assertRaisesRegex(ValueError,'conflict'):u.context(self.put(o))

    def test_shadowrocket_multi_source_and_legacy_usb_integrity(self):
        o=self.fixture('shadowrocket','ios');self.prepare(o)
        conf=(self.root/'plan/shadowrocket.conf').read_text()
        self.assertIn('CR_CLAUDE = select,CR_RESIDENTIAL',conf)
        self.assertIn('dns-fallback-system = false',conf)
        self.assertEqual(mobile.check(self.manifest,self.root/'plan')['offlineIntegrity'],'pass')
        o['sources'][0]['sha256']='0'*64;self.put(o)
        with self.assertRaises(ValueError):mobile.check(self.manifest,self.root/'plan')

    def test_shadowrocket_one_node_no_ordinary_keeps_fail_closed(self):
        o=self.fixture('shadowrocket','ios');o['sources']=o['sources'][:1];o['roles']['ordinary']=[];o['roles']['ordinaryUnavailableAccepted']=True
        self.prepare(o)
        self.assertIn('CR_NORMAL = select,REJECT',(self.root/'plan/shadowrocket.conf').read_text())

    def test_surge_uses_native_protocol_and_stun_semantics(self):
        o=self.fixture('surge','ios');self.prepare(o)
        conf=(self.root/'plan/surge.conf').read_text()
        self.assertIn('PROTOCOL,STUN,REJECT',conf);self.assertIn('encrypted-dns-server =',conf)
        self.assertNotIn('dns-fallback-system',conf)
        self.assertIn('CR_CLAUDE = select,CR_RESIDENTIAL',conf)
        for text in ('[Proxy]\na = vless,192.0.2.1,443,password=x',
                     '[Proxy]\na = trojan,192.0.2.1,443,password=x,underlying-proxy=DIRECT',
                     '[Proxy]\na = ss,192.0.2.1,443,password=x,method=aes-128-gcm'):
            with self.assertRaises(ValueError):surge_adapter.nodes(text)

    def test_candidates_and_backups_never_overwritten(self):
        o=self.fixture();self.prepare(o)
        with self.assertRaises(ValueError):u.prepare(self.manifest,self.root/'plan')
        c=self.root/'plan/mihomo.json';c.write_text('{}')
        with self.assertRaisesRegex(ValueError,'Candidate changed'):u.check(self.manifest,self.root/'plan')

    def test_native_version_scope_and_baseline_safety(self):
        for mutate in (lambda o:o['target'].update(version='latest'),lambda o:o['target'].update(scope='clients'),lambda o:o['policy'].update(directGeosites=['cn'])):
            o=self.fixture('surge','ios');mutate(o)
            with self.assertRaises(ValueError):u.context(self.put(o))
        o=self.fixture('shadowrocket','ios');o['baseline']=self.source('rewrite.conf','[Script]\nprivate = script-path=secret\n[Rule]\nGEOIP,CN,DIRECT\n')
        with self.assertRaisesRegex(ValueError,'sections'):u.prepare(self.put(o),self.root/'plan')

    def test_cli_failure_redacts_private_input_and_does_not_write(self):
        p=self.root/'secret.json';p.write_text('{"credential":"TOKEN_MUST_NOT_PRINT",')
        q=subprocess.run([sys.executable,str(u.ROOT/'scripts/universal.py'),'prepare','--manifest',str(p),'--output',str(self.root/'plan')],capture_output=True,text=True)
        self.assertNotEqual(q.returncode,0);self.assertNotIn('TOKEN_MUST_NOT_PRINT',q.stdout+q.stderr)
        self.assertFalse((self.root/'plan').exists())

    def test_existing_verge_profile_need_not_be_fixed_subscription(self):
        o=self.fixture('clash-verge',u.PLATFORMS.get(sys.platform,'macos'))
        if sys.platform not in ('win32','darwin'): self.skipTest('Verge target host only')
        vd=self.root/'verge';vd.mkdir();base=vd/'clash-verge.yaml'
        base.write_text(json.dumps({'mixed-port':7897,'external-controller-unix':'/tmp/test-only.sock','external-controller-pipe':r'\\.\pipe\test-only','tun':{'enable':False}}))
        idx=vd/'profiles.yaml';idx.write_text(json.dumps({'current':'ordinary-profile','items':[]}))
        o['vergeDir']=str(vd);o['baseline']={'path':str(base),'sha256':u.sha(base.read_bytes())}
        self.prepare(o);settings=u.load(self.root/'plan/settings.json')
        self.assertEqual(settings['baseUid'],'ordinary-profile')
        self.assertIn('fixedNode',settings)
        self.assertNotIn('residentialUid',settings)


class UniversalDiscoveryTests(unittest.TestCase):
    def test_draft_auto_sources_without_guessing_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'.private';root.mkdir();vd=root/'verge';(vd/'profiles').mkdir(parents=True)
            (vd/'profiles/p.json').write_text(json.dumps({'proxies':[{'name':'US label not proof','type':'http','server':'192.0.2.1','port':443}]}))
            (vd/'profiles.yaml').write_text(json.dumps({'current':'p','items':[{'uid':'p','type':'local','file':'p.json'}]}))
            (vd/'clash-verge.yaml').write_text('{"mixed-port":7897}')
            with patch.object(u.manage,'discover_paths',return_value=([],[])):
                inv=u.discover(vd)
                self.assertEqual(len(inv['vergeProfiles']),1)
                self.assertTrue(inv['roleSelectionRequired'])
                args=SimpleNamespace(verge_dir=vd,target='windows',adapter='clash-verge',source=None,baseline=None,manifest=root/'draft.json')
                u.draft(args)
            o=u.load(args.manifest)
            self.assertEqual(len(o['sources']),1)
            self.assertEqual(o['sources'][0]['usage'],'unassigned');self.assertIsNone(o['roles']['claude'])
            self.assertIsNone(o['target']['version']);self.assertFalse(o['reviewedPolicyReplacement'])
            self.assertEqual(o['privacy']['webRTC'],'unselected')

    def test_unknown_config_is_not_silently_parsed_as_shadowrocket(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'unknown.conf';p.write_text('{"outbounds": []}')
            with self.assertRaises(ValueError):u.parse_nodes(p,'surge')
            with self.assertRaises(ValueError):u.parse_nodes(p,'mihomo')

class UniversalBridgeTests(unittest.TestCase):
    setUp=UniversalTests.setUp
    source=UniversalTests.source
    fixture=UniversalTests.fixture
    put=UniversalTests.put
    prepare=UniversalTests.prepare
    def test_schema2_usb_stages_only_matching_native_app(self):
        import asyncio
        import mobile_usb
        from test_mobile_usb import Documents
        o=self.fixture('shadowrocket','ios');self.prepare(o)
        device={'device':'fixture-only','iosVersion':'18.0','shadowrocketVersion':'2.2.93','shadowrocketBuild':'3488'}
        service=Documents()
        r=asyncio.run(mobile_usb.stage(service,self.manifest,self.root/'plan',device))
        self.assertEqual(len(service.writes),1);self.assertFalse(r['activated']);self.assertFalse(r['networkVerified'])

    def test_mihomo_region_filter_does_not_match_source_id(self):
        o=self.fixture();o['sources'][1]['id']='US-source'
        for n in o['roles']['ordinary']:n['source']='US-source'
        self.prepare(o);s=u.load(self.root/'plan/settings.json')
        self.assertIn('US-source',s['ordinaryPreferredFilter'])
        self.assertNotIn('JP',s['ordinaryPreferredFilter'])

    def test_verge_prepare_accepts_ordinary_base_without_switching(self):
        if sys.platform not in ('win32','darwin'): self.skipTest('Verge supported hosts only')
        o=self.fixture('clash-verge',u.PLATFORMS[sys.platform]);vd=self.root/'verge';(vd/'profiles').mkdir(parents=True)
        (vd/'profiles/main.json').write_text(json.dumps({'proxies':[{'name':'different-active-node','type':'http','server':'192.0.2.20','port':443}]}))
        (vd/'profiles/script.js').write_text('function main(c){return c;}')
        (vd/'profiles.yaml').write_text(json.dumps({'current':'active','items':[{'uid':'active','file':'main.json','option':{'script':'s'}},{'uid':'s','file':'script.js'}]}))
        bp=vd/'clash-verge.yaml';bp.write_text(json.dumps({'mixed-port':7897,'external-controller-unix':'/tmp/test-only.sock','external-controller-pipe':r'\\.\pipe\test-only','tun':{'enable':False}}))
        o['vergeDir']=str(vd);o['baseline']={'path':str(bp),'sha256':u.sha(bp.read_bytes())}
        self.prepare(o);before=bp.read_bytes()
        real_run=subprocess.run
        def checked(args,**kw):
            if args[0]=='fake-mihomo':return subprocess.CompletedProcess(args,0,b'fixture syntax only',b'')
            return real_run(args,**kw)
        a=SimpleNamespace(settings=self.root/'plan/settings.json',verge_dir=vd,plan=self.root/'install',mihomo=Path('fake-mihomo'))
        with patch.object(manage.subprocess,'run',side_effect=checked),patch.object(manage,'choose_port',return_value=19684):
            manage.prepare(a)
        self.assertEqual(bp.read_bytes(),before)
        candidate=manage.read(a.plan/'runtime.json')
        self.assertEqual(candidate['proxies'][0]['server'],'192.0.2.1')
        self.assertEqual(manage.read(vd/'profiles.yaml')['current'],'active')


if __name__=='__main__':unittest.main()
