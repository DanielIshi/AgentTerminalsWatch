"""ATW Stripe Test-Mode Setup Script.

Creates Products and Prices in Stripe TEST MODE for AgentTerminalsWatch billing tiers.

REQUIRES: STRIPE_SECRET_KEY_TEST env var with sk_test_ or rk_test_ prefix.
FAILS LOUD if only a live key is available — no fallback, no mock, no silent skip.

Idempotent: detects existing products via metadata.atw_tier and skips/updates
instead of creating duplicates.

Output: state/stripe/atw_products_test.json

Usage:
    python scripts/stripe_setup_test.py [--output PATH]

Environment:
    STRIPE_SECRET_KEY_TEST  — required, sk_test_ or rk_test_ prefix
    ATW_STATE_DIR           — optional, overrides default state/ directory path
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import stripe

# ── Tier Configuration ────────────────────────────────────────────────────────

# Pricing in Euro cents (1 EUR = 100 cents).
# Annual = monthly * 12 * 0.80 (20% discount)
#
# Solo:       €19/mo  | €182.40/yr
# Team:       €49/mo  | €470.40/yr
# Enterprise: €199/mo | €1910.40/yr

TIER_CONFIG: dict[str, dict] = {
    "solo": {
        "name": "ATW Solo",
        "description": "AgentTerminalsWatch — Solo plan (up to 5 agents monitored)",
        "monthly_cents": 1900,
        "overage_limit": 5,         # soft-cap at 2x = 10 agents
        "sso_enabled": "false",
        "currency": "eur",
    },
    "team": {
        "name": "ATW Team",
        "description": "AgentTerminalsWatch — Team plan (up to 25 agents monitored)",
        "monthly_cents": 4900,
        "overage_limit": 25,        # soft-cap at 2x = 50 agents
        "sso_enabled": "false",
        "currency": "eur",
    },
    "enterprise": {
        "name": "ATW Enterprise",
        "description": "AgentTerminalsWatch — Enterprise plan (up to 100 agents, SSO included)",
        "monthly_cents": 19900,
        "overage_limit": 100,       # soft-cap at 2x = 200 agents
        "sso_enabled": "true",      # SSO feature-flag — Enterprise only
        "currency": "eur",
    },
}


# ── Key Validation ────────────────────────────────────────────────────────────

def get_test_key() -> str:
    """Return the Stripe test secret key from environment.

    Raises RuntimeError if STRIPE_SECRET_KEY_TEST is unset or has wrong prefix.
    NEVER falls back to a live key — fail loud.
    """
    key = os.environ.get("STRIPE_SECRET_KEY_TEST")
    if not key:
        raise RuntimeError(
            "STRIPE_SECRET_KEY_TEST is not set. "
            "Set it to a sk_test_ or rk_test_ key before running this script. "
            "DO NOT use a live key (sk_live_) for test-mode setup."
        )
    if not (key.startswith("sk_test_") or key.startswith("rk_test_")):
        raise RuntimeError(
            f"STRIPE_SECRET_KEY_TEST must start with sk_test_ or rk_test_ "
            f"(got prefix: {key[:8]}...). "
            "Live keys are NOT permitted for test-mode product setup."
        )
    return key


# ── Price Computation ─────────────────────────────────────────────────────────

def annual_price_cents(monthly_cents: int) -> int:
    """Compute annual price in cents (monthly * 12 * 0.80, rounded to integer)."""
    return round(monthly_cents * 12 * 0.8)


# ── Core Setup Logic ──────────────────────────────────────────────────────────

def _find_existing_product(tier: str) -> stripe.Product | None:
    """Search for an existing product with metadata.atw_tier == tier."""
    products = stripe.Product.list(limit=100, active=True)
    for product in products.auto_paging_iter():
        if product.metadata.get("atw_tier") == tier:
            return product
    return None


def _find_existing_price(product_id: str, interval: str) -> stripe.Price | None:
    """Search for an existing price for the product with the given billing interval."""
    prices = stripe.Price.list(product=product_id, active=True)
    for price in prices.auto_paging_iter():
        if price.recurring and price.recurring.interval == interval:
            return price
    return None


def setup_tier(tier: str, cfg: dict) -> dict:
    """Create (or retrieve existing) Product + monthly + annual Price for one tier.

    Returns dict with product_id, price_id_monthly, price_id_annual.
    """
    # ── Product ───────────────────────────────────────────────────────────────
    existing = _find_existing_product(tier)
    if existing:
        product_id = existing.id
        print(f"  [SKIP] Product for tier={tier} already exists: {product_id}")
    else:
        product = stripe.Product.create(
            name=cfg["name"],
            description=cfg["description"],
            metadata={
                "atw_tier": tier,
                "sso_enabled": cfg.get("sso_enabled", "false"),
                "overage_limit": str(cfg["overage_limit"]),
                "overage_cap": str(cfg["overage_limit"] * 2),
            },
        )
        product_id = product.id
        print(f"  [CREATED] Product tier={tier}: {product_id}")

    # ── Monthly Price ─────────────────────────────────────────────────────────
    existing_monthly = _find_existing_price(product_id, "month")
    if existing_monthly:
        price_id_monthly = existing_monthly.id
        print(f"  [SKIP] Monthly price for {tier} already exists: {price_id_monthly}")
    else:
        monthly = stripe.Price.create(
            product=product_id,
            unit_amount=cfg["monthly_cents"],
            currency=cfg["currency"],
            recurring={"interval": "month"},
            metadata={
                "atw_tier": tier,
                "billing_period": "monthly",
            },
        )
        price_id_monthly = monthly.id
        print(f"  [CREATED] Monthly price for {tier}: {price_id_monthly} ({cfg['monthly_cents']} {cfg['currency'].upper()}/mo)")

    # ── Annual Price ──────────────────────────────────────────────────────────
    annual_cents = annual_price_cents(cfg["monthly_cents"])
    existing_annual = _find_existing_price(product_id, "year")
    if existing_annual:
        price_id_annual = existing_annual.id
        print(f"  [SKIP] Annual price for {tier} already exists: {price_id_annual}")
    else:
        annual = stripe.Price.create(
            product=product_id,
            unit_amount=annual_cents,
            currency=cfg["currency"],
            recurring={"interval": "year"},
            metadata={
                "atw_tier": tier,
                "billing_period": "annual",
                "discount_pct": "20",
            },
        )
        price_id_annual = annual.id
        print(f"  [CREATED] Annual price for {tier}: {price_id_annual} ({annual_cents} {cfg['currency'].upper()}/yr)")

    return {
        "product_id": product_id,
        "price_id_monthly": price_id_monthly,
        "price_id_annual": price_id_annual,
    }


def run_setup(output_path: Path | None = None) -> dict:
    """Run full setup for all 3 tiers and write output JSON.

    output_path defaults to state/stripe/atw_products_test.json relative to
    ATW_STATE_DIR env (or repo root).
    """
    if output_path is None:
        state_dir = os.environ.get("ATW_STATE_DIR")
        if state_dir:
            base = Path(state_dir)
        else:
            base = Path(__file__).resolve().parent.parent / "state"
        output_path = base / "stripe" / "atw_products_test.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict] = {}
    for tier, cfg in TIER_CONFIG.items():
        print(f"\nSetting up tier: {tier}")
        results[tier] = setup_tier(tier, cfg)

    output_path.write_text(json.dumps(results, indent=2))
    print(f"\n[OK] Product IDs written to: {output_path}")
    return results


# ── Entry Point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create ATW Stripe products in TEST MODE (idempotent)."
    )
    parser.add_argument("--output", type=Path, default=None, help="Output JSON path")
    args = parser.parse_args()

    # Validate test key — fail loud if absent or wrong prefix
    key = get_test_key()
    stripe.api_key = key
    stripe.api_version = "2026-05-27.dahlia"

    print("ATW Stripe Test-Mode Setup")
    print(f"  Key prefix: {key[:12]}...")
    print(f"  API version: {stripe.api_version}")
    print(f"  Tiers: {list(TIER_CONFIG.keys())}")

    run_setup(output_path=args.output)


if __name__ == "__main__":
    main()
