/**
 * Sentry frontend wrapper — ATW M2 (GH#785 follow-up, R106 Free-Tier).
 *
 * Design goals:
 *   - Zero cost when SENTRY_DSN is missing (no bundle load, no network).
 *   - Optional: only calls into @sentry/browser if the package resolves at runtime.
 *   - Never leaks the DSN through public API.
 *
 * Wire-up:
 *   In src/main.tsx (before render):
 *     import { initSentry } from "./sentry";
 *     initSentry({
 *       dsn: import.meta.env.VITE_SENTRY_DSN,
 *       environment: import.meta.env.MODE,
 *       release: import.meta.env.VITE_APP_VERSION,
 *     });
 *
 *   Anywhere in the app:
 *     import { captureError } from "./sentry";
 *     try { ... } catch (e) { captureError(e); throw e; }
 */

export interface SentryInitOptions {
  dsn?: string;
  environment?: string;
  release?: string;
  /** Sample rate for errors (0.0 - 1.0), default 1.0 */
  tracesSampleRate?: number;
}

export interface SentryInitResult {
  enabled: boolean;
  /** Set only if enabled — the environment tag applied. Never contains the DSN. */
  environment?: string;
}

interface InternalState {
  enabled: boolean;
  client?: unknown;
}

function getState(): InternalState {
  const g = globalThis as any;
  if (!g.__ATW_SENTRY_STATE__) {
    g.__ATW_SENTRY_STATE__ = { enabled: false } as InternalState;
  }
  return g.__ATW_SENTRY_STATE__ as InternalState;
}

/**
 * Initialise Sentry. Called once at app boot.
 * Returns { enabled } — never exposes the DSN through the return value.
 */
export function initSentry(opts: SentryInitOptions = {}): SentryInitResult {
  const state = getState();
  const dsn = opts.dsn;

  if (!dsn || !dsn.startsWith("https://")) {
    state.enabled = false;
    return { enabled: false };
  }

  state.enabled = true;
  // Async-load the actual SDK — if @sentry/browser is not installed, this
  // fails silently and we operate as a no-op (initSentry() still returns enabled=true
  // because DSN was provided; captureError() will just log to console until SDK loads).
  //
  // We use dynamic import so bundlers don't include @sentry/browser when unused.
  void (async () => {
    try {
      const mod = await import(/* @vite-ignore */ "@sentry/browser");
      const Sentry = (mod as any).default ?? mod;
      Sentry.init({
        dsn,
        environment: opts.environment,
        release: opts.release,
        tracesSampleRate: opts.tracesSampleRate ?? 0.1,
      });
      state.client = Sentry;
    } catch {
      // @sentry/browser not installed — remain in fallback mode
    }
  })();

  return { enabled: true, environment: opts.environment };
}

/**
 * Capture an error. Safe to call whether Sentry is initialised or not.
 * If Sentry is loaded, forwards to Sentry.captureException. Otherwise falls
 * back to console.error (so the developer still sees the error locally).
 */
export function captureError(err: unknown): void {
  const state = getState();
  const client = state.client as any;

  if (client && typeof client.captureException === "function") {
    try {
      if (err instanceof Error) {
        client.captureException(err);
      } else {
        client.captureMessage(String(err), "error");
      }
      return;
    } catch {
      // Sentry failure must not crash the app — fall through to console
    }
  }

  // Fallback: local console (production users won't see this, but Chrome DevTools does)
  // eslint-disable-next-line no-console
  console.error("[atw/sentry-fallback]", err);
}

export function isEnabled(): boolean {
  return getState().enabled;
}
