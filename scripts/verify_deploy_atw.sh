#!/usr/bin/env bash
# verify_deploy_atw.sh — R-NEW-AJ Deploy-Live-Verify Runner (M4)
#
# Runs after each ATW deploy. Curls all critical endpoints, verifies HTTP + body markers.
# On failure: dispatches ntfy + tg alert. On success: writes state/atw/last_verify.txt.
#
# USAGE:
#   verify_deploy_atw.sh              # full run against live URLs
#   verify_deploy_atw.sh --dry-run    # list targets, no curl
#   verify_deploy_atw.sh --help       # show usage
#
# ENV:
#   ATW_BASE_URL       default https://atw.agentic-movers.com
#   ATW_ALERT_DISABLED set to 1 to skip ntfy/tg (unit-test isolation)
#   NTFY_TOPIC_ATW     default atw-payments
#   NTFY_URL           default https://ntfy.sh
#
# EXIT CODES:
#   0 = all checks passed
#   1 = at least one check failed
#   2 = usage error

set -u

ATW_BASE_URL="${ATW_BASE_URL:-https://atw.agentic-movers.com}"
ATW_ALERT_DISABLED="${ATW_ALERT_DISABLED:-0}"
NTFY_TOPIC_ATW="${NTFY_TOPIC_ATW:-atw-payments}"
NTFY_URL="${NTFY_URL:-https://ntfy.sh}"

DRY_RUN=0
STATE_DIR="${ATW_STATE_DIR:-/var/lib/atw-verify}"

usage() {
    cat <<EOF
Usage: $(basename "$0") [--dry-run] [--help]

verify ATW deploy — curls critical endpoints, alerts on failure.

Env:
  ATW_BASE_URL         default https://atw.agentic-movers.com
  ATW_ALERT_DISABLED   set to 1 to skip ntfy/tg dispatch
  NTFY_TOPIC_ATW       default atw-payments
  NTFY_URL             default https://ntfy.sh

Exit: 0 all pass, 1 any fail, 2 usage error.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --help|-h) usage; exit 0 ;;
        --dry-run) DRY_RUN=1 ;;
        *) echo "unknown arg: $arg" >&2; usage >&2; exit 2 ;;
    esac
done

# Targets: url|expect-http|body-marker (empty marker = no body check)
TARGETS=(
    "${ATW_BASE_URL}/|200|"
    "${ATW_BASE_URL}/health|200|"
    "${ATW_BASE_URL}/pricing|200|"
    "${ATW_BASE_URL}/legal/impressum|200|"
    "${ATW_BASE_URL}/legal/agb|200|"
    "${ATW_BASE_URL}/legal/datenschutz|200|"
    "${ATW_BASE_URL}/webhooks/stripe|400|"
)

FAILED=()
PASSED=()

if [[ "$DRY_RUN" == "1" ]]; then
    echo "== dry-run: ${#TARGETS[@]} targets =="
    for t in "${TARGETS[@]}"; do
        IFS='|' read -r url expect marker <<< "$t"
        echo "  ${url} -> expect HTTP ${expect}"
    done
    exit 0
fi

for t in "${TARGETS[@]}"; do
    IFS='|' read -r url expect marker <<< "$t"
    if [[ -z "$marker" ]]; then
        http=$(curl -sSL -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")
        actual_body=""
    else
        body=$(curl -sSL --max-time 10 -w "|||HTTP:%{http_code}" "$url" 2>/dev/null || echo "|||HTTP:000")
        http="${body##*|||HTTP:}"
        actual_body="${body%|||HTTP:*}"
    fi

    if [[ "$http" != "$expect" ]]; then
        FAILED+=("${url} HTTP=${http} expected=${expect}")
        echo "FAIL ${url} HTTP=${http} expected=${expect}"
    elif [[ -n "$marker" ]] && [[ "$actual_body" != *"$marker"* ]]; then
        FAILED+=("${url} HTTP=${http} body-marker '${marker}' missing")
        echo "FAIL ${url} HTTP=${http} body-marker missing"
    else
        PASSED+=("${url}")
        echo "OK   ${url} HTTP=${http}"
    fi
done

TOTAL="${#TARGETS[@]}"
NUM_PASS="${#PASSED[@]}"
NUM_FAIL="${#FAILED[@]}"

echo
echo "== Result: ${NUM_PASS}/${TOTAL} passed, ${NUM_FAIL} failed =="

if [[ "$NUM_FAIL" -eq 0 ]]; then
    mkdir -p "$STATE_DIR" 2>/dev/null || true
    date -u -Iseconds > "$STATE_DIR/last_verify_ok.txt" 2>/dev/null || true
    exit 0
fi

# ── Failure path — dispatch alerts unless disabled ────────────────────────
MSG="ATW Deploy-Verify FAIL (${NUM_FAIL}/${TOTAL})"
FAIL_LIST=$(printf '  - %s\n' "${FAILED[@]}")

if [[ "$ATW_ALERT_DISABLED" == "1" ]]; then
    echo "alerts skipped (ATW_ALERT_DISABLED=1)"
    exit 1
fi

# ntfy
if command -v curl >/dev/null 2>&1; then
    curl -sS -X POST \
        -H "Title: ATW Deploy-Verify FAIL" \
        -H "Priority: high" \
        -H "Tags: rotating_light,warning" \
        --data "${MSG}
${FAIL_LIST}" \
        --max-time 5 \
        "${NTFY_URL}/${NTFY_TOPIC_ATW}" > /dev/null 2>&1 || \
        echo "ntfy dispatch failed" >&2
fi

# tg (best-effort, --force bypasses rate-limit)
if command -v tg >/dev/null 2>&1; then
    tg --force "${MSG}
${FAIL_LIST}" > /dev/null 2>&1 || echo "tg dispatch failed" >&2
fi

exit 1
