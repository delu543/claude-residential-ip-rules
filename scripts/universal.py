#!/usr/bin/env python3
"""Offline discovery and role-based planning; never activates a VPN or fetches subscriptions."""
import argparse
import copy
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

import mobile
import manage
from adapt import choose_port
from platform_support import default_verge_dir, controller_options

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = {
    'clash-verge': {'format': 'mihomo', 'platforms': ['windows','macos'], 'deployment': 'existing-backed-up-manage-workflow'},
    'mihomo': {'format': 'mihomo', 'platforms': ['windows','macos','android','linux'], 'deployment': 'native-import-required'},
    'shadowrocket': {'format': 'shadowrocket', 'platforms': ['ios'], 'deployment': 'native-import-required'},
    'surge': {'format': 'surge', 'platforms': ['macos','ios'], 'deployment': 'native-import-required'},
}
PLATFORMS = {'darwin':'macos', 'win32':'windows', 'linux':'linux'}
MOBILE = {'ios','android'}
MAX_FILE = 8 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def local(path):
    p = Path(path).expanduser().resolve()
    if not p.is_file() or p.stat().st_size > MAX_FILE:
        raise ValueError('Input must be an existing local file no larger than 8 MiB')
    return p, p.read_bytes()


def load(path):
    p, b = local(path)
    return json.loads(b.decode('utf-8-sig'))


def write(path, data):
    mobile.save_new(path, data if isinstance(data,str) else json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def resolve(manifest, value):
    return mobile.resolve(Path(manifest).resolve(), value).resolve()


def validate_mihomo_node(n):
    if not isinstance(n,dict) or not isinstance(n.get('name'),str) or not n['name']:
        raise ValueError('Every node needs an unambiguous local name')
    if n.get('type') not in {'http','socks5','ss','ssr','vmess','vless','trojan','hysteria','hysteria2','tuic','snell','wireguard','anytls'}:
        raise ValueError('Unsupported concrete proxy type; do not substitute a node')
    if not isinstance(n.get('server'),str) or not n['server'] or type(n.get('port')) is not int or not 1<=n['port']<=65535:
        raise ValueError('Node is missing an actual server/port')
    if any(c in n['server'] for c in '\r\n, /#'):
        raise ValueError('Invalid proxy server')
    if n.get('dialer-proxy') or n.get('interface-name') or n.get('routing-mark'):
        raise ValueError('Chained/interface-bound nodes require a separately reviewed adapter')
    def tls(v):
        if isinstance(v,dict):
            for k,x in v.items():
                if k in ('skip-cert-verify','insecure','allow-insecure') and x not in (False,None):
                    raise ValueError('TLS certificate verification must remain enabled')
                tls(x)
        elif isinstance(v,list):
            for x in v: tls(x)
    tls(n)


def parse_nodes(path, fmt):
    _, raw = local(path)
    text = raw.decode('utf-8-sig')
    if fmt == 'shadowrocket':
        return mobile.nodes(text)
    if fmt == 'surge':
        from surge_adapter import nodes
        return nodes(text)
    if fmt != 'mihomo':
        raise ValueError('Unknown native format; do not translate by filename')
    doc = manage.read(path)
    if not isinstance(doc,dict) or not isinstance(doc.get('proxies'),list) or not doc['proxies']:
        raise ValueError('Export actual proxies or an authorized provider cache; a provider URL is not a node list')
    result={}
    for n in doc['proxies']:
        validate_mihomo_node(n)
        if n['name'] in result: raise ValueError('Duplicate node names within one source')
        result[n['name']]={'definition':n,'endpoint':(n['server'].lower().rstrip('.'),n['port']), 'type':n['type']}
    return result


def discover(verge_dir=None):
    """Bounded local inventory. No source contents or commands with credentials in stdout."""
    host=PLATFORMS.get(sys.platform,'unknown')
    roots=[]
    apps=[]
    if sys.platform=='darwin':
        for root in [Path('/Applications'),Path.home()/'Applications']:
            if root.is_dir():
                for p in root.glob('*.app'):
                    if not re.search('clash|surge|shadowrocket|sing.box|chrome|edge|firefox|claude',p.name,re.I): continue
                    try:
                        info=plistlib.loads((p/'Contents/Info.plist').read_bytes())
                        apps.append({'name':p.name,'path':str(p),'bundle':info.get('CFBundleIdentifier'), 'version':info.get('CFBundleShortVersionString')})
                    except (OSError,ValueError): pass
        roots=[Path.home()/'Library/Application Support',Path.home()/'.config']
    elif sys.platform=='win32':
        roots=[Path(os.environ.get('APPDATA',str(Path.home()/'AppData/Roaming'))),Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))]
        # Known installation roots only. Not registry credentials, browser history, or command lines.
        for env in ('LOCALAPPDATA','ProgramFiles','ProgramFiles(x86)'):
            if not os.environ.get(env): continue
            for rel in ('Google/Chrome/Application/chrome.exe','Microsoft/Edge/Application/msedge.exe','Clash Verge/clash-verge.exe','Programs/Clash Verge/clash-verge.exe','FlClash/FlClash.exe','Programs/FlClash/FlClash.exe'):
                p=Path(os.environ[env])/rel
                if p.is_file(): apps.append({'name':p.name,'path':str(p),'version':None})
    else: roots=[Path.home()/'.config']
    hints=[]
    for root in roots:
        if root.is_dir():
            hints += [str(p) for p in root.iterdir() if p.is_dir() and re.search('clash|mihomo|surge|sing.box',p.name,re.I)]
    profiles=[]
    base=Path(verge_dir) if verge_dir else default_verge_dir()
    if (base/'profiles.yaml').is_file():
        doc=manage.read(base/'profiles.yaml')
        for item in doc.get('items',[]):
            if item.get('type') not in ('remote','local'): continue
            p=manage.profile_path(base,item)
            row={'uid':item['uid'],'path':str(p),'active':doc.get('current')==item['uid']}
            try:
                rows=parse_nodes(p,'mihomo')
                row.update(nodes=[{'name':k,'type':v['type']} for k,v in rows.items()],sha256=sha(p.read_bytes()))
            except (ValueError,TypeError,KeyError,OSError): row['requiresNativeExport']=True
            profiles.append(row)
    try:
        cp,xp=manage.discover_paths() if sys.platform in ('win32','darwin') else ([],[])
    except (OSError,ValueError,subprocess.SubprocessError): cp,xp=[],[]
    return {'schema':2,'host':host,'applications':apps,'configDirectoryHints':hints,'vergeProfiles':profiles,
            'claudePaths':cp,'codexPaths':xp,'dependencies':{k:bool(shutil.which(k)) for k in ('node','git','curl','python3','python')},
            'phone':'not-inspected; use authorized device bridge/native export',
            'roleSelectionRequired':True,'networkChanged':False,'fullyVerified':False}


