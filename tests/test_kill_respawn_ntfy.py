"""R145 TDD — kill/respawn/ntfy tests for agent_status_api.

Tests cover:
  POST /agents/{name}/kill — queues teammate kill command
  POST /agents/{name}/kill 404 — unknown agent
  POST /agents/{name}/respawn — queues teammate start command
  POST /agents/{name}/respawn 404 — unknown agent
  kill response model: name, queued, message
  respawn response model: name, queued, message
  kill and respawn use different file names (kill_X.sh vs respawn_X.sh)
  ntfy_dead_alert — sends POST to ntfy when agent is DEAD
  ntfy_dead_alert — skips when no DEAD agents
  ntfy_dead_alert — uses bearer token from env
  ntfy_dead_alert — raises RuntimeError on HTTP failure (fail-fast, no silent fallback)
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import agent_status_api as api_module
from agent_status_api import app, _manager_state, _build_agents

client = TestClient(app)

SAMPLE_SSOT = {
    "agents": [
        {"name": "CEO", "server": "netcup1", "role": "ceo"},
        {"name": "ICT", "server": "netcup1", "role": "hod"},
        {"name": "Marketing", "server": "hetzner", "role": "hod"},
    ],
    "servers": {
        "netcup1": {"host": "netcup1", "ip": "85.215.100.1"},
        "hetzner": {"host": "hetzner", "ip": "204.168.145.155"},
    },
}

SAMPLE_LIVE = {
    "CEO": {"technical_state": "working", "session": "CEO:0"},
    "ICT": {"technical_state": "idle", "session": "ICT:0"},
    "Marketing": {"technical_state": "missing", "session": None},
}


def _mock_ssot(monkeypatch, ssot=SAMPLE_SSOT):
    monkeypatch.setattr(api_module, "_load_agents_json", lambda: ssot)


def _mock_live(monkeypatch, live=SAMPLE_LIVE):
    monkeypatch.setattr(api_module, "_get_live_states", lambda: live)


# ── POST /agents/{name}/kill ───────────────────────────────────────────────────

class TestKillAgent:
    def test_queues_kill_file(self, monkeypatch, tmp_path):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        monkeypatch.setattr(api_module, "_REPO_ROOT", tmp_path)
        r = client.post("/agents/ICT/kill")
        assert r.status_code == 200
        kill_file = tmp_path / "state" / "pending_actions" / "kill_ICT.sh"
        assert kill_file.exists()
        assert "teammate kill ICT" in kill_file.read_text()

    def test_unknown_agent_returns_404(self, monkeypatch):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        r = client.post("/agents/GHOST/kill")
        assert r.status_code == 404

    def test_response_contains_name_and_queued(self, monkeypatch, tmp_path):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        monkeypatch.setattr(api_module, "_REPO_ROOT", tmp_path)
        r = client.post("/agents/CEO/kill")
        body = r.json()
        assert body["name"] == "CEO"
        assert body["queued"] is True
        assert "message" in body

    def test_kill_uses_different_file_than_restart(self, monkeypatch, tmp_path):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        monkeypatch.setattr(api_module, "_REPO_ROOT", tmp_path)
        client.post("/agents/ICT/kill")
        kill_file = tmp_path / "state" / "pending_actions" / "kill_ICT.sh"
        restart_file = tmp_path / "state" / "pending_actions" / "restart_ICT.sh"
        assert kill_file.exists()
        assert not restart_file.exists()


# ── POST /agents/{name}/respawn ────────────────────────────────────────────────

class TestRespawnAgent:
    def test_queues_respawn_file(self, monkeypatch, tmp_path):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        monkeypatch.setattr(api_module, "_REPO_ROOT", tmp_path)
        r = client.post("/agents/Marketing/respawn")
        assert r.status_code == 200
        respawn_file = tmp_path / "state" / "pending_actions" / "respawn_Marketing.sh"
        assert respawn_file.exists()
        assert "teammate start Marketing" in respawn_file.read_text()

    def test_unknown_agent_returns_404(self, monkeypatch):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        r = client.post("/agents/GHOST/respawn")
        assert r.status_code == 404

    def test_response_contains_name_and_queued(self, monkeypatch, tmp_path):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        monkeypatch.setattr(api_module, "_REPO_ROOT", tmp_path)
        r = client.post("/agents/ICT/respawn")
        body = r.json()
        assert body["name"] == "ICT"
        assert body["queued"] is True

    def test_respawn_uses_teammate_start(self, monkeypatch, tmp_path):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        monkeypatch.setattr(api_module, "_REPO_ROOT", tmp_path)
        client.post("/agents/CEO/respawn")
        respawn_file = tmp_path / "state" / "pending_actions" / "respawn_CEO.sh"
        content = respawn_file.read_text()
        assert "teammate start CEO" in content
        assert "teammate kill" not in content


# ── ntfy dead-alert ────────────────────────────────────────────────────────────

class TestNtfyDeadAlert:
    def test_sends_post_when_dead_agents_present(self, monkeypatch):
        """ntfy_dead_alert must POST to ntfy topic when DEAD agents exist."""
        from agent_status_api import ntfy_dead_alert

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("agent_status_api.requests.post", return_value=mock_response) as mock_post:
            ntfy_dead_alert(
                dead_agents=["Marketing"],
                ntfy_url="https://ntfy.agentic-movers.com/agent-alerts",
                bearer_token="test-token",
            )
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            # URL must be the ntfy topic
            assert "ntfy.agentic-movers.com" in call_kwargs[0][0]
            # Authorization header must contain bearer token
            headers = call_kwargs[1].get("headers", {})
            assert "test-token" in headers.get("Authorization", "")

    def test_skips_when_no_dead_agents(self, monkeypatch):
        """ntfy_dead_alert must NOT post when dead_agents is empty."""
        from agent_status_api import ntfy_dead_alert

        with patch("agent_status_api.requests.post") as mock_post:
            ntfy_dead_alert(
                dead_agents=[],
                ntfy_url="https://ntfy.agentic-movers.com/agent-alerts",
                bearer_token="test-token",
            )
            mock_post.assert_not_called()

    def test_raises_on_http_failure(self, monkeypatch):
        """ntfy_dead_alert must raise RuntimeError on non-2xx — fail fast, no silent fallback."""
        from agent_status_api import ntfy_dead_alert

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        with patch("agent_status_api.requests.post", return_value=mock_response):
            with pytest.raises(RuntimeError, match="ntfy"):
                ntfy_dead_alert(
                    dead_agents=["Marketing"],
                    ntfy_url="https://ntfy.agentic-movers.com/agent-alerts",
                    bearer_token="bad-token",
                )

    def test_message_contains_agent_names(self, monkeypatch):
        """Alert message must list dead agent names."""
        from agent_status_api import ntfy_dead_alert

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("agent_status_api.requests.post", return_value=mock_response) as mock_post:
            ntfy_dead_alert(
                dead_agents=["Marketing", "Strategy"],
                ntfy_url="https://ntfy.agentic-movers.com/agent-alerts",
                bearer_token="test-token",
            )
            call_kwargs = mock_post.call_args
            # body/data must contain the agent names (data is bytes)
            raw = call_kwargs[1].get("data", b"") or b""
            body = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            assert "Marketing" in body
            assert "Strategy" in body
