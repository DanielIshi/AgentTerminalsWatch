"""ATW backend Sentry wrapper — M2 (GH#785 follow-up, R106 Free-Tier).

Design goals:
- Zero cost when SENTRY_DSN is missing (no SDK load, no network).
- Optional dependency on sentry_sdk — if not installed, falls back to logger.
- Never leaks the DSN through public return values or log messages.

Wire-up in stripe_webhook.py (top of module):
    import atw_sentry
    atw_sentry.init_sentry(
        dsn=os.environ.get("SENTRY_DSN"),
        environment=os.environ.get("SENTRY_ENV", "prod"),
        release=os.environ.get("ATW_VERSION"),
    )

Anywhere in the backend:
    from atw_sentry import capture_error
    try:
        ...
    except Exception as e:
        capture_error(e)
        raise
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

_STATE: dict[str, Any] = {"enabled": False, "sdk": None}


def _reset_for_test() -> None:
    """Test-only: clear internal state."""
    _STATE["enabled"] = False
    _STATE["sdk"] = None


def _load_sdk() -> Any:
    """Import sentry_sdk lazily. Returns the module or None if not installed."""
    try:
        import sentry_sdk  # type: ignore
        return sentry_sdk
    except ImportError:
        return None


def init_sentry(
    *,
    dsn: str | None = None,
    environment: str | None = None,
    release: str | None = None,
    traces_sample_rate: float = 0.1,
) -> bool:
    """Initialise Sentry. Called once at app boot.

    Returns True if a DSN was provided AND is well-formed (not necessarily that
    the SDK loaded — fallback mode still counts as enabled=True).
    """
    if not dsn or not dsn.startswith("https://"):
        _STATE["enabled"] = False
        _STATE["sdk"] = None
        return False

    _STATE["enabled"] = True

    sdk = _load_sdk()
    if sdk is None:
        log.info("SENTRY: DSN configured but sentry_sdk not installed — running in log-fallback mode")
        return True

    try:
        sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            traces_sample_rate=traces_sample_rate,
        )
        _STATE["sdk"] = sdk
        log.info("SENTRY: initialised (env=%s, release=%s)", environment, release)
    except Exception as e:
        # SDK init failure must not crash the app
        log.error("SENTRY: init failed: %s", type(e).__name__)
        _STATE["sdk"] = None
    return True


def capture_error(err: Any) -> None:
    """Capture an error. Safe to call whether Sentry is initialised or not.

    - If Sentry SDK is loaded: forwards to capture_exception (or capture_message for strings).
    - Otherwise: falls back to logger.error so devs still see it in server logs.
    - SDK exceptions are swallowed to guarantee the caller is never crashed.
    """
    sdk = _STATE.get("sdk")

    if sdk is not None:
        try:
            if isinstance(err, BaseException):
                sdk.capture_exception(err)
            else:
                sdk.capture_message(str(err), level="error")
            return
        except Exception:
            # Sentry itself failed — fall through to logger
            pass

    # Fallback path
    if isinstance(err, BaseException):
        log.error("[atw/sentry-fallback] %s: %s", type(err).__name__, err)
    else:
        log.error("[atw/sentry-fallback] %s", err)


def is_enabled() -> bool:
    return bool(_STATE.get("enabled"))
