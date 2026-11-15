function taskRoute(method,path,body,store) {
 try {
  const parse=()=>JSON.parse(body.toString('utf8')||'{}');
  if(path==='/v1/ceo/requests') {
   if(method!=='POST')return {status:405,body:{error:'method_not_allowed'}};
   return {status:201,body:store.accept(parse())};
  }
  if(path==='/v1/tasks')return method==='GET'?{status:200,body:{tasks:store.list(),synced_at:new Date().toISOString()}}:{status:405,body:{error:'method_not_allowed'}};
  const match=path.match(/^\/v1\/tasks\/([a-zA-Z0-9-]+)(\/replies)?$/);
  if(match) {
   if(!match[2] && method==='GET')return {status:200,body:store.get(match[1])};
   if(match[2] && method==='POST')return {status:201,body:store.reply(match[1],parse())};
   return {status:405,body:{error:'method_not_allowed'}};
  }
  return {status:404,body:{error:'not_found'}};
 } catch(e) {return {status:e.status||400,body:{error:e instanceof SyntaxError?'invalid_json':e.message}};}
}
module.exports={taskRoute};
