// Local IPC only; credentials/config travel on stdin, not shell arguments.
const http = require('node:http');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', s => input += s);
process.stdin.on('end', () => {
  try {
    const o = JSON.parse(input);
    if (!o.socketPath || !o.path.startsWith('/') || !['GET','PUT'].includes(o.method)) throw Error();
    const data = o.body == null ? '' : JSON.stringify(o.body);
    const req = http.request({socketPath:o.socketPath, path:o.path, method:o.method,
      headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)}}, res => {
      let out = '';
      res.setEncoding('utf8');
      res.on('data', s => {out += s; if(out.length > 16*1024*1024) req.destroy(Error());});
      res.on('end', () => {if(res.statusCode < 200 || res.statusCode >= 300) process.exitCode=1; else process.stdout.write(out);});
      res.on('error', () => process.exitCode=1);
    });
    const deadline=setTimeout(()=>req.destroy(Error()),15000);
    req.on('close',()=>clearTimeout(deadline));
    req.on('error',()=>{process.exitCode=1;});
    req.end(data);
  } catch {process.exitCode=1;}
});
