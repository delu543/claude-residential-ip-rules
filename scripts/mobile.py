#!/usr/bin/env python3
"""Offline Shadowrocket adapter. Never operates the phone or fetches subscriptions.

Inputs are local native Shadowrocket exports, NOT Clash YAML or a subscription URL.
Only reviewed node transports are accepted. Unsupported data stops generation.
"""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / 'src/policy.json').read_text(encoding='utf-8'))
FIXED, CLAUDE, NORMAL = 'CR_RESIDENTIAL', 'CR_CLAUDE', 'CR_NORMAL'
PROTOCOLS = {'ss', 'vmess', 'vless', 'trojan', 'hysteria2'}
# Preserve native parameters; never translate a new protocol by guessing.
PARAMS = {'password', 'method', 'obfs', 'obfs-host', 'obfs-uri', 'obfsparam',
          'tls', 'peer', 'sni', 'alpn', 'tfo', 'udp', 'alterid', 'auth',
          'public-key', 'short-id', 'pbk', 'sid', 'flow', 'fingerprint',
          'allowinsecure', 'skip-cert-verify', 'skip-common-name-verify'}
INSECURE = {'allowinsecure', 'skip-cert-verify', 'skip-common-name-verify'}
RULE_TYPES = {'DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD', 'IP-CIDR', 'IP-CIDR6', 'GEOIP'}
ACCEPTANCE = ['import_and_compile', 'claude_route', 'ordinary_route', 'domestic_route',
              'residential_failure', 'ordinary_failure_and_recovery', 'dns', 'webrtc',
              'wifi_cellular_ipv6', 'rollback']


def digest(data):
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def read(path):
    return Path(path).read_text(encoding='utf-8-sig')


def save_new(path, text):
    path = Path(path)
    if '.private' not in path.resolve().parts:
        raise ValueError('Private output must be inside a .private directory')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Never replace a previous export, receipt, backup, or symlink.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(text)


def token(value):
    if not isinstance(value, str) or not value.strip() or any(c in value for c in '\r\n,=[]#;'):
        raise ValueError('Invalid native config token (delimiter/control character)')
    if any(ord(c) < 32 for c in value):
        raise ValueError('Control character in native config token')
    return value.strip()


def domain(value):
    value = token(value).lower().rstrip('.')
    if not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}', value):
        raise ValueError('Use an ASCII DNS name, not a URL, wildcard or IP')
    return value


def sections(text):
    result, section = {}, None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(('#', ';')):
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1]
            if section in result:
                raise ValueError('Duplicate section in native export')
            result[section] = []
        elif section is None:
            raise ValueError('Expected a native Shadowrocket .conf export')
        else:
            result[section].append(line)
    return result


def nodes(text):
    result = {}
    for line in sections(text).get('Proxy', []):
        name, sep, definition = line.partition('=')
        if not sep:
            raise ValueError('Invalid native node declaration')
        name = token(name)
        if name in result:
            raise ValueError('Duplicate node name in export')
        parts = [p.strip() for p in definition.split(',')]
        if len(parts) < 4 or parts[0].lower() not in PROTOCOLS:
            raise ValueError('Unsupported node protocol/format: needs reviewed native adapter')
        kind, host = parts[0].lower(), parts[1]
        try:
            ipaddress.ip_address(host)
        except ValueError:
            domain(host)
        if not parts[2].isdigit() or not 1 <= int(parts[2]) <= 65535:
            raise ValueError('Invalid native node port')
        attrs = {}
        for part in parts[3:]:
            key, sep, value = part.partition('=')
            if not sep or key.lower() not in PARAMS or key.lower() in attrs:
                raise ValueError('Unsupported or duplicate transport option; do not silently discard it')
            if not value or any(c in value for c in '\r\n,[]#;') or any(ord(c) < 32 for c in value):
                raise ValueError('Invalid native transport value')
            if key.lower() in INSECURE and value.lower() not in ('0', 'false'):
                raise ValueError('TLS verification must remain enabled')
            attrs[key.lower()] = value
        if not attrs.get('password', attrs.get('auth')):
            raise ValueError('Missing native node authentication')
        result[name] = {'definition': ', '.join(parts), 'endpoint': (host.lower(), int(parts[2])), 'type': kind}
    if not result:
        raise ValueError('No [Proxy] nodes. Export/share the actual native nodes first; rules-only exports are insufficient')
    return result


