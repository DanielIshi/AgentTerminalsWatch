"""R145 TDD — §312f Confirmation Mail + K4 Legal Routes (T18–T24).

Tests:
  T18: checkout.session.completed webhook triggers send_confirmation_email (mock SMTP)
  T19: Email body contains Widerrufsbelehrung text (not just URL)
  T20: Email body contains Muster-Widerrufsformular text (not just URL)
  T21: Email body contains Waiver-Bestätigung with ISO timestamp
  T22: confirmation_mail_log.jsonl entry has correct fields
  T23: GET /legal/widerrufsbelehrung returns HTML with snippet content
  T24: GET /legal/muster-widerrufsformular returns HTML with snippet content
"""
from __future__ import annotations

import email as email_lib
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from email.mime.multipart import MIMEMultipart

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import stripe_webhook as wh


def _decode_mime_message(msg_str: str) -> str:
    """Parse MIME message string and return all decoded text parts concatenated."""
    msg = email_lib.message_from_string(msg_str)
    parts = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        payload = part.get_payload(decode=True)
        if payload:
            charset = part.get_content_charset() or "utf-8"
            parts.append(payload.decode(charset, errors="replace"))
    return "\n".join(parts)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "subscriptions.db"
    wh.init_db(p)
    return p


@pytest.fixture
def state_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def client(db_path, state_dir, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET_TEST", "whsec_testkey")
    monkeypatch.setenv("ATW_STATE_DIR", state_dir)
    monkeypatch.setenv("MAIL_INFO_USER", "info@agentic-movers.com")
    monkeypatch.setenv("MAIL_INFO_PASS", "testpassword")
    monkeypatch.setenv("SMTP_HOST", "mail.boost-my-life.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setattr(wh, "_get_db_path", lambda: db_path)
    return TestClient(wh.app)


def _make_checkout_event(
    customer_email: str = "kunde@example.com",
    tier: str = "solo",
    waiver_accepted_at: str | None = "2026-07-19T12:00:00+00:00",
    session_id: str = "cs_test_abc123",
    sub_id: str = "sub_test_xyz",
    amount_total: int = 1900,
) -> dict:
    return {
        "id": f"evt_test_checkout",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "subscription": sub_id,
                "customer": "cus_test_123",
                "client_reference_id": "user_001",
                "customer_details": {"email": customer_email},
                "amount_total": amount_total,
                "metadata": {
                    "tier": tier,
                    **({"waiver_accepted_at": waiver_accepted_at} if waiver_accepted_at else {}),
                },
            }
        },
        "created": int(time.time()),
    }


def _post_event(client, event: dict):
    payload = json.dumps(event).encode()
    ts = int(time.time())
    sig = f"t={ts},v1=fakesig"
    return client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": sig, "content-type": "application/json"},
    )


# ── T18: checkout.session.completed triggers send_confirmation_email ──────────

def test_T18_checkout_completed_sends_email(client, monkeypatch):
    """T18: checkout.session.completed triggers send_confirmation_email with SMTP call."""
    event = _make_checkout_event()

    mock_sub = MagicMock()
    mock_sub.status = "active"
    mock_sub.current_period_end = int(time.time()) + 2592000
    mock_sub.metadata = {}

    sent_calls = []

    def fake_send_email(to_email, session_id, tier, amount_total, receipt_url, waiver_accepted_at, waiver_version="2026-07-19"):
        sent_calls.append({
            "to_email": to_email,
            "session_id": session_id,
            "tier": tier,
            "amount_total": amount_total,
            "waiver_accepted_at": waiver_accepted_at,
        })

    monkeypatch.setattr(wh.stripe.Webhook, "construct_event", lambda *a, **k: event)
    monkeypatch.setattr(wh.stripe.Subscription, "retrieve", lambda *a, **k: mock_sub)
    monkeypatch.setattr(wh, "send_confirmation_email", fake_send_email)

    resp = _post_event(client, event)
    assert resp.status_code == 200
    assert len(sent_calls) == 1
    assert sent_calls[0]["to_email"] == "kunde@example.com"
    assert sent_calls[0]["tier"] == "solo"
    assert sent_calls[0]["amount_total"] == 1900


