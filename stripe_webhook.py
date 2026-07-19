"""ATW Stripe Webhook Handler.

FastAPI endpoint: POST /webhooks/stripe

Verifies Stripe signature, persists subscription state to SQLite, and handles
overage-cap notifications.

Events handled:
  - checkout.session.completed       → upsert subscription row
  - customer.subscription.updated    → update status + period_end
  - customer.subscription.deleted    → mark canceled
  - invoice.payment_succeeded        → update period_end + check overage cap
  - invoice.payment_failed           → mark past_due
  - <any other>                      → log + return 200 (Stripe requires 200)

Environment:
  STRIPE_WEBHOOK_SECRET_TEST  — required for signature verification
  ATW_STATE_DIR               — optional override for state/ directory

DB: SQLite at state/atw/subscriptions.db
"""
from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

import stripe
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="ATW Stripe Webhook", version="0.1.0", lifespan=lifespan)

# ── Tier limits (for overage cap calculation) ─────────────────────────────────

TIER_LIMITS: dict[str, int] = {
    "solo": 5,
    "team": 25,
    "enterprise": 100,
}

SSO_TIERS = {"enterprise"}


# ── DB Setup ──────────────────────────────────────────────────────────────────

def _get_db_path() -> Path:
    """Return path to subscriptions SQLite DB."""
    state_dir = os.environ.get("ATW_STATE_DIR")
    if state_dir:
        base = Path(state_dir)
    else:
        base = Path(__file__).resolve().parent / "state"
    return base / "atw" / "subscriptions.db"


def init_db(db_path: Path | None = None) -> None:
    """Create subscriptions table if it does not exist."""
    if db_path is None:
        db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id                 TEXT,
            stripe_customer_id      TEXT NOT NULL,
            stripe_subscription_id  TEXT NOT NULL UNIQUE,
            tier                    TEXT NOT NULL,
            status                  TEXT NOT NULL,
            current_period_end      INTEGER,
            sso_enabled             INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def _db_upsert(sub_id: str, fields: dict) -> None:
    """Insert or update a subscription row."""
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    existing = conn.execute(
        "SELECT id FROM subscriptions WHERE stripe_subscription_id=?", (sub_id,)
    ).fetchone()
    if existing:
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [sub_id]
        conn.execute(
            f"UPDATE subscriptions SET {set_clause} WHERE stripe_subscription_id=?",
            values,
        )
    else:
        fields["stripe_subscription_id"] = sub_id
        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        conn.execute(
            f"INSERT INTO subscriptions ({cols}) VALUES ({placeholders})",
            list(fields.values()),
        )
    conn.commit()
    conn.close()


def _db_update_status(sub_id: str, status: str) -> None:
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE subscriptions SET status=? WHERE stripe_subscription_id=?",
        (status, sub_id),
    )
    conn.commit()
    conn.close()


def _db_update_period_end(sub_id: str, period_end: int) -> None:
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE subscriptions SET current_period_end=? WHERE stripe_subscription_id=?",
        (period_end, sub_id),
    )
    conn.commit()
    conn.close()


# ── Overage Cap ───────────────────────────────────────────────────────────────

def send_overage_email(subscription_id: str, tier: str, usage_count: int, limit: int) -> None:
    """Send overage warning email to customer.

    In production, wire this to your email provider (e.g. Brevo, Resend).
    Currently logs the event — implementation pending email-tool integration.
    """
    logger.warning(
        "[OVERAGE] sub=%s tier=%s usage=%d cap=%d — sending overage email",
        subscription_id, tier, usage_count, limit * 2,
    )
    # TODO: integrate with shared email-tool (Brevo/Resend)
    # send_email(customer_email, subject="Agent limit warning", ...)


def _check_overage_and_notify(
    subscription_id: str, tier: str, usage_count: int
) -> None:
    """Check if usage exceeds 2x tier limit and trigger email if so."""
    limit = TIER_LIMITS.get(tier, 0)
    if limit > 0 and usage_count > limit * 2:
        send_overage_email(subscription_id, tier, usage_count, limit)


# ── Event Handlers ────────────────────────────────────────────────────────────

