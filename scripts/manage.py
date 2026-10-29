#!/usr/bin/env python3
"""Local-only macOS setup. No subscription credentials are logged or uploaded."""
import argparse
import datetime
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = Path.home() / 'Library/Application Support/io.github.clash-verge-rev.clash-verge-rev'

def read(path):
    raw = Path(path).read_text()
    try:
        return json.loads(raw)
    except ValueError:
        # macOS ships Ruby/Psych. Linux agents may install PyYAML in their own venv.
        try:
            import yaml
            return yaml.safe_load(raw)
        except ImportError:
            return json.loads(subprocess.check_output(['ruby', '-rjson', '-ryaml', '-e',
                'puts JSON.generate(YAML.safe_load(STDIN.read, permitted_classes: [Time, Symbol], aliases: true))'], input=raw.encode(), stderr=subprocess.DEVNULL))

def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.staged')
    # Set permissions on creation, not after private bytes have been written.
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(data.encode() if isinstance(data, str) else data)
    os.replace(temp, path)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(x):
    return json.dumps(x, ensure_ascii=False, indent=2)

def profile_path(base, item):
    p = (base / 'profiles' / item['file']).resolve()
    if p.parent != (base / 'profiles').resolve():
        raise ValueError('Unexpected profile path')
    return p

def api(o, endpoint, method='GET', body=None):
    cmd = ['curl', '-fsS', '--max-time', '15', '--unix-socket', o['apiSocket'],
           '-X', method, 'http://localhost' + endpoint]
    if body is not None:
        cmd += ['-H', 'Content-Type: application/json', '--data-binary', '@-']
    result = subprocess.run(cmd, input=json.dumps(body) if body is not None else None,
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None

def validate_options(o):
    ipaddress.ip_address(o['expectedIp'])
    if not isinstance(o['port'], int) or not 1024 <= o['port'] <= 65535:
        raise ValueError('Invalid dedicated port')
    if not o['claudePaths'] or not o['codexPaths']:
        raise ValueError('Inspect actual app paths first')
    for p in o['claudePaths'] + o['codexPaths']:
        if not p.startswith('/') or any(c in p for c in ',\n\r') or 'REPLACE' in p:
            raise ValueError('Invalid process path')
    p = o['ordinaryProvider']
    url = urllib.parse.urlsplit(p['url'])
    if p['type'] != 'http' or url.scheme not in ('http', 'https') or not url.hostname or url.hostname.endswith('.invalid'):
        raise ValueError('A real ordinary subscription URL is required locally')
    if p.get('proxy', 'DIRECT') != 'DIRECT':
        raise ValueError('Subscription refresh must not borrow the residential group')
    if not o['proxyServerNameservers'] or any('#' in s and not s.endswith('#DIRECT') for s in o['proxyServerNameservers']):
        raise ValueError('Node bootstrap DNS must be independent of proxy groups')
    if o['residential']['type'] in ('direct', 'reject', 'compatible', 'pass'):
        raise ValueError('Residential endpoint must be an actual proxy')

def discover_paths():
    home = Path.home()
    claude, codex = [], []
    for folder in [Path('/Applications'), home / 'Applications', home / 'Desktop']:
        for app in folder.glob('*.app'):
            try:
                info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
                bid = info.get('CFBundleIdentifier', '')
                if bid == 'com.openai.codex':
                    codex.append(str(app) + '/')
                if bid in ('com.anthropic.claudefordesktop', 'com.anthropic.claude') or app.name == 'Claude.app':
                    claude.append(str(app) + '/')
            except (OSError, ValueError):
                continue
    claude += [str(home / '.local/share/claude/versions') + '/',
               str(home / 'Library/Caches/com.anthropic.claudefordesktop.ShipIt') + '/']
    return sorted(set(claude)), sorted(set(codex))

def inspect(base):
    profiles = read(base / 'profiles.yaml')
    print('Current profile:', profiles.get('current'))
    for item in profiles['items']:
        if item.get('type') not in ('remote', 'local'):
            continue
        doc = read(profile_path(base, item))
        print(dump({'uid': item['uid'], 'name': item.get('name'),
                    'nodes': [{'name': p.get('name'), 'type': p.get('type')} for p in doc.get('proxies', [])]}))
    cp, xp = discover_paths()
    print(dump({'claudePaths': cp, 'codexPaths': xp}))

def init_settings(a):
    profiles = read(a.verge_dir / 'profiles.yaml')
    items = {i['uid']: i for i in profiles['items']}
    if a.residential_uid == a.ordinary_uid:
        raise ValueError('Two distinct subscriptions are required')
    res = read(profile_path(a.verge_dir, items[a.residential_uid]))
    candidates = [p for p in res.get('proxies', []) if p.get('name') == a.node]
    if len(candidates) != 1:
        raise ValueError('Select one unambiguous residential node from inspect')
    node = candidates[0]
    o = read(ROOT / 'examples/settings.example.json')
    o['residential'] = {k: node[k] for k in ('name', 'server', 'port', 'type')}
    o['expectedIp'] = a.expected_ip
    o['ordinaryProvider']['url'] = items[a.ordinary_uid]['url']
    o['claudePaths'], o['codexPaths'] = discover_paths()
    # Preserve vendor-specific bootstrap resolvers when already configured.
    runtime = read(a.verge_dir / 'clash-verge.yaml')
    o['proxyServerNameservers'] = runtime.get('dns', {}).get('proxy-server-nameserver') or o['proxyServerNameservers']
    o['residentialUid'] = a.residential_uid
    o['ordinaryUid'] = a.ordinary_uid
    validate_options(o)
    if a.settings.exists():
        raise ValueError('Settings already exist; review them without overwriting')
    save(a.settings, dump(o))
    print('Private settings created. Inspect ordinary subscription identity, US pattern and DNS before prepare.')

def prepare(a):
    o = read(a.settings); validate_options(o)
    profiles = read(a.verge_dir / 'profiles.yaml')
    items = {i['uid']: i for i in profiles['items']}
    if profiles['current'] != o['residentialUid']:
        raise ValueError('Select the residential base profile in Clash Verge first')
    res = items[o['residentialUid']]
    script_item = items[res['option']['script']]
    target = profile_path(a.verge_dir, script_item)
    runtime = a.verge_dir / 'clash-verge.yaml'
    raw = read(profile_path(a.verge_dir, res))
    base = read(runtime)
    base['proxies'] = raw.get('proxies', [])
    script = (ROOT / 'src/routing.js').read_text() + '\nconst OPTIONS = ' + json.dumps(o, ensure_ascii=False) + ';\nfunction main(config) { return build(config, OPTIONS); }\n'
    a.plan.mkdir(parents=True, exist_ok=False); a.plan.chmod(0o700)
    save(a.plan / 'routing.js', script)
    js = "const fs=require('fs'),vm=require('vm');let c={};vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);process.stdout.write(JSON.stringify(c.main(JSON.parse(fs.readFileSync(0,'utf8')))));"
    result = subprocess.run(['node', '-e', js, str(a.plan / 'routing.js')], input=json.dumps(base), text=True, capture_output=True, check=True)
    candidate = json.loads(result.stdout)
    fixed = next(p for p in candidate['proxies'] if p['name'] == '住宅固定节点')
    if fixed['type'] == 'reject':
        raise ValueError('Pinned residential node is absent; no deployment prepared')
    save(a.plan / 'runtime.json', dump(candidate))
    q = subprocess.run([str(a.mihomo), '-t', '-d', str(a.verge_dir), '-f', str(a.plan / 'runtime.json')], capture_output=True)
    save(a.plan / 'validation.log', q.stdout + q.stderr)
    if q.returncode:
        raise ValueError('Mihomo rejected candidate; inspect private validation.log')
    targets = [target, runtime]
    for i, p in enumerate(targets):
        save(a.plan / f'before-{i}', p.read_bytes())
    save(a.plan / 'settings.json', dump(o))
    save(a.plan / 'plan.json', dump({'targets': list(map(str, targets)), 'before': [digest(p) for p in targets],
        'candidate': [digest(a.plan / n) for n in ('routing.js', 'runtime.json')],
        'profileIndex': str(a.verge_dir / 'profiles.yaml'), 'profileHash': digest(a.verge_dir / 'profiles.yaml'),
        'created': datetime.datetime.now().astimezone().isoformat()}))
    print('Prepared and syntax checked; no running configuration changed.')
    print('Replaces selected profile rules/groups/DNS policy; preserves TUN and other listener settings.')
    print('Claude + ChatGPT: fixed residential. Codex + ordinary: ordinary US, then other ordinary regions.')

def preflight(o):
    if api(o, '/configs')['mode'] != 'rule':
        raise ValueError('Core is not in rule mode')
    groups = api(o, '/proxies')['proxies']
    for name in ['Claude 固定出口', 'ChatGPT 住宅出口']:
        g = groups.get(name, {})
        if g.get('all') != ['住宅固定节点'] or g.get('now') != '住宅固定节点':
            raise ValueError('Fixed group was changed')
    out = subprocess.check_output(['curl', '-fsS', '--max-time', '15', '--connect-timeout', '5',
        '--noproxy', '', '--proxy', f"http://127.0.0.1:{o['port']}",
        'https://www.cloudflare.com/cdn-cgi/trace'], stderr=subprocess.DEVNULL).decode()
    trace = dict(line.split('=', 1) for line in out.splitlines() if '=' in line)
    if trace.get('ip') != o['expectedIp'] or trace.get('loc') != o['country']:
        raise ValueError('Public egress differs from the locally approved IP/country')
    print('Fixed proxy preflight passed; this is not a continuous OS firewall.')

def apply(a):
    p = read(a.plan / 'plan.json'); o = read(a.plan / 'settings.json')
    if digest(p['profileIndex']) != p['profileHash'] or [digest(t) for t in p['targets']] != p['before']:
        raise ValueError('Configuration changed since prepare; prepare a fresh plan')
    sources = [a.plan / 'routing.js', a.plan / 'runtime.json']
    if [digest(s) for s in sources] != p['candidate']:
        raise ValueError('Candidate changed after validation')
    try:
        for src, dst in zip(sources, p['targets']):
            save(dst, src.read_bytes())
        api(o, '/configs?force=false', 'PUT', {'path': p['targets'][1]})
        preflight(o)
    except Exception:
        for i, dst in enumerate(p['targets']):
            save(dst, (a.plan / f'before-{i}').read_bytes())
        api(o, '/configs?force=false', 'PUT', {'path': p['targets'][1]})
        raise ValueError('Apply verification failed; restored previous configuration') from None
    save(a.plan / 'applied.json', dump({'hashes': [digest(t) for t in p['targets']]}))
    print('Applied without restarting core. Complete client UI and connection-chain verification next.')

def rollback(a):
    p = read(a.plan / 'plan.json'); applied = read(a.plan / 'applied.json')
    if [digest(t) for t in p['targets']] != applied['hashes']:
        raise ValueError('Later edits detected; refuse to overwrite them')
    for i, dst in enumerate(p['targets']):
        if digest(a.plan / f'before-{i}') != p['before'][i]:
            raise ValueError('Backup integrity check failed')
    for i, dst in enumerate(p['targets']):
        save(dst, (a.plan / f'before-{i}').read_bytes())
    api(read(a.plan / 'settings.json'), '/configs?force=false', 'PUT', {'path': p['targets'][1]})
    print('Previous script and runtime restored. Check client connectivity.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inspect', 'init', 'prepare', 'apply', 'rollback', 'check'])
    parser.add_argument('--verge-dir', type=Path, default=DEFAULT_DIR)
    parser.add_argument('--settings', type=Path, default=ROOT / '.private/settings.json')
    parser.add_argument('--plan', type=Path, default=ROOT / '.private/plan')
    parser.add_argument('--mihomo', type=Path, default=Path('/Applications/Clash Verge.app/Contents/MacOS/verge-mihomo'))
    parser.add_argument('--residential-uid'); parser.add_argument('--ordinary-uid')
    parser.add_argument('--node'); parser.add_argument('--expected-ip')
    a = parser.parse_args()
    a.verge_dir = a.verge_dir.resolve(); a.plan = a.plan.resolve()
    os.umask(0o077)
    if a.command == 'inspect': inspect(a.verge_dir)
    elif a.command == 'init': init_settings(a)
    elif a.command == 'prepare': prepare(a)
    elif a.command == 'apply': apply(a)
    elif a.command == 'rollback': rollback(a)
    else: preflight(read(a.settings))

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        # Exceptions from subprocesses may embed sensitive args; do not print them.
        print('Stopped: ' + (str(e) if isinstance(e, ValueError) else type(e).__name__), file=sys.stderr)
        sys.exit(1)
