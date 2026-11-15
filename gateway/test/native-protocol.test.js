// Runs the real Java gateway client/signing/pin code against the real Node gateway.
// Only Android identity storage/Base64/Context and endpoint config use JVM adapters.
const {test}=require('node:test');const assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');const fs=require('node:fs');const os=require('node:os');const path=require('node:path');const crypto=require('node:crypto');
const {fingerprintPublicKey}=require('../lib/auth');
test('native Java protocol interoperates with signed Node API and rejects wrong TLS pin',async t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'watch-native-protocol-'));
 const pkg=path.join(dir,'src/com/spockymagicai/agentterminals');fs.mkdirSync(pkg,{recursive:true});
 const write=(name,text)=>{const dest=path.join(dir,'src',name);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,text);return dest;};
 const files=[];
 files.push(write('android/content/Context.java','package android.content; public class Context {}'));
 files.push(write('android/util/Base64.java','package android.util; public class Base64 { public static String encodeToString(byte[] b,int flags){return java.util.Base64.getEncoder().encodeToString(b);} }'));
 files.push(write('com/spockymagicai/agentterminals/GatewayConfig.java','package com.spockymagicai.agentterminals; public class GatewayConfig { public static final String BASE_URL=System.getenv("TEST_URL"); public static final String SERVER_CERT_SHA256=System.getenv("TEST_PIN"); }'));
 files.push(write('com/spockymagicai/agentterminals/DeviceIdentity.java',`package com.spockymagicai.agentterminals;
 public class DeviceIdentity {
 public static java.security.PrivateKey privateKey(android.content.Context c)throws Exception {return java.security.KeyFactory.getInstance("EC").generatePrivate(new java.security.spec.PKCS8EncodedKeySpec(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(System.getenv("TEST_PRIVATE_KEY")))));}
 public static String publicKeyBase64(android.content.Context c){return System.getenv("TEST_PUBLIC_KEY");}
 }`));
 files.push(write('GatewayProtocolTest.java',`import com.spockymagicai.agentterminals.*;import org.json.*;
 public class GatewayProtocolTest {
 public static void main(String[] args)throws Exception {
 SecureGatewayClient client=new SecureGatewayClient(null);
 if(args.length>0){try{client.requestJson("GET","/v1/tasks",null);throw new AssertionError("bad pin accepted");}catch(javax.net.ssl.SSLHandshakeException expected){System.out.println("Wrong pin rejected");return;}}
 JSONObject payload=new JSONObject().put("client_request_id","native-protocol-123").put("kind","task").put("text","Deutscher Prüfauftrag mit Umlauten: Grüße");
 JSONObject first=client.requestJson("POST","/v1/ceo/requests",payload);
 if(!first.getString("status").equals("accepted"))throw new AssertionError();
 JSONObject again=client.requestJson("POST","/v1/ceo/requests",payload);
 if(!first.getString("id").equals(again.getString("id")))throw new AssertionError();
 if(client.requestJson("GET","/v1/tasks",null).getJSONArray("tasks").length()!=1)throw new AssertionError();
 payload.put("text","Anderer Inhalt");try{client.requestJson("POST","/v1/ceo/requests",payload);throw new AssertionError();}catch(SecureGatewayClient.GatewayException e){if(e.status!=409)throw e;}
 System.out.println("Native signed acceptance, UTF8, retry, snapshot and conflict passed");
 }} `));
 const source=path.join(__dirname,'../../native/src/com/spockymagicai/agentterminals');
 for(const name of ['SecureGatewayClient','PinnedTrustManager','PinnedHostnameVerifier','CertificateFingerprint'])files.push(path.join(source,name+'.java'));
 const jsonJar=process.env.ANDROID_JSON_JAR||'/usr/share/java/com.android.json.jar';
 execFileSync('javac',['-cp',jsonJar,'-d',path.join(dir,'classes'),...files],{stdio:'pipe'});
 execFileSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-keyout',path.join(dir,'key.pem'),'-out',path.join(dir,'cert.pem'),'-days','1','-subj','/CN=localhost'],{stdio:'ignore'});
 const cert=new crypto.X509Certificate(fs.readFileSync(path.join(dir,'cert.pem')));const pin=crypto.createHash('sha256').update(cert.raw).digest('hex');
 const {privateKey,publicKey}=crypto.generateKeyPairSync('ec',{namedCurve:'prime256v1'});const der=publicKey.export({format:'der',type:'spki'});
 fs.writeFileSync(path.join(dir,'device.der'),privateKey.export({format:'der',type:'pkcs8'}),{mode:0o600});
 const child=spawn(process.execPath,['server.js'],{cwd:path.join(__dirname,'..'),env:{...process.env,WATCH_GATEWAY_HOST:'127.0.0.1',WATCH_GATEWAY_PORT:'19445',WATCH_GATEWAY_CERT:path.join(dir,'cert.pem'),WATCH_GATEWAY_KEY:path.join(dir,'key.pem'),WATCH_GATEWAY_ALLOWED_FINGERPRINTS:fingerprintPublicKey(der),WATCH_TASK_DB:path.join(dir,'tasks.sqlite'),WATCH_DELIVERY_DISABLED:'1'}});
 t.after(async()=>{if(child.exitCode===null){const exit=new Promise(resolve=>child.once('exit',resolve));child.kill();await exit;}fs.rmSync(dir,{recursive:true});});
 await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('start timeout')),5000);child.stdout.on('data',data=>{if(String(data).includes('listening')){clearTimeout(timer);resolve();}});child.once('exit',code=>{clearTimeout(timer);reject(new Error('gateway exited '+code));});});
 const env={...process.env,TEST_URL:'https://127.0.0.1:19445',TEST_PIN:pin,TEST_PRIVATE_KEY:path.join(dir,'device.der'),TEST_PUBLIC_KEY:der.toString('base64')};
 const result=execFileSync('java',['-cp',path.join(dir,'classes')+':'+jsonJar,'GatewayProtocolTest'],{env,encoding:'utf8',timeout:20000});
 assert.match(result,/Native signed acceptance/);
 const bad=execFileSync('java',['-cp',path.join(dir,'classes')+':'+jsonJar,'GatewayProtocolTest','bad-pin'],{env:{...env,TEST_PIN:'00'.repeat(32)},encoding:'utf8',timeout:20000});
 assert.match(bad,/Wrong pin rejected/);
});