def draft(a):
    inv=discover(a.verge_dir)
    target=a.target or inv['host']
    if target not in ADAPTERS[a.adapter]['platforms']:
        raise ValueError('Selected adapter does not support the target OS')
    fmt=ADAPTERS[a.adapter]['format']
    paths=list(a.source or [])
    if not paths and a.adapter=='clash-verge':
        paths=[Path(x['path']) for x in inv['vergeProfiles'] if not x.get('requiresNativeExport')]
    sources=[]
    for i,p in enumerate(paths):
        p,raw=local(p);parse_nodes(p,fmt)
        sources.append({'id':f'source-{i+1}','path':str(p),'format':fmt,'sha256':sha(raw),'usage':'unassigned'})
    base = a.baseline
    if not base and a.adapter=='clash-verge': base=(a.verge_dir or default_verge_dir())/'clash-verge.yaml'
    baseline=None
    if base:
        p,raw=local(base);baseline={'path':str(p),'sha256':sha(raw)}
    o={'schema':2,'target':{'platform':target,'adapter':a.adapter,'client':None,'version':None,'osVersion':None,'scope':'domains-only'},
       'sources':sources,'baseline':baseline,'reviewedPolicyReplacement':False,
       'roles':{'claude':None,'ordinary':[],'ordinaryUnavailableAccepted':False},
       'policy':{'preferredPattern':r'(?i)(美国|美國|United States|\bUS\b|🇺🇸)', 'directCountries':[], 'directGeosites':[], 'directDomains':[], 'extraClaudeDomains':[]},
       'privacy':{'webRTC':'unselected','directResolvers':[], 'proxiedResolvers':[], 'bootstrapResolvers':[]},
       'claudePaths':inv['claudePaths'] if target==inv['host'] else [],'codexPaths':inv['codexPaths'] if target==inv['host'] else [],'port':None}
    if a.adapter=='clash-verge': o['vergeDir']=str((a.verge_dir or default_verge_dir()).resolve())
    write(a.manifest,o)
    return {'status':'draft-needs-role-and-privacy-review','sources':len(sources),'networkChanged':False}