def _handle_checkout_completed(obj: dict) -> None:
    """Upsert subscription on checkout completion."""
    sub_id = obj.get("subscription")
    customer_id = obj.get("customer")
    user_id = obj.get("client_reference_id")
    tier = obj.get("metadata", {}).get("tier", "")

    if not sub_id:
        logger.warning("checkout.session.completed: no subscription field, skipping")
        return

    # Retrieve subscription to get accurate status + period_end
    sub = stripe.Subscription.retrieve(sub_id)
    status = sub.status
    period_end = sub.current_period_end

    # Derive tier from subscription metadata if not in session metadata
    if not tier:
        tier = sub.metadata.get("atw_tier", "")

    sso_enabled = 1 if tier in SSO_TIERS else 0

    _db_upsert(
        sub_id,
        {
            "user_id": user_id,
            "stripe_customer_id": customer_id,
            "tier": tier,
            "status": status,
            "current_period_end": period_end,
            "sso_enabled": sso_enabled,
        },
    )
    logger.info("checkout.session.completed: upserted sub=%s tier=%s status=%s", sub_id, tier, status)


def _handle_subscription_updated(obj: dict) -> None:
    """Update subscription status and period_end."""
    sub_id = obj.get("id")
    status = obj.get("status")
    period_end = obj.get("current_period_end")

    if sub_id and status:
        _db_upsert(
            sub_id,
            {
                "stripe_customer_id": obj.get("customer", ""),
                "status": status,
                "current_period_end": period_end,
                "tier": obj.get("metadata", {}).get("atw_tier", ""),
            },
        )
        logger.info("customer.subscription.updated: sub=%s status=%s", sub_id, status)


def _handle_subscription_deleted(obj: dict) -> None:
    """Mark subscription as canceled."""
    sub_id = obj.get("id")
    if sub_id:
        _db_update_status(sub_id, "canceled")
        logger.info("customer.subscription.deleted: sub=%s → canceled", sub_id)


def _handle_invoice_payment_succeeded(obj: dict) -> None:
    """Update period_end and check overage cap."""
    sub_id = obj.get("subscription")
    if not sub_id:
        return

    # Extract new period_end from invoice lines
    lines = obj.get("lines", {}).get("data", [])
    period_end = None
    if lines:
        period_end = lines[0].get("period", {}).get("end")

    if period_end:
        _db_update_period_end(sub_id, period_end)

    # Overage cap check — usage_count would come from your metrics store.
    # For now, we retrieve tier from DB and let caller inject usage if needed.
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT tier FROM subscriptions WHERE stripe_subscription_id=?", (sub_id,)
    ).fetchone()
    conn.close()

    if row:
        tier = row[0]
        # TODO: fetch actual usage_count from metrics store
        usage_count = 0  # placeholder — real impl reads from usage DB
        _check_overage_and_notify(sub_id, tier, usage_count)

    logger.info("invoice.payment_succeeded: sub=%s period_end=%s", sub_id, period_end)


def _handle_invoice_payment_failed(obj: dict) -> None:
    """Mark subscription as past_due."""
    sub_id = obj.get("subscription")
    if sub_id:
        _db_update_status(sub_id, "past_due")
        logger.info("invoice.payment_failed: sub=%s → past_due", sub_id)


# ── Webhook Endpoint ──────────────────────────────────────────────────────────

EVENT_HANDLERS = {
    "checkout.session.completed": _handle_checkout_completed,
    "customer.subscription.updated": _handle_subscription_updated,
    "customer.subscription.deleted": _handle_subscription_deleted,
    "invoice.payment_succeeded": _handle_invoice_payment_succeeded,
    "invoice.payment_failed": _handle_invoice_payment_failed,
}


@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request) -> Response:
    """Receive and process Stripe webhook events.

    Verifies signature via STRIPE_WEBHOOK_SECRET_TEST.
    Returns 200 for all known + unknown events (Stripe requirement).
    Returns 400 for invalid signature.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET_TEST", "")

    if not webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET_TEST not set — cannot verify signatures")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.SignatureVerificationError as exc:
        logger.warning("Stripe signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    event_type = event["type"]
    obj = event["data"]["object"]

    handler = EVENT_HANDLERS.get(event_type)
    if handler:
        handler(obj)
    else:
        logger.info("Unhandled Stripe event type: %s — ignoring (returning 200)", event_type)

    return Response(content='{"received": true}', media_type="application/json", status_code=200)


