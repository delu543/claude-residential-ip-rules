"""Host-specific discovery helpers. No provider identity is inferred from names."""
import socket
from pathlib import Path

MANAGED_LISTENER = 'claude-only-http'


def reserved_ports(runtime):
    return {p for p in [runtime.get(k) for k in ('port','socks-port','mixed-port','redir-port','tproxy-port')]
            if isinstance(p,int) and p>0} | {x.get('port') for x in runtime.get('listeners',[]) if x.get('name')!=MANAGED_LISTENER}


def managed_port(runtime):
    rows=[l for l in runtime.get('listeners',[]) if l.get('name')==MANAGED_LISTENER]
    if len(rows)==1 and rows[0].get('type')=='http' and rows[0].get('listen')=='127.0.0.1' and rows[0].get('proxy')=='住宅固定节点':
        return rows[0].get('port')
    return None


def free_port(port=0):
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            s.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        s.bind(('127.0.0.1',port))
        return s.getsockname()[1]


def choose_port(runtime, requested=None):
    existing=managed_port(runtime)
    port=requested if requested is not None else existing
    if port is not None:
        if type(port)!=int or not 1024<=port<=65535 or port in reserved_ports(runtime):
            raise ValueError('Dedicated local port conflicts with current configuration')
        if port!=existing:
            try:free_port(port)
            except OSError:raise ValueError('Requested local port is already occupied') from None
        return port
    for _ in range(16):
        port=free_port()
        if port not in reserved_ports(runtime):return port
    raise ValueError('No free local listener port found')


def provider_options(item, path, template):
    result=dict(template)
    if item.get('type')=='remote' and item.get('url'):
        result.update(type='http',url=item['url'])
    elif item.get('type')=='local' and Path(path).is_file():
        result.update(type='file',path=str(Path(path).resolve()))
        result.pop('url',None);result.pop('interval',None);result.pop('proxy',None)
    else:raise ValueError('Ordinary source must be a remote subscription or an existing local Clash node file')
    return result
