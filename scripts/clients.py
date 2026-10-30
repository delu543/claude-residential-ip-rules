#!/usr/bin/env python3
"""Configure only recognized Claude settings; preserve unrelated fields."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from manage import ROOT, read, save, dump, digest, preflight
from platform_support import require_platform, process_inventory

def proxy_env(o):
    url = f"http://127.0.0.1:{o['port']}"
    return {k: url for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy')} | {'NO_PROXY': '', 'no_proxy': ''}

def check_code(o, home):
    path = home / '.claude/settings.json'
    env = read(path).get('env', {}) if path.is_file() else {}
    return isinstance(env, dict) and all(env.get(k) == v for k,v in proxy_env(o).items())

def targets(o, home, code_only=False):
    if code_only:
        code = home / ".claude/settings.json"
        c = read(code) if code.exists() else {}
        c["env"] = {**c.get("env", {}), **proxy_env(o)}
        return [(code, c)]
    lib = home / 'Library/Application Support/Claude-3p/configLibrary'
    meta = read(lib / '_meta.json')
    ident = meta['appliedId']
    if not isinstance(ident, str) or '/' in ident or '..' in ident:
        raise ValueError('Unknown desktop configuration identity')
    desktop = lib / (ident + '.json')
    d = read(desktop)
    if not isinstance(d, dict):
        raise ValueError('Unknown desktop configuration format')
    d['egressProxyUrl'] = f"http://127.0.0.1:{o['port']}"
    d.pop('egressProxyPacUrl', None)
    code = home / '.claude/settings.json'
    c = read(code) if code.exists() else {}
    c['env'] = {**c.get('env', {}), **proxy_env(o)}
    return [(desktop, d), (code, c)]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'apply', 'check', 'rollback', 'code'])
    parser.add_argument('--settings', type=Path, default=ROOT / '.private/settings.json')
    parser.add_argument('--backup', type=Path, default=ROOT / '.private/clients')
    parser.add_argument('--binary', default=str(Path.home() / ('.local/bin/claude.exe' if sys.platform == 'win32' else '.local/bin/claude')))
    parser.add_argument('--code-only', action='store_true', help='Configure Code independently of Desktop format')
    a, rest = parser.parse_known_args()
    require_platform()
    os.umask(0o077)
    o = read(a.settings)
    if a.command == 'code':
        preflight(o)
        if sys.platform == 'win32' and (not Path(a.binary).is_file() or Path(a.binary).suffix.lower() != '.exe'):
            raise ValueError('Use an existing native Windows Claude executable, not a shell wrapper or WSL binary')
        env = dict(os.environ); env.update(proxy_env(o))
        argv = [a.binary] + (rest[1:] if rest[:1] == ['--'] else rest)
        if sys.platform == 'win32':
            sys.exit(subprocess.call(argv, env=env))
        os.execvpe(a.binary, argv, env)
    if rest:
        raise ValueError('Unexpected arguments')
    if a.command == 'check':
        if not a.code_only:
            raise ValueError('Use check --code-only; Desktop has a separate platform policy check')
        ok = check_code(o, Path.home())
        print(json.dumps({'configured':ok, 'clientBehaviorVerified':False}))
        if not ok: raise ValueError('Claude Code fixed proxy environment is missing or changed')
        return
    if a.command in ('plan', 'apply'):
        # Unknown desktop builds stop here. Do not fabricate a config file path.
        if sys.platform == 'win32' and not a.code_only:
            raise ValueError('Use windows_desktop.py for Desktop and clients.py --code-only for native Code')
        changes = targets(o, Path.home(), a.code_only)
        if a.command == 'plan':
            print('Recognized desktop proxy settings and Claude Code env settings; other keys preserved.')
            print('Quit Claude normally before apply; this tool does not terminate processes.')
            return
        preflight(o)
        ps = ('\n'.join(x.get('ExecutablePath') or x['Name'] for x in process_inventory()) if sys.platform == 'win32'
              else subprocess.check_output(['ps', '-axo', 'command=']).decode())
        if sys.platform == 'win32' and any('claude' in line.lower() for line in ps.splitlines()):
            raise ValueError('Claude is running; save work and exit before changing client settings')
        if any('/Claude.app/Contents/MacOS/' in line for line in ps.splitlines()):
            raise ValueError('Claude is running; save work and quit before client settings change')
        a.backup.mkdir(parents=True, exist_ok=False)
        receipt = []
        for i, (path, content) in enumerate(changes):
            existed = path.exists()
            before = path.read_bytes() if existed else b'{}\n'
            save(a.backup / str(i), before)
            receipt.append({'path': str(path), 'existed': existed,
                'beforeHash': digest(a.backup / str(i)), 'afterHash': None})
        save(a.backup / 'receipt.json', dump(receipt))
        try:
            for i, (path, content) in enumerate(changes):
                save(path, dump(content)); receipt[i]['afterHash'] = digest(path)
                save(a.backup / 'receipt.json', dump(receipt))
        except Exception:
            for i, (path, _) in enumerate(changes):
                save(path, (a.backup / str(i)).read_bytes())
            raise
        print('Client settings saved. Open Claude normally; verify UI and live route before acceptance.')
    else:
        rows = read(a.backup / 'receipt.json')
        for i, row in enumerate(rows):
            if digest(row['path']) != row['afterHash'] or digest(a.backup / str(i)) != row['beforeHash']:
                raise ValueError('Client settings/backup changed; refusing overwrite')
        for i, row in enumerate(rows):
            save(row['path'], (a.backup / str(i)).read_bytes())
        print('Client keys restored. A previously absent settings.json is retained as an empty object.')

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('Stopped: ' + (str(e) if isinstance(e, ValueError) else type(e).__name__) +
              '. Unknown desktop builds need version-specific setup; see docs/CLIENTS.md.', file=sys.stderr)
        sys.exit(1)
