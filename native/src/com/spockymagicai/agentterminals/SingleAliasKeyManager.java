package com.spockymagicai.agentterminals;

import java.net.Socket;
import java.security.Principal;
import java.security.PrivateKey;
import java.security.cert.X509Certificate;
import javax.net.ssl.SSLEngine;
import javax.net.ssl.X509ExtendedKeyManager;

/* loaded from: classes2.dex */
public final class SingleAliasKeyManager extends X509ExtendedKeyManager {
    private final String alias;
    private final X509Certificate[] chain;
    private final PrivateKey privateKey;

    public SingleAliasKeyManager(String alias, X509Certificate certificate, PrivateKey privateKey) {
        this.alias = alias;
        this.chain = new X509Certificate[]{certificate};
        this.privateKey = privateKey;
    }

    @Override // javax.net.ssl.X509KeyManager
    public String chooseClientAlias(String[] keyType, Principal[] issuers, Socket socket) {
        return this.alias;
    }

    @Override // javax.net.ssl.X509ExtendedKeyManager
    public String chooseEngineClientAlias(String[] keyType, Principal[] issuers, SSLEngine engine) {
        return this.alias;
    }

    @Override // javax.net.ssl.X509KeyManager
    public String chooseServerAlias(String keyType, Principal[] issuers, Socket socket) {
        return null;
    }

    @Override // javax.net.ssl.X509ExtendedKeyManager
    public String chooseEngineServerAlias(String keyType, Principal[] issuers, SSLEngine engine) {
        return null;
    }

    @Override // javax.net.ssl.X509KeyManager
    public X509Certificate[] getCertificateChain(String alias) {
        if (this.alias.equals(alias)) {
            return this.chain;
        }
        return null;
    }

    @Override // javax.net.ssl.X509KeyManager
    public String[] getClientAliases(String keyType, Principal[] issuers) {
        return new String[]{this.alias};
    }

    @Override // javax.net.ssl.X509KeyManager
    public PrivateKey getPrivateKey(String alias) {
        if (this.alias.equals(alias)) {
            return this.privateKey;
        }
        return null;
    }

    @Override // javax.net.ssl.X509KeyManager
    public String[] getServerAliases(String keyType, Principal[] issuers) {
        return null;
    }
}
