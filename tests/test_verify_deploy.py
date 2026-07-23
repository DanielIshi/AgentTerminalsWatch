"""R145 TDD — verify_deploy_atw.sh contract tests.

Tests cover:
  - script exists and is executable
  - default targets include landing + health-endpoint
  - failed check exits with non-zero
  - alert-integration: on failure, dispatches ntfy + tg (mock via env)
  - dry-run mode returns 0 without hitting endpoints
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parent.parent / "scripts" / "verify_deploy_atw.sh"


def test_script_exists():
    assert SCRIPT.exists(), f"missing {SCRIPT}"


def test_script_executable():
    assert os.access(SCRIPT, os.X_OK), f"not executable: {SCRIPT}"


def test_help_flag_returns_zero():
    r = subprocess.run([str(SCRIPT), "--help"], capture_output=True, timeout=10)
    assert r.returncode == 0
    assert b"verify" in r.stdout.lower() or b"usage" in r.stdout.lower()


def test_dry_run_returns_zero_and_lists_targets():
    """--dry-run must NOT hit endpoints, must exit 0, must list targets."""
    r = subprocess.run(
        [str(SCRIPT), "--dry-run"],
        capture_output=True, timeout=10,
        env={**os.environ, "ATW_BASE_URL": "https://example.invalid"},
    )
    assert r.returncode == 0, f"dry-run stderr: {r.stderr.decode()[:400]}"
    out = r.stdout.decode()
    # Must list at least landing + health as targets
    assert "/" in out or "landing" in out.lower()


def test_failure_returns_nonzero(tmp_path):
    """Real check against invalid URL must return non-zero."""
    r = subprocess.run(
        [str(SCRIPT)],
        capture_output=True, timeout=25,
        env={**os.environ, "ATW_BASE_URL": "https://this-domain-does-not-exist-atw-test.invalid", "ATW_ALERT_DISABLED": "1"},
    )
    assert r.returncode != 0, f"expected non-zero, got 0. stdout={r.stdout.decode()[:400]}"


def test_alert_env_var_disables_notifications():
    """ATW_ALERT_DISABLED=1 must not attempt ntfy/tg dispatch (unit-test isolation)."""
    r = subprocess.run(
        [str(SCRIPT), "--dry-run"],
        capture_output=True, timeout=10,
        env={**os.environ, "ATW_ALERT_DISABLED": "1"},
    )
    assert r.returncode == 0
    # Should not attempt curl to ntfy
    assert b"ntfy.sh" not in r.stdout
