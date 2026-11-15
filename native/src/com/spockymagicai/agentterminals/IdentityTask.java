package com.spockymagicai.agentterminals;

import android.util.Log;

/* loaded from: classes2.dex */
public final class IdentityTask implements Runnable {
    private final MainActivity activity;

    public IdentityTask(MainActivity activity) {
        this.activity = activity;
    }

    @Override // java.lang.Runnable
    public void run() {
        try {
            DeviceIdentity.ensureKey(this.activity);
            String fingerprint = DeviceIdentity.fingerprint(this.activity);
            Log.i("AgentTerminals", "CLIENT_KEY_SHA256=" + fingerprint);
            this.activity.setStatus("Device key:\n" + fingerprint + "\n\nGateway:\n" + GatewayConfig.BASE_URL);
            this.activity.connectAfterIdentityReady();
        } catch (Exception e) {
            this.activity.setStatus("Identity error:\n" + e.getMessage());
        }
    }
}