def baseline_rules(text, protected):
    """Retain the user's audited domestic/foreign classification, not remote code."""
    parsed = sections(text)
    # A rewrite/script/host/PAC could change the meaning of rules. Require an
    # explicit clean baseline rather than quietly dropping existing abilities.
    allowed = {'General', 'Rule', 'Proxy', 'Proxy Group', 'Host'}
    if any(lines for key, lines in parsed.items() if key not in allowed):
        raise ValueError('Baseline has Host/rewrite/script/module sections: review separately')
    if any(re.sub(r'\s+', '', line) != 'localhost=127.0.0.1' for line in parsed.get('Host', [])):
        raise ValueError('Custom Host mappings need separate review')
    for line in parsed.get('General', []):
        if line.split('=', 1)[0].strip() in {'include', 'update-url'}:
            raise ValueError('Baseline contains external configuration; export the reviewed compiled rules')
    result = []
    for line in parsed.get('Rule', []):
        p = [s.strip() for s in line.split(',')]
        if p[0] == 'FINAL':
            if len(p) != 2 or p[1] not in ('PROXY', 'DIRECT'):
                raise ValueError('Unknown baseline final policy')
            continue
        if len(p) not in (3, 4) or p[0] not in RULE_TYPES or p[2] not in ('DIRECT', 'PROXY'):
            raise ValueError('Unsupported baseline rule/group/ad filter: review instead of dropping it')
        if len(p) == 4 and p[3] != 'no-resolve':
            raise ValueError('Unsupported baseline rule option')
        if p[0] in ('DOMAIN', 'DOMAIN-SUFFIX'):
            p[1] = domain(p[1])
            if any(p[1] == d or p[1].endswith('.' + d) for d in protected):
                continue  # The protected rules at the top own these targets.
        elif p[0] == 'DOMAIN-KEYWORD':
            token(p[1])
        elif p[0].startswith('IP-CIDR'):
            ipaddress.ip_network(p[1], strict=False)
        elif not re.fullmatch(r'[A-Z]{2}|LAN', p[1]):
            raise ValueError('Invalid country code in baseline')
        p[2] = 'DIRECT' if p[2] == 'DIRECT' else NORMAL
        if p[0].startswith('IP-') or p[0] == 'GEOIP':
            p = p[:3] + ['no-resolve']
        result.append(','.join(p))
    if not result:
        raise ValueError('Need local reviewed domestic/foreign baseline rules, e.g. exported default.conf')
    return result


def resolve(settings, value):
    if not isinstance(value, str) or not value:
        raise ValueError('Missing local input path')
    p = Path(value).expanduser()
    return p if p.is_absolute() else settings.parent / p