def encrypted(values):
    if not isinstance(values,list) or not values: raise ValueError('Select reachable encrypted DNS explicitly')
    for x in values:
        if not isinstance(x,str): raise ValueError('Invalid encrypted DNS')
        u=urlsplit(x)
        if u.scheme!='https' or u.username or u.password or u.query or u.fragment or not u.path or any(c in x for c in ',\r\n '):
            raise ValueError('Use HTTPS DNS without embedded policy, credentials or query')
        try: ipaddress.ip_address(u.hostname)
        except ValueError: raise ValueError('Use literal-IP DoH to avoid DNS bootstrap loops') from None
    return values


def context(path):
    o=load(path)
    if o.get('schema')!=2: raise ValueError('Use a schema 2 local manifest')
    t=o['target'];ad=ADAPTERS.get(t.get('adapter'))
    if not ad or t.get('platform') not in ad['platforms']: raise ValueError('Unsupported client/engine/platform; collect native capability evidence first')
    for k in ('client','version','osVersion'):
        if not isinstance(t.get(k),str) or not t[k].strip() or t[k].lower() in ('latest','unknown'):
            raise ValueError('Record actual client and OS versions; do not infer latest')
    if t.get('scope') not in ('clients','domains-only'): raise ValueError('Choose clients or domains-only scope')
    if t['adapter'] not in ('clash-verge','mihomo') and t['scope']!='domains-only':
        raise ValueError('This native adapter currently supports domain routing only')
    if t['platform'] in MOBILE and t['scope']!='domains-only': raise ValueError('Phone app attribution cannot be inferred from desktop paths')
    if o.get('reviewedPolicyReplacement') is not True: raise ValueError('Review baseline rules/groups/DNS before replacing policy')
    sources={};texts={};hashes={}
    if not isinstance(o.get('sources'),list) or not o['sources']: raise ValueError('No local source; obtain a native export')
    for s in o['sources']:
        sid=s.get('id')
        if not isinstance(sid,str) or not re.fullmatch('[A-Za-z0-9_-]+',sid) or sid in sources: raise ValueError('Source IDs must be unique safe identifiers')
        if s.get('format')!=ad['format']: raise ValueError('Native format mismatch; no online or guessed protocol conversion')
        if s.get('usage') not in ('claude-only','ordinary','mixed','unused'): raise ValueError('Assign billing/route roles explicitly')
        p,raw=local(resolve(path,s['path']))
        if sha(raw)!=s.get('sha256'): raise ValueError('Source changed; re-inspect roles and prepare a fresh plan')
        sources[sid]=(s,parse_nodes(p,s['format']));texts[sid]=raw.decode('utf-8-sig');hashes[str(p)]=sha(raw)
    def selected(ref):
        if not isinstance(ref,dict) or ref.get('source') not in sources: raise ValueError('Select a source and exact node; roles cannot be guessed')
        s,ns=sources[ref['source']]
        if ref.get('node') not in ns: raise ValueError('Selected node missing/renamed; do not choose another')
        return s,copy.deepcopy(ns[ref['node']])
    r=o['roles'];ref=r.get('claude');s,fixed=selected(ref)
    if s['usage'] not in ('claude-only','mixed'): raise ValueError('Claude node source not approved for Claude')
    ipaddress.ip_address(ref['expectedIp'])
    if not re.fullmatch('[A-Z]{2}',ref.get('country','')): raise ValueError('Approved fixed egress country required')
    normal=[];seen=set();exclusive={n['endpoint'] for source,ns in sources.values() if source['usage']=='claude-only' for n in ns.values()}
    if not isinstance(r.get('ordinary'),list): raise ValueError('Ordinary selections must be a list')
    for nr in r['ordinary']:
        ns,n=selected(nr)
        if ns['usage'] not in ('ordinary','mixed'): raise ValueError('Ordinary traffic may not borrow a protected source')
        if n['endpoint']==fixed['endpoint'] or n['endpoint'] in exclusive: raise ValueError('Ordinary endpoint overlaps protected capacity, including renamed copies')
        if n['endpoint'] in seen: raise ValueError('Duplicate ordinary endpoint; select one identity explicitly')
        seen.add(n['endpoint']);n.update(source=nr['source'],name=nr['node']);normal.append(n)
    if not normal and r.get('ordinaryUnavailableAccepted') is not True:
        raise ValueError('No ordinary pool: select another node or explicitly accept ordinary traffic rejection')
    b=o.get('baseline')
    if not isinstance(b,dict): raise ValueError('Supply current native baseline before preparing')
    bp,raw=local(resolve(path,b['path']))
    if sha(raw)!=b.get('sha256'): raise ValueError('Baseline changed; re-inspect before preparing')
    texts['baselineFile']=raw.decode('utf-8-sig');hashes[str(bp)]=sha(raw)
    privacy=o['privacy'];webrtc=privacy.get('webRTC')
    allowed=['browser-policy','reject-udp'] if t['platform'] not in MOBILE else ['reject-udp']
    if t['adapter'] in ('shadowrocket','surge'): allowed+=['client-stun']
    if webrtc not in allowed: raise ValueError('Choose an available WebRTC method; desktop policies cannot protect mobile browsers')
    if webrtc=='reject-udp' and privacy.get('udpImpactAccepted') is not True:
        raise ValueError('UDP rejection can break calls/games; record user acceptance first')
    if webrtc=='browser-policy' and privacy.get('browser') not in ('chrome','edge'):
        raise ValueError('Select a supported desktop browser; other browsers require a reviewed adapter')
    if webrtc=='browser-policy' and t['platform'] not in ('windows','macos'):
        raise ValueError('No automated browser policy writer for this OS')
    encrypted(privacy.get('directResolvers'))
    if t['adapter'] in ('clash-verge','mihomo'):
        encrypted(privacy.get('proxiedResolvers')); encrypted(privacy.get('bootstrapResolvers'))
    pol=o['policy'];pattern=pol.get('preferredPattern')
    if not isinstance(pattern,str) or not pattern or len(pattern)>256: raise ValueError('Use an explicit bounded preferred-region pattern')
    re.compile(pattern)
    for k in ('directCountries',):
        if any(not re.fullmatch('[A-Z]{2}',c) for c in pol.get(k,[])): raise ValueError('Invalid direct country')
    if any(not re.fullmatch('[a-zA-Z0-9_.!@-]+',x) for x in pol.get('directGeosites',[])): raise ValueError('Invalid geosite')
    if ad['format']!='mihomo' and pol.get('directGeosites'):
        raise ValueError('GeoSite tags are engine-specific; use the native reviewed baseline instead')
    for k in ('directDomains','extraClaudeDomains'):
        for d in pol.get(k,[]): mobile.domain(d)
    protected=mobile.POLICY['claudeDomains']+pol.get('extraClaudeDomains',[])
    for d in pol.get('directDomains',[]):
        if any(d==x or d.endswith('.'+x) or x.endswith('.'+d) for x in protected): raise ValueError('Direct domains conflict with protected targets')
    if any(d==x or d.endswith('.'+x) or x.endswith('.'+d) for d in pol.get('extraClaudeDomains',[]) for x in mobile.POLICY['openaiDomains']):
        raise ValueError('Do not classify OpenAI as Claude')
    return o,fixed,normal,texts,hashes,bp


