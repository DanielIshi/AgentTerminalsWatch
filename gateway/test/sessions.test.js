const assert = require("assert");
const { findSession, publicSessions, sessions } = require("../lib/sessions");

assert.strictEqual(sessions.length, 5, "five sessions are configured");
assert.deepStrictEqual(
  publicSessions().map((session) => session.id),
  ["ceo", "marketing", "strategy", "operations", "ict"],
  "public session order matches watch UI"
);
assert.strictEqual(findSession("ceo").server, "netcup1", "CEO routes to netcup1");
assert.strictEqual(findSession("missing"), undefined, "missing session is undefined");

console.log("sessions.test.js ok");
