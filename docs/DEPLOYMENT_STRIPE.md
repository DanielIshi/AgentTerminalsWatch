# ATW Stripe Integration — Deployment Guide

> STATUS: TEST-MODE ONLY. Live payments blocked pending LEGAL Launch-Gate.
> See "LEGAL Launch-Gate" section below before switching to live keys.

---

## Overview

AgentTerminalsWatch uses Stripe Billing for subscription management.

| Tier       | Monthly | Annual (20% off) | Agents | SSO |
|------------|---------|------------------|--------|-----|
| Solo       | €19     | €182.40/yr       | 5      | No  |
| Team       | €49     | €470.40/yr       | 25     | No  |
| Enterprise | €199    | €1910.40/yr      | 100    | Yes |

Overage cap: soft-limit at 2× the tier's agent count. Customer is warned by
email when usage exceeds this cap; service is not hard-cut.

---

## Environment Variables

| Variable                    | Required | Description                                              |
|-----------------------------|----------|----------------------------------------------------------|
| `STRIPE_SECRET_KEY_TEST`    | YES      | Test-mode secret key (`sk_test_...` or `rk_test_...`)   |
| `STRIPE_WEBHOOK_SECRET_TEST`| YES      | Webhook signing secret from Stripe Dashboard (test mode) |
| `STRIPE_PUBLISHABLE_KEY_TEST`| YES (frontend) | Publishable key for Checkout.js / Elements         |
| `ATW_STATE_DIR`             | No       | Override for `state/` directory (default: repo root)    |

Add these to `/home/claude/clawd/.env` (never commit live keys).

---

## Step 1 — Activate Stripe Test Mode

