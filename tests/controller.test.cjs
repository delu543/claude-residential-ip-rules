const {test}=require('node:test');
const assert=require('node:assert/strict');
const http=require('node:http');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawn}=require('node:child_process');
test('IPC controller handles chunked Unicode response and PUT without TCP listener',async()=>{
  const socketPath=process.platform==='win32'?`\\\\.\\pipe\\claude-rules-test-${process.pid}`:path.join(os.tmpdir(),`claude-rules-${process.pid}.sock`);
  const server=http.createServer((req,res)=>{let b='';req.on('data',s=>b+=s);req.on('end',()=>{
    assert.equal(req.method,'PUT');assert.equal(JSON.parse(b).path,'住宅.json');
    res.writeHead(200,{'Content-Type':'application/json'});res.write('{"ok":');res.end('"住宅"}');
  });});
  await new Promise(resolve=>server.listen(socketPath,resolve));
  try {
    const child=spawn(process.execPath,[path.join(__dirname,'../scripts/controller.cjs')]);
    let out='';child.stdout.on('data',s=>out+=s);
    child.stdin.end(JSON.stringify({socketPath,path:'/configs?force=false',method:'PUT',body:{path:'住宅.json'}}));
    const exit=await new Promise(resolve=>child.on('close',resolve));assert.equal(exit,0);assert.deepEqual(JSON.parse(out),{ok:'住宅'});
  }finally{await new Promise(resolve=>server.close(resolve));}
});
