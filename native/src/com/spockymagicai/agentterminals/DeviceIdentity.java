package com.spockymagicai.agentterminals;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Base64;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
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

    public static synchronized void ensureKey(Context context) throws Exception {
        SharedPreferences prefs = prefs(context);
        if (prefs.contains(PUBLIC_KEY) && prefs.contains("private-key-encrypted")) return;
        if (prefs.contains(PRIVATE_KEY) && prefs.contains(PUBLIC_KEY)) {
            storeEncrypted(prefs, decode(prefs.getString(PRIVATE_KEY, "")), prefs.getString(PUBLIC_KEY, ""));
            return;
        }
        KeyPairGenerator generator = KeyPairGenerator.getInstance("EC");
        generator.initialize(new ECGenParameterSpec("secp256r1"));
        KeyPair pair = generator.generateKeyPair();
        storeEncrypted(prefs, pair.getPrivate().getEncoded(), encode(pair.getPublic().getEncoded()));
    }

    public static PrivateKey privateKey(Context context) throws Exception {
        ensureKey(context);
        SharedPreferences prefs = prefs(context);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, wrappingKey(), new GCMParameterSpec(128, decode(prefs.getString("private-key-iv", ""))));
        byte[] encoded = cipher.doFinal(decode(prefs.getString("private-key-encrypted", "")));
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

    private static SecretKey wrappingKey() throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
        String alias="agent-terminals-identity-wrap";
        if(store.containsAlias(alias))return (SecretKey)store.getKey(alias,null);
        KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setKeySize(256).build());
        return generator.generateKey();
    }
    private static void storeEncrypted(SharedPreferences prefs, byte[] privateBytes, String publicKey) throws Exception {
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,wrappingKey());
        if(!prefs.edit().putString("private-key-encrypted",encode(cipher.doFinal(privateBytes)))
            .putString("private-key-iv",encode(cipher.getIV())).putString(PUBLIC_KEY,publicKey).remove(PRIVATE_KEY).commit())
            throw new IllegalStateException("Geräteidentität konnte nicht sicher gespeichert werden");
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
