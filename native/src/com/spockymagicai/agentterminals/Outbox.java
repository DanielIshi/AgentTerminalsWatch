package com.spockymagicai.agentterminals;
import org.json.*;
/** One atomic persisted document: retries keep the original request ID and payload. */
public final class Outbox {
 public interface Storage {String read();boolean write(String value);}
 private final Storage storage;
 public Outbox(Storage storage){this.storage=storage;}
 private JSONObject load()throws JSONException {
  String value=storage.read();
  if(value.isEmpty())return new JSONObject().put("pending",new JSONArray()).put("review",new JSONArray());
  JSONObject doc=new JSONObject(value);doc.getJSONArray("pending");doc.getJSONArray("review");return doc;
 }
 private void save(JSONObject doc){if(!storage.write(doc.toString()))throw new IllegalStateException("Lokales Speichern fehlgeschlagen");}
 public synchronized JSONArray pending()throws JSONException{return load().getJSONArray("pending");}
 public synchronized JSONArray review()throws JSONException{return load().getJSONArray("review");}
 public synchronized JSONObject head()throws JSONException{return pending().optJSONObject(0);}
 public synchronized void enqueue(String path,JSONObject payload)throws JSONException {
  JSONObject doc=load();doc.getJSONArray("pending").put(new JSONObject().put("path",path).put("payload",payload));save(doc);
 }
 public synchronized void ack(JSONObject ack)throws JSONException {
  JSONObject doc=load();JSONArray queue=doc.getJSONArray("pending");JSONObject first=queue.optJSONObject(0);
  if(first==null || !first.getJSONObject("payload").getString("client_request_id").equals(ack.optString("client_request_id"))||ack.optString("id").isEmpty()||!"accepted".equals(ack.optString("status")))throw new IllegalArgumentException("Ungültige Serverannahme");
  queue.remove(0);save(doc);
 }
 public synchronized void quarantine(String reason)throws JSONException {
  JSONObject doc=load();JSONArray queue=doc.getJSONArray("pending");JSONObject first=queue.optJSONObject(0);
  if(first==null)return;first.put("error",reason);doc.getJSONArray("review").put(first);queue.remove(0);save(doc);
 }
}
