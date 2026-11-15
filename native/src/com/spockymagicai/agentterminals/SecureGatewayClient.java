package com.spockymagicai.agentterminals;

import android.content.Context;
import android.util.Base64;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.URL;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.security.Signature;
import java.util.Locale;
import java.util.UUID;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import org.json.JSONObject;

/* loaded from: classes2.dex */
public final class SecureGatewayClient {
    private final Context context;

    public SecureGatewayClient(Context context) {
        this.context = context;
    }

    public JSONObject requestJson(String method, String path, JSONObject payload) throws Exception {
        String response = signedRequest(method, path, payload == null ? new byte[0] : payload.toString().getBytes("UTF-8"));
        JSONObject result = responseJson(response);
        if (!response.matches("(?s)^HTTP 2[0-9][0-9]\\n.*")) {
            throw new GatewayException(response.startsWith("HTTP 409") ? 409 : response.startsWith("HTTP 403") ? 403 : 500,
                result.optString("error", "Serverfehler"));
        }
        return result;
    }
    public static final class GatewayException extends Exception {
        public final int status;
        public GatewayException(int status, String message) { super(message); this.status = status; }
    }

    public String loadSessions() throws Exception {
        return signedGet("/api/sessions");
    }

    public String createLaunchUrl(String sessionId) throws Exception {
        String response = signedGet("/api/web-session/" + sessionId);
        int start = response.indexOf("\"launchPath\":\"");
        if (start < 0) {
            throw new IllegalStateException("Gateway did not return a launch path: " + response);
        }
        int start2 = start + "\"launchPath\":\"".length();
        int end = response.indexOf(34, start2);
        if (end < 0) {
            throw new IllegalStateException("Malformed launch response");
        }
        return GatewayConfig.BASE_URL + response.substring(start2, end).replace("\\/", "/");
    }

    public String captureTerminal(String sessionId) throws Exception {
        String response = signedRequest("GET", "/api/terminal/" + sessionId + "/snapshot", new byte[0]);
        JSONObject root = responseJson(response);
        if (!root.optBoolean("ok")) {
            throw new IllegalStateException(root.optString("error", response));
        }
        return root.optString("text", "");
    }

    public void sendTerminalInput(String sessionId, String text, boolean enter) throws Exception {
        JSONObject payload = new JSONObject();
        payload.put("text", text == null ? "" : text);
        payload.put("enter", enter);
        String response = signedRequest("POST", "/api/terminal/" + sessionId + "/send", payload.toString().getBytes("UTF-8"));
        JSONObject root = responseJson(response);
        if (!root.optBoolean("ok")) {
            throw new IllegalStateException(root.optString("error", response));
        }
    }

    private String signedGet(String path) throws Exception {
        return signedRequest("GET", path, new byte[0]);
    }

    private String signedRequest(String method, String path, byte[] body) throws Exception {
        InputStream stream;
        SSLContext sslContext = SSLContext.getInstance("TLS");
        sslContext.init(null, new TrustManager[]{new PinnedTrustManager(GatewayConfig.SERVER_CERT_SHA256)}, new SecureRandom());
        URL url = new URL(GatewayConfig.BASE_URL + path);
        HttpsURLConnection connection = (HttpsURLConnection) url.openConnection();
        connection.setSSLSocketFactory(sslContext.getSocketFactory());
        connection.setHostnameVerifier(new PinnedHostnameVerifier());
        connection.setConnectTimeout(8000);
        connection.setReadTimeout(8000);
        connection.setRequestMethod(method);
        connection.setRequestProperty("accept", "application/json");
        addSignatureHeaders(connection, method, path, body);
        if (body.length > 0 || "POST".equals(method)) {
            connection.setDoOutput(true);
            connection.setRequestProperty("content-type", "application/json; charset=utf-8");
            connection.setFixedLengthStreamingMode(body.length);
            OutputStream output = connection.getOutputStream();
            output.write(body);
            output.close();
        }
        int code = connection.getResponseCode();
        if (code >= 200 && code < 400) {
            stream = connection.getInputStream();
        } else {
            stream = connection.getErrorStream();
        }
        String responseBody = readAll(stream);
        return "HTTP " + code + "\n" + responseBody;
    }

    private static JSONObject responseJson(String response) throws Exception {
        int start = response.indexOf(123);
        if (start < 0) {
            throw new IllegalStateException("Gateway did not return JSON: " + response);
        }
        return new JSONObject(response.substring(start));
    }

    private static String readAll(InputStream stream) throws Exception {
        if (stream == null) {
            return "";
        }
        BufferedReader reader = new BufferedReader(new InputStreamReader(stream));
        StringBuilder builder = new StringBuilder();
        while (true) {
            String line = reader.readLine();
            if (line != null) {
                builder.append(line).append('\n');
            } else {
                return builder.toString().trim();
            }
        }
    }

    private void addSignatureHeaders(HttpsURLConnection connection, String method, String path, byte[] body) throws Exception {
        String timestamp = String.valueOf(System.currentTimeMillis() / 1000);
        String nonce = UUID.randomUUID().toString();
        String bodyHash = sha256Hex(body);
        String canonical = method + "\n" + path + "\n" + timestamp + "\n" + nonce + "\n" + bodyHash;
        Signature signer = Signature.getInstance("SHA256withECDSA");
        signer.initSign(DeviceIdentity.privateKey(this.context));
        signer.update(canonical.getBytes("UTF-8"));
        connection.setRequestProperty("x-client-public-key", DeviceIdentity.publicKeyBase64(this.context));
        connection.setRequestProperty("x-timestamp", timestamp);
        connection.setRequestProperty("x-nonce", nonce);
        connection.setRequestProperty("x-signature", Base64.encodeToString(signer.sign(), 2));
    }

    private static String sha256Hex(byte[] data) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(data);
        StringBuilder builder = new StringBuilder();
        for (byte b : digest) {
            builder.append(String.format(Locale.US, "%02x", Integer.valueOf(b & 255)));
        }
        return builder.toString();
    }
}
