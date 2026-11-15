const crypto = require("crypto");

function normalizeFingerprint(value) {
  if (!value || typeof value !== "string") return "";
  return value.replace(/[^a-fA-F0-9]/g, "").toUpperCase();
}

function parseAllowlist(value) {
  if (!value) return new Set();
  if (Array.isArray(value)) {
    return new Set(value.map(normalizeFingerprint).filter(Boolean));
  }
  return new Set(
    String(value)
      .split(/[,\s]+/)
      .map(normalizeFingerprint)
      .filter(Boolean)
  );
}

function fingerprintPublicKey(publicKeyDer) {
  return crypto.createHash("sha256").update(publicKeyDer).digest("hex").toUpperCase();
}

function isClientAllowed(fingerprint, allowlist) {
  return allowlist.has(normalizeFingerprint(fingerprint));
}

function canonicalRequest({ method, path, timestamp, nonce, body }) {
  const bodyHash = crypto.createHash("sha256").update(body || Buffer.alloc(0)).digest("hex");
  return [method.toUpperCase(), path, String(timestamp), String(nonce), bodyHash].join("\n");
}

function verifySignedRequest(req, body, allowlist, nonceCache, nowSeconds = Math.floor(Date.now() / 1000)) {
  const publicKeyBase64 = req.headers["x-client-public-key"];
  const timestamp = req.headers["x-timestamp"];
  const nonce = req.headers["x-nonce"];
  const signatureBase64 = req.headers["x-signature"];

  if (!publicKeyBase64 || !timestamp || !nonce || !signatureBase64) {
    return { ok: false, status: 403, error: "missing_signature_headers" };
  }

  const timestampNumber = Number(timestamp);
  if (!Number.isFinite(timestampNumber) || Math.abs(nowSeconds - timestampNumber) > 180) {
    return { ok: false, status: 403, error: "stale_signature_timestamp" };
  }

  const publicKeyDer = Buffer.from(String(publicKeyBase64), "base64");
  const fingerprint = fingerprintPublicKey(publicKeyDer);
  if (!isClientAllowed(fingerprint, allowlist)) {
    return { ok: false, status: 403, error: "client_key_not_allowed", fingerprint };
  }

  const nonceKey = `${fingerprint}:${nonce}`;
  if (nonceCache.has(nonceKey)) {
    return { ok: false, status: 403, error: "replayed_signature", fingerprint };
  }

  const keyObject = crypto.createPublicKey({ key: publicKeyDer, format: "der", type: "spki" });
  const verifier = crypto.createVerify("SHA256");
  verifier.update(canonicalRequest({
    method: req.method,
    path: new URL(req.url, "https://watch-gateway.local").pathname,
    timestamp,
    nonce,
    body,
  }));
  verifier.end();

  const valid = verifier.verify(keyObject, Buffer.from(String(signatureBase64), "base64"));
  if (!valid) {
    return { ok: false, status: 403, error: "invalid_signature", fingerprint };
  }

  nonceCache.set(nonceKey, timestampNumber);
  for (const [key, seenAt] of nonceCache) {
    if (nowSeconds - seenAt > 300) nonceCache.delete(key);
  }
  return { ok: true, fingerprint };
}

function base64url(input) {
  return Buffer.from(input).toString("base64url");
}

function signSessionToken(payload, secret) {
  const encoded = base64url(JSON.stringify(payload));
  const signature = crypto.createHmac("sha256", secret).update(encoded).digest("base64url");
  return `${encoded}.${signature}`;
}

function verifySessionToken(token, secret, nowSeconds = Math.floor(Date.now() / 1000)) {
  if (!token || !secret || !String(token).includes(".")) {
    return { ok: false, error: "missing_session" };
  }
  const [encoded, signature] = String(token).split(".");
  const expected = crypto.createHmac("sha256", secret).update(encoded).digest("base64url");
  if (Buffer.byteLength(signature) !== Buffer.byteLength(expected)) {
    return { ok: false, error: "invalid_session_signature" };
  }
  if (!crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) {
    return { ok: false, error: "invalid_session_signature" };
  }
  const payload = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
  if (!payload.exp || payload.exp < nowSeconds) {
    return { ok: false, error: "expired_session" };
  }
  return { ok: true, payload };
}

function cookieValue(req, name) {
  const cookie = req.headers.cookie || "";
  for (const part of cookie.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return rest.join("=");
  }
  return "";
}

module.exports = {
  canonicalRequest,
  cookieValue,
  fingerprintPublicKey,
  isClientAllowed,
  normalizeFingerprint,
  parseAllowlist,
  signSessionToken,
  verifySessionToken,
  verifySignedRequest,
};
