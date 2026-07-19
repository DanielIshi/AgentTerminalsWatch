/**
 * R145 TDD — §312j BGB Payment Button compliance tests.
 *
 * Tests cover:
 *   T1: Button text is exactly "Zahlungspflichtig bestellen"
 *   T2: Price display above button contains € symbol
 *   T3: Price display contains tier name
 *   T4: onCheckout is called on click
 *   T5: Button is disabled when onCheckout is undefined
 *   T6: Annual toggle changes price (€19/mo → €182.40/yr)
 *   T7: Verboten words NOT in button text (Regression-Guard §312j)
 *   T8: data-testid format matches pattern
 *   T9: Solo monthly price is €19
 *   T10: Team monthly price is €49
 *   T11: Enterprise monthly price is €199
 *   T12: Annual prices carry 20% discount
 *   T13: VAT notice is visible in price block
 *   T14: Disabled state during in-flight (isLoading)
 *   T15: All three tier cards render in PricingPage
 *   T16: Annual/monthly toggle exists on PricingPage
 */

// @vitest-environment jsdom
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { vi } from "vitest";

import {
  PaymentButton,
  BUTTON_TEXT,
  TIER_PRICES,
  FORBIDDEN_BUTTON_TEXTS,
  getPriceDisplay,
} from "../src/components/PaymentButton";
import PricingPage from "../src/PricingPage";

// ─── T1: Button text exact match ────────────────────────────────────────────
describe("T1: §312j BGB Button-Text", () => {
  it('button text is exactly "Zahlungspflichtig bestellen"', () => {
    const onCheckout = vi.fn();
    render(
      <PaymentButton tier="solo" billingCycle="monthly" onCheckout={onCheckout} />
    );
    const btn = screen.getByTestId("payment-button-solo-monthly");
    expect(btn.textContent).toBe("Zahlungspflichtig bestellen");
  });

  it("BUTTON_TEXT constant equals §312j exact wording", () => {
    expect(BUTTON_TEXT).toBe("Zahlungspflichtig bestellen");
  });
});

// ─── T2: € symbol in price display ──────────────────────────────────────────
describe("T2: Price display contains € symbol", () => {
  it("shows € in the price block above the button", () => {
    const onCheckout = vi.fn();
    render(
      <PaymentButton tier="solo" billingCycle="monthly" onCheckout={onCheckout} />
    );
    const priceBlock = screen.getByTestId("price-display-solo-monthly");
    expect(priceBlock.textContent).toContain("€");
  });
});

// ─── T3: Tier name in price display ─────────────────────────────────────────
describe("T3: Tier name in price display", () => {
  it("shows tier name 'Solo' in price block", () => {
    render(
      <PaymentButton tier="solo" billingCycle="monthly" onCheckout={vi.fn()} />
    );
    const priceBlock = screen.getByTestId("price-display-solo-monthly");
    expect(priceBlock.textContent).toMatch(/Solo/i);
  });

  it("shows tier name 'Team' in price block", () => {
    render(
      <PaymentButton tier="team" billingCycle="monthly" onCheckout={vi.fn()} />
    );
    const priceBlock = screen.getByTestId("price-display-team-monthly");
    expect(priceBlock.textContent).toMatch(/Team/i);
  });

  it("shows tier name 'Enterprise' in price block", () => {
    render(
      <PaymentButton
        tier="enterprise"
        billingCycle="monthly"
        onCheckout={vi.fn()}
      />
    );
    const priceBlock = screen.getByTestId("price-display-enterprise-monthly");
    expect(priceBlock.textContent).toMatch(/Enterprise/i);
  });
});

// ─── T4: onCheckout called on click ─────────────────────────────────────────
describe("T4: onCheckout called on click", () => {
  it("fires onCheckout when button is clicked (waiver accepted)", () => {
    const onCheckout = vi.fn();
    render(
      <PaymentButton
        tier="solo"
        billingCycle="monthly"
        onCheckout={onCheckout}
        withdrawalWaiverAccepted={true}
      />
    );
    fireEvent.click(screen.getByTestId("payment-button-solo-monthly"));
    expect(onCheckout).toHaveBeenCalledTimes(1);
  });
});

