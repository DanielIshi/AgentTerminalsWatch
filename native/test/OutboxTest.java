import com.spockymagicai.agentterminals.Outbox;
import com.spockymagicai.agentterminals.RequestPolicy;
import org.json.*;
public class OutboxTest {
 static final class Disk implements Outbox.Storage {String data=""; boolean fail=false;public String read(){return data;}public boolean write(String value){if(fail)return false;data=value;return true;}}
 static void require(boolean value){if(!value)throw new AssertionError();}
 public static void main(String[] args)throws Exception {
  Disk disk=new Disk();Outbox first=new Outbox(disk);
  JSONObject payload=new JSONObject().put("client_request_id","stable-123").put("text","Auftrag");
  first.enqueue("/v1/ceo/requests",payload);
  Outbox restarted=new Outbox(disk);require(restarted.head().getJSONObject("payload").getString("client_request_id").equals("stable-123"));
  try{restarted.ack(new JSONObject().put("client_request_id","wrong").put("id","server-id").put("status","accepted"));throw new AssertionError();}catch(IllegalArgumentException expected){}
  require(restarted.pending().length()==1);
  disk.fail=true;try{restarted.ack(new JSONObject().put("client_request_id","stable-123").put("id","server-id").put("status","accepted"));throw new AssertionError();}catch(IllegalStateException expected){}
  require(restarted.pending().length()==1);disk.fail=false;
  restarted.ack(new JSONObject().put("client_request_id","stable-123").put("id","server-id").put("status","accepted"));require(new Outbox(disk).head()==null);
  first.enqueue("/v1/tasks/one/replies",payload);first.quarantine("stale question");require(first.pending().length()==0);require(first.review().length()==1);
  require(RequestPolicy.kind("Was läuft gerade?").equals("query"));require(RequestPolicy.kind("CEO, Wie weit ist Auftrag 42?").equals("query"));require(RequestPolicy.kind("Lass Marketing drei Videos machen").equals("task"));
  disk.data="broken";try{new Outbox(disk).pending();throw new AssertionError();}catch(JSONException expected){}
  System.out.println("Native outbox/restart/conflict/persistence/query tests passed");
 }
}
