"""R145 TDD — Sentry backend wrapper (ATW M2).

Contract analog to frontend sentry.ts:
  - init_sentry() without DSN → returns False (disabled, no-op)
  - init_sentry() with DSN → returns True (or attempts SDK load)
  - capture_error() is safe to call whether Sentry is initialised or not
  - Never leaks DSN through any public return value

Backend uses sentry_sdk (Python) — but wrapper degrades gracefully to
console-log if package not installed. Zero cost when SENTRY_DSN missing.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import atw_sentry


@pytest.fixture(autouse=True)
def reset_state():
    atw_sentry._reset_for_test()
    yield
    atw_sentry._reset_for_test()


def test_init_returns_false_without_dsn():
    assert atw_sentry.init_sentry(dsn="") is False
    assert atw_sentry.init_sentry(dsn=None) is False


def test_init_returns_false_for_non_https_dsn():
    assert atw_sentry.init_sentry(dsn="not-a-url") is False


def test_init_returns_true_with_valid_dsn(monkeypatch):
    monkeypatch.setattr(atw_sentry, "_load_sdk", lambda: MagicMock())
    assert atw_sentry.init_sentry(dsn="https://public@sentry.io/1") is True


def test_init_returns_true_even_if_sdk_missing(monkeypatch):
    """If sentry_sdk is not installed, init still returns True (fallback mode)."""
    monkeypatch.setattr(atw_sentry, "_load_sdk", lambda: None)
    assert atw_sentry.init_sentry(dsn="https://public@sentry.io/1") is True


def test_capture_error_does_not_raise_without_init():
    atw_sentry.capture_error(ValueError("boom"))
    # must not raise


def test_capture_error_calls_sdk_when_initialised(monkeypatch):
    fake_sdk = MagicMock()
    monkeypatch.setattr(atw_sentry, "_load_sdk", lambda: fake_sdk)
    atw_sentry.init_sentry(dsn="https://public@sentry.io/1")
    atw_sentry.capture_error(ValueError("boom"))
    fake_sdk.capture_exception.assert_called_once()


def test_capture_error_accepts_string_message(monkeypatch):
    fake_sdk = MagicMock()
    monkeypatch.setattr(atw_sentry, "_load_sdk", lambda: fake_sdk)
    atw_sentry.init_sentry(dsn="https://public@sentry.io/1")
    atw_sentry.capture_error("string message")
    fake_sdk.capture_message.assert_called_once()


def test_is_enabled_reflects_last_init():
    assert atw_sentry.is_enabled() is False
    with patch.object(atw_sentry, "_load_sdk", return_value=MagicMock()):
        atw_sentry.init_sentry(dsn="https://public@sentry.io/1")
    assert atw_sentry.is_enabled() is True


def test_init_does_not_leak_dsn_in_logs(monkeypatch, caplog):
    fake_sdk = MagicMock()
    monkeypatch.setattr(atw_sentry, "_load_sdk", lambda: fake_sdk)
    import logging
    with caplog.at_level(logging.INFO):
        atw_sentry.init_sentry(dsn="https://SECRET_PUBLIC_KEY@sentry.io/1")
    for record in caplog.records:
        assert "SECRET_PUBLIC_KEY" not in record.getMessage()


def test_capture_error_survives_sdk_exception(monkeypatch):
    """If Sentry SDK itself raises, capture_error must not crash."""
    fake_sdk = MagicMock()
    fake_sdk.capture_exception.side_effect = RuntimeError("sentry down")
    monkeypatch.setattr(atw_sentry, "_load_sdk", lambda: fake_sdk)
    atw_sentry.init_sentry(dsn="https://public@sentry.io/1")
    # Must not raise
    atw_sentry.capture_error(ValueError("original"))
