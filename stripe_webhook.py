"""ATW Stripe Webhook Handler.

FastAPI endpoint: POST /webhooks/stripe

Verifies Stripe signature, persists subscription state to SQLite, and handles
overage-cap notifications.

Events handled:
  - checkout.session.completed       → upsert subscription row + send §312f confirmation mail
  - customer.subscription.updated    → update status + period_end
  - customer.subscription.deleted    → mark canceled
  - invoice.payment_succeeded        → update period_end + check overage cap
  - invoice.payment_failed           → mark past_due
  - <any other>                      → log + return 200 (Stripe requires 200)

Environment:
  STRIPE_WEBHOOK_SECRET_TEST  — required for signature verification
  ATW_STATE_DIR               — optional override for state/ directory
  MAIL_INFO_USER              — SMTP sender (info@agentic-movers.com)
  MAIL_INFO_PASS              — SMTP password
  SMTP_HOST                   — SMTP host (default: mail.boost-my-life.com)
  SMTP_PORT                   — SMTP port (default: 587)

DB: SQLite at state/atw/subscriptions.db
Log: state/atw/confirmation_mail_log.jsonl
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import smtplib
import sqlite3
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from textwrap import dedent
from typing import Any

import stripe
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

import atw_sentry

logger = logging.getLogger(__name__)

# M2: Sentry init. No-op if SENTRY_DSN not set (zero cost, no SDK load).
atw_sentry.init_sentry(
    dsn=os.environ.get("SENTRY_DSN"),
    environment=os.environ.get("SENTRY_ENV", "prod"),
    release=os.environ.get("ATW_VERSION"),
)

# ── §312f Legal Texts (from LEGAL deliverable atw_widerruf_html_snippet_2026-07-19.md) ──

WIDERRUFSBELEHRUNG_HTML = dedent("""\
    <section class="widerrufsbelehrung" aria-label="Widerrufsbelehrung">
      <h2>Widerrufsbelehrung</h2>
      <h3>Widerrufsrecht</h3>
      <p>Sie haben das Recht, binnen vierzehn Tagen ohne Angabe von Gr&#252;nden diesen Vertrag zu
      widerrufen. Die Widerrufsfrist betr&#228;gt vierzehn Tage ab dem Tag des Vertragsschlusses.</p>
      <p>Um Ihr Widerrufsrecht auszu&#252;ben, m&#252;ssen Sie uns (Bratschke Solutions GmbH,
      Paul-Zobel-Str. 3, 10367 Berlin, E-Mail: info@agentic-movers.com) mittels einer eindeutigen
      Erkl&#228;rung (z.&#160;B. ein mit der Post versandter Brief oder eine E-Mail) &#252;ber Ihren
      Entschluss, diesen Vertrag zu widerrufen, informieren. Sie k&#246;nnen daf&#252;r das beigef&#252;gte
      Muster-Widerrufsformular verwenden, das jedoch nicht vorgeschrieben ist.</p>
      <p>Zur Wahrung der Widerrufsfrist reicht es aus, dass Sie die Mitteilung &#252;ber die Aus&#252;bung
      des Widerrufsrechts vor Ablauf der Widerrufsfrist absenden.</p>
      <h3>Folgen des Widerrufs</h3>
      <p>Wenn Sie diesen Vertrag widerrufen, haben wir Ihnen alle Zahlungen, die wir von Ihnen
      erhalten haben, unverz&#252;glich und sp&#228;testens binnen vierzehn Tagen ab dem Tag zur&#252;ckzuzahlen,
      an dem die Mitteilung &#252;ber Ihren Widerruf dieses Vertrags bei uns eingegangen ist. F&#252;r diese
      R&#252;ckzahlung verwenden wir dasselbe Zahlungsmittel, das Sie bei der urspr&#252;nglichen Transaktion
      eingesetzt haben, es sei denn, mit Ihnen wurde ausdr&#252;cklich etwas anderes vereinbart.</p>
      <p>Haben Sie verlangt, dass die Dienstleistung w&#228;hrend der Widerrufsfrist beginnen soll, so
      haben Sie uns einen angemessenen Betrag zu zahlen, der dem Anteil der bis zu dem Zeitpunkt,
      zu dem Sie uns von der Aus&#252;bung des Widerrufsrechts hinsichtlich dieses Vertrags unterrichten,
      bereits erbrachten Dienstleistungen im Vergleich zum Gesamtumfang der im Vertrag vorgesehenen
      Dienstleistungen entspricht.</p>
    </section>""")

MUSTER_WIDERRUFSFORMULAR_HTML = dedent("""\
    <section class="muster-widerruf" aria-label="Muster-Widerrufsformular">
      <h3>Muster-Widerrufsformular</h3>
      <p><em>(Wenn Sie den Vertrag widerrufen wollen, f&#252;llen Sie bitte dieses Formular aus und
      senden Sie es zur&#252;ck.)</em></p>
      <ul>
        <li>An: Bratschke Solutions GmbH, Paul-Zobel-Str. 3, 10367 Berlin, E-Mail: info@agentic-movers.com</li>
        <li>Hiermit widerrufe(n) ich/wir (*) den von mir/uns (*) abgeschlossenen Vertrag &#252;ber die
        Erbringung der folgenden Dienstleistung: AgentTerminalsWatch (Tarif: __________)</li>
        <li>Bestellt am (*)/erhalten am (*): __________</li>
        <li>Name des/der Verbraucher(s): __________</li>
        <li>Anschrift des/der Verbraucher(s): __________</li>
        <li>Datum: __________</li>
        <li><small>(*) Unzutreffendes streichen.</small></li>
      </ul>
    </section>""")

WIDERRUFSBELEHRUNG_TEXT = (
    "Widerrufsbelehrung: Sie haben das Recht, binnen vierzehn Tagen ohne Angabe von "
    "Gruenden diesen Vertrag zu widerrufen. Die Widerrufsfrist betraegt vierzehn Tage "
    "ab dem Tag des Vertragsschlusses. Um Ihr Widerrufsrecht auszuueben, muessen Sie uns "
    "(Bratschke Solutions GmbH, Paul-Zobel-Str. 3, 10367 Berlin, info@agentic-movers.com) "
    "mittels einer eindeutigen Erklaerung ueber Ihren Entschluss, diesen Vertrag zu widerrufen, "
    "informieren."
)

MUSTER_FORMULAR_TEXT = (
    "Muster-Widerrufsformular: An Bratschke Solutions GmbH, Paul-Zobel-Str. 3, 10367 Berlin, "
    "info@agentic-movers.com. Hiermit widerrufe(n) ich/wir den von mir/uns abgeschlossenen "
    "Vertrag ueber die Erbringung der folgenden Dienstleistung: AgentTerminalsWatch (Tarif: ___). "
    "Bestellt am: ___ / Name: ___ / Anschrift: ___ / Datum: ___"
)

# ── §312f Confirmation Mail ───────────────────────────────────────────────────

def _get_mail_log_path() -> Path:
    """Return path to confirmation mail log."""
    state_dir = os.environ.get("ATW_STATE_DIR")
    if state_dir:
        base = Path(state_dir)
    else:
        base = Path(__file__).resolve().parent / "state"
    return base / "atw" / "confirmation_mail_log.jsonl"


def _log_confirmation_mail(
    session_id: str,
    email: str,
    sent_at: str,
    waiver_hash: str,
    waiver_version: str,
) -> None:
    """Append one JSON line to confirmation_mail_log.jsonl."""
    log_path = _get_mail_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "session_id": session_id,
        "email": email,
        "sent_at": sent_at,
        "waiver_hash": waiver_hash,
        "waiver_version": waiver_version,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def send_confirmation_email(
    to_email: str,
    session_id: str,
    tier: str,
    amount_total: int | None,
    receipt_url: str | None,
    waiver_accepted_at: str | None,
    waiver_version: str = "2026-07-19",
) -> None:
    """Send §312f confirmation mail including Widerrufsbelehrung on dauerhaftem Datentraeger.

    Uses SMTP credentials from env: MAIL_INFO_USER / MAIL_INFO_PASS / SMTP_HOST / SMTP_PORT.
    Falls back to BREVO_API_KEY SMTP relay if MAIL_INFO_USER is absent.

    Raises RuntimeError if no SMTP credentials are available — fail loud per Daniel-Direktive.
    """
    smtp_user = os.environ.get("MAIL_INFO_USER", "").strip()
    smtp_pass = os.environ.get("MAIL_INFO_PASS", "").strip()
    smtp_host = os.environ.get("SMTP_HOST", "mail.boost-my-life.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    brevo_key = os.environ.get("BREVO_API_KEY", "").strip()

    if not smtp_user and not brevo_key:
        raise RuntimeError(
            "§312f confirmation mail: no SMTP credentials configured. "
            "Set MAIL_INFO_USER+MAIL_INFO_PASS or BREVO_API_KEY in .env"
        )

    # Use Brevo SMTP relay if primary creds absent but BREVO_API_KEY present
    if not smtp_user and brevo_key:
        smtp_user = "apikey"
        smtp_pass = brevo_key
        smtp_host = "smtp-relay.brevo.com"
        smtp_port = 587

    sent_at = datetime.now(timezone.utc).isoformat()
    waiver_text = waiver_accepted_at or "nicht angegeben"
    waiver_hash = hashlib.sha256(
        f"{session_id}:{waiver_text}:{waiver_version}".encode()
    ).hexdigest()

    price_str = f"€{amount_total / 100:.2f}" if amount_total else "siehe Stripe-Rechnung"
    receipt_line = f"Stripe-Rechnung: {receipt_url}" if receipt_url else ""

    waiver_confirmation = (
        f"Sie haben durch aktive Zustimmung am {waiver_accepted_at} auf Ihr Widerrufsrecht "
        f"bei vollstaendiger Vertragserfuellung verzichtet (§ 356 Abs. 4 BGB)."
        if waiver_accepted_at
        else ""
    )

    body_text = dedent(f"""\
        Vielen Dank fuer Ihren Kauf!

        Bestellbestaetigung — AgentTerminalsWatch
        ==========================================
        Tarif: {tier}
        Preis: {price_str}
        {receipt_line}

        {waiver_confirmation}

        ------------------------------------------------------------------
        {WIDERRUFSBELEHRUNG_TEXT}

        ------------------------------------------------------------------
        {MUSTER_FORMULAR_TEXT}
        ------------------------------------------------------------------

        Bei Fragen wenden Sie sich an info@agentic-movers.com.
        Bratschke Solutions GmbH | Paul-Zobel-Str. 3 | 10367 Berlin
    """)

    body_html = dedent(f"""\
        <!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
        <title>Bestellbestaetigung AgentTerminalsWatch</title></head>
        <body style="font-family:sans-serif;max-width:640px;margin:0 auto;">
        <h1>Vielen Dank fuer Ihren Kauf!</h1>
        <h2>Bestellbestaetigung &mdash; AgentTerminalsWatch</h2>
        <table><tr><td><strong>Tarif:</strong></td><td>{tier}</td></tr>
        <tr><td><strong>Preis:</strong></td><td>{price_str}</td></tr>
        {"<tr><td><strong>Rechnung:</strong></td><td><a href='" + receipt_url + "'>" + receipt_url + "</a></td></tr>" if receipt_url else ""}
        </table>
        {("<p><strong>" + waiver_confirmation + "</strong></p>") if waiver_accepted_at else ""}
        <hr>
        {WIDERRUFSBELEHRUNG_HTML}
        <hr>
        {MUSTER_WIDERRUFSFORMULAR_HTML}
        <hr>
        <p style="font-size:12px;color:#666;">
          Bei Fragen: <a href="mailto:info@agentic-movers.com">info@agentic-movers.com</a><br>
          Bratschke Solutions GmbH | Paul-Zobel-Str. 3 | 10367 Berlin
        </p>
        </body></html>
    """)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Bestellbestaetigung AgentTerminalsWatch ({tier})"
    msg["From"] = smtp_user if smtp_user != "apikey" else "info@agentic-movers.com"
    msg["To"] = to_email
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(msg["From"], [to_email], msg.as_string())

    logger.info(
        "§312f confirmation mail sent: session=%s to=%s tier=%s sent_at=%s",
        session_id, to_email, tier, sent_at,
    )
    _log_confirmation_mail(
        session_id=session_id,
        email=to_email,
        sent_at=sent_at,
        waiver_hash=waiver_hash,
        waiver_version=waiver_version,
    )


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
    """Upsert subscription on checkout completion + send §312f confirmation mail."""
    sub_id = obj.get("subscription")
    customer_id = obj.get("customer")
    user_id = obj.get("client_reference_id")
    tier = obj.get("metadata", {}).get("tier", "")
    session_id = obj.get("id", "")
    customer_email = obj.get("customer_details", {}).get("email") or obj.get("customer_email") or ""
    amount_total = obj.get("amount_total")
    receipt_url = None  # filled from invoice if available

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

    # §312f BGB — send confirmation mail on dauerhaftem Datentraeger
    # Includes Widerrufsbelehrung + Muster-Widerrufsformular content (not just links)
    if customer_email:
        waiver_accepted_at = obj.get("metadata", {}).get("waiver_accepted_at")
        try:
            send_confirmation_email(
                to_email=customer_email,
                session_id=session_id,
                tier=tier,
                amount_total=amount_total,
                receipt_url=receipt_url,
                waiver_accepted_at=waiver_accepted_at,
            )
        except Exception as exc:
            # Log but do not raise — DB upsert already succeeded; email failure is
            # non-fatal for the webhook (Stripe must receive 200). Ops must monitor log.
            logger.error(
                "§312f confirmation mail FAILED: session=%s email=%s error=%s",
                session_id, customer_email, exc,
            )
    else:
        logger.warning(
            "checkout.session.completed: no customer_email for session=%s — "
            "§312f confirmation mail NOT sent",
            session_id,
        )


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


def _dispatch_payment_alert(
    *,
    event_type: str,
    subscription_id: str,
    customer_id: str | None = None,
) -> None:
    """Send M3 payment-failure alert to ntfy + telegram.

    Errors are logged and swallowed — webhook MUST return 200 to Stripe.
    """
    import subprocess

    msg = (
        f"[ATW] Stripe {event_type}\n"
        f"subscription: {subscription_id}\n"
        f"customer: {customer_id or '-'}\n"
        f"check: state/atw/subscriptions.db (status=past_due)"
    )
    ntfy_topic = os.environ.get("NTFY_TOPIC_ATW", "atw-payments")
    ntfy_url = os.environ.get("NTFY_URL", "https://ntfy.sh") + f"/{ntfy_topic}"
    try:
        import urllib.request
        req = urllib.request.Request(
            ntfy_url,
            data=msg.encode("utf-8"),
            headers={"Title": "ATW Payment-Failed", "Priority": "high", "Tags": "warning,money"},
        )
        urllib.request.urlopen(req, timeout=5).read()
        logger.info("ntfy dispatched: %s", ntfy_topic)
    except Exception as e:
        logger.error("ntfy dispatch failed: %s", e)

    try:
        subprocess.run(
            ["tg", "--force", msg],
            capture_output=True, timeout=8, check=False,
        )
        logger.info("tg dispatched (force flag for P0)")
    except Exception as e:
        logger.error("tg dispatch failed: %s", e)


def _handle_invoice_payment_failed(obj: dict) -> None:
    """Mark subscription as past_due and dispatch M3 alert (ntfy + tg)."""
    sub_id = obj.get("subscription")
    if sub_id:
        _db_update_status(sub_id, "past_due")
        logger.info("invoice.payment_failed: sub=%s → past_due", sub_id)
        try:
            _dispatch_payment_alert(
                event_type="invoice.payment_failed",
                subscription_id=sub_id,
                customer_id=obj.get("customer"),
            )
        except Exception as e:
            logger.error("alert dispatch failed (webhook still returns 200): %s", e)


# ── K4: §356 Legal Pages ─────────────────────────────────────────────────────

_LEGAL_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — AgentTerminalsWatch</title>
  <style>
    body {{ font-family: sans-serif; max-width: 720px; margin: 40px auto; padding: 0 20px;
           line-height: 1.7; color: #111; }}
    h2, h3 {{ color: #1a1a2e; }}
    ul {{ padding-left: 1.4em; }}
    a {{ color: #7c3aed; }}
    .back {{ margin-top: 32px; font-size: 14px; }}
  </style>
</head>
<body>
{content}
<p class="back"><a href="/">&larr; Zur&#252;ck zur Startseite</a> &nbsp;|&nbsp;
<a href="/agb">AGB</a> &nbsp;|&nbsp;
<a href="/datenschutz">Datenschutz</a> &nbsp;|&nbsp;
<a href="/impressum">Impressum</a></p>
</body>
</html>"""


@app.get("/legal/widerrufsbelehrung", response_class=HTMLResponse)
async def legal_widerrufsbelehrung() -> HTMLResponse:
    """§355/§356 BGB Widerrufsbelehrung — required standalone page (K4 fix).

    Content: LEGAL-approved Snippet 1 (atw_widerruf_html_snippet_2026-07-19.md).
    """
    html = _LEGAL_PAGE_TEMPLATE.format(
        title="Widerrufsbelehrung",
        content=WIDERRUFSBELEHRUNG_HTML,
    )
    return HTMLResponse(content=html, status_code=200)


@app.get("/legal/muster-widerrufsformular", response_class=HTMLResponse)
async def legal_muster_widerrufsformular() -> HTMLResponse:
    """§355 BGB Muster-Widerrufsformular — required standalone page (K4 fix).

    Content: LEGAL-approved Snippet 2 (atw_widerruf_html_snippet_2026-07-19.md).
    """
    html = _LEGAL_PAGE_TEMPLATE.format(
        title="Muster-Widerrufsformular",
        content=MUSTER_WIDERRUFSFORMULAR_HTML,
    )
    return HTMLResponse(content=html, status_code=200)


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


