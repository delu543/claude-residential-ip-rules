"""Conservative native Surge profile adapter, not a Shadowrocket converter.
Original implementation from documented syntax; native device acceptance pending.
"""
import ipaddress
import re
from urllib.parse import urlsplit
import mobile

KINDS={'http','https','socks5','socks5-tls','ss','trojan'}
PARAMS={'username','password','encrypt-method','sni','skip-cert-verify','tfo','udp-relay','obfs','obfs-host','obfs-uri','ws','ws-path','ws-headers','always-use-connect'}


def nodes(text):
    result={}
    for line in mobile.sections(text).get('Proxy',[]):
        name,sep,definition=line.partition('=');name=mobile.token(name)
        if not sep or name in result: raise ValueError('Duplicate or malformed native Surge node')
        p=[x.strip() for x in definition.split(',')]
        if len(p)<3 or p[0] not in KINDS: raise ValueError('Surge adapter does not support this native protocol')
        try: ipaddress.ip_address(p[1])
        except ValueError: mobile.domain(p[1])
        if not p[2].isdigit() or not 1<=int(p[2])<=65535: raise ValueError('Invalid Surge node port')
        attrs={};positional=[]
        for part in p[3:]:
            if not part or any(ord(c)<32 or c in '#;[]' for c in part): raise ValueError('Unsupported native Surge value')
            key,eq,value=part.partition('=')
            if not eq:
                if attrs or p[0] not in {'http','https','socks5','socks5-tls'}: raise ValueError('Unsupported positional credentials')
                positional.append(part);continue
            if key not in PARAMS or key in attrs or not value: raise ValueError('Unsupported native Surge option; preserve it for separate review')
            if key=='skip-cert-verify' and value.lower()!='false': raise ValueError('TLS verification must remain enabled')
            attrs[key]=value
        if len(positional) not in (0,2): raise ValueError('Incomplete positional credentials')
        if positional and ('username' in attrs or 'password' in attrs): raise ValueError('Ambiguous credentials')
        if p[0] in {'ss','trojan'} and not attrs.get('password'): raise ValueError('Missing native credentials')
        if p[0]=='ss' and not attrs.get('encrypt-method'): raise ValueError('Surge uses encrypt-method; do not translate Shadowrocket options')
        result[name]={'definition':', '.join(p),'endpoint':(p[1].lower().rstrip('.'),int(p[2])),'type':p[0]}
    if not result: raise ValueError('Need a native Surge export containing actual nodes')
    return result


def render(o,fixed,normal,baseline):
    protected=list(dict.fromkeys(mobile.POLICY['claudeDomains']+o['policy'].get('extraClaudeDomains',[])))
    rules=mobile.baseline_rules(baseline,protected)
    privacy=o['privacy'];dns=privacy['directResolvers']
    # Literal-IP DoH avoids bootstrap lookups. Traditional servers are explicit,
    # used by Surge for connectivity tests, not ordinary domain queries with DoH.
    ips=list(dict.fromkeys(urlsplit(x).hostname for x in dns))
    pref=re.compile(o['policy']['preferredPattern'])
    normal=sorted(normal,key=lambda n:not bool(pref.search(n['name'])))
    aliases=[f'CR_NORMAL_{i:03}' for i in range(1,len(normal)+1)]
    lines=['# Private candidate. Import as a NEW profile; no device validation yet.',
           '[General]','ipv6 = false','dns-server = '+', '.join(ips),
           'encrypted-dns-server = '+', '.join(dns),'encrypted-dns-skip-cert-verification = false',
           'encrypted-dns-follow-outbound-mode = false','hijack-dns = *:53',
           '', '[Proxy]', mobile.FIXED+' = '+fixed['definition']]
    lines += [alias+' = '+n['definition'] for alias,n in zip(aliases,normal)]
    lines += ['', '[Proxy Group]',mobile.CLAUDE+' = select,'+mobile.FIXED,
              (mobile.NORMAL+' = fallback,'+','.join(aliases)+',interval=600') if aliases else mobile.NORMAL+' = select,REJECT',
              '', '[Rule]']
    if privacy['webRTC']=='client-stun': lines+=['PROTOCOL,STUN,REJECT']
    if privacy['webRTC']=='reject-udp': lines+=['PROTOCOL,UDP,REJECT']
    lines += [f'AND,((PROTOCOL,UDP),(DOMAIN-SUFFIX,{d})),REJECT' for d in protected]
    lines += [f'DOMAIN-SUFFIX,{d},{mobile.CLAUDE}' for d in protected]
    lines += [f'DOMAIN-SUFFIX,{d},{mobile.NORMAL}' for d in mobile.POLICY['openaiDomains']]
    lines += ['DOMAIN,localhost,DIRECT','DOMAIN-SUFFIX,local,DIRECT',
              'IP-CIDR,127.0.0.0/8,DIRECT,no-resolve','IP-CIDR,10.0.0.0/8,DIRECT,no-resolve',
              'IP-CIDR,172.16.0.0/12,DIRECT,no-resolve','IP-CIDR,192.168.0.0/16,DIRECT,no-resolve']
    lines += [f'DOMAIN-SUFFIX,{d},DIRECT' for d in o['policy'].get('directDomains',[])]
    lines += [f'GEOIP,{c},DIRECT,no-resolve' for c in o['policy'].get('directCountries',[])]
    lines += rules+['FINAL,'+mobile.NORMAL,'']
    return '\n'.join(lines)
