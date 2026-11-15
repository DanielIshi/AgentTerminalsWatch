package com.spockymagicai.agentterminals;

import javax.net.ssl.HostnameVerifier;
import javax.net.ssl.SSLSession;

/* loaded from: classes2.dex */
public final class PinnedHostnameVerifier implements HostnameVerifier {
    @Override // javax.net.ssl.HostnameVerifier
    public boolean verify(String hostname, SSLSession session) {
        return true;
    }
}
