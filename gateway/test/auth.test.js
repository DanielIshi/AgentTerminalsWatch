const assert = require("assert");
const crypto = require("crypto");
const {
  canonicalRequest,
  fingerprintPublicKey,
  isClientAllowed,
  normalizeFingerprint,
  parseAllowlist,
  verifySignedRequest,
} = require("../lib/auth");

assert.strictEqual(
  normalizeFingerprint("aa:bb cc-dd"),
  "AABBCCDD",
  "fingerprints are normalized to uppercase hex"
);

const allowlist = parseAllowlist("aa:bb:cc dd-ee-ff");
assert.strictEqual(allowlist.has("AABBCC"), true, "colon fingerprint parsed");
assert.strictEqual(allowlist.has("DDEEFF"), true, "dash fingerprint parsed");
assert.strictEqual(isClientAllowed("aa:bb:cc", allowlist), true, "allowed client accepted");
assert.strictEqual(isClientAllowed("11:22:33", allowlist), false, "unknown client rejected");

const { publicKey, privateKey } = crypto.generateKeyPairSync("ec", {
  namedCurve: "prime256v1",
});
const publicKeyDer = publicKey.export({ format: "der", type: "spki" });
const publicKeyBase64 = publicKeyDer.toString("base64");
const keyFingerprint = fingerprintPublicKey(publicKeyDer);
const timestamp = "1800000000";
const nonce = "nonce-1";
const body = Buffer.alloc(0);
const signer = crypto.createSign("SHA256");
signer.update(canonicalRequest({
  method: "GET",
  path: "/api/sessions",
  timestamp,
  nonce,
  body,
}));
signer.end();

const req = {
  method: "GET",
  url: "/api/sessions",
  headers: {
    "x-client-public-key": publicKeyBase64,
    "x-timestamp": timestamp,
    "x-nonce": nonce,
    "x-signature": signer.sign(privateKey).toString("base64"),
  },
};
const signedAllowlist = parseAllowlist(keyFingerprint);
const nonceCache = new Map();
assert.strictEqual(
  verifySignedRequest(req, body, signedAllowlist, nonceCache, 1800000001).ok,
  true,
  "valid signed request accepted"
);
assert.strictEqual(
  verifySignedRequest(req, body, signedAllowlist, nonceCache, 1800000001).error,
  "replayed_signature",
  "nonce replay rejected"
);

console.log("auth.test.js ok");
