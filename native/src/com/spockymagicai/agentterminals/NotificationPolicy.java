package com.spockymagicai.agentterminals;
public final class NotificationPolicy {
 private NotificationPolicy(){}
 public static boolean shouldNotify(String status,int version,int seen){
  return version>seen && (status.equals("needs_input")||status.equals("completed")||status.equals("failed"));
 }
}
