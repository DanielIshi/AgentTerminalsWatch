package com.spockymagicai.agentterminals;

import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import javax.net.ssl.X509TrustManager;

/* loaded from: classes2.dex */
public final class PinnedTrustManager implements X509TrustManager {
    private final String expectedFingerprint;

    public PinnedTrustManager(String expectedFingerprint) {
        this.expectedFingerprint = CertificateFingerprint.normalize(expectedFingerprint);
    }

    @Override // javax.net.ssl.X509TrustManager
    public void checkClientTrusted(X509Certificate[] chain, String authType) {
    }

    @Override // javax.net.ssl.X509TrustManager
    public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
        if (this.expectedFingerprint.length() == 0) {
            throw new CertificateException("Server certificate pin is not configured.");
        }
        if (chain == null || chain.length == 0) {
            throw new CertificateException("Server did not send a certificate.");
        }
        try {
            if (!CertificateFingerprint.matches(this.expectedFingerprint, chain[0])) {
                throw new CertificateException("Server certificate pin mismatch.");
            }
        } catch (CertificateException e) {
            throw e;
        } catch (Exception e2) {
            throw new CertificateException("Could not verify server certificate pin.", e2);
        }
    }

    @Override // javax.net.ssl.X509TrustManager
    public X509Certificate[] getAcceptedIssuers() {
        return new X509Certificate[0];
    }
}
