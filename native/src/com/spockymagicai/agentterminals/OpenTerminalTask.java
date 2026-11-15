package com.spockymagicai.agentterminals;

import android.util.Log;

/* loaded from: classes2.dex */
public final class OpenTerminalTask implements Runnable {
    private final MainActivity activity;
    private final String sessionId;
    private final String sessionName;

    public OpenTerminalTask(MainActivity activity, String sessionId, String sessionName) {
        this.activity = activity;
        this.sessionId = sessionId;
        this.sessionName = sessionName;
    }

    @Override // java.lang.Runnable
    public void run() {
        try {
            this.activity.setStatus("Opening " + this.sessionName + "...");
            new SecureGatewayClient(this.activity).captureTerminal(this.sessionId);
            Log.i("AgentTerminals", "TERMINAL_READY session=" + this.sessionId);
            TerminalActivity.open(this.activity, this.sessionId, this.sessionName);
        } catch (Exception e) {
            Log.e("AgentTerminals", "OPEN_TERMINAL_ERROR", e);
            this.activity.setStatus("Open error:\n" + e.getClass().getSimpleName() + ": " + e.getMessage());
        }
    }
}