def build(settings):
    settings = Path(settings).resolve()
    o = json.loads(read(settings))
    if o.get('_template') or o.get('schema') != 1:
        raise ValueError('Initialize local settings; template cannot be used')
    paths = {k: resolve(settings, o.get(k)) for k in ('residentialFile', 'ordinaryFile', 'baselineFile')}
    source = {k: read(v) for k, v in paths.items()}
    if paths['residentialFile'].resolve() == paths['ordinaryFile'].resolve() or source['residentialFile'] == source['ordinaryFile']:
        raise ValueError('Residential and ordinary must be separate, explicitly identified sources')
    r, n = nodes(source['residentialFile']), nodes(source['ordinaryFile'])
    if o.get('residentialNode') not in r:
        raise ValueError('Fixed node missing/renamed: stop, never choose another node')
    fixed = r[o['residentialNode']]
    names = o.get('ordinaryNodes')
    if not isinstance(names, list) or not names or len(set(names)) != len(names) or any(x not in n for x in names):
        raise ValueError('Choose unique actual ordinary nodes from the ordinary source')
    # Refuse accidental mixed subscriptions, including renamed copies.
    res_endpoints = {v['endpoint'] for v in r.values()}
    if any(n[x]['endpoint'] in res_endpoints for x in names):
        raise ValueError('Ordinary source overlaps residential endpoints; confirm source identities')
    ipaddress.ip_address(o.get('expectedIp'))
    if not re.fullmatch('[A-Z]{2}', o.get('country', '')):
        raise ValueError('Expected exit country must be explicit')
    for k in ('iosVersion', 'shadowrocketVersion'):
        if not isinstance(o.get(k), str) or not o[k].strip():
            raise ValueError('Record actual target device versions; never infer latest')
    preferred = re.compile(o.get('preferredPattern', r'(?i)\bUS\b|USA|United States|美国|美國|🇺🇸'))
    ordered = [x for x in names if preferred.search(x)] + [x for x in names if not preferred.search(x)]
    dns = o.get('directDns')
    if not isinstance(dns, list) or not dns:
        raise ValueError('Provide working encrypted DNS for domestic/bootstrap resolution')
    for value in dns:
        u = urlsplit(value)
        if u.scheme != 'https' or u.username or u.password or u.query or u.fragment or any(c in value for c in ',\r\n '):
            raise ValueError('Use HTTPS DNS without credentials/query/fragment')
        try:
            ipaddress.ip_address(u.hostname)
        except ValueError:
            raise ValueError('Use literal-IP encrypted DNS to avoid a system DNS bootstrap dependency') from None
        if not u.path:
            raise ValueError('Missing DoH path')
    extra = o.get('extraClaudeDomains', [])
    if not isinstance(extra, list):
        raise ValueError('extraClaudeDomains must be a list')
    protected = list(dict.fromkeys(POLICY['claudeDomains'] + [domain(d) for d in extra]))
    ordinary_domains = POLICY['openaiDomains']
    if any(d == x or d.endswith('.' + x) or x.endswith('.' + d) for d in protected for x in ordinary_domains):
        raise ValueError('Do not classify ordinary OpenAI traffic as Claude')
    base = baseline_rules(source['baselineFile'], protected)
    dns_text = ', '.join(d + '#no-h3' for d in dns)
    output = ['# Generated locally. Private nodes inside. Import as a NEW configuration.',
              '# VPN-active domain routing only; not per-app or VPN-off isolation.', '[General]',
              'bypass-system = false', 'ipv6 = false', 'prefer-ipv6 = false',
              'dns-server = ' + dns_text, 'direct-dns-server = ' + dns_text,
              'fallback-dns-server = ' + dns_text, 'dns-fallback-system = false',
              'dns-direct-system = false', 'dns-direct-fallback-proxy = false',
              'always-ip-address = false', 'hijack-dns = :53',
              'udp-policy-not-supported-behaviour = REJECT', '', '[Proxy]',
              FIXED + ' = ' + fixed['definition']]
    aliases = [f'CR_NORMAL_{i:03}' for i in range(1, len(ordered) + 1)]
    output += [alias + ' = ' + n[name]['definition'] for alias, name in zip(aliases, ordered)]
    output += ['', '[Proxy Group]', CLAUDE + ' = select,' + FIXED,
               NORMAL + ' = fallback,' + ','.join(aliases) + ',url=https://www.gstatic.com/generate_204,interval=600,timeout=5',
               '', '[Rule]']
    # Reject QUIC/other UDP for known Claude destinations. Never fall back to direct UDP.
    output += [f'AND,((PROTOCOL,UDP),(DOMAIN-SUFFIX,{d})),REJECT' for d in protected]
    output += [f'DOMAIN-SUFFIX,{d},{CLAUDE}' for d in protected]
    output += [f'DOMAIN-SUFFIX,{d},{NORMAL}' for d in ordinary_domains]
    output += ['DOMAIN,localhost,DIRECT', 'DOMAIN-SUFFIX,local,DIRECT',
               'IP-CIDR,127.0.0.0/8,DIRECT,no-resolve', 'IP-CIDR,10.0.0.0/8,DIRECT,no-resolve',
               'IP-CIDR,172.16.0.0/12,DIRECT,no-resolve', 'IP-CIDR,192.168.0.0/16,DIRECT,no-resolve']
    output += base + ['FINAL,' + NORMAL, '', '[Host]', 'localhost = 127.0.0.1', '']
    conf = '\n'.join(output)
    report = {'schema': 1, 'status': 'candidate-not-phone-verified', 'configSha256': digest(conf),
              'settingsSha256': digest(read(settings)), 'sourceHashes': {k: digest(v) for k,v in source.items()},
              'scope': 'VPN-active known destination domains; no per-app or VPN-off guarantee',
              'target': {k:o[k] for k in ('iosVersion','shadowrocketVersion')},
              'ordinaryNodeCount': len(aliases), 'preferredNodeCount': sum(bool(preferred.search(x)) for x in names),
              'expectedIp': o['expectedIp'], 'expectedCountry': o['country'],
              'requiresUI': ['Config routing mode', 'Disable global fallback and scene/easy overrides',
                             'Enable Disable STUN; no stun-response-ip override', 'Compile/import and verify both routes'],
              'phoneAcceptance': {k: {'status': 'pending', 'evidence': None} for k in ACCEPTANCE},
              'fullyVerified': False, 'vpnOffIsolation': False,
              'notes': ['Native export credentials are private; no subscription converter used',
                        'Node snapshots do not auto-update subscriptions; regenerate after source changes',
                        'IP-only/unknown/shared-CDN requests need phone logs and explicit reviewed rules',
                        'Ordinary fallback ordering and all-dead behavior require native engine verification']}
    return conf, report


