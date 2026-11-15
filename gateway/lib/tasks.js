// Durable acceptance + outbox in a single transaction. No terminal input is an ACK.
const { DatabaseSync } = require('node:sqlite');
const { randomUUID, createHash } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const statuses = new Set(['accepted','scheduled','in_progress','needs_input','completed','failed','cancelled']);
function error(message, status=400) { return Object.assign(new Error(message),{status}); }
function input(raw) {
 if (!raw || typeof raw.client_request_id !== 'string' || !/^[a-zA-Z0-9_-]{8,128}$/.test(raw.client_request_id)) throw error('invalid client_request_id');
 if (typeof raw.text !== 'string' || !raw.text.trim() || raw.text.length>12000) throw error('invalid text');
 if (raw.kind && !['task','query'].includes(raw.kind)) throw error('invalid kind');
 return {client_request_id:raw.client_request_id,text:raw.text.trim(),kind:raw.kind||'task'};
}
class TaskStore {
 constructor(filename) {
  fs.mkdirSync(path.dirname(filename),{recursive:true,mode:0o700});
  this.db=new DatabaseSync(filename);
  fs.chmodSync(filename,0o600);
  this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA busy_timeout=5000;
   CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, data TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, hash TEXT NOT NULL, response TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, text TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0);`);
 }
 transaction(fn) { this.db.exec('BEGIN IMMEDIATE'); try { const r=fn();this.db.exec('COMMIT');return r; } catch(e) { this.db.exec('ROLLBACK');throw e; } }
 dedup(key,payload,fn) {
  const hash=createHash('sha256').update(JSON.stringify(payload)).digest('hex');
  return this.transaction(()=>{
   const old=this.db.prepare('SELECT * FROM requests WHERE id=?').get(key);
   if(old) {if(old.hash!==hash)throw error('request conflict',409);return JSON.parse(old.response);}
   const result=fn();
   this.db.prepare('INSERT INTO requests VALUES(?,?,?)').run(key,hash,JSON.stringify(result));return result;
  });
 }
 save(task) {this.db.prepare('INSERT OR REPLACE INTO tasks VALUES(?,?)').run(task.id,JSON.stringify(task));return task;}
 accept(raw) {
  const data=input(raw);
  return this.dedup(data.client_request_id,data,()=>{
   const id=randomUUID(), now=new Date().toISOString();
   const task={id,client_request_id:data.client_request_id,kind:data.kind,[data.kind==='query'?'query_id':'task_id']:id,title:data.text.slice(0,100),summary:data.text,status:'accepted',responsible_agent:null,current_activity:'Wartet auf CEO',accepted_at:now,updated_at:now,version:1,parent_id:null,result:null,question:null};
   this.save(task);this.db.prepare('INSERT INTO outbox(task_id,text) VALUES(?,?)').run(id,data.text);
   return task;
  });
 }
 get(id) {const row=this.db.prepare('SELECT data FROM tasks WHERE id=?').get(id);if(!row)throw error('task not found',404);return JSON.parse(row.data);}
 list() {return this.db.prepare('SELECT data FROM tasks ORDER BY rowid DESC LIMIT 200').all().map(x=>JSON.parse(x.data));}
 pending() {return this.db.prepare('SELECT * FROM outbox WHERE delivered=0 ORDER BY id LIMIT 10').all();}
 delivered(id) {this.db.prepare('UPDATE outbox SET delivered=1 WHERE task_id=?').run(id);}
 deliveredMessage(id) {this.db.prepare('UPDATE outbox SET delivered=1 WHERE id=?').run(id);}
 update(id,patch) {return this.transaction(()=>{
  const task=this.get(id);
  if(!statuses.has(patch.status))throw error('invalid status');
  if(patch.status==='needs_input' && !String(patch.question||'').trim())throw error('question required');
  if(patch.status==='completed' && !String(patch.result||'').trim())throw error('result required');
  task.status=patch.status; task.version++;task.updated_at=new Date().toISOString();
  for(const field of ['responsible_agent','current_activity','result'])if(typeof patch[field]==='string')task[field]=patch[field].slice(0,20000);
  task.question=patch.status==='needs_input'?{id:randomUUID(),version:task.version,text:String(patch.question).slice(0,12000)}:null;
  return this.save(task);
 });}
 reply(id,raw) {
  const data=input(raw);
  const payload={...data,task_id:id,question_id:raw.question_id,question_version:raw.question_version};
  return this.dedup(data.client_request_id,payload,()=>{
   const task=this.get(id), q=task.question;
   if(!q || q.id!==raw.question_id || q.version!==raw.question_version)throw error('stale question',409);
   task.status='accepted';task.current_activity='Antwort wartet auf CEO';task.question=null;task.version++;task.updated_at=new Date().toISOString();
   this.db.prepare('INSERT INTO outbox(task_id,text) VALUES(?,?)').run(id,`Antwort auf Rückfrage ${q.id}: ${data.text}`);
   this.save(task);return {id:task.id,status:'accepted',accepted_at:task.updated_at,client_request_id:data.client_request_id};
  });
 }
 close() {this.db.close();}
}
module.exports={TaskStore};
