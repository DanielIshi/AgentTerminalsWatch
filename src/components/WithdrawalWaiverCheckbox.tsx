/**
 * WithdrawalWaiverCheckbox — §356 Abs. 4/5 BGB Widerrufsverzicht-Checkbox.
 *
 * Gesetzliche Grundlage: §356 Abs. 4 BGB i.V.m. §312g BGB.
 * Bei sofortigem SaaS-Dienstbeginn vor Ablauf der Widerrufsfrist MUSS
 * der Verbraucher AKTIV zustimmen, sein Widerrufsrecht zu verlieren.
 *
 * Text-Quelle: atw_rechtsdokumente_paket_2026-07-19.md §3a (LEGAL commit 2686fac85)
 * "Erlöschen bei sofortiger Ausführung (§ 356 Abs. 4/5 BGB): Wünscht der
 *  Verbraucher den Dienstbeginn vor Ablauf der Widerrufsfrist, holt der
 *  Anbieter im Checkout dessen ausdrückliche Zustimmung + Kenntnisnahme
 *  des Widerrufsverlusts bei vollständiger Vertragserfüllung ein (Checkbox)."
 *
 * KRITISCH:
 *  - Default IMMER unchecked (aktives Opt-in erforderlich, §307 Abs. 2 Nr.1 BGB)
 *  - Text NICHT kürzen oder paraphrasieren — Legal-geprüfter Wortlaut
 *  - Checkbox UNTER dem PaymentButton, vor Absenden sichtbar
 */

import React from "react";

/**
 * Rechtsverbindlicher Wortlaut nach §356 Abs. 4/5 BGB.
 * Quelle: LEGAL-Freigabe 2026-07-19 (finaler Text, BGH-konform)
 * NICHT ändern ohne LEGAL-Approval — Text ist Nachweis-relevant (Log-Hash).
 *
 * Unterschied zu §3a-Langfassung im Paket: LEGAL hat Final-Formulierung
 * auf BGH-Muster (§356 Abs.4 BGB, Art.246a §1 Abs.2 Nr.1 EGBGB) gekürzt.
 *
 * Bestätigt durch: atw_widerruf_html_snippet_2026-07-19.md Snippet 3 (Anwalts-Letztprüfung).
 */
export const WITHDRAWAL_WAIVER_TEXT =
  "Ich verlange ausdrücklich, dass Sie mit der Ausführung der Dienstleistung " +
  "vor Ablauf der Widerrufsfrist beginnen. Mir ist bekannt, dass mein " +
  "Widerrufsrecht mit vollständiger Vertragserfüllung erlischt." as const;

/**
 * Versionierungskennung für Belehrungs-Nachweis (LEGAL-Kriterium #5, 2026-07-19).
 * Format: waiver_v{N}_{YYYY-MM-DD}
 * Bei Textänderung durch LEGAL: bump N + Datum.
 * Wird in waiver_log.db + confirmation_mail_log.jsonl als `waiver_version` gespeichert.
 */
export const WAIVER_VERSION = "waiver_v1_2026-07-19" as const;

/** Logging-Payload nach §356 Nachweis-Pflicht (BGH) + LEGAL-Kriterium #5. */
export interface WaiverLogEntry {
  /** ISO-Timestamp der Bestätigung */
  waiver_accepted_at: string;
  /**
   * FNV-1a Hash des exakten WITHDRAWAL_WAIVER_TEXT (sync).
   * Backend (stripe_webhook.py) ersetzt durch echten SHA-256 für Stripe-Metadata.
   * Sichert, dass zum Zeitpunkt der Zustimmung kein anderer Text gezeigt wurde.
   */
  waiver_text_hash: string;
  /**
   * Belehrungs-Version für historischen Nachweis (LEGAL-Kriterium #5, 2026-07-19).
   * Zeigt welche Fassung der Belehrung der Nutzer gesehen hat.
   * Format: "waiver_v{N}_{YYYY-MM-DD}" — bump bei jeder LEGAL-Textänderung.
   */
  waiver_version: string;
}

export interface WithdrawalWaiverCheckboxProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Optional: wird aufgerufen wenn Checkbox auf true wechselt — für Logging */
  onWaiverAccepted?: (entry: WaiverLogEntry) => void;
}

/**
 * §356-Widerrufsverzicht-Checkbox — muss aktiv angeklickt werden.
 *
 * @param checked   - aktueller Zustand (von Parent gehalten)
 * @param onChange  - wird mit neuem boolean aufgerufen bei Änderung
 */
/**
 * Berechnet einen deterministischen "Hash" des Waiver-Texts (FNV-1a 32bit, hex).
 * In Production sollte WebCrypto SHA-256 verwendet werden — hier ohne async
 * für Test-Kompatibilität. SHA-256 via Stripe-Metadata-Handler (Backend).
 *
 * HINWEIS: Echter SHA-256 wird im Backend (stripe_webhook.py) berechnet wenn
 * checkout.session.metadata["waiver_text_hash"] gespeichert wird.
 */
export function computeWaiverTextHash(text: string): string {
  // FNV-1a 32bit — deterministisch, sync, test-freundlich
  let hash = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    hash ^= text.charCodeAt(i);
    hash = (hash * 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

export function WithdrawalWaiverCheckbox({
  checked,
  onChange,
  onWaiverAccepted,
}: WithdrawalWaiverCheckboxProps): React.ReactElement {
  const handleChange = (newChecked: boolean) => {
    onChange(newChecked);
    if (newChecked && onWaiverAccepted) {
      onWaiverAccepted({
        waiver_accepted_at: new Date().toISOString(),
        waiver_text_hash: computeWaiverTextHash(WITHDRAWAL_WAIVER_TEXT),
        waiver_version: WAIVER_VERSION,
      });
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 10,
          padding: "12px 14px",
          background: "#0f0f1a",
          border: checked ? "1px solid #7c3aed" : "1px solid #3d2f60",
          borderRadius: 8,
          cursor: "pointer",
        }}
        onClick={() => handleChange(!checked)}
      >
        <input
          data-testid="withdrawal-waiver-checkbox"
          type="checkbox"
          checked={checked}
          onChange={(e) => handleChange(e.target.checked)}
          onClick={(e) => e.stopPropagation()}
          style={{
            width: 18,
            height: 18,
            marginTop: 2,
            flexShrink: 0,
            accentColor: "#7c3aed",
            cursor: "pointer",
          }}
          aria-label="Widerrufsrecht-Verzicht bestätigen"
        />
        <label
          style={{
            fontSize: 12,
            color: "#94a3b8",
            lineHeight: 1.5,
            cursor: "pointer",
            userSelect: "none",
          }}
        >
          {WITHDRAWAL_WAIVER_TEXT}
        </label>
      </div>

      {/* §356 Pflicht-Links — TODO: LEGAL liefert HTML-Snippet nach (2026-07-19) */}
      <div style={{ fontSize: 11, color: "#555", paddingLeft: 2 }}>
        <a
          href="/legal/widerrufsbelehrung"
          style={{ color: "#7c3aed", textDecoration: "underline" }}
        >
          Widerrufsbelehrung
        </a>
        {" · "}
        <a
          href="/legal/muster-widerrufsformular"
          style={{ color: "#7c3aed", textDecoration: "underline" }}
        >
          Muster-Widerrufsformular
        </a>
      </div>
    </div>
  );
}

export default WithdrawalWaiverCheckbox;
