package com.spockymagicai.agentterminals;
import android.app.*;
import android.app.job.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.Build;
import org.json.*;

/** Battery-aware fallback where the current signed gateway has no push transport. */
public class BackgroundSync extends JobService {
 public static final Object SYNC_LOCK=new Object();
 private volatile boolean stopped=false;
 public static void schedule(Context context){
  JobScheduler jobs=(JobScheduler)context.getSystemService(JOB_SCHEDULER_SERVICE);
  jobs.schedule(new JobInfo.Builder(4192,new ComponentName(context,BackgroundSync.class))
   .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPeriodic(15*60*1000L).setPersisted(true).build());
 }
 @Override public boolean onStartJob(JobParameters params){
  stopped=false;
  new Thread(()->{
   boolean retry=false;
   synchronized(SYNC_LOCK){
    try{
     SharedPreferences prefs=getSharedPreferences("ceo-overview",MODE_PRIVATE);
     if(prefs.getLong("foreground_until",0)<System.currentTimeMillis()){
      DeviceIdentity.ensureKey(this);
      JSONArray tasks=new SecureGatewayClient(this).requestJson("GET","/v1/tasks",null).getJSONArray("tasks");
      if(!stopped){
       prefs.edit().putString("tasks",tasks.toString()).putLong("last_sync",System.currentTimeMillis()).commit();
       notifyChanges(prefs,tasks);
      }
     }
    }catch(Exception e){retry=true;}
   }
   if(!stopped)jobFinished(params,retry);
  },"watch-background-sync").start();
  return true;
 }
 @Override public boolean onStopJob(JobParameters params){stopped=true;return true;}
 private void notifyChanges(SharedPreferences prefs,JSONArray tasks){
  if(Build.VERSION.SDK_INT>=33 && checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=PackageManager.PERMISSION_GRANTED)return;
  NotificationManager manager=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
  manager.createNotificationChannel(new NotificationChannel("ceo-updates","CEO: Rückfragen und Ergebnisse",NotificationManager.IMPORTANCE_DEFAULT));
  if(!manager.areNotificationsEnabled())return;
  for(int i=0;i<tasks.length();i++){
   JSONObject task=tasks.optJSONObject(i);if(task==null)continue;
   String id=task.optString("id"),status=task.optString("status");int version=task.optInt("version");
   int seen=Math.max(prefs.getInt("seen-"+id,0),prefs.getInt("notified-"+id,0));
   if(!NotificationPolicy.shouldNotify(status,version,seen))continue;
   String title=status.equals("needs_input")?"CEO braucht deine Antwort":status.equals("completed")?"Ergebnis liegt vor":"Auftrag fehlgeschlagen";
   Intent intent=new Intent(this,MainActivity.class).putExtra("task_id",id).setAction("task-"+id);
   PendingIntent tap=PendingIntent.getActivity(this,id.hashCode(),intent,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
   manager.notify(id.hashCode(),new Notification.Builder(this,"ceo-updates")
    .setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle(title)
    .setContentText(task.optString("title")).setVisibility(Notification.VISIBILITY_PRIVATE)
    .setLocalOnly(true).setAutoCancel(true).setContentIntent(tap).setOnlyAlertOnce(true).build());
   prefs.edit().putInt("notified-"+id,version).commit();
  }
 }
}
