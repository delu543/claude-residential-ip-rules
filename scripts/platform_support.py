"""Platform discovery and bounded local IPC. Never open an unauthenticated TCP API."""
import json
import os
from pathlib import Path
import subprocess
import sys


def require_platform():
    if sys.platform not in ('darwin', 'win32'):
        raise ValueError('Installer supports macOS and Windows; WSL/Linux require separate networking review')


def default_verge_dir():
    if sys.platform == 'win32':
        return Path(os.environ.get('APPDATA', str(Path.home() / 'AppData/Roaming'))) / 'io.github.clash-verge-rev.clash-verge-rev'
    return Path.home() / 'Library/Application Support/io.github.clash-verge-rev.clash-verge-rev'


def powershell(script):
    return subprocess.check_output(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        '[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); $ErrorActionPreference="Stop"; ' + script],
        timeout=30).decode('utf-8-sig').strip()


def process_inventory():
    raw = powershell("@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(Claude|Codex|verge-mihomo.*)\\.exe$' } | Select-Object Name,ExecutablePath) | ConvertTo-Json -Compress")
    rows = json.loads(raw or '[]')
    return rows if isinstance(rows, list) else [rows]


def windows_paths():
    # Only observed executables / existing native CLI files, never all node.exe.
    rows = process_inventory()
    claude = [x['ExecutablePath'] for x in rows if x.get('ExecutablePath') and x['Name'].lower() == 'claude.exe']
    codex = [x['ExecutablePath'] for x in rows if x.get('ExecutablePath') and x['Name'].lower() == 'codex.exe']
    for name, target in [('claude', claude), ('codex', codex)]:
        p = Path.home() / '.local/bin' / (name + '.exe')
        if p.is_file(): target.append(str(p))
    return sorted(set(claude)), sorted(set(codex))


def default_mihomo():
    if sys.platform != 'win32':
        return Path('/Applications/Clash Verge.app/Contents/MacOS/verge-mihomo')
    # inspect/--help should not require PowerShell or a running service.
    for env in ('LOCALAPPDATA', 'ProgramFiles', 'ProgramFiles(x86)'):
        if os.environ.get(env):
            for rel in ('Clash Verge/verge-mihomo.exe', 'Programs/Clash Verge/verge-mihomo.exe'):
                p = Path(os.environ[env]) / rel
                if p.is_file(): return p
    return None


def controller_options(runtime):
    if sys.platform == 'win32':
        pipe = runtime.get('external-controller-pipe')
        if not isinstance(pipe, str) or not pipe.startswith('\\\\.\\pipe\\') or len(pipe) <= 9:
            raise ValueError('No local named-pipe API in actual runtime; enable Verge local service or review version-specific controller')
        return {'apiPipe': pipe, 'apiSocket': None}
    socket = runtime.get('external-controller-unix')
    if not socket or not Path(socket).is_absolute():
        raise ValueError('No absolute local Unix controller in runtime')
    return {'apiSocket': socket}


def ipc_api(pipe, endpoint, method='GET', body=None):
    if not pipe.startswith('\\\\.\\pipe\\') or '\n' in pipe or '\r' in pipe:
        raise ValueError('Only a local Windows named pipe is allowed')
    # Node handles named pipes, HTTP framing/chunking and bounded request timeouts.
    result = subprocess.run(['node', str(Path(__file__).with_name('controller.cjs'))],
        input=json.dumps({'socketPath': pipe, 'path': endpoint, 'method': method, 'body': body}),
        capture_output=True, text=True, encoding='utf-8', timeout=20)
    if result.returncode: raise ValueError('Local controller request failed; check Verge service without exposing API to LAN')
    return json.loads(result.stdout) if result.stdout.strip() else None