def prepare(settings, output):
    conf, report = build(settings)
    output = Path(output)
    if output.exists():
        raise ValueError('Use a new output directory; previous bundles are preserved')
    save_new(output / 'shadowrocket.conf', conf)
    save_new(output / 'receipt.json', json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


def check(settings, output):
    conf, current = build(settings)
    old = json.loads(read(Path(output) / 'receipt.json'))
    if read(Path(output) / 'shadowrocket.conf') != conf or any(old[k] != current[k] for k in ('settingsSha256','sourceHashes','configSha256')):
        raise ValueError('Candidate or inputs changed; prepare a new bundle, do not reuse acceptance')
    return {'offlineIntegrity': 'pass', 'phoneVerified': False, 'vpnOffIsolation': False}


def init(a):
    for key in ('residential_file', 'ordinary_file', 'baseline_file', 'node', 'expected_ip', 'ios_version', 'shadowrocket_version', 'dns'):
        if not getattr(a, key, None):
            raise ValueError('init requires explicit source roles, node, expected IP, actual versions and DNS')
    ordinary = nodes(read(a.ordinary_file))
    o = {'schema': 1, 'residentialFile': str(a.residential_file.resolve()),
         'ordinaryFile': str(a.ordinary_file.resolve()), 'baselineFile': str(a.baseline_file.resolve()),
         'residentialNode': a.node, 'ordinaryNodes': list(ordinary), 'expectedIp': a.expected_ip,
         'country': a.country, 'iosVersion': a.ios_version, 'shadowrocketVersion': a.shadowrocket_version,
         'directDns': a.dns, 'extraClaudeDomains': []}
    # Validation happens before generating an importable bundle. Settings alone
    # do not operate the phone; no files or subscriptions are fetched.
    save_new(a.settings, json.dumps(o, ensure_ascii=False, indent=2) + '\n')
    return {'status': 'settings-created-review-locally', 'ordinaryNodeCount':len(ordinary)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['capabilities', 'inspect', 'init', 'prepare', 'check'])
    p.add_argument('--file', type=Path)
    p.add_argument('--settings', type=Path, default=Path('.private/mobile-settings.json'))
    p.add_argument('--output', type=Path, default=Path('.private/mobile-plan'))
    p.add_argument('--residential-file', type=Path)
    p.add_argument('--ordinary-file', type=Path)
    p.add_argument('--baseline-file', type=Path)
    p.add_argument('--node')
    p.add_argument('--expected-ip')
    p.add_argument('--country', default='US')
    p.add_argument('--ios-version')
    p.add_argument('--shadowrocket-version')
    p.add_argument('--dns', action='append')
    a = p.parse_args()
    try:
        if a.action == 'capabilities':
            result = {'offlineGenerator':True, 'phoneReadWriteAdapter':False,
                      'automaticOSPermission':False, 'nativeEngineVerified':False,
                      'next':'Authorized local native exports required; no unattended phone installation claim'}
        elif a.action == 'init':
            result = init(a)
        elif a.action == 'inspect':
            if not a.file:
                p.error('inspect requires --file')
            data = nodes(read(a.file))
            result = {'count':len(data), 'nodes':[{'name':k,'type':v['type']} for k,v in data.items()]}
        elif a.action == 'prepare':
            r = prepare(a.settings, a.output)
            result = {k:r[k] for k in ('status','ordinaryNodeCount','preferredNodeCount','fullyVerified')}
        else:
            result = check(a.settings, a.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, TypeError, KeyError) as exc:
        # Deliberately no source text, URL, credential, or exception traceback.
        print('Mobile preparation stopped: ' + (str(exc) if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError) else type(exc).__name__), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