# ── T19: Email body contains Widerrufsbelehrung text ─────────────────────────

def test_T19_email_body_contains_widerrufsbelehrung(monkeypatch, tmp_path):
    """T19: send_confirmation_email body includes Widerrufsbelehrung full text."""
    monkeypatch.setenv("MAIL_INFO_USER", "info@agentic-movers.com")
    monkeypatch.setenv("MAIL_INFO_PASS", "testpass")
    monkeypatch.setenv("SMTP_HOST", "mail.boost-my-life.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("ATW_STATE_DIR", str(tmp_path))

    captured_messages = []

    class FakeSMTP:
        def __init__(self, host, port): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def ehlo(self): pass
        def starttls(self): pass
        def login(self, user, pw): pass
        def sendmail(self, from_addr, to_addrs, msg_str):
            captured_messages.append(msg_str)

    monkeypatch.setattr(wh.smtplib, "SMTP", FakeSMTP)

    wh.send_confirmation_email(
        to_email="test@example.com",
        session_id="cs_test_T19",
        tier="team",
        amount_total=4900,
        receipt_url=None,
        waiver_accepted_at="2026-07-19T10:00:00+00:00",
    )

    assert len(captured_messages) == 1
    # Decode MIME (base64) to readable text
    decoded = _decode_mime_message(captured_messages[0])
    # Must contain Widerrufsbelehrung content — not just a link
    assert "vierzehn Tagen" in decoded
    assert "Widerrufsrecht" in decoded
    assert "Bratschke Solutions GmbH" in decoded


# ── T20: Email body contains Muster-Widerrufsformular text ───────────────────

def test_T20_email_body_contains_muster_formular(monkeypatch, tmp_path):
    """T20: send_confirmation_email body includes Muster-Widerrufsformular full text."""
    monkeypatch.setenv("MAIL_INFO_USER", "info@agentic-movers.com")
    monkeypatch.setenv("MAIL_INFO_PASS", "testpass")
    monkeypatch.setenv("SMTP_HOST", "mail.boost-my-life.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("ATW_STATE_DIR", str(tmp_path))

    captured_messages = []

    class FakeSMTP:
        def __init__(self, host, port): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def ehlo(self): pass
        def starttls(self): pass
        def login(self, user, pw): pass
        def sendmail(self, from_addr, to_addrs, msg_str):
            captured_messages.append(msg_str)

    monkeypatch.setattr(wh.smtplib, "SMTP", FakeSMTP)

    wh.send_confirmation_email(
        to_email="test@example.com",
        session_id="cs_test_T20",
        tier="solo",
        amount_total=1900,
        receipt_url=None,
        waiver_accepted_at=None,
    )

    assert len(captured_messages) == 1
    decoded = _decode_mime_message(captured_messages[0])
    # Must contain Muster-Widerrufsformular content
    assert "Muster-Widerrufsformular" in decoded
    assert "AgentTerminalsWatch" in decoded
    assert "info@agentic-movers.com" in decoded


# ── T21: Email body contains Waiver-Bestätigung with ISO timestamp ─────────────

def test_T21_email_body_contains_waiver_confirmation_with_timestamp(monkeypatch, tmp_path):
    """T21: Email body contains waiver confirmation text with the ISO timestamp."""
    monkeypatch.setenv("MAIL_INFO_USER", "info@agentic-movers.com")
    monkeypatch.setenv("MAIL_INFO_PASS", "testpass")
    monkeypatch.setenv("SMTP_HOST", "mail.boost-my-life.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("ATW_STATE_DIR", str(tmp_path))

    captured_messages = []

    class FakeSMTP:
        def __init__(self, host, port): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def ehlo(self): pass
        def starttls(self): pass
        def login(self, user, pw): pass
        def sendmail(self, from_addr, to_addrs, msg_str):
            captured_messages.append(msg_str)

    monkeypatch.setattr(wh.smtplib, "SMTP", FakeSMTP)

    waiver_ts = "2026-07-19T12:34:56+00:00"
    wh.send_confirmation_email(
        to_email="test@example.com",
        session_id="cs_test_T21",
        tier="enterprise",
        amount_total=19900,
        receipt_url="https://pay.stripe.com/receipts/test123",
        waiver_accepted_at=waiver_ts,
    )

    assert len(captured_messages) == 1
    decoded = _decode_mime_message(captured_messages[0])
    # Must contain the waiver timestamp
    assert waiver_ts in decoded
    # Must contain § 356 reference
    assert "356" in decoded


# ── T22: confirmation_mail_log.jsonl entry with correct fields ────────────────

def test_T22_confirmation_mail_log_entry(monkeypatch, tmp_path):
    """T22: After send_confirmation_email, log entry has session_id, email, sent_at, waiver_hash, waiver_version."""
    monkeypatch.setenv("MAIL_INFO_USER", "info@agentic-movers.com")
    monkeypatch.setenv("MAIL_INFO_PASS", "testpass")
    monkeypatch.setenv("SMTP_HOST", "mail.boost-my-life.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("ATW_STATE_DIR", str(tmp_path))

    class FakeSMTP:
        def __init__(self, host, port): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def ehlo(self): pass
        def starttls(self): pass
        def login(self, user, pw): pass
        def sendmail(self, *a): pass

    monkeypatch.setattr(wh.smtplib, "SMTP", FakeSMTP)

    wh.send_confirmation_email(
        to_email="logtest@example.com",
        session_id="cs_test_T22",
        tier="solo",
        amount_total=1900,
        receipt_url=None,
        waiver_accepted_at="2026-07-19T08:00:00+00:00",
        waiver_version="2026-07-19",
    )

    log_path = Path(tmp_path) / "atw" / "confirmation_mail_log.jsonl"
    assert log_path.exists(), "confirmation_mail_log.jsonl must be created"

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])

    assert entry["session_id"] == "cs_test_T22"
    assert entry["email"] == "logtest@example.com"
    assert "sent_at" in entry and entry["sent_at"]
    assert "waiver_hash" in entry and len(entry["waiver_hash"]) == 64  # sha256 hex
    assert entry["waiver_version"] == "2026-07-19"


# ── T23: /legal/widerrufsbelehrung returns HTML with snippet content ──────────

def test_T23_legal_widerrufsbelehrung_route(client):
    """T23: GET /legal/widerrufsbelehrung returns 200 HTML with Snippet 1 content."""
    resp = client.get("/legal/widerrufsbelehrung")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    body = resp.text
    # Must contain actual Widerrufsbelehrung text from LEGAL snippet
    assert "vierzehn Tagen" in body
    assert "Widerrufsrecht" in body
    assert "Bratschke Solutions GmbH" in body
    assert "Paul-Zobel-Str" in body
    # Must NOT be a placeholder
    assert "TODO" not in body
    assert "placeholder" not in body.lower()


# ── T24: /legal/muster-widerrufsformular returns HTML with snippet content ────

def test_T24_legal_muster_widerrufsformular_route(client):
    """T24: GET /legal/muster-widerrufsformular returns 200 HTML with Snippet 2 content."""
    resp = client.get("/legal/muster-widerrufsformular")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    body = resp.text
    # Must contain Muster-Widerrufsformular content from LEGAL snippet
    assert "Muster-Widerrufsformular" in body
    assert "AgentTerminalsWatch" in body
    assert "info@agentic-movers.com" in body
    assert "Bratschke Solutions GmbH" in body
    # Must NOT be a placeholder
    assert "TODO" not in body
    assert "placeholder" not in body.lower()
