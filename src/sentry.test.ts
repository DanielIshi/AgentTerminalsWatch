/**
 * R145 TDD — Sentry frontend wrapper (M2, GH#785+M2 follow-up).
 *
 * Contract:
 *   - initSentry() with no DSN → returns { enabled: false } (no-op)
 *   - initSentry() with DSN + VITE_SENTRY_DSN set → returns { enabled: true }
 *   - captureError() is safe to call whether Sentry is initialised or not
 *
 * Zero-cost when DSN missing: no @sentry/browser bundle load, no network.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { initSentry, captureError, isEnabled } from "./sentry";

describe("sentry frontend wrapper", () => {
  beforeEach(() => {
    // reset internal state between tests
    (globalThis as any).__ATW_SENTRY_STATE__ = undefined;
  });

  it("initSentry returns { enabled: false } when no DSN provided", () => {
    const r = initSentry({ dsn: "", environment: "test", release: "0.0.0" });
    expect(r.enabled).toBe(false);
  });

  it("initSentry returns { enabled: false } when dsn is undefined", () => {
    const r = initSentry({ environment: "test", release: "0.0.0" });
    expect(r.enabled).toBe(false);
  });

  it("initSentry returns { enabled: true } when DSN is set (schedules async load)", () => {
    const r = initSentry({
      dsn: "https://public@sentry.example.com/1",
      environment: "prod",
      release: "1.0.0",
    });
    expect(r.enabled).toBe(true);
  });

  it("isEnabled reflects the last init call", () => {
    initSentry({ environment: "test" });
    expect(isEnabled()).toBe(false);
    initSentry({ dsn: "https://public@sentry.example.com/1", environment: "test" });
    expect(isEnabled()).toBe(true);
  });

  it("captureError is a no-op when Sentry is not initialised", () => {
    // just must not throw
    expect(() => captureError(new Error("boom"))).not.toThrow();
  });

  it("captureError accepts a string message", () => {
    expect(() => captureError("string message")).not.toThrow();
  });

  it("initSentry sanitises DSN to boolean — does not leak the DSN in return value", () => {
    const r = initSentry({ dsn: "https://public@sentry.example.com/1", environment: "prod" });
    // Return should not expose the DSN string to callers (prevents accidental logging)
    expect(JSON.stringify(r)).not.toContain("public@sentry.example.com");
  });
});
