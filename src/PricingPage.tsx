/**
 * PricingPage — AgentTerminalsWatch Subscription Pricing.
 *
 * §312j BGB konform: Alle Preis-Angaben inkl. 19% MwSt.,
 * Button-Text "Zahlungspflichtig bestellen" via PaymentButton.
 *
 * LEGAL-Basis:
 *   AGB:          commit b52913c75
 *   Datenschutz:  commit 2686fac85
 *   AVV + Impressum: commit 2686fac85
 *
 * NOTE: onCheckout-Handler bleibt absichtlich entkoppelt (KEIN Live-Stripe-Call).
 * Integration via Props wenn Stripe-Checkout-Session-Endpoint live geht (GH#709).
 */

import React, { useState } from "react";
import { PaymentButton, TIER_PRICES } from "./components/PaymentButton";
import type { Tier, BillingCycle } from "./components/PaymentButton";
import { WithdrawalWaiverCheckbox } from "./components/WithdrawalWaiverCheckbox";
import type { WaiverLogEntry } from "./components/WithdrawalWaiverCheckbox";

// ── Tier Feature Lists ──────────────────────────────────────────────────────

const TIER_FEATURES: Record<Tier, string[]> = {
  solo: [
    "5 Agents gleichzeitig",
    "AgentTerminals Dashboard",
    "Email-Support",
    "Webhook-Alerts",
    "Kein SSO",
  ],
  team: [
    "25 Agents gleichzeitig",
    "AgentTerminals Dashboard",
    "Priority-Support",
    "Webhook-Alerts + Slack",
    "Kein SSO",
    "Team-Rollen (read-only Members)",
  ],
  enterprise: [
    "100 Agents gleichzeitig",
    "AgentTerminals Dashboard",
    "Dedicated Support",
    "Webhook-Alerts + Slack + PagerDuty",
    "SSO (SAML/OIDC) inklusive",
    "Custom Overage-Limits",
    "SLA 99,9%",
  ],
};

// ── TierCard ─────────────────────────────────────────────────────────────────

interface TierCardProps {
  tier: Tier;
  billingCycle: BillingCycle;
  onCheckout?: (tier: Tier, cycle: BillingCycle) => void;
  onWaiverLog?: (entry: WaiverLogEntry) => void;
}

function TierCard({ tier, billingCycle, onCheckout, onWaiverLog }: TierCardProps) {
  const config = TIER_PRICES[tier];
  const features = TIER_FEATURES[tier];
  const price = config[billingCycle];
  const isEnterprise = tier === "enterprise";
  const [waiverAccepted, setWaiverAccepted] = useState(false);

  return (
    <div
      style={{
        border: isEnterprise ? "2px solid #7c3aed" : "1px solid #2d2d4e",
        borderRadius: 12,
        padding: "24px 20px",
        background: isEnterprise ? "#0f0a1e" : "#12121f",
        display: "flex",
        flexDirection: "column",
        gap: 16,
        minWidth: 260,
        flex: 1,
        maxWidth: 340,
        position: "relative",
      }}
    >
      {isEnterprise && (
        <div
          style={{
            position: "absolute",
            top: -12,
            left: "50%",
            transform: "translateX(-50%)",
            background: "#7c3aed",
            color: "#fff",
            fontSize: 11,
            fontWeight: 700,
            padding: "3px 12px",
            borderRadius: 20,
            letterSpacing: "0.05em",
            whiteSpace: "nowrap",
          }}
        >
          MOST POWERFUL
        </div>
      )}

      <div>
        <div style={{ fontSize: 20, fontWeight: 800, color: "#e2e8f0" }}>
          {config.label}
        </div>
        <div style={{ fontSize: 32, fontWeight: 900, color: "#a78bfa", marginTop: 8 }}>
          €{price % 1 === 0 ? price : price.toFixed(2)}
          <span style={{ fontSize: 14, fontWeight: 400, color: "#666", marginLeft: 6 }}>
            {billingCycle === "monthly" ? "/ Monat" : "/ Jahr"}
          </span>
        </div>
        <div style={{ fontSize: 11, color: "#555", marginTop: 2 }}>
          inkl. 19% MwSt.
        </div>
      </div>

      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 6 }}>
        {features.map((feat) => (
          <li
            key={feat}
            style={{ fontSize: 13, color: "#94a3b8", display: "flex", alignItems: "flex-start", gap: 6 }}
          >
            <span style={{ color: "#7c3aed", flexShrink: 0 }}>✓</span>
            {feat}
          </li>
        ))}
      </ul>

      <WithdrawalWaiverCheckbox
        checked={waiverAccepted}
        onChange={setWaiverAccepted}
        onWaiverAccepted={onWaiverLog}
      />
      <PaymentButton
        tier={tier}
        billingCycle={billingCycle}
        withdrawalWaiverAccepted={waiverAccepted}
        onCheckout={onCheckout ? () => onCheckout(tier, billingCycle) : undefined}
      />
    </div>
  );
}

