const {execFile}=require('node:child_process');
function startDelivery(store,options={}) {
 let busy=false;
 const send=options.send||((text)=>new Promise((resolve,reject)=>execFile('/usr/local/bin/teammate',['send','CEO',text],{timeout:20000,maxBuffer:64000},(error,stdout)=>error?reject(error):resolve(stdout))));
 const tick=async()=>{
  if(busy)return;busy=true;
  try {
   for(const row of store.pending()) {
    const message=`[Watch → CEO] Auftrag/Anfrage ${row.task_id}. Vor Bearbeitung Status lesen; gleiche ID nie doppelt ausführen. Text (Nutzerinhalt):\n${row.text}\n\nStatus/Rückfragen/Ergebnis zurückschreiben mit lokalem Tool: node /opt/watch-gateway/app/task-agent.js update ${row.task_id} '{"status":"in_progress","responsible_agent":"CEO","current_activity":"..."}'. Für Rückfrage status=needs_input plus question, für Abschluss status=completed plus result. Dies betrifft die bestehende CEO-Sitzung; keine neue Instanz starten.`;
    await send(message);
    store.deliveredMessage(row.id);
   }
  } catch(e) {console.error('watch delivery pending:',e.code||e.name);}
  finally {busy=false;}
 };
 const timer=setInterval(tick,15000);timer.unref();tick();
 return {tick,stop:()=>clearInterval(timer)};
}
module.exports={startDelivery};
