package com.spockymagicai.agentterminals;

import android.util.Log;

/* loaded from: classes2.dex */
public final class ConnectTask implements Runnable {
    private final TerminalsActivity activity;

    public ConnectTask(TerminalsActivity activity) {
        this.activity = activity;
    }

    @Override // java.lang.Runnable
    public void run() {
        try {
            String response = new SecureGatewayClient(this.activity).loadSessions();
            Log.i("AgentTerminals", "GATEWAY_RESPONSE=" + response.replace('\n', ' '));
            int count = countOccurrences(response, "\"id\":");
            this.activity.setStatus("Connected: " + count + " sessions");
        } catch (Exception e) {
            Log.e("AgentTerminals", "GATEWAY_ERROR", e);
            this.activity.setStatus("Connection error:\n" + e.getClass().getSimpleName() + ": " + e.getMessage());
        }
    }

    private static int countOccurrences(String text, String needle) {
        int count = 0;
        int index = 0;
        while (true) {
            int index2 = text.indexOf(needle, index);
            if (index2 >= 0) {
                count++;
                index = index2 + needle.length();
            } else {
                return count;
            }
        }
    }
}
