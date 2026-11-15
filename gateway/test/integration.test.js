const {test}=require('node:test');const assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');const fs=require('node:fs');const os=require('node:os');const path=require('node:path');const https=require('node:https');const crypto=require('node:crypto');
const {canonicalRequest,fingerprintPublicKey}=require('../lib/auth');
test('real TLS gateway authenticates acceptance, restart/retry, question and result; never spawns sessions',async t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'watch-e2e-'));
 execFileSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-keyout',path.join(dir,'key.pem'),'-out',path.join(dir,'cert.pem'),'-days','1','-subj','/CN=localhost'],{stdio:'ignore'});
 const {privateKey,publicKey}=crypto.generateKeyPairSync('ec',{namedCurve:'prime256v1'});const der=publicKey.export({format:'der',type:'spki'});
 let child;
 const port=19443;
 function start(){return new Promise((resolve,reject)=>{
  child=spawn(process.execPath,['server.js'],{cwd:path.join(__dirname,'..'),env:{...process.env,WATCH_GATEWAY_HOST:'127.0.0.1',WATCH_GATEWAY_PORT:String(port),WATCH_GATEWAY_CERT:path.join(dir,'cert.pem'),WATCH_GATEWAY_KEY:path.join(dir,'key.pem'),WATCH_GATEWAY_ALLOWED_FINGERPRINTS:fingerprintPublicKey(der),WATCH_TASK_DB:path.join(dir,'tasks.sqlite'),WATCH_DELIVERY_DISABLED:'1'}});
  const timer=setTimeout(()=>reject(new Error('gateway start timeout')),5000);
  child.once('exit',code=>{clearTimeout(timer);reject(new Error('gateway exited '+code));});
  child.stdout.on('data',data=>{if(String(data).includes('listening')){clearTimeout(timer);resolve();}});
 });}
 async function stop(){if(child && child.exitCode===null){const exiting=new Promise(resolve=>child.once('exit',resolve));child.kill();await exiting;}}
 t.after(async()=>{await stop();fs.rmSync(dir,{recursive:true});});
 async function request(method,url,payload,authorized=true){
  const body=Buffer.from(payload?JSON.stringify(payload):'');const timestamp=String(Math.floor(Date.now()/1000)),nonce=crypto.randomUUID();
  const signature=crypto.sign('sha256',Buffer.from(canonicalRequest({method,path:url,timestamp,nonce,body})),privateKey);
  const headers=authorized?{'x-client-public-key':der.toString('base64'),'x-timestamp':timestamp,'x-nonce':nonce,'x-signature':signature.toString('base64')}:{};
  return new Promise((resolve,reject)=>{const req=https.request({hostname:'127.0.0.1',port,path:url,method,rejectUnauthorized:false,headers:{...headers,'content-type':'application/json','content-length':body.length}},res=>{let data='';res.on('data',x=>data+=x);res.on('end',()=>resolve({status:res.statusCode,body:JSON.parse(data)}));});req.on('error',reject);req.end(body);});
 }
 await start();
 assert.equal((await request('GET','/v1/tasks',null,false)).status,403);
 const payload={client_request_id:'e2e-stable-request',text:'Prüfauftrag ohne Ausführung',kind:'task'};
 const accepted=await request('POST','/v1/ceo/requests',payload);assert.equal(accepted.status,201);
 await stop();await start();
 assert.deepEqual((await request('POST','/v1/ceo/requests',payload)).body,accepted.body);
 assert.equal((await request('POST','/v1/ceo/requests',{...payload,text:'conflict'})).status,409);
 const {TaskStore}=require('../lib/tasks');const store=new TaskStore(path.join(dir,'tasks.sqlite'));t.after(()=>store.close());
 store.update(accepted.body.id,{status:'needs_input',question:'Blau oder Rot?',responsible_agent:'CEO'});
 let detail=(await request('GET','/v1/tasks/'+accepted.body.id)).body;assert.equal(detail.status,'needs_input');
 const reply={client_request_id:'reply-e2e-stable',text:'Blau',question_id:detail.question.id,question_version:detail.question.version};
 assert.equal((await request('POST',`/v1/tasks/${detail.id}/replies`,reply)).status,201);
 assert.equal((await request('POST',`/v1/tasks/${detail.id}/replies`,{...reply,client_request_id:'reply-obsolete'})).status,409);
 store.update(detail.id,{status:'completed',result:'Blau umgesetzt.'});
 detail=(await request('GET','/v1/tasks/'+detail.id)).body;assert.equal(detail.result,'Blau umgesetzt.');
 const list=(await request('GET','/v1/tasks')).body.tasks;assert.equal(list.length,1);
 const sessions=(await request('GET','/api/sessions')).body.sessions;assert.equal(sessions.length,5);
});
