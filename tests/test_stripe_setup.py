"""R145 TDD — stripe_setup_test unit tests.

Tests cover:
  - fail-loud when STRIPE_SECRET_KEY_TEST not set
  - fail-loud when key has wrong prefix (not sk_test_ or rk_test_)
  - 3-tier product structure (Solo/Team/Enterprise)
  - monthly + annual price per product
  - annual price is exactly 20% off monthly * 12
  - SSO metadata only on Enterprise
  - overage cap metadata on all products
  - idempotency: existing product detected via metadata.atw_tier
  - idempotency: existing product NOT duplicated on second run
  - output JSON contains product_id, price_id_monthly, price_id_annual for all 3 tiers
  - Enterprise annual price correctness (€1910.40 / yr = €159.20 / mo billed annually)
  - Solo annual price correctness (€182.40 / yr)
  - Team annual price correctness (€470.40 / yr)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import stripe_setup_test as sut


# ── Tier pricing constants (ground truth) ─────────────────────────────────────

TIERS = {
    "solo":       {"monthly_eur": 1900,  "annual_eur": 18240,  "limit": 5},
    "team":       {"monthly_eur": 4900,  "annual_eur": 47040,  "limit": 25},
    "enterprise": {"monthly_eur": 19900, "annual_eur": 191040, "limit": 100},
}

# 20% discount on annual (monthly * 12 * 0.8)
def _expected_annual(monthly_cents: int) -> int:
    return round(monthly_cents * 12 * 0.8)


# ── Helper factories ──────────────────────────────────────────────────────────

def _make_product(tier: str, product_id: str = "prod_test") -> MagicMock:
    p = MagicMock()
    p.id = product_id
    p.metadata = {"atw_tier": tier}
    return p


def _make_price(price_id: str, unit_amount: int, interval: str) -> MagicMock:
    pr = MagicMock()
    pr.id = price_id
    pr.unit_amount = unit_amount
    pr.recurring = MagicMock(interval=interval)
    return pr


def _empty_list() -> MagicMock:
    lst = MagicMock()
    lst.data = []
    lst.auto_paging_iter.return_value = iter([])
    return lst


def _list_of(*items) -> MagicMock:
    lst = MagicMock()
    lst.data = list(items)
    lst.auto_paging_iter.return_value = iter(items)
    return lst


# ── 1. Key validation ─────────────────────────────────────────────────────────

def test_fail_loud_when_no_test_key(monkeypatch):
    """Must raise RuntimeError if STRIPE_SECRET_KEY_TEST is not set."""
    monkeypatch.delenv("STRIPE_SECRET_KEY_TEST", raising=False)
    with pytest.raises(RuntimeError, match="STRIPE_SECRET_KEY_TEST"):
        sut.get_test_key()


def test_fail_loud_when_live_key_passed(monkeypatch):
    """Must raise RuntimeError if key does not start with sk_test_ or rk_test_."""
    monkeypatch.setenv("STRIPE_SECRET_KEY_TEST", "sk_live_BADKEY")
    with pytest.raises(RuntimeError, match="sk_test_|rk_test_"):
        sut.get_test_key()


def test_accepts_sk_test_prefix(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY_TEST", "sk_test_GOODKEY")
    assert sut.get_test_key() == "sk_test_GOODKEY"


def test_accepts_rk_test_prefix(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY_TEST", "rk_test_GOODKEY")
    assert sut.get_test_key() == "rk_test_GOODKEY"


# ── 2. Annual discount correctness ────────────────────────────────────────────

def test_annual_discount_solo():
    assert _expected_annual(TIERS["solo"]["monthly_eur"]) == 18240


def test_annual_discount_team():
    assert _expected_annual(TIERS["team"]["monthly_eur"]) == 47040


def test_annual_discount_enterprise():
    assert _expected_annual(TIERS["enterprise"]["monthly_eur"]) == 191040


def test_compute_annual_price_matches_spec():
    """sut.annual_price_cents must compute 20% off monthly * 12."""
    assert sut.annual_price_cents(1900) == 18240
    assert sut.annual_price_cents(4900) == 47040
    assert sut.annual_price_cents(19900) == 191040


# ── 3. Tier config completeness ───────────────────────────────────────────────

def test_three_tiers_defined():
    assert set(sut.TIER_CONFIG.keys()) == {"solo", "team", "enterprise"}


def test_all_tiers_have_required_fields():
    for tier, cfg in sut.TIER_CONFIG.items():
        assert "name" in cfg, f"{tier} missing name"
        assert "monthly_cents" in cfg, f"{tier} missing monthly_cents"
        assert "overage_limit" in cfg, f"{tier} missing overage_limit"


def test_sso_flag_only_on_enterprise():
    for tier, cfg in sut.TIER_CONFIG.items():
        if tier == "enterprise":
            assert cfg.get("sso_enabled") == "true", "Enterprise must have sso_enabled=true"
        else:
            assert cfg.get("sso_enabled") != "true", f"{tier} must NOT have sso_enabled=true"


def test_overage_cap_present_on_all_tiers():
    for tier, cfg in sut.TIER_CONFIG.items():
        assert "overage_limit" in cfg, f"{tier} missing overage_limit"
        assert cfg["overage_limit"] > 0


# ── 4. Idempotency ────────────────────────────────────────────────────────────

@patch("stripe_setup_test.stripe")
def test_idempotency_skips_existing_product(mock_stripe, monkeypatch, tmp_path):
    """Second run must not create a duplicate product."""
    monkeypatch.setenv("STRIPE_SECRET_KEY_TEST", "sk_test_GOODKEY")
    monkeypatch.setenv("ATW_STATE_DIR", str(tmp_path))

    existing = _make_product("solo", "prod_solo_existing")
    mock_stripe.Product.list.return_value = _list_of(existing)

    # Prices already exist
    monthly_price = _make_price("price_solo_m", 1900, "month")
    annual_price = _make_price("price_solo_a", 18240, "year")
    mock_stripe.Price.list.return_value = _list_of(monthly_price, annual_price)

    result = sut.setup_tier("solo", sut.TIER_CONFIG["solo"])

    # Product.create must NOT have been called
    mock_stripe.Product.create.assert_not_called()
    assert result["product_id"] == "prod_solo_existing"


@patch("stripe_setup_test.stripe")
def test_idempotency_creates_missing_product(mock_stripe, monkeypatch, tmp_path):
    """If product not found, it must be created exactly once."""
    monkeypatch.setenv("STRIPE_SECRET_KEY_TEST", "sk_test_GOODKEY")
    monkeypatch.setenv("ATW_STATE_DIR", str(tmp_path))

    mock_stripe.Product.list.return_value = _empty_list()
    new_prod = _make_product("solo", "prod_solo_new")
    mock_stripe.Product.create.return_value = new_prod
    mock_stripe.Price.list.return_value = _empty_list()
    monthly_price = _make_price("price_solo_m_new", 1900, "month")
    annual_price = _make_price("price_solo_a_new", 18240, "year")
    mock_stripe.Price.create.side_effect = [monthly_price, annual_price]

    result = sut.setup_tier("solo", sut.TIER_CONFIG["solo"])

    mock_stripe.Product.create.assert_called_once()
    assert result["product_id"] == "prod_solo_new"


# ── 5. Output JSON structure ──────────────────────────────────────────────────

@patch("stripe_setup_test.setup_tier")
def test_output_json_has_all_tiers(mock_setup, monkeypatch, tmp_path):
    """run_setup() must write JSON with all 3 tiers."""
    monkeypatch.setenv("STRIPE_SECRET_KEY_TEST", "sk_test_GOODKEY")
    monkeypatch.setenv("ATW_STATE_DIR", str(tmp_path))

    def fake_setup(tier, cfg):
        return {
            "product_id": f"prod_{tier}",
            "price_id_monthly": f"price_{tier}_m",
            "price_id_annual": f"price_{tier}_a",
        }

    mock_setup.side_effect = fake_setup

    out_path = tmp_path / "atw_products_test.json"
    sut.run_setup(output_path=out_path)

    data = json.loads(out_path.read_text())
    assert set(data.keys()) == {"solo", "team", "enterprise"}
    for tier in ("solo", "team", "enterprise"):
        assert "product_id" in data[tier]
        assert "price_id_monthly" in data[tier]
        assert "price_id_annual" in data[tier]
