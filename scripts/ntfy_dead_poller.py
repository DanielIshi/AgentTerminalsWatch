#!/usr/bin/env python3
"""ntfy_dead_poller — Poll agent status every 5 min, alert ntfy on DEAD agents.

Usage:
    python3 scripts/ntfy_dead_poller.py [--once]

Options:
    --once   Run a single check and exit (for cron / testing).

Environment (loaded from /home/claude/clawd/.env if available):
    NTFY_BEARER_TOKEN   Bearer token for ntfy auth
    NTFY_TOPIC_URL      Full ntfy topic URL (default: https://ntfy.agentic-movers.com/agent-alerts)
    API_BASE_URL        AgentTerminalsWatch API base (default: http://127.0.0.1:8001)
    API_USER            Basic-auth username (default: admin)
    API_PASSWORD        Basic-auth password

Fail-fast per Daniel-Direktive: RuntimeError on API or ntfy failure.
No silent fallbacks, no placeholder outputs.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────

_ENV_FILE = Path("/home/claude/clawd/.env")
_POLL_INTERVAL_SECONDS = 300  # 5 minutes


def _load_env() -> None:
    """Load /home/claude/clawd/.env into os.environ if the file exists."""
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip()


def _cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# ── Core ──────────────────────────────────────────────────────────────────────

def fetch_dead_agents(api_base: str, user: str, password: str) -> list[str]:
    """Return names of agents in DEAD state from the API.

    Raises RuntimeError on HTTP error — fail fast.
    """
    url = f"{api_base}/agents?state=DEAD"
    try:
        r = requests.get(url, auth=(user, password) if user else None, timeout=15)
    except requests.RequestException as exc:
        raise RuntimeError(f"API unreachable at {url}: {exc}") from exc

    if r.status_code != 200:
        raise RuntimeError(f"API error {r.status_code} fetching dead agents: {r.text}")

    return [a["name"] for a in r.json()]


def check_and_alert(
    api_base: str,
    api_user: str,
    api_password: str,
    ntfy_url: str,
    bearer_token: str,
) -> list[str]:
    """Fetch dead agents and send ntfy alert if any. Returns dead agent names."""
    # Import from sibling directory — add project root to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agent_status_api import ntfy_dead_alert

    dead = fetch_dead_agents(api_base, api_user, api_password)
    if dead:
        print(f"[ntfy-poller] DEAD agents: {dead} — sending alert", flush=True)
        ntfy_dead_alert(
            dead_agents=dead,
            ntfy_url=ntfy_url,
            bearer_token=bearer_token,
        )
    else:
        print("[ntfy-poller] All agents alive — no alert sent", flush=True)
    return dead


def main() -> None:
    _load_env()

    parser = argparse.ArgumentParser(description="Poll agent status and alert via ntfy")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    api_base = _cfg("API_BASE_URL", "http://127.0.0.1:8001")
    api_user = _cfg("API_USER", "admin")
    api_password = _cfg("API_PASSWORD", "")
    ntfy_url = _cfg("NTFY_TOPIC_URL", "https://ntfy.agentic-movers.com/agent-alerts")
    # NTFY_USER_TOKEN = ntfy user token (tk_...) — preferred
    # NTFY_BEARER_TOKEN = legacy key name, used as fallback
    bearer_token = _cfg("NTFY_USER_TOKEN", "") or _cfg("NTFY_BEARER_TOKEN", "")

    if not bearer_token:
        raise RuntimeError(
            "NTFY_USER_TOKEN (or NTFY_BEARER_TOKEN) not set — cannot send alerts. "
            "Set it in /home/claude/clawd/.env or environment."
        )

    if args.once:
        dead = check_and_alert(api_base, api_user, api_password, ntfy_url, bearer_token)
        sys.exit(0 if not dead else 1)

    print(f"[ntfy-poller] Starting — polling every {_POLL_INTERVAL_SECONDS}s", flush=True)
    while True:
        try:
            check_and_alert(api_base, api_user, api_password, ntfy_url, bearer_token)
        except RuntimeError as exc:
            # Log but don't crash the loop — transient API errors are possible
            print(f"[ntfy-poller] ERROR: {exc}", file=sys.stderr, flush=True)
        time.sleep(_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
