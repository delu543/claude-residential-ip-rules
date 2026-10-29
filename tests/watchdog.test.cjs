const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const crypto=require('node:crypto');
const http=require('node:http');
const {spawn}=require('node:child_process');
test('Windows independent recovery process restores fake core on deadline without parent requests', {skip:process.platform!=='win32'},async()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'claude-tun-recovery-'));
  const pipe=`\\\\.\\pipe\\claude-tun-recovery-${process.pid}`;
  let enabled=true,restores=0;
  const server=http.createServer((req,res)=>{
    let b='';req.on('data',s=>b+=s);req.on('end',()=>{
      if(req.method==='PUT'){
        const baseline=JSON.parse(fs.readFileSync(JSON.parse(b).path,'utf8'));enabled=baseline.tun.enable;restores++;
        res.writeHead(204);res.end();
      }else{res.setHeader('Content-Type','application/json');res.end(JSON.stringify({tun:{enable:enabled}}));}
    });
  });
  await new Promise(resolve=>server.listen(pipe,resolve));
  try{
    const baseline=JSON.stringify({tun:{enable:false}});
    fs.writeFileSync(path.join(dir,'baseline.json'),baseline);
    fs.writeFileSync(path.join(dir,'settings.json'),JSON.stringify({apiPipe:pipe}));
    fs.writeFileSync(path.join(dir,'trial.json'),JSON.stringify({seconds:0.2,baselineHash:crypto.createHash('sha256').update(baseline).digest('hex')}));
    const child=spawn('python',[path.join(__dirname,'../scripts/tun_trial.py'),'_watch','--plan',dir]);
    let err='';child.stderr.on('data',s=>err+=s);
    const code=await new Promise(resolve=>child.on('close',resolve));
    assert.equal(code,0,err);assert.equal(enabled,false);assert.equal(restores,1);
    assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'restored.json'),'utf8')).restored,true);
  }finally{await new Promise(resolve=>server.close(resolve));fs.rmSync(dir,{recursive:true});}
});
