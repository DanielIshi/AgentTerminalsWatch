#!/usr/bin/env node
// Local agent tool: never exposed as a public HTTP mutation endpoint.
const path=require('node:path');
const {TaskStore}=require('./lib/tasks');
const filename=process.env.WATCH_TASK_DB||path.join(__dirname,'state/tasks.sqlite');
const store=new TaskStore(filename);
try {
 const [operation,id,...args]=process.argv.slice(2);
 if(operation==='list')console.log(JSON.stringify(store.list(),null,2));
 else if(operation==='get')console.log(JSON.stringify(store.get(id),null,2));
 else if(operation==='update')console.log(JSON.stringify(store.update(id,JSON.parse(args.join(' '))),null,2));
 else throw new Error('Usage: task-agent.js list | get ID | update ID JSON');
} finally {store.close();}