// ─── T5: Disabled when onCheckout undefined ──────────────────────────────────
describe("T5: Disabled state when onCheckout is undefined", () => {
  it("button is disabled when no onCheckout handler provided", () => {
    render(<PaymentButton tier="solo" billingCycle="monthly" />);
    const btn = screen.getByTestId("payment-button-solo-monthly");
    expect(btn).toBeDisabled();
  });

  it("button is NOT disabled when onCheckout is provided and waiver accepted", () => {
    render(
      <PaymentButton
        tier="solo"
        billingCycle="monthly"
        onCheckout={vi.fn()}
        withdrawalWaiverAccepted={true}
      />
    );
    const btn = screen.getByTestId("payment-button-solo-monthly");
    expect(btn).not.toBeDisabled();
  });
});

// ─── T6: Annual toggle changes price ────────────────────────────────────────
describe("T6: Annual toggle changes price display", () => {
  it("monthly solo shows €19", () => {
    render(
      <PaymentButton tier="solo" billingCycle="monthly" onCheckout={vi.fn()} />
    );
    const priceBlock = screen.getByTestId("price-display-solo-monthly");
    expect(priceBlock.textContent).toContain("19");
  });

  it("annual solo shows €182.40", () => {
    render(
      <PaymentButton tier="solo" billingCycle="annual" onCheckout={vi.fn()} />
    );
    const priceBlock = screen.getByTestId("price-display-solo-annual");
    expect(priceBlock.textContent).toContain("182.40");
  });

  it("getPriceDisplay returns correct monthly price for solo", () => {
    const display = getPriceDisplay("solo", "monthly");
    expect(display.amount).toBe(19);
    expect(display.currency).toBe("€");
  });

  it("getPriceDisplay returns correct annual price for solo", () => {
    const display = getPriceDisplay("solo", "annual");
    expect(display.amount).toBe(182.40);
    expect(display.currency).toBe("€");
  });
});

// ─── T7: Regression-Guard — verbotene Wörter ────────────────────────────────
describe("T7: §312j Regression-Guard — verbotene Button-Texte", () => {
  it("FORBIDDEN_BUTTON_TEXTS list is non-empty", () => {
    expect(FORBIDDEN_BUTTON_TEXTS.length).toBeGreaterThan(0);
  });

  it('"Bestellen" is in forbidden list', () => {
    expect(FORBIDDEN_BUTTON_TEXTS).toContain("Bestellen");
  });

  it('"Weiter" is in forbidden list', () => {
    expect(FORBIDDEN_BUTTON_TEXTS).toContain("Weiter");
  });

  it('"Jetzt starten" is in forbidden list', () => {
    expect(FORBIDDEN_BUTTON_TEXTS).toContain("Jetzt starten");
  });

  it('"Buchen" is in forbidden list', () => {
    expect(FORBIDDEN_BUTTON_TEXTS).toContain("Buchen");
  });

  it("BUTTON_TEXT does NOT equal any forbidden standalone label", () => {
    // §312j test: the forbidden texts are STANDALONE button labels (not substrings).
    // "Zahlungspflichtig bestellen" CONTAINS "bestellen" as a word, but is itself
    // not a forbidden label — the statute forbids "Bestellen" as the full button text.
    // Test: BUTTON_TEXT must not EQUAL any forbidden entry (case-insensitive).
    for (const forbidden of FORBIDDEN_BUTTON_TEXTS) {
      expect(BUTTON_TEXT.toLowerCase()).not.toBe(forbidden.toLowerCase());
    }
  });

  it("rendered button text does NOT equal any forbidden text", () => {
    render(
      <PaymentButton tier="team" billingCycle="monthly" onCheckout={vi.fn()} />
    );
    const btn = screen.getByTestId("payment-button-team-monthly");
    for (const forbidden of FORBIDDEN_BUTTON_TEXTS) {
      expect(btn.textContent).not.toBe(forbidden);
    }
  });
});