1. Log into [https://dashboard.stripe.com](https://dashboard.stripe.com)
2. Toggle **"Test mode"** (top-right switch) — ensure it is ON.
3. Go to **Developers → API keys** and copy the Secret key (`sk_test_...`).
4. Set in `.env`:
   ```bash
   STRIPE_SECRET_KEY_TEST=sk_test_YOUR_KEY_HERE
   STRIPE_PUBLISHABLE_KEY_TEST=pk_test_YOUR_KEY_HERE
   ```

---

## Step 2 — Create Products via Script

The setup script is idempotent — safe to run multiple times.

```bash
cd /home/claude/projects/AgentTerminalsWatch
python scripts/stripe_setup_test.py
```

Output is written to `state/stripe/atw_products_test.json`:

```json
{
  "solo": {
    "product_id": "prod_...",
    "price_id_monthly": "price_...",
    "price_id_annual": "price_..."
  },
  "team": { ... },
  "enterprise": { ... }
}
```

The script will **fail loud** if `STRIPE_SECRET_KEY_TEST` is missing or has a
live key prefix — no silent fallback, no mock output.

---

## Step 3 — Register Webhook Endpoint

The webhook handler runs at `POST /webhooks/stripe`.

### 3a. Start the webhook server locally

```bash
uvicorn stripe_webhook:app --host 127.0.0.1 --port 8001
```

### 3b. Expose via ngrok for local testing

```bash
ngrok http 8001
# Copy the HTTPS URL: https://abc123.ngrok.io
```

### 3c. Register in Stripe Dashboard (Test Mode)

1. Go to **Developers → Webhooks → Add endpoint**
2. URL: `https://YOUR_DOMAIN/webhooks/stripe`  
   (example ngrok: `https://abc123.ngrok.io/webhooks/stripe`)
3. Events to select:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. After saving, copy the **Signing secret** (`whsec_...`)
5. Set in `.env`:
   ```bash
   STRIPE_WEBHOOK_SECRET_TEST=whsec_YOUR_SIGNING_SECRET
   ```

### 3d. Stripe CLI (alternative for local dev)

```bash
stripe listen --forward-to localhost:8001/webhooks/stripe
# Outputs: Ready! Your webhook signing secret is whsec_...
```

---

## Test Card Numbers

Use these in Stripe's test mode to simulate payment flows:

| Card Number           | Scenario                        |
|-----------------------|---------------------------------|
| `4242 4242 4242 4242` | Successful payment              |
| `4000 0000 0000 0002` | Card declined                   |
| `4000 0025 0000 3155` | Requires 3D Secure authentication|
| `4000 0000 0000 9995` | Insufficient funds              |
| `4000 0000 0000 0069` | Expired card                    |

Expiry: any future date. CVC: any 3 digits. ZIP: any 5 digits.

Full list: [https://docs.stripe.com/testing#cards](https://docs.stripe.com/testing#cards)

---

## Subscription State DB

Subscriptions are persisted in SQLite at `state/atw/subscriptions.db`.

Schema:

```sql
CREATE TABLE subscriptions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                 TEXT,
    stripe_customer_id      TEXT NOT NULL,
    stripe_subscription_id  TEXT NOT NULL UNIQUE,
    tier                    TEXT NOT NULL,          -- solo|team|enterprise
    status                  TEXT NOT NULL,          -- active|past_due|canceled|...
    current_period_end      INTEGER,               -- Unix timestamp
    sso_enabled             INTEGER NOT NULL DEFAULT 0  -- 1 for enterprise only
);
```

---

## §312j BGB Compliance — Button-Text

**Gesetzliche Pflicht (§312j Abs. 3 BGB — Fernabsatzrecht):**

Der Bestell-Button MUSS exakt beschriftet sein mit:

> **"Zahlungspflichtig bestellen"**

Dieser Text ist im `PaymentButton`-Component als Konstante `BUTTON_TEXT` hinterlegt
(`src/components/PaymentButton.tsx`) und darf NICHT ohne LEGAL-Approval geändert werden.

**LEGAL-Basis:**
- AGB: commit `b52913c75`
- Datenschutz + AVV + Impressum: commit `2686fac85`

**Verbotene Alternativ-Texte (§312j-Verstoß):**
- "Bestellen", "Weiter", "Anmelden", "Jetzt starten", "Buchen"

**CI-Check:**
```bash
bash scripts/check_button_312j.sh   # Exit 0 = clean, Exit 1 = violation
```

---

## §356 BGB Compliance — Widerrufsverzicht-Checkbox

**Gesetzliche Pflicht (§356 Abs. 4/5 BGB i.V.m. §312g BGB):**

Bei sofortigem SaaS-Dienstbeginn (Zugriff direkt nach Bestellung) muss der
Verbraucher AKTIV zustimmen, sein Widerrufsrecht zu verlieren.

**LEGAL-finaler Checkbox-Text (2026-07-19, BGH-konform):**

> "Ich verlange ausdrücklich, dass Sie mit der Ausführung der Dienstleistung
> vor Ablauf der Widerrufsfrist beginnen. Mir ist bekannt, dass mein
> Widerrufsrecht mit vollständiger Vertragserfüllung erlischt."

**Implementation:** `src/components/WithdrawalWaiverCheckbox.tsx`
- Default: **unchecked** (aktive Zustimmung Pflicht — kein Pre-Tick, BGH)
- `PaymentButton` bleibt disabled bis Checkbox aktiv bestätigt
- Bei Bestätigung: `WaiverLogEntry { waiver_accepted_at: ISO, waiver_text_hash: hex }`
  → Stripe-Checkout-Metadata + optional `state/atw/waiver_log.db`

**Text-Quelle:** `atw_rechtsdokumente_paket_2026-07-19.md` §3a (Bratschke Solutions GmbH)

**LEGAL-Snippet-Lieferung (2026-07-19):**
Source: `05_LEGAL/deliverables/atw_widerruf_html_snippet_2026-07-19.md` (LEGAL-approved, Aitava-geprüft).
Eingebettet in `stripe_webhook.py` als `WIDERRUFSBELEHRUNG_HTML` + `MUSTER_WIDERRUFSFORMULAR_HTML`.

---

## LEGAL Launch-Gate

**LIVE payments are blocked until ALL of the following are cleared:**

- [x] **AGB (Terms of Service)** — commit `b52913c75` (inkl. §3a Widerrufsrecht,
      §312g, Kündigung, Datenlöschung 30 Tage, §6 Pane-Screenshots)
- [x] **Datenschutzerklärung** — commit `2686fac85` (Stripe als Verantwortlicher,
      Pane-Screenshot-Retention, AVV)
- [x] **Impressum** — commit `2686fac85`
- [x] **§312j Button-Text** — "Zahlungspflichtig bestellen" implementiert + CI-Check
- [x] **§356 Widerrufsverzicht** — Checkbox implementiert, LEGAL-Text 2026-07-19 final
- [x] **K3: §312f Confirmation-Mail** — send_confirmation_email() in stripe_webhook.py
      implementiert. SMTP via MAIL_INFO_USER/MAIL_INFO_PASS (Fallback: BREVO_API_KEY).
      Enthält Widerrufsbelehrung + Muster-Formular als dauerhaftem Datenträger.
      Log: `state/atw/confirmation_mail_log.jsonl`. Tests T18–T22 grün.
- [x] **K4: §356 Widerrufsbelehrung-Seiten** — Routes `/legal/widerrufsbelehrung` +
      `/legal/muster-widerrufsformular` in stripe_webhook.py implementiert.
      Content: LEGAL-Snippets 1+2 (atw_widerruf_html_snippet_2026-07-19.md).
      PricingPage-Link aktualisiert von `/widerrufsrecht` → `/legal/widerrufsbelehrung`.
      Tests T23–T24 grün.
- [ ] **Stripe DPA (Data Processing Agreement)** signed via Stripe Dashboard
      (Settings → Legal → Data Processing Agreement). **Daniel-Action erforderlich.**
- [ ] **Stripe Compliance Checklist** completed:
      [https://docs.stripe.com/get-started/checklist/go-live](https://docs.stripe.com/get-started/checklist/go-live)
- [ ] **§5 UWG SLA-Wording** in Preisliste geklärt (Variante A/B — LEGAL/Marketing)
- [ ] **LEGAL team sign-off** in Notion (GH#709 LEGAL Launch-Gate task).
- [ ] Daniel explicit approval for sk_live_ key deployment.

### Daniel-Action Items (LEGAL Launch-Gate)
1. `BREVO_API_KEY` in `/home/claude/clawd/.env` eintragen (app.brevo.com/settings/keys/api) — für SMTP-Relay-Fallback
2. Stripe DPA signing im Stripe Dashboard (Settings → Legal)
3. Stripe Compliance Checklist abarbeiten
4. LEGAL sign-off in Notion GH#709

---

## Live Rollout Procedure (sk_test_ → sk_live_)

Only after LEGAL Launch-Gate is fully cleared:

1. In Stripe Dashboard: switch to **Live mode**.
2. Obtain live API keys from **Developers → API keys**.
3. Re-run setup script with live key to create live products:
   ```bash
   STRIPE_SECRET_KEY_TEST=sk_live_... python scripts/stripe_setup_test.py \
     --output state/stripe/atw_products_live.json
   ```
   Note: the script variable name stays `STRIPE_SECRET_KEY_TEST` — update the
   check prefix in `get_test_key()` OR create a separate `stripe_setup_live.py`.
4. Register a new live webhook endpoint in Stripe Dashboard.
5. Update `.env` with live keys:
   ```bash
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_PUBLISHABLE_KEY=pk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_...  (live webhook secret, not test)
   ```
6. Update `stripe_webhook.py` to read `STRIPE_WEBHOOK_SECRET` (not `_TEST`).
7. Deploy with zero-downtime — ensure DB migration if schema changed.
8. Smoke-test with a real card (€0.50 charge + immediate refund).

---

## Running Tests

```bash
cd /home/claude/projects/AgentTerminalsWatch
python -m pytest tests/test_stripe_setup.py tests/test_stripe_webhook.py -v
```

All tests use mocked Stripe API — no live or test-mode API calls are made.