def mihomo_options(o,fixed,normal,base):
    p=o['privacy'];t=o['target'];r=o['roles']['claude']
    providers={};preferred_names=[]
    pattern=re.compile(o['policy']['preferredPattern'])
    for n in normal:
        key='ordinary-'+n['source']
        nd=copy.deepcopy(n['definition']);nd['name']=n['source']+' | '+n['name']
        providers.setdefault(key,{'type':'inline','payload':[]})['payload'].append(nd)
        if pattern.search(n['name']): preferred_names.append(nd['name'])
    opt={'residential':{k:fixed['definition'][k] for k in ('name','type','server','port')},
         'fixedNode':fixed['definition'],'ordinaryProviders':providers,'expectedIp':r['expectedIp'],'country':r['country'],
         'port':o.get('port'), 'platform':{'windows':'win32','macos':'darwin'}.get(t['platform'],t['platform']),
         'claudePaths':o.get('claudePaths',[]),'codexPaths':o.get('codexPaths',[]),'scope':t['scope'],
         'proxyServerNameservers':p['bootstrapResolvers'],'defaultNameservers':p['bootstrapResolvers'],
         'directResolvers':p['directResolvers'],'proxiedResolvers':p['proxiedResolvers'],
         'rejectAllUdp':p['webRTC']=='reject-udp', **o['policy']}
    # Match original labels, not source IDs; use a RE2-compatible exact alias set.
    escape=lambda s: re.sub(r'([\\.*+?()\[\]{}^$|])', r'\\\1', s)
    opt['ordinaryPreferredFilter']='^(?:'+'|'.join(escape(n) for n in preferred_names)+')$' if preferred_names else 'a^'
    if t['platform'] in MOBILE:
        if opt['claudePaths'] or opt['codexPaths']: raise ValueError('Do not copy desktop paths onto a phone')
    # Only the actual target host can allocate/check a desktop listener.
    if t['platform']==PLATFORMS.get(sys.platform) and t['platform'] in ('windows','macos','linux'):
        opt['port']=choose_port(base,o.get('port'))
    elif type(opt['port']) is not int:
        raise ValueError('Foreign target needs an explicitly inspected unused listener port')
    manage.validate_options(opt)
    return opt


