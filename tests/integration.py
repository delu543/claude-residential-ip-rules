#!/usr/bin/env python3
"""Real Mihomo, fake localhost proxy upstreams. No real subscription or WAN traffic.
Usage: python3 tests/integration.py --mihomo /path/to/mihomo
"""
import argparse
import http.server
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

class FakeProxy:
    def __init__(self, label):
        self.label = label; self.healthy = True; self.calls = []
        outer = self
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def do_CONNECT(self):
                if not outer.healthy:
                    self.connection.shutdown(socket.SHUT_RDWR); self.connection.close(); return
                self.send_response(200); self.end_headers(); self.close_connection = False
            def log_message(self, *a): pass
            def do_GET(self):
                outer.calls.append(self.path)
                if not outer.healthy:
                    self.connection.shutdown(socket.SHUT_RDWR); self.connection.close(); return
                health = '/health' in self.path
                self.send_response(204 if health else 200); self.send_header('Content-Length', str(0 if health else len(outer.label))); self.end_headers()
                if not health: self.wfile.write(outer.label.encode())
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_port
    def node(self, name):
        return {'name': name, 'type': 'http', 'server': '127.0.0.1', 'port': self.port}
    def close(self):
        self.server.shutdown(); self.server.server_close()

def freeport():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--mihomo', required=True); a=parser.parse_args()
    us, jp, res = FakeProxy('US'), FakeProxy('JP'), FakeProxy('RES')
    proc=None
    try:
        with tempfile.TemporaryDirectory(prefix='claude-route-integration-') as td:
            td=Path(td); normalport, dedicated, control = freeport(), freeport(), freeport()
            o=json.loads((ROOT/'examples/settings.example.json').read_text())
            o.update(residential=res.node('fixed-test'), port=dedicated, claudePaths=['/nonexistent/Claude.app/'],codexPaths=['/nonexistent/Codex.app/'])
            o['residential']={k:o['residential'][k] for k in ('name','type','server','port')}
            o['ordinaryProvider']={'type':'file','path':str(td/'ordinary.json')}
            (td/'ordinary.json').write_text(json.dumps({'proxies':[us.node('US test'),jp.node('JP test')]}))
            inp={'proxies':[res.node('fixed-test')]}
            js="const {build}=require(process.argv[1]);let fs=require('fs'),i=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(build(i.c,i.o)));"
            cfg=json.loads(subprocess.check_output(['node','-e',js,str(ROOT/'src/routing.js')],input=json.dumps({'c':inp,'o':o}).encode()))
            # Keep generated groups/listener, substitute deterministic domain rules to
            # avoid downloading geodata and inspect actual routing without real clients.
            cfg.update({'mixed-port':normalport,'external-controller':f'127.0.0.1:{control}',
                'allow-lan':False,'bind-address':'127.0.0.1','tun':{'enable':False},
                'dns':{'enable':False},'log-level':'warning',
                'rules':['DOMAIN,claude.ai,Claude 固定出口', 'DOMAIN,chatgpt.com,ChatGPT 普通出口',
                         'DOMAIN,localhost,DIRECT', 'MATCH,普通外网（美国优先）']})
            for g in cfg['proxy-groups']:
                if g['type']=='fallback':g.update(url='http://health.example.invalid/health',timeout=500,interval=3600)
            path=td/'config.json';path.write_text(json.dumps(cfg, ensure_ascii=False))
            log=open(td/'core.log','w')
            proc=subprocess.Popen([a.mihomo,'-d',str(td),'-f',str(path)],stdout=log,stderr=log)
            def api(endpoint):
                return json.loads(subprocess.check_output(['curl','-sS','--noproxy','*','--max-time','4',f'http://127.0.0.1:{control}'+endpoint],stderr=subprocess.DEVNULL))
            for _ in range(60):
                try:api('/version');break
                except subprocess.CalledProcessError:
                    if proc.poll() is not None:raise RuntimeError((td/'core.log').read_text())
                    time.sleep(.1)
            def health():
                for name in ['REJECT', 'US test', 'JP test', '普通·美国', '普通·其他地区', '普通外网（美国优先）']:
                    api('/proxies/'+urllib.parse.quote(name,safe='')+'/delay?url='+urllib.parse.quote('http://health.example.invalid/health',safe='')+'&timeout=500')
            def request(port,url):
                return subprocess.run(['curl','-fsS','--noproxy','','--proxy',f'http://127.0.0.1:{port}','--max-time','3',url],capture_output=True,text=True)
            health()
            q=request(normalport,'http://ordinary.example.invalid/request')
            assert q.stdout=='US', (q.stdout, q.stderr, api('/proxies'), us.calls, jp.calls, (td/'core.log').read_text())
            assert request(dedicated,'http://downloads.example.invalid/file').stdout=='RES'
            assert request(normalport,'http://claude.ai/request').stdout=='RES'
            assert request(normalport,'http://chatgpt.com/request').stdout=='US'
            # A real DIRECT request to our own local HTTP listener.
            assert request(normalport,f'http://localhost:{jp.port}/direct').stdout=='JP'
            us.healthy=False;health()
            assert request(normalport,'http://ordinary.example.invalid/request').stdout=='JP'
            jp.healthy=False;health();before=len(res.calls)
            assert request(normalport,'http://ordinary.example.invalid/request').returncode!=0
            assert len(res.calls)==before,'ordinary traffic borrowed residential'
            us.healthy=True;jp.healthy=True;health();res.healthy=False
            count=(len(us.calls),len(jp.calls))
            assert request(dedicated,'http://downloads.example.invalid/file').returncode!=0
            assert request(normalport,'http://claude.ai/request').returncode!=0
            assert (len(us.calls),len(jp.calls))==count,'residential traffic fell back to ordinary'
            proc.terminate();proc.wait(timeout=5);proc=None
            assert request(dedicated,'http://downloads.example.invalid/file').returncode!=0
            log.close()
            print('PASS: US priority; other-region failover; all ordinary dead rejects; no residential borrowing; residential fails closed; private DIRECT; dedicated listener closed fails.')
    finally:
        if proc is not None:
            proc.terminate();proc.wait(timeout=5)
        for p in [us,jp,res]:p.close()

if __name__=='__main__':main()
