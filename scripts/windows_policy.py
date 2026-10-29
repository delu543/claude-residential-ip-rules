"""Small transactional HKCU REG_SZ writer. Machine policies are never overwritten."""
import json
import os
from pathlib import Path
import sys


def registry():
    if sys.platform != 'win32': raise ValueError('Windows registry operation requires native Windows Python')
    import winreg
    return winreg


def snapshot(path, names, machine=False):
    w = registry(); result = {}
    try:
        with w.OpenKey(w.HKEY_LOCAL_MACHINE if machine else w.HKEY_CURRENT_USER, path, 0, w.KEY_READ | w.KEY_WOW64_64KEY) as key:
            for name in names:
                try:
                    value, kind = w.QueryValueEx(key, name)
                    if kind != w.REG_SZ: raise ValueError('Existing policy has unsupported type; inspect without overwriting')
                    result[name] = value
                except FileNotFoundError: result[name] = None
    except FileNotFoundError: result = dict.fromkeys(names)
    return result


def machine_present(path):
    w = registry()
    try:
        with w.OpenKey(w.HKEY_LOCAL_MACHINE, path, 0, w.KEY_READ | w.KEY_WOW64_64KEY) as key:
            return w.QueryInfoKey(key)[1] > 0
    except FileNotFoundError: return False


def write(path, values):
    w = registry()
    with w.CreateKeyEx(w.HKEY_CURRENT_USER, path, 0, w.KEY_SET_VALUE | w.KEY_WOW64_64KEY) as key:
        for name, value in values.items():
            if value is None:
                try: w.DeleteValue(key, name)
                except FileNotFoundError: pass
            else: w.SetValueEx(key, name, 0, w.REG_SZ, value)


def apply(path, values, backup):
    if machine_present(path): raise ValueError('Machine policy exists and may override HKCU; stop for administrator review')
    before = snapshot(path, values)
    backup = Path(backup); backup.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump({'path': path, 'before': before, 'after': values}, f, ensure_ascii=False)
    try:
        write(path, values)
        if snapshot(path, values) != values: raise ValueError('Registry readback failed')
    except Exception:
        write(path, before)
        raise


def rollback(backup):
    r = json.loads(Path(backup).read_text(encoding='utf-8'))
    if machine_present(r['path']) or snapshot(r['path'], r['after']) != r['after']:
        raise ValueError('Policy changed after apply; refuse overwrite')
    write(r['path'], r['before'])