def native_options(o):
    r=o['roles']['claude']
    return {'expectedIp':r['expectedIp'],'country':r['country'],'iosVersion':o['target']['osVersion'],
            'shadowrocketVersion':o['target']['version'],'directDns':o['privacy']['directResolvers'],
            'preferredPattern':o['policy']['preferredPattern'],'extraClaudeDomains':o['policy'].get('extraClaudeDomains',[]),
            'directCountries':o['policy'].get('directCountries',[]),'directDomains':o['policy'].get('directDomains',[]),
            'rejectAllUdp':o['privacy']['webRTC']=='reject-udp'}


def build_shadowrocket(path):
    o,fixed,normal,texts,hashes,bp=context(path)
    if o['target']['adapter']!='shadowrocket': raise ValueError('Shadowrocket USB requires a Shadowrocket target')
    ns={n['source']+' | '+n['name']:n for n in normal}
    conf,receipt=mobile.render(native_options(o),texts,fixed,ns,list(ns),mobile.read(path))
    receipt.update(inputHashes=hashes,sourceCount=len(o['sources']),privacyMethod=o['privacy']['webRTC'])
    if o['privacy']['webRTC']=='reject-udp':
        receipt['requiresUI']=[x for x in receipt['requiresUI'] if not x.startswith('Enable Disable STUN')]
    return conf,receipt