// ─── T8: data-testid format ──────────────────────────────────────────────────
describe("T8: data-testid format", () => {
  it("solo monthly testid matches pattern", () => {
    render(
      <PaymentButton tier="solo" billingCycle="monthly" onCheckout={vi.fn()} />
    );
    expect(
      screen.getByTestId("payment-button-solo-monthly")
    ).toBeInTheDocument();
  });

  it("enterprise annual testid matches pattern", () => {
    render(
      <PaymentButton
        tier="enterprise"
        billingCycle="annual"
        onCheckout={vi.fn()}
      />
    );
    expect(
      screen.getByTestId("payment-button-enterprise-annual")
    ).toBeInTheDocument();
  });
});

// ─── T9-T11: Tier prices monthly ────────────────────────────────────────────
describe("T9-T11: Monthly prices from TIER_PRICES config", () => {
  it("Solo monthly = €19", () => {
    expect(TIER_PRICES.solo.monthly).toBe(19);
  });

  it("Team monthly = €49", () => {
    expect(TIER_PRICES.team.monthly).toBe(49);
  });

  it("Enterprise monthly = €199", () => {
    expect(TIER_PRICES.enterprise.monthly).toBe(199);
  });
});

// ─── T12: Annual 20% discount ────────────────────────────────────────────────
describe("T12: Annual prices have 20% discount", () => {
  it("Solo annual = €182.40", () => {
    expect(TIER_PRICES.solo.annual).toBe(182.40);
  });

  it("Team annual = €470.40", () => {
    expect(TIER_PRICES.team.annual).toBe(470.40);
  });

  it("Enterprise annual = €1910.40", () => {
    expect(TIER_PRICES.enterprise.annual).toBe(1910.40);
  });
});

// ─── T13: VAT notice ─────────────────────────────────────────────────────────
describe("T13: VAT notice in price display", () => {
  it("price block contains MwSt or USt reference", () => {
    render(
      <PaymentButton tier="solo" billingCycle="monthly" onCheckout={vi.fn()} />
    );
    const priceBlock = screen.getByTestId("price-display-solo-monthly");
    expect(priceBlock.textContent).toMatch(/MwSt|USt|inkl/i);
  });
});

// ─── T14: Disabled during loading ────────────────────────────────────────────
describe("T14: Disabled state during in-flight", () => {
  it("button is disabled when isLoading=true", () => {
    render(
      <PaymentButton
        tier="solo"
        billingCycle="monthly"
        onCheckout={vi.fn()}
        isLoading={true}
      />
    );
    expect(screen.getByTestId("payment-button-solo-monthly")).toBeDisabled();
  });
});

// ─── T15: PricingPage renders all three tier cards ───────────────────────────
describe("T15: PricingPage renders all tier cards", () => {
  it("renders Solo, Team, Enterprise cards", () => {
    render(<PricingPage />);
    // Use getAllByText since tier names appear multiple times (heading + price display)
    expect(screen.getAllByText(/^Solo$/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/^Team$/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/^Enterprise$/i).length).toBeGreaterThan(0);
  });

  it("renders all three payment buttons (disabled until waiver accepted)", () => {
    render(<PricingPage />);
    // Buttons present but disabled — waiver checkbox unchecked by default
    expect(
      screen.getByTestId("payment-button-solo-monthly")
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("payment-button-team-monthly")
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("payment-button-enterprise-monthly")
    ).toBeInTheDocument();
  });
});

// ─── T16: Annual/monthly toggle on PricingPage ───────────────────────────────
describe("T16: Annual/monthly toggle on PricingPage", () => {
  it("toggle button exists on PricingPage", () => {
    render(<PricingPage />);
    expect(screen.getByTestId("billing-cycle-toggle")).toBeInTheDocument();
  });

  it("toggling to annual changes solo price display", () => {
    render(<PricingPage />);
    const toggle = screen.getByTestId("billing-cycle-toggle");
    fireEvent.click(toggle);
    // After toggle: annual buttons appear
    expect(
      screen.getByTestId("payment-button-solo-annual")
    ).toBeInTheDocument();
  });

  it("annual toggle shows 20% discount badge", () => {
    render(<PricingPage />);
    const toggle = screen.getByTestId("billing-cycle-toggle");
    fireEvent.click(toggle);
    expect(screen.getByTestId("annual-discount-badge")).toBeInTheDocument();
  });
});