// ── PricingPage ──────────────────────────────────────────────────────────────

export interface PricingPageProps {
  /** Optional checkout handler — bleibt undefined bis Stripe-Integration live (GH#709) */
  onCheckout?: (tier: Tier, cycle: BillingCycle) => void;
  /** Optional waiver-log handler — für Nachweis-Persistenz (state/atw/waiver_log.db) */
  onWaiverLog?: (entry: WaiverLogEntry) => void;
}

export default function PricingPage({ onCheckout, onWaiverLog }: PricingPageProps = {}) {
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly");

  const isAnnual = billingCycle === "annual";

  return (
    <div
      style={{
        fontFamily: "system-ui, -apple-system, sans-serif",
        background: "#0a0a14",
        minHeight: "100vh",
        color: "#e2e8f0",
        padding: "48px 24px",
      }}
    >
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 40 }}>
        <h1 style={{ fontSize: 32, fontWeight: 900, margin: "0 0 8px", color: "#fff" }}>
          AgentTerminalsWatch
        </h1>
        <p style={{ color: "#94a3b8", fontSize: 15, margin: 0 }}>
          Echtzeit-Monitoring für dein KI-Agent-Netzwerk
        </p>

        {/* Billing Cycle Toggle */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 12,
            marginTop: 24,
            background: "#1a1a2e",
            padding: "8px 16px",
            borderRadius: 40,
            border: "1px solid #2d2d4e",
          }}
        >
          <span style={{ fontSize: 13, color: isAnnual ? "#555" : "#e2e8f0", fontWeight: isAnnual ? 400 : 600 }}>
            Monatlich
          </span>
          <button
            data-testid="billing-cycle-toggle"
            onClick={() => setBillingCycle(isAnnual ? "monthly" : "annual")}
            style={{
              width: 44,
              height: 24,
              background: isAnnual ? "#7c3aed" : "#2d2d4e",
              borderRadius: 12,
              border: "none",
              cursor: "pointer",
              position: "relative",
              transition: "background 0.2s",
            }}
            aria-label="Abrechnungszyklus wechseln"
            aria-pressed={isAnnual}
          >
            <span
              style={{
                position: "absolute",
                top: 3,
                left: isAnnual ? 23 : 3,
                width: 18,
                height: 18,
                background: "#fff",
                borderRadius: "50%",
                transition: "left 0.2s",
              }}
            />
          </button>
          <span style={{ fontSize: 13, color: isAnnual ? "#e2e8f0" : "#555", fontWeight: isAnnual ? 600 : 400 }}>
            Jährlich
          </span>
          {isAnnual && (
            <span
              data-testid="annual-discount-badge"
              style={{
                background: "#14532d",
                color: "#86efac",
                fontSize: 11,
                fontWeight: 700,
                padding: "2px 8px",
                borderRadius: 20,
              }}
            >
              20% Rabatt
            </span>
          )}
        </div>
      </div>

      {/* Tier Cards */}
      <div
        style={{
          display: "flex",
          gap: 20,
          justifyContent: "center",
          flexWrap: "wrap",
          maxWidth: 1100,
          margin: "0 auto",
        }}
      >
        {(["solo", "team", "enterprise"] as Tier[]).map((tier) => (
          <TierCard
            key={tier}
            tier={tier}
            billingCycle={billingCycle}
            onCheckout={onCheckout}
            onWaiverLog={onWaiverLog}
          />
        ))}
      </div>

      {/* §312j Pflicht-Fußnote + LEGAL-Links */}
      <div
        style={{
          textAlign: "center",
          marginTop: 48,
          fontSize: 12,
          color: "#555",
          maxWidth: 600,
          margin: "48px auto 0",
          lineHeight: 1.7,
        }}
      >
        <p>
          Alle Preise inkl. 19% MwSt. Die Abonnements verlängern sich automatisch
          zum jeweiligen Preis. Kündigung jederzeit zum Periodenende möglich.
          EU-Widerrufsrecht: 14 Tage ab Vertragsschluss (digitale Inhalte).
        </p>
        <p style={{ marginTop: 8 }}>
          <a href="/agb" style={{ color: "#7c3aed", textDecoration: "none" }}>AGB</a>
          {" · "}
          <a href="/datenschutz" style={{ color: "#7c3aed", textDecoration: "none" }}>Datenschutz</a>
          {" · "}
          <a href="/legal/widerrufsbelehrung" style={{ color: "#7c3aed", textDecoration: "none" }}>Widerrufsrecht</a>
          {" · "}
          <a href="/impressum" style={{ color: "#7c3aed", textDecoration: "none" }}>Impressum</a>
        </p>
      </div>
    </div>
  );
}
