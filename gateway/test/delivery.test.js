const {test}=require('node:test'); const assert=require('node:assert/strict');
const {startDelivery}=require('../lib/delivery');
test('unavailable CEO retains durable outbox; retry delivers same task without changing status',async()=>{
 let sent=[], marked=[], failing=true;
 const store={pending:()=>marked.length?[]:[{id:7,task_id:'stable-task',text:'Bitte prüfen'}],deliveredMessage:id=>marked.push(id)};
 const sender=startDelivery(store,{send:async text=>{if(failing)throw new Error('offline');sent.push(text);}});
 sender.stop();
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(marked.length,0);
 failing=false;await sender.tick();
 assert.deepEqual(marked,[7]);assert.match(sent[0],/stable-task/);
 await sender.tick();assert.equal(sent.length,1);
});
