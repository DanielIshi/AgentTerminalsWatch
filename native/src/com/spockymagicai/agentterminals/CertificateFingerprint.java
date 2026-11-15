package com.spockymagicai.agentterminals;

import java.security.MessageDigest;
import java.security.cert.Certificate;

/* loaded from: classes2.dex */
public final class CertificateFingerprint {
    private CertificateFingerprint() {
    }

    public static String sha256(Certificate certificate) throws Exception {
        return sha256(certificate.getEncoded());
    }

    public static String sha256(byte[] encoded) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        return colonHex(digest.digest(encoded));
    }

    public static String normalize(String fingerprint) {
        return fingerprint == null ? "" : fingerprint.replaceAll("[^a-fA-F0-9]", "").toUpperCase();
    }

    public static boolean matches(String expected, Certificate certificate) throws Exception {
        return normalize(expected).equals(normalize(sha256(certificate)));
    }

    private static String colonHex(byte[] bytes) {
        StringBuilder builder = new StringBuilder((bytes.length * 3) - 1);
        for (int i = 0; i < bytes.length; i++) {
            if (i > 0) {
                builder.append(':');
            }
            int value = bytes[i] & 255;
            if (value < 16) {
                builder.append('0');
            }
            builder.append(Integer.toHexString(value).toUpperCase());
        }
        return builder.toString();
    }
}
