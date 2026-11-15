package com.spockymagicai.agentterminals;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognizerIntent;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.HapticFeedbackConstants;
import android.view.View;
import android.widget.*;
import org.json.*;
import java.util.ArrayList;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;

/** Native Watch/phone overview. The existing terminal Activity stays a separate destination. */
public class MainActivity extends Activity {
    private SharedPreferences prefs;
    private Outbox outbox;
    private LinearLayout content;
    private EditText draft;
    private TextView connection;
    private String page="overview", filter="", selected="", replyTask="", questionId="";
    private int questionVersion=0;
    private JSONArray tasks=new JSONArray();
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private boolean active=false, syncing=false, appendSpeech=false;
    private String network="Verbindung wird hergestellt";
    private final Runnable refresh=new Runnable(){public void run(){if(active){sync();handler.postDelayed(this,30000);}}};

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        prefs=getSharedPreferences("ceo-overview",MODE_PRIVATE);
        BackgroundSync.schedule(this);
        outbox=new Outbox(new Outbox.Storage(){public String read(){return prefs.getString("durable_outbox","");}public boolean write(String value){return prefs.edit().putString("durable_outbox",value).commit();}});
        try {tasks=new JSONArray(prefs.getString("tasks","[]"));}catch(Exception ignored){}
        if(state!=null){page=state.getString("page","overview");selected=state.getString("selected","");replyTask=state.getString("replyTask","");questionId=state.getString("questionId","");questionVersion=state.getInt("questionVersion",0);appendSpeech=state.getBoolean("appendSpeech",false);}
        if("detail".equals(page) && !selected.isEmpty())showDetail(selected);else if("editor".equals(page))showEditor(!replyTask.isEmpty());else showOverview();
        String task=getIntent().getStringExtra("task_id");
        String terminal=getIntent().getStringExtra("session-id");
        if(task!=null)showDetail(task);
        else if(terminal!=null && terminal.matches("ceo|marketing|strategy|operations|ict")) TerminalActivity.open(this,terminal,terminal);
    }
    @Override protected void onResume(){super.onResume();active=true;handler.post(refresh);}
    @Override protected void onPause(){active=false;handler.removeCallbacks(refresh);prefs.edit().putLong("foreground_until",0).apply();super.onPause();}
    @Override protected void onDestroy(){handler.removeCallbacksAndMessages(null);worker.shutdown();super.onDestroy();}
    @Override public void onSaveInstanceState(Bundle out){out.putString("page",page);out.putString("selected",selected);out.putString("replyTask",replyTask);out.putString("questionId",questionId);out.putInt("questionVersion",questionVersion);out.putBoolean("appendSpeech",appendSpeech);super.onSaveInstanceState(out);}
    @Override public void onBackPressed(){if("overview".equals(page))super.onBackPressed();else showOverview();}

    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private void screen(String title) {
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(Color.rgb(12,17,23));
        content=new LinearLayout(this);content.setOrientation(1);
        boolean round=getResources().getConfiguration().isScreenRound();
        content.setPadding(dp(round?30:18),dp(round?28:18),dp(round?30:18),dp(round?36:24));
        scroll.addView(content);setContentView(scroll);
        text(title,20);
    }
    private TextView text(String value,int size){TextView t=new TextView(this);t.setText(value);t.setTextColor(Color.WHITE);t.setTextSize(size);t.setPadding(0,dp(5),0,dp(5));content.addView(t);return t;}
    private Button button(String label,Runnable action){Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setMinHeight(dp(48));b.setTextSize(15);b.setOnClickListener(v->action.run());content.addView(b,new LinearLayout.LayoutParams(-1,-2));return b;}
    private String freshness(){long last=prefs.getLong("last_sync",0);return last==0?"Noch kein bestätigter Stand":"Stand: "+android.text.format.DateFormat.format("dd.MM. HH:mm:ss",last);}
    private void showOverview(){
        page="overview";replyTask="";questionId="";questionVersion=0;
        screen("Übersicht");connection=text(network+"\n"+freshness(),12);
        Button speak=button("Zum CEO sprechen",()->{showEditor(false);speak(false);});speak.setMinHeight(dp(64));speak.setTextSize(18);
        int running=0,needs=0,done=0;
        for(int i=0;i<tasks.length();i++){JSONObject t=tasks.optJSONObject(i);if(t==null||!"task".equals(t.optString("kind")))continue;String s=t.optString("status");if("needs_input".equals(s))needs++;else if("completed".equals(s)){if(prefs.getInt("seen-"+t.optString("id"),0)<t.optInt("version"))done++;}else if(isRunning(s))running++;}
        text(running+" laufen · "+needs+" Rückfragen",14);
        int waiting=queue().length();if(waiting>0)text(waiting+" warten auf Verbindung",14);
        try{if(outbox.review().length()>0)button("Versand prüfen · "+outbox.review().length(),this::showReview);}catch(Exception e){text("Versandspeicher nicht lesbar – nichts wird verworfen",14);}
        final int n=needs,r=running,d=done;
        button("Braucht dich · "+n,()->showList("needs_input"));
        button("Läuft · "+r,()->showList("running"));
        button("Fertig · "+d,()->showList("completed"));
        button("Alle Aufträge und Anfragen",()->showList(""));
        button("Entwurf / Texteingabe",()->showEditor(false));
        button("Agenten und Terminals",()->startActivity(new Intent(this,TerminalsActivity.class)));
        button("Aktualisieren",this::sync);
        button("Einstellungen",()->{page="settings";screen("Sprache und Zugang");button("Benachrichtigungen erlauben",()->{if(android.os.Build.VERSION.SDK_INT>=33)requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},42);else startActivity(new Intent(android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(android.provider.Settings.EXTRA_APP_PACKAGE,getPackageName()));});text("Rückfragen/Ergebnisse: Hintergrundabgleich etwa alle 15 Minuten, vom System ggf. verzögert. Beim Öffnen sofort. Kein dauerhafter Terminalkanal.",13);text("Systemdiktat: Audio verarbeitet der auf diesem Gerät gewählte Spracherkennungsdienst. Die App sendet nur den bestätigten Text an den Server. Keine automatische Sprachausgabe.",15);text("Gerätekennung: "+prefs.getString("device_fingerprint","Noch nicht initialisiert"),11);text("Zugang: signierte Anfragen und geprüftes Serverzertifikat. Keine neue Agentensitzung beim Öffnen.",15);button("Zur Übersicht",this::showOverview);});
    }
    private boolean isRunning(String s){return s.equals("accepted")||s.equals("scheduled")||s.equals("in_progress");}
    private String label(String s){switch(s){case "accepted":return "Angenommen";case "scheduled":return "Eingeplant";case "in_progress":return "In Bearbeitung";case "needs_input":return "Braucht dich";case "completed":return "Fertig";case "failed":return "Fehlgeschlagen";case "cancelled":return "Abgebrochen";default:return s;}}
    private void showList(String which){
        page="list";filter=which;screen("Aufträge und Anfragen");
        EditText search=new EditText(this);search.setSingleLine();search.setHint("Suchen");search.setTextColor(Color.WHITE);search.setHintTextColor(Color.LTGRAY);content.addView(search);
        LinearLayout rows=new LinearLayout(this);rows.setOrientation(1);content.addView(rows);
        Runnable render=()->{rows.removeAllViews();for(int i=0;i<tasks.length();i++){
            JSONObject t=tasks.optJSONObject(i);if(t==null)continue;String s=t.optString("status");
            if(!which.isEmpty() && !(which.equals("running")?isRunning(s):which.equals(s)))continue;
            if(!t.optString("summary").toLowerCase().contains(search.getText().toString().toLowerCase()))continue;
            Button row=new Button(this);row.setAllCaps(false);row.setText(label(s)+" · "+t.optString("title"));row.setMinHeight(dp(48));row.setOnClickListener(v->showDetail(t.optString("id")));rows.addView(row);
        }};
        search.addTextChangedListener(watcher(render));render.run();
        if(queue().length()>0){text("Versand ausstehend",16);JSONArray pending=queue();for(int i=0;i<pending.length();i++){JSONObject p=pending.optJSONObject(i);if(p!=null)text("Wartet auf Verbindung: "+p.optJSONObject("payload").optString("text"),14);}}
        button("Zur Übersicht",this::showOverview);
    }
    private JSONObject findTask(String id){for(int i=0;i<tasks.length();i++){JSONObject t=tasks.optJSONObject(i);if(t!=null && id.equals(t.optString("id")))return t;}return null;}
    private void showDetail(String id){
        page="detail";selected=id;screen("Auftrag");JSONObject t=findTask(id);
        if(t==null){text("Detail noch nicht synchronisiert",15);button("Aktualisieren",this::sync);button("Zur Übersicht",this::showOverview);return;}
        prefs.edit().putInt("seen-"+id,t.optInt("version")).apply();
        text(label(t.optString("status")),18);text("ID: "+id,11);text(t.optString("summary"),16);
        text("Verantwortlich: "+t.optString("responsible_agent","CEO"),14);text(t.optString("current_activity"),14);text("Bestätigt: "+t.optString("updated_at"),11);
        if(!t.isNull("result"))text(t.optString("result"),16);
        JSONObject q=t.optJSONObject("question");
        if(q!=null){text(q.optString("text"),18);button("Antworten",()->{replyTask=id;questionId=q.optString("id");questionVersion=q.optInt("version");showEditor(true);});}
        connection=text(network+"\n"+freshness(),12);button("Aktualisieren",this::sync);button("Zur Übersicht",this::showOverview);
    }
    private TextWatcher watcher(Runnable changed){return new TextWatcher(){public void beforeTextChanged(CharSequence s,int start,int count,int after){}public void onTextChanged(CharSequence s,int start,int before,int count){}public void afterTextChanged(Editable e){changed.run();}};}
    private String draftKey(){return replyTask.isEmpty()?"draft":"draft-reply-"+replyTask+"-"+questionId;}
    private void showEditor(boolean reply){
        if(!reply){replyTask="";questionId="";questionVersion=0;}
        page="editor";screen(reply?"Rückfrage beantworten":"Zum CEO sprechen");
        text("Systemdiktat · erst Senden übergibt den Text",12);
        draft=new EditText(this);draft.setTextColor(Color.WHITE);draft.setHintTextColor(Color.LTGRAY);draft.setHint("Auftrag oder Anfrage");draft.setMinLines(3);draft.setText(prefs.getString(draftKey(),""));content.addView(draft);
        draft.addTextChangedListener(watcher(()->prefs.edit().putString(draftKey(),draft.getText().toString()).commit()));
        button("Senden",this::submit);
        button("Ergänzen",()->speak(true));button("Neu aufnehmen",()->speak(false));
        button("Zur Übersicht (Entwurf behalten)",this::showOverview);
    }
    private void speak(boolean append){
        appendSpeech=append;
        Intent intent=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE,"de-DE");intent.putExtra(RecognizerIntent.EXTRA_PROMPT,"Zum CEO sprechen");
        try{draft.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY);startActivityForResult(intent,41);}catch(android.content.ActivityNotFoundException e){Toast.makeText(this,"Kein Systemdiktat verfügbar. Texteingabe bleibt möglich.",Toast.LENGTH_LONG).show();}
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==41 && result==RESULT_OK && data!=null){ArrayList<String> values=data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);if(values!=null&&!values.isEmpty()){if(draft==null)showEditor(!replyTask.isEmpty());String old=appendSpeech?draft.getText().toString().trim():"";draft.setText((old.isEmpty()?"":old+"\n")+values.get(0));draft.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY);}}}
    private void showReview(){page="review";screen("Versand prüfen");try{JSONArray rows=outbox.review();for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);text(row.optString("error"),14);text(row.getJSONObject("payload").getString("text"),16);}text("Die alten Nachrichten bleiben hier erhalten. Öffne die aktuelle Aufgabe für eine neue Antwort.",14);}catch(Exception e){text("Versandspeicher nicht lesbar",14);}button("Alle Aufgaben",()->showList(""));button("Zur Übersicht",this::showOverview);}
    private JSONArray queue(){try{return outbox.pending();}catch(Exception e){network="Lokaler Versandspeicher nicht lesbar";return new JSONArray();}}
    private void submit(){
        String value=draft.getText().toString().trim();if(value.isEmpty())return;
        try{
            JSONObject payload=new JSONObject().put("client_request_id",UUID.randomUUID().toString()).put("text",value).put("kind",RequestPolicy.kind(value));
            String path="/v1/ceo/requests";
            if(!replyTask.isEmpty()){path="/v1/tasks/"+replyTask+"/replies";payload.put("question_id",questionId).put("question_version",questionVersion);}
            outbox.enqueue(path,payload);prefs.edit().putString(draftKey(),"").commit();
            Toast.makeText(this,"Wartet auf Verbindung – noch nicht angenommen",Toast.LENGTH_LONG).show();showOverview();sync();
        }catch(Exception e){Toast.makeText(this,"Entwurf bleibt erhalten: "+e.getMessage(),Toast.LENGTH_LONG).show();}
    }
    private void sync(){
        if(syncing||isFinishing()||worker.isShutdown())return;syncing=true;prefs.edit().putLong("foreground_until",System.currentTimeMillis()+60000).apply();
        worker.execute(()->{synchronized(BackgroundSync.SYNC_LOCK){
            String error=null;JSONArray received=null;String accepted="";
            try{
                DeviceIdentity.ensureKey(this);prefs.edit().putString("device_fingerprint",DeviceIdentity.fingerprint(this)).apply();SecureGatewayClient client=new SecureGatewayClient(this);
                while(true){
                    JSONObject item=outbox.head();if(item==null)break;
                    JSONObject payload=item.getJSONObject("payload");JSONObject ack;
                    try {ack=client.requestJson("POST",item.getString("path"),payload);}
                    catch(SecureGatewayClient.GatewayException e){if(e.status==409){outbox.quarantine(e.getMessage());continue;}throw e;}
                    if(!payload.getString("client_request_id").equals(ack.optString("client_request_id"))||ack.optString("id").isEmpty()||!"accepted".equals(ack.optString("status")))throw new Exception("Ungültige Serverannahme");
                    accepted=ack.getString("id");
                    outbox.ack(ack);
                }
                received=client.requestJson("GET","/v1/tasks",null).getJSONArray("tasks");
                prefs.edit().putString("tasks",received.toString()).putLong("last_sync",System.currentTimeMillis()).commit();
            }catch(Exception e){error=e instanceof SecureGatewayClient.GatewayException && ((SecureGatewayClient.GatewayException)e).status==409?"Rückfrage veraltet oder ID-Konflikt – Versand prüfen":e instanceof SecureGatewayClient.GatewayException && ((SecureGatewayClient.GatewayException)e).status==403?"Anmeldung prüfen – Entwurf bleibt erhalten":"Offline / Server nicht erreichbar";}
            final String failure=error, ackId=accepted;final JSONArray snapshot=received;
            runOnUiThread(()->{syncing=false;if(isFinishing()||isDestroyed())return;network=failure==null?"Verbunden":failure;if(snapshot!=null)tasks=snapshot;if(!ackId.isEmpty())Toast.makeText(this,"Auftrag angenommen · "+ackId,Toast.LENGTH_LONG).show();if("overview".equals(page))showOverview();else if("list".equals(page))showList(filter);else if("detail".equals(page))showDetail(selected);});
        }});
    }
}
