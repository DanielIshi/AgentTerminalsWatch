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

## LEGAL Launch-Gate

**LIVE payments are blocked until ALL of the following are cleared:**

- [ ] **AGB (Terms of Service)** updated to include subscription billing terms,
      cancellation policy (14-day EU statutory withdrawal right for digital services),
      and auto-renewal disclosure.
- [ ] **Datenschutzerklärung (Privacy Policy)** updated: Stripe listed as payment
      processor under Art. 28 DSGVO (Auftragsverarbeitungsvertrag with Stripe).
- [ ] **Impressum** updated: add legal notice about subscription pricing and
      right of withdrawal.
- [ ] **Stripe DPA (Data Processing Agreement)** signed via Stripe Dashboard
      (Settings → Legal → Data Processing Agreement).
- [ ] **Stripe Compliance Checklist** completed:
      [https://docs.stripe.com/get-started/checklist/go-live](https://docs.stripe.com/get-started/checklist/go-live)
- [ ] **LEGAL team sign-off** in Notion (GH#709 LEGAL Launch-Gate task).
- [ ] Daniel explicit approval for sk_live_ key deployment.

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