def prepare(path,output):
    output=Path(output)
    if output.exists(): raise ValueError('Use a new plan directory; do not overwrite prior backups')
    o,fixed,normal,texts,hashes,bp=context(path)
    adapter=o['target']['adapter']
    result={};options=None
    if adapter=='shadowrocket':
        conf,receipt=build_shadowrocket(path)
        result['shadowrocket.conf']=conf
    elif adapter=='surge':
        from surge_adapter import render
        conf=render(o,fixed,normal,texts['baselineFile'])
        result['surge.conf']=conf;receipt={}
    else:
        base=manage.read(bp)
        if not isinstance(base,dict): raise ValueError('Mihomo baseline must be an object')
        options=mihomo_options(o,fixed,normal,base)
        # Keep stale unrelated nodes/providers out of newly compiled policy reachability.
        base=copy.deepcopy(base);base['proxies']=[];base['proxy-providers']={}
        js="const fs=require('fs'),{build}=require(process.argv[1]);const x=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(build(x.base,x.options)));"
        q=subprocess.run(['node','-e',js,str(ROOT/'src/routing.js')],input=json.dumps({'base':base,'options':options}),capture_output=True,text=True,encoding='utf-8',timeout=30)
        if q.returncode: raise ValueError('Mihomo rendering failed; verify options/pattern compatibility')
        result['mihomo.json']=json.loads(q.stdout)
        if adapter=='clash-verge':
            if PLATFORMS.get(sys.platform)!=o['target']['platform']: raise ValueError('Verge deployment settings must be prepared on the target host')
            vd=resolve(path,o['vergeDir'])
            if bp!=(vd/'clash-verge.yaml').resolve(): raise ValueError('Verge baseline must be its current runtime')
            profiles=manage.read(vd/'profiles.yaml');options['baseUid']=profiles['current']
            options.update(controller_options(base));hashes[str(vd/'profiles.yaml')]=sha((vd/'profiles.yaml').read_bytes())
        result['settings.json']=options;receipt={}
    # Candidate generation is not activation or native-engine validation.
    receipt.update(schema=2,adapter=adapter,status='candidate-not-device-verified',fullyVerified=False,
                   manifestSha256=sha(Path(path).read_bytes()),inputHashes=hashes,
                   sourceCount=len(o['sources']),ordinaryNodeCount=len(normal),
                   expectedIp=o['roles']['claude']['expectedIp'],expectedCountry=o['roles']['claude']['country'],
                   vpnOffIsolation=False,snapshotRefresh='reinspect-and-regenerate-no-automatic-role-expansion',
                   privacy={'method':o['privacy']['webRTC'],'dns':'configured-not-observed','webrtc':'pending-native-test'},
                   acceptance={k:'pending' for k in ('native_compile','client_route','ordinary_route','domestic_route','dns_udp_tcp_ipv6','webrtc','fixed_failure','ordinary_failover','proxy_exit','rollback')},
                   replaced=['rules','proxy-groups','DNS policy','node snapshots; native General settings'],networkChanged=False)
    receipt['files']={k:sha((v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode()) for k,v in result.items()}
    for name,data in result.items(): write(output/name,data)
    write(output/'receipt.json',receipt)
    return {'status':receipt['status'],'adapter':adapter,'sourceCount':receipt['sourceCount'],'ordinaryNodeCount':len(normal),'fullyVerified':False,'networkChanged':False}


def check(path,output):
    # No port reallocation or mutation on check. Validate exact inputs and every artifact.
    context(path)
    receipt=load(Path(output)/'receipt.json')
    if sha(Path(path).read_bytes())!=receipt['manifestSha256']: raise ValueError('Manifest changed; prepare a new plan')
    for p,h in receipt['inputHashes'].items():
        if sha(local(p)[1])!=h: raise ValueError('Input changed; prepare a new plan')
    for name,h in receipt['files'].items():
        if Path(name).name!=name: raise ValueError('Invalid candidate path')
        if sha(local(Path(output)/name)[1])!=h: raise ValueError('Candidate changed; do not deploy')
    return {'offlineIntegrity':'pass','fullyVerified':False,'networkChanged':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['discover','draft','inspect','prepare','check','capabilities'])
    p.add_argument('--manifest',type=Path,default=ROOT/'.private/universal.json')
    p.add_argument('--output',type=Path,default=ROOT/'.private/universal-plan')
    p.add_argument('--verge-dir',type=Path)
    p.add_argument('--adapter',choices=list(ADAPTERS))
    p.add_argument('--target',choices=['windows','macos','ios','android','linux'])
    p.add_argument('--source',type=Path,action='append')
    p.add_argument('--baseline',type=Path)
    p.add_argument('--format',choices=['mihomo','shadowrocket','surge'])
    a=p.parse_args()
    if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    try:
        if a.action=='capabilities': r={'adapters':ADAPTERS,'arbitraryClientSupport':False,'nativeMobileVerified':False,'automaticPermission':False}
        elif a.action=='discover':
            r=discover(a.verge_dir);write(a.output/'inventory.json',r)
            r={k:r[k] for k in ('schema','host','dependencies','phone','networkChanged','fullyVerified')}
            r['inventory']='saved privately; inspect roles locally'
        elif a.action=='draft':
            if not a.adapter: raise ValueError('Choose adapter based on actual client/engine, not file extension')
            r=draft(a)
        elif a.action=='inspect':
            if not a.source or not a.format: raise ValueError('inspect requires local --source and explicit native --format')
            r={'sources':[{'index':i,'count':len(parse_nodes(x,a.format))} for i,x in enumerate(a.source)],'secretsPrinted':False}
            write(a.output/'nodes.json',[{'index':i,'nodes':[{'name':k,'type':v['type']} for k,v in parse_nodes(x,a.format).items()]} for i,x in enumerate(a.source)])
        elif a.action=='prepare': r=prepare(a.manifest,a.output)
        else:r=check(a.manifest,a.output)
        print(json.dumps(r,ensure_ascii=False,indent=2));return 0
    except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError):
        # Paths/names/errors from imported YAML/JSON libraries may contain secrets.
        print('Universal preparation stopped. Verify native format, role selections, hashes, versions, DNS and privacy prerequisites; no network changes made.',file=sys.stderr)
        return 1


if __name__=='__main__': sys.exit(main())
