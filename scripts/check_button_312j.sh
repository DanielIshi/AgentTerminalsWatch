#!/usr/bin/env bash
# check_button_312j.sh — §312j BGB Button-Text Compliance Check
#
# Prüft ob src/ irgendwo verbotene Button-Texte nach §312j Abs. 3 BGB enthält.
# Exit 0 = clean, Exit 1 = violation found.
#
# CI-integrierbar: füge als pre-merge-check in GitHub Actions ein.
# Ref: §312j Abs. 3 BGB — Button muss "zahlungspflichtig bestellen" oder
#      gleichwertige eindeutige Formulierung tragen.
#
# LEGAL-Basis:
#   AGB:         commit b52913c75
#   Datenschutz: commit 2686fac85
#   §3a/§356:    atw_rechtsdokumente_paket_2026-07-19.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${SCRIPT_DIR}/../src"
VIOLATIONS=0
FOUND_FILES=()

# ── Verbotene Button-Texte (§312j Abs. 3 BGB) ──────────────────────────────
# Diese Texte dürfen NICHT als primärer Bestell-Button-Text erscheinen.
# Quelle: BGH-Rechtsprechung + BT-Drs. 17/7745 (Gesetzesbegründung zu §312j).
FORBIDDEN_PATTERNS=(
  "Bestellen"
  "Jetzt bestellen"
  "Weiter"
  "Anmelden"
  "Jetzt starten"
  "Buchen"
  "Registrieren"
  "Los geht's"
  "Get started"
  "Subscribe now"
  "Order now"
)

# ── Pflicht-Text muss vorhanden sein ────────────────────────────────────────
REQUIRED_TEXT="Zahlungspflichtig bestellen"

echo "=== §312j BGB Button-Text Compliance Check ==="
echo "Scanning: ${SRC_DIR}"
echo ""

# Check 1: Required text present in PaymentButton
REQUIRED_FILE="${SRC_DIR}/components/PaymentButton.tsx"
if [[ ! -f "${REQUIRED_FILE}" ]]; then
  echo "FAIL: PaymentButton.tsx not found at expected path"
  echo "      Expected: ${REQUIRED_FILE}"
  exit 1
fi

if ! grep -q "${REQUIRED_TEXT}" "${REQUIRED_FILE}"; then
  echo "FAIL: Required button text not found in PaymentButton.tsx"
  echo "      Missing: '${REQUIRED_TEXT}'"
  echo "      File: ${REQUIRED_FILE}"
  VIOLATIONS=$((VIOLATIONS + 1))
else
  echo "OK  : Required text '${REQUIRED_TEXT}' found in PaymentButton.tsx"
fi

# Check 2: BUTTON_TEXT constant present
if ! grep -q "BUTTON_TEXT" "${REQUIRED_FILE}"; then
  echo "WARN: BUTTON_TEXT constant not exported from PaymentButton.tsx"
  echo "      (CI-Tests rely on this export for T7 regression guard)"
fi

# Check 3: Scan for forbidden patterns in button contexts
echo ""
echo "--- Scanning for forbidden button text patterns ---"

for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
  # Look for pattern in button element text contexts (tsx/jsx)
  # Matches: <button>...</button>, button text props, aria-label with forbidden text
  # Excludes: comments (lines starting with //), FORBIDDEN_BUTTON_TEXTS array itself
  MATCHES=$(grep -rn \
    --include="*.tsx" \
    --include="*.ts" \
    --include="*.jsx" \
    --include="*.js" \
    "${pattern}" "${SRC_DIR}" \
    | grep -v "FORBIDDEN_BUTTON_TEXTS\|// \|FORBIDDEN_PATTERN\|forbidden\|verboten\|check_button" \
    | grep -i "button\|onClick\|checkout\|bestell" \
    || true)

  if [[ -n "${MATCHES}" ]]; then
    echo "WARN: Pattern '${pattern}' found in button context:"
    echo "${MATCHES}" | while IFS= read -r line; do
      echo "      ${line}"
    done
    # Only count as hard violation if it's literally the button label text
    EXACT_MATCH=$(echo "${MATCHES}" | grep -F ">${pattern}<\|\"${pattern}\"\|'${pattern}'" || true)
    if [[ -n "${EXACT_MATCH}" ]]; then
      echo "FAIL: '${pattern}' appears as exact button label — §312j violation!"
      VIOLATIONS=$((VIOLATIONS + 1))
    fi
  fi
done

# Check 4: §356 Waiver Checkbox present
WAIVER_FILE="${SRC_DIR}/components/WithdrawalWaiverCheckbox.tsx"
if [[ ! -f "${WAIVER_FILE}" ]]; then
  echo ""
  echo "FAIL: WithdrawalWaiverCheckbox.tsx missing"
  echo "      §356 Abs. 4/5 BGB requires waiver checkbox for immediate service start"
  VIOLATIONS=$((VIOLATIONS + 1))
else
  echo ""
  echo "OK  : WithdrawalWaiverCheckbox.tsx present (§356 compliance)"
  if ! grep -q "WITHDRAWAL_WAIVER_TEXT" "${WAIVER_FILE}"; then
    echo "FAIL: WITHDRAWAL_WAIVER_TEXT constant missing in WithdrawalWaiverCheckbox.tsx"
    VIOLATIONS=$((VIOLATIONS + 1))
  else
    echo "OK  : WITHDRAWAL_WAIVER_TEXT constant present"
  fi
fi

# Check 5: PricingPage integrates both components
PRICING_FILE="${SRC_DIR}/PricingPage.tsx"
if [[ -f "${PRICING_FILE}" ]]; then
  if grep -q "WithdrawalWaiverCheckbox" "${PRICING_FILE}"; then
    echo "OK  : PricingPage integrates WithdrawalWaiverCheckbox"
  else
    echo "FAIL: PricingPage missing WithdrawalWaiverCheckbox integration"
    VIOLATIONS=$((VIOLATIONS + 1))
  fi
  if grep -q "PaymentButton" "${PRICING_FILE}"; then
    echo "OK  : PricingPage integrates PaymentButton"
  else
    echo "FAIL: PricingPage missing PaymentButton integration"
    VIOLATIONS=$((VIOLATIONS + 1))
  fi
fi

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "=== Result ==="
if [[ ${VIOLATIONS} -eq 0 ]]; then
  echo "PASS: §312j + §356 compliance check clean (0 violations)"
  exit 0
else
  echo "FAIL: ${VIOLATIONS} violation(s) found — fix before Go-Live"
  exit 1
fi
