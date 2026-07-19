"""R145 TDD — stripe_webhook handler unit tests.

Tests cover:
  - invalid signature → 400
  - valid signature + checkout.session.completed → DB upsert with tier + sso_enabled
  - valid signature + customer.subscription.updated → DB status update
  - valid signature + customer.subscription.deleted → DB status=canceled
  - valid signature + invoice.payment_succeeded → DB current_period_end updated
  - valid signature + invoice.payment_failed → DB status=past_due
  - unknown event type → 200 + logged (no crash)
  - overage cap email triggered at 2x tier limit on invoice.payment_succeeded
  - overage cap email NOT triggered below 2x limit
  - DB schema has all required columns
  - sso_enabled=True only for enterprise tier subscriptions
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import stripe_webhook as wh


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "subscriptions.db"
    wh.init_db(p)
    return p


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET_TEST", "whsec_testkey")
    monkeypatch.setattr(wh, "_get_db_path", lambda: db_path)
    return TestClient(wh.app)


def _make_event(event_type: str, data: dict) -> dict:
    return {
        "id": f"evt_test_{event_type.replace('.', '_')}",
        "type": event_type,
        "data": {"object": data},
        "created": int(time.time()),
    }


def _post_event(client, event: dict, secret: str = "whsec_testkey"):
    payload = json.dumps(event).encode()
    # Build a mock Stripe-Signature header
    ts = int(time.time())
    sig = f"t={ts},v1=fakesig"
    return client.post(
        "/webhooks/stripe",
        content=payload,
        headers={
            "stripe-signature": sig,
            "content-type": "application/json",
        },
    )


# ── 1. Signature verification ─────────────────────────────────────────────────

def test_invalid_signature_returns_400(client, monkeypatch):
    """Invalid Stripe signature must return 400."""
    monkeypatch.setattr(
        wh.stripe.Webhook,
        "construct_event",
        MagicMock(side_effect=wh.stripe.SignatureVerificationError("bad sig", "sig_header")),
    )
    resp = client.post(
        "/webhooks/stripe",
        content=b'{"type":"test"}',
        headers={"stripe-signature": "t=0,v1=badsig", "content-type": "application/json"},
    )
    assert resp.status_code == 400


# ── 2. checkout.session.completed ────────────────────────────────────────────

def test_checkout_completed_upserts_subscription(client, db_path, monkeypatch):
    event_data = {
        "customer": "cus_test123",
        "subscription": "sub_test123",
        "client_reference_id": "user_42",
        "metadata": {"tier": "solo"},
        "mode": "subscription",
    }
    event = _make_event("checkout.session.completed", event_data)

    monkeypatch.setattr(
        wh.stripe.Webhook,
        "construct_event",
        MagicMock(return_value=event),
    )
    # Mock subscription retrieval
    mock_sub = MagicMock()
    mock_sub.status = "active"
    mock_sub.current_period_end = int(time.time()) + 2592000
    mock_sub.metadata = {"atw_tier": "solo"}
    monkeypatch.setattr(wh.stripe.Subscription, "retrieve", MagicMock(return_value=mock_sub))

    resp = _post_event(client, event)
    assert resp.status_code == 200

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT user_id, stripe_customer_id, tier, status FROM subscriptions WHERE stripe_subscription_id=?",
        ("sub_test123",),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "user_42"
    assert row[1] == "cus_test123"
    assert row[2] == "solo"
    assert row[3] == "active"


def test_checkout_completed_enterprise_sets_sso(client, db_path, monkeypatch):
    event_data = {
        "customer": "cus_ent",
        "subscription": "sub_ent",
        "client_reference_id": "user_99",
        "metadata": {"tier": "enterprise"},
        "mode": "subscription",
    }
    event = _make_event("checkout.session.completed", event_data)
    monkeypatch.setattr(wh.stripe.Webhook, "construct_event", MagicMock(return_value=event))

    mock_sub = MagicMock()
    mock_sub.status = "active"
    mock_sub.current_period_end = int(time.time()) + 2592000
    mock_sub.metadata = {"atw_tier": "enterprise"}
    monkeypatch.setattr(wh.stripe.Subscription, "retrieve", MagicMock(return_value=mock_sub))

    resp = _post_event(client, event)
    assert resp.status_code == 200

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT sso_enabled FROM subscriptions WHERE stripe_subscription_id=?",
        ("sub_ent",),
    ).fetchone()
    conn.close()
    assert row[0] == 1  # True


def test_checkout_completed_solo_no_sso(client, db_path, monkeypatch):
    event_data = {
        "customer": "cus_solo",
        "subscription": "sub_solo_nosso",
        "client_reference_id": "user_77",
        "metadata": {"tier": "solo"},
        "mode": "subscription",
    }
    event = _make_event("checkout.session.completed", event_data)
    monkeypatch.setattr(wh.stripe.Webhook, "construct_event", MagicMock(return_value=event))

    mock_sub = MagicMock()
    mock_sub.status = "active"
    mock_sub.current_period_end = int(time.time()) + 2592000
    mock_sub.metadata = {"atw_tier": "solo"}
    monkeypatch.setattr(wh.stripe.Subscription, "retrieve", MagicMock(return_value=mock_sub))

    _post_event(client, event)

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT sso_enabled FROM subscriptions WHERE stripe_subscription_id=?",
        ("sub_solo_nosso",),
    ).fetchone()
    conn.close()
    assert row[0] == 0  # False


# ── 3. customer.subscription.updated ─────────────────────────────────────────

def test_subscription_updated_changes_status(client, db_path, monkeypatch):
    # Pre-seed DB
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO subscriptions (user_id, stripe_customer_id, stripe_subscription_id, tier, status, current_period_end, sso_enabled) VALUES (?,?,?,?,?,?,?)",
        ("user_1", "cus_1", "sub_upd", "team", "active", 9999999, 0),
    )
    conn.commit()
    conn.close()

    event_data = {
        "id": "sub_upd",
        "customer": "cus_1",
        "status": "past_due",
        "current_period_end": 8888888,
        "metadata": {"atw_tier": "team"},
    }
    event = _make_event("customer.subscription.updated", event_data)
    monkeypatch.setattr(wh.stripe.Webhook, "construct_event", MagicMock(return_value=event))

    resp = _post_event(client, event)
    assert resp.status_code == 200

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status, current_period_end FROM subscriptions WHERE stripe_subscription_id=?",
        ("sub_upd",),
    ).fetchone()
    conn.close()
    assert row[0] == "past_due"
    assert row[1] == 8888888


# ── 4. customer.subscription.deleted ─────────────────────────────────────────

def test_subscription_deleted_sets_canceled(client, db_path, monkeypatch):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO subscriptions (user_id, stripe_customer_id, stripe_subscription_id, tier, status, current_period_end, sso_enabled) VALUES (?,?,?,?,?,?,?)",
        ("user_2", "cus_2", "sub_del", "solo", "active", 9999999, 0),
    )
    conn.commit()
    conn.close()

    event_data = {"id": "sub_del", "customer": "cus_2", "metadata": {}}
    event = _make_event("customer.subscription.deleted", event_data)
    monkeypatch.setattr(wh.stripe.Webhook, "construct_event", MagicMock(return_value=event))

    resp = _post_event(client, event)
    assert resp.status_code == 200

    conn = sqlite3.connect(db_path)
    status = conn.execute(
        "SELECT status FROM subscriptions WHERE stripe_subscription_id=?", ("sub_del",)
    ).fetchone()[0]
    conn.close()
    assert status == "canceled"


# ── 5. invoice.payment_succeeded ─────────────────────────────────────────────

def test_invoice_payment_succeeded_updates_period(client, db_path, monkeypatch):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO subscriptions (user_id, stripe_customer_id, stripe_subscription_id, tier, status, current_period_end, sso_enabled) VALUES (?,?,?,?,?,?,?)",
        ("user_3", "cus_3", "sub_inv", "team", "active", 1000, 0),
    )
    conn.commit()
    conn.close()

    new_period_end = int(time.time()) + 2592000
    event_data = {
        "subscription": "sub_inv",
        "customer": "cus_3",
        "lines": {"data": [{"period": {"end": new_period_end}}]},
        "metadata": {},
    }
    event = _make_event("invoice.payment_succeeded", event_data)
    monkeypatch.setattr(wh.stripe.Webhook, "construct_event", MagicMock(return_value=event))

    with patch.object(wh, "_check_overage_and_notify") as mock_overage:
        mock_overage.return_value = None
        resp = _post_event(client, event)

    assert resp.status_code == 200
    conn = sqlite3.connect(db_path)
    end = conn.execute(
        "SELECT current_period_end FROM subscriptions WHERE stripe_subscription_id=?", ("sub_inv",)
    ).fetchone()[0]
    conn.close()
    assert end == new_period_end


# ── 6. invoice.payment_failed ────────────────────────────────────────────────

def test_invoice_payment_failed_sets_past_due(client, db_path, monkeypatch):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO subscriptions (user_id, stripe_customer_id, stripe_subscription_id, tier, status, current_period_end, sso_enabled) VALUES (?,?,?,?,?,?,?)",
        ("user_4", "cus_4", "sub_fail", "solo", "active", 9999, 0),
    )
    conn.commit()
    conn.close()

    event_data = {"subscription": "sub_fail", "customer": "cus_4", "metadata": {}}
    event = _make_event("invoice.payment_failed", event_data)
    monkeypatch.setattr(wh.stripe.Webhook, "construct_event", MagicMock(return_value=event))

    resp = _post_event(client, event)
    assert resp.status_code == 200

    conn = sqlite3.connect(db_path)
    status = conn.execute(
        "SELECT status FROM subscriptions WHERE stripe_subscription_id=?", ("sub_fail",)
    ).fetchone()[0]
    conn.close()
    assert status == "past_due"


# ── 7. Unknown event ──────────────────────────────────────────────────────────

def test_unknown_event_returns_200(client, monkeypatch):
    event = _make_event("some.unknown.event", {"foo": "bar"})
    monkeypatch.setattr(wh.stripe.Webhook, "construct_event", MagicMock(return_value=event))
    resp = _post_event(client, event)
    assert resp.status_code == 200


# ── 8. Overage cap ───────────────────────────────────────────────────────────

def test_overage_cap_email_triggered_above_2x_limit(monkeypatch):
    """_check_overage_and_notify must call send_overage_email when usage > 2x limit."""
    with patch.object(wh, "send_overage_email") as mock_email:
        wh._check_overage_and_notify(
            subscription_id="sub_x",
            tier="solo",
            usage_count=11,  # 2x solo limit (5) = 10 → 11 triggers
        )
        mock_email.assert_called_once()


def test_overage_cap_email_not_triggered_below_2x_limit(monkeypatch):
    """_check_overage_and_notify must NOT send email when usage <= 2x limit."""
    with patch.object(wh, "send_overage_email") as mock_email:
        wh._check_overage_and_notify(
            subscription_id="sub_y",
            tier="solo",
            usage_count=10,  # exactly 2x limit — not over
        )
        mock_email.assert_not_called()


# ── 9. DB schema ──────────────────────────────────────────────────────────────

def test_db_schema_has_required_columns(db_path):
    conn = sqlite3.connect(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(subscriptions)")}
    conn.close()
    required = {
        "user_id", "stripe_customer_id", "stripe_subscription_id",
        "tier", "status", "current_period_end", "sso_enabled",
    }
    assert required.issubset(cols), f"Missing columns: {required - cols}"
