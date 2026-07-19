/**
 * PaymentButton — §312j BGB konforme Zahlungsschaltfläche.
 *
 * Gesetzliche Grundlage: § 312j Abs. 3 BGB (Fernabsatzrecht).
 * Der Button-Text "Zahlungspflichtig bestellen" ist die direkte Übernahme
 * aus dem Gesetzestext und darf NICHT paraphrasiert oder abgekürzt werden.
 *
 * Commits LEGAL:
 *   AGB:          b52913c75
 *   Datenschutz:  2686fac85
 *
 * NIEMALS ändern: BUTTON_TEXT — dieser String ist rechtlich bindend.
 */

import React from "react";

// ── §312j Compliance Constants ──────────────────────────────────────────────

/**
 * Exakter Wortlaut §312j Abs. 3 Satz 2 BGB.
 * NICHT ändern ohne LEGAL-Approval.
 */
export const BUTTON_TEXT = "Zahlungspflichtig bestellen" as const;

/**
 * Verbotene Button-Texte nach §312j BGB.
 * Verwendung eines dieser Texte ist eine Ordnungswidrigkeit (§ 312j Abs. 4 BGB).
 * CI-Test T7 prüft automatisch dass keiner dieser Texte im Button vorkommt.
 */
export const FORBIDDEN_BUTTON_TEXTS: readonly string[] = [
  "Bestellen",
  "Weiter",
  "Anmelden",
  "Jetzt starten",
  "Buchen",
  "Kaufen",       // Kein Widerspruch: "Kaufen" ist nach §312j erlaubt, aber wir
                  // nutzen es nicht um Verwechslungen zu vermeiden (DRY-Policy).
                  // Stripe-Checkout übernimmt Kaufen-Semantik intern.
  "Registrieren",
  "Los geht's",
  "Get started",
  "Subscribe",
  "Order now",
];

// ── Pricing Config ───────────────────────────────────────────────────────────

export type Tier = "solo" | "team" | "enterprise";
export type BillingCycle = "monthly" | "annual";

interface TierPriceConfig {
  monthly: number;
  annual: number;
  agents: number;
  sso: boolean;
  label: string;
}

export const TIER_PRICES: Record<Tier, TierPriceConfig> = {
  solo: {
    monthly: 19,
    annual: 182.40,
    agents: 5,
    sso: false,
    label: "Solo",
  },
  team: {
    monthly: 49,
    annual: 470.40,
    agents: 25,
    sso: false,
    label: "Team",
  },
  enterprise: {
    monthly: 199,
    annual: 1910.40,
    agents: 100,
    sso: true,
    label: "Enterprise",
  },
};

// ── Helper ───────────────────────────────────────────────────────────────────

export interface PriceDisplay {
  amount: number;
  currency: string;
  cycle: BillingCycle;
  tierLabel: string;
  agents: number;
  sso: boolean;
}

export function getPriceDisplay(tier: Tier, cycle: BillingCycle): PriceDisplay {
  const config = TIER_PRICES[tier];
  return {
    amount: config[cycle],
    currency: "€",
    cycle,
    tierLabel: config.label,
    agents: config.agents,
    sso: config.sso,
  };
}

// ── Component Props ──────────────────────────────────────────────────────────

export interface PaymentButtonProps {
  tier: Tier;
  billingCycle: BillingCycle;
  onCheckout?: () => void;
  isLoading?: boolean;
  /**
   * §356 Abs. 4/5 BGB — Widerrufsrecht-Verzicht.
   * Button bleibt disabled bis Verbraucher Checkbox aktiv bestätigt hat.
   * Default: false (sicher — nicht zahlbar ohne Bestätigung).
   */
  withdrawalWaiverAccepted?: boolean;
}

// ── PaymentButton ────────────────────────────────────────────────────────────

/**
 * §312j-konformer Zahlungsbutton mit Preis-Zusammenfassung.
 *
 * Über dem Button wird angezeigt:
 *   - Tier-Name
 *   - Endpreis inkl. 19% MwSt.
 *   - Abrechnungszyklus
 *   - Anzahl inkludierter Agents
 *   - SSO-Status (nur Enterprise)
 *
 * @param tier          - Tarif: 'solo' | 'team' | 'enterprise'
 * @param billingCycle  - Abrechnungszyklus: 'monthly' | 'annual'
 * @param onCheckout    - Callback für Stripe-Checkout-Redirect. Fehlt → Button disabled.
 * @param isLoading     - true während async Checkout-Initialisierung → Button disabled.
 */
export function PaymentButton({
  tier,
  billingCycle,
  onCheckout,
  isLoading = false,
  withdrawalWaiverAccepted = false,
}: PaymentButtonProps): React.ReactElement {
  const display = getPriceDisplay(tier, billingCycle);
  const waiverMissing = !withdrawalWaiverAccepted;
  const isDisabled = !onCheckout || isLoading || waiverMissing;
  const testId = `payment-button-${tier}-${billingCycle}`;
  const priceTestId = `price-display-${tier}-${billingCycle}`;

  const formattedAmount =
    display.amount % 1 === 0
      ? `${display.currency}${display.amount}`
      : `${display.currency}${display.amount.toFixed(2)}`;

  const cycleLabel = billingCycle === "monthly" ? "/ Monat" : "/ Jahr";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {/* Pflicht-Preisanzeige über dem Button — §312j Abs. 3 BGB */}
      <div
        data-testid={priceTestId}
        style={{
          padding: "12px 16px",
          background: "#1a1a2e",
          borderRadius: 8,
          border: "1px solid #2d2d4e",
          fontSize: 14,
          lineHeight: 1.5,
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>
          {display.tierLabel}
        </div>
        <div style={{ fontSize: 22, fontWeight: 800, color: "#a78bfa" }}>
          {formattedAmount}
          <span style={{ fontSize: 13, fontWeight: 400, color: "#888", marginLeft: 4 }}>
            {cycleLabel}
          </span>
        </div>
        <div style={{ fontSize: 12, color: "#666", marginTop: 2 }}>
          inkl. 19% MwSt. — {display.agents} Agents{display.sso ? " — SSO inklusive" : ""}
        </div>
      </div>

      {/* Hinweis wenn Widerrufsverzicht fehlt */}
      {waiverMissing && onCheckout && !isLoading && (
        <div
          data-testid="waiver-missing-hint"
          style={{ fontSize: 11, color: "#f59e0b", padding: "4px 2px" }}
        >
          Bitte Widerrufsverzicht bestätigen
        </div>
      )}

      {/* §312j-konformer Bestell-Button */}
      <button
        data-testid={testId}
        onClick={isDisabled ? undefined : onCheckout}
        disabled={isDisabled}
        style={{
          padding: "14px 24px",
          fontSize: 15,
          fontWeight: 700,
          background: isDisabled ? "#333" : "#7c3aed",
          color: isDisabled ? "#666" : "#fff",
          border: "none",
          borderRadius: 8,
          cursor: isDisabled ? "not-allowed" : "pointer",
          transition: "background 0.2s",
          letterSpacing: "0.01em",
        }}
      >
        {/* §312j Abs. 3 BGB — exakter Gesetzestext, NICHT ändern */}
        {BUTTON_TEXT}
      </button>
    </div>
  );
}

export default PaymentButton;
