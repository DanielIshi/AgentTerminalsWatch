const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { TaskStore } = require('../lib/tasks');
function fixture(t) {
 const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'watch-tasks-'));
 const db = path.join(dir, 'tasks.sqlite');
 const store = new TaskStore(db);
 t.after(() => { store.close(); fs.rmSync(dir, {recursive:true}); });
 return { store, db };
}
test('acceptance survives reopening and retries return exactly the same task', t => {
 const {store,db}=fixture(t);
 const input={client_request_id:'request-12345678',text:'Bitte Status prüfen',kind:'task'};
 const first=store.accept(input);
 const reopened=new TaskStore(db);
 t.after(()=>reopened.close());
 assert.deepEqual(reopened.accept(input),first);
 assert.equal(reopened.list().length,1);
 assert.equal(reopened.pending().length,1);
 assert.throws(()=>reopened.accept({...input,text:'Anderer Auftrag'}), /conflict/);
});
test('query has query_id; delivery never claims work has started',t=>{
 const {store}=fixture(t);
 const accepted=store.accept({client_request_id:'request-query123',text:'Was läuft?',kind:'query'});
 assert.ok(accepted.query_id); assert.equal(accepted.task_id,undefined);
 store.delivered(accepted.id);
 assert.equal(store.get(accepted.id).status,'accepted');
 assert.equal(store.pending().length,0);
});
test('question replies are durable, deduplicated and reject obsolete versions',t=>{
 const {store}=fixture(t);
 const task=store.accept({client_request_id:'request-task1234',text:'Auftrag',kind:'task'});
 store.update(task.id,{status:'needs_input',question:'Welche Farbe?',responsible_agent:'CEO'});
 const question=store.get(task.id).question;
 const reply={client_request_id:'reply-123456789',question_id:question.id,question_version:question.version,text:'Blau'};
 const result=store.reply(task.id,reply);
 assert.deepEqual(store.reply(task.id,reply),result);
 assert.equal(store.get(task.id).status,'accepted');
 assert.throws(()=>store.reply(task.id,{...reply,client_request_id:'reply-different123'}),/stale/);
 assert.throws(()=>store.reply(task.id,{...reply,text:'Rot'}),/conflict/);
});
test('completion is explicit, versioned and does not count query as task',t=>{
 const {store}=fixture(t);
 const task=store.accept({client_request_id:'request-result123',text:'Auftrag'});
 store.accept({client_request_id:'request-query123',text:'Wie weit?',kind:'query'});
 store.update(task.id,{status:'completed',result:'Ergebnis liegt vor.'});
 assert.equal(store.get(task.id).version,2);
 assert.equal(store.get(task.id).result,'Ergebnis liegt vor.');
 assert.equal(store.list().filter(x=>x.kind==='task').length,1);
 assert.throws(()=>store.update(task.id,{status:'magic'}),/status/);
});
