package com.spockymagicai.agentterminals;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Base64;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.spec.ECGenParameterSpec;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;

/* loaded from: classes2.dex */
public final class DeviceIdentity {
    private static final String PREFS = "device-identity";
    private static final String PRIVATE_KEY = "private-key-pkcs8";
    private static final String PUBLIC_KEY = "public-key-spki";

    private DeviceIdentity() {
    }

    public static void ensureKey(Context context) throws Exception {
        SharedPreferences prefs = prefs(context);
        if (prefs.contains(PRIVATE_KEY) && prefs.contains(PUBLIC_KEY)) {
            return;
        }
        KeyPairGenerator generator = KeyPairGenerator.getInstance("EC");
        generator.initialize(new ECGenParameterSpec("secp256r1"));
        KeyPair pair = generator.generateKeyPair();
        prefs.edit().putString(PRIVATE_KEY, encode(pair.getPrivate().getEncoded())).putString(PUBLIC_KEY, encode(pair.getPublic().getEncoded())).apply();
    }

    public static PrivateKey privateKey(Context context) throws Exception {
        byte[] encoded = decode(prefs(context).getString(PRIVATE_KEY, ""));
        return KeyFactory.getInstance("EC").generatePrivate(new PKCS8EncodedKeySpec(encoded));
    }

    public static PublicKey publicKey(Context context) throws Exception {
        byte[] encoded = publicKeyBytes(context);
        return KeyFactory.getInstance("EC").generatePublic(new X509EncodedKeySpec(encoded));
    }

    public static byte[] publicKeyBytes(Context context) {
        return decode(prefs(context).getString(PUBLIC_KEY, ""));
    }

    public static String publicKeyBase64(Context context) {
        return prefs(context).getString(PUBLIC_KEY, "");
    }

    public static String fingerprint(Context context) throws Exception {
        return CertificateFingerprint.sha256(publicKeyBytes(context));
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, 0);
    }

    private static String encode(byte[] data) {
        return Base64.encodeToString(data, 2);
    }

    private static byte[] decode(String data) {
        return Base64.decode(data, 2);
    }
}
