const {test}=require('node:test'); const assert=require('node:assert/strict');
const {taskRoute}=require('../lib/task-routes');
test('task POST and read routes preserve durable status and enforce methods',async()=>{
 const store={accept:x=>({...x,id:'one',status:'accepted'}),list:()=>[{id:'one'}],get:id=>({id}),reply:(id,x)=>({id,...x})};
 assert.equal(taskRoute('POST','/v1/ceo/requests',Buffer.from('{"text":"Hi"}'),store).status,201);
 assert.equal(taskRoute('GET','/v1/tasks',Buffer.alloc(0),store).body.tasks.length,1);
 assert.equal(taskRoute('GET','/v1/tasks/one',Buffer.alloc(0),store).body.id,'one');
 assert.equal(taskRoute('DELETE','/v1/tasks/one',Buffer.alloc(0),store).status,405);
 assert.equal(taskRoute('POST','/v1/ceo/requests',Buffer.from('broken'),store).status,400);
 assert.equal(taskRoute('GET','/v1/not-real',Buffer.alloc(0),store).status,404);
});
