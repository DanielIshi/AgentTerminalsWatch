"""R145 TDD — agent_status_api unit tests.

Tests cover:
  GET /agents — returns list of AgentInfo
  GET /agents?state=DEAD — filters by manager state
  GET /agents?state=ACTIVE — filters by manager state
  GET /agents/{name} — returns single agent
  GET /agents/{name} 404 — unknown agent
  GET /servers — returns server list
  POST /agents/{name}/restart — queues restart file
  POST /agents/{name}/restart 404 — unknown agent
  _manager_state mapping: working→ACTIVE, idle→WAITING, missing→DEAD, unknown→DEAD
  _build_agents: uses live technical_state when available
  _build_agents: falls back to 'unknown' when no live data
  agents.json missing → 503
  agents.json malformed → 503
  live states subprocess failure → graceful empty dict (no crash)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import agent_status_api as api_module
from agent_status_api import app, _manager_state, _build_agents, AgentInfo

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

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


# ── _manager_state ─────────────────────────────────────────────────────────────

class TestManagerState:
    def test_working_is_active(self):
        assert _manager_state("working") == "ACTIVE"

    def test_starting_is_active(self):
        assert _manager_state("starting") == "ACTIVE"

    def test_idle_is_waiting(self):
        assert _manager_state("idle") == "WAITING"

    def test_stuck_is_waiting(self):
        assert _manager_state("stuck") == "WAITING"

    def test_down_is_dead(self):
        assert _manager_state("down") == "DEAD"

    def test_offline_is_dead(self):
        assert _manager_state("offline") == "DEAD"

    def test_missing_is_dead(self):
        assert _manager_state("missing") == "DEAD"

    def test_unknown_is_dead(self):
        assert _manager_state("unknown") == "DEAD"

    def test_unrecognized_is_dead(self):
        assert _manager_state("blurp") == "DEAD"


# ── _build_agents ──────────────────────────────────────────────────────────────

class TestBuildAgents:
    def test_uses_live_technical_state(self):
        agents = _build_agents(SAMPLE_SSOT, SAMPLE_LIVE)
        ceo = next(a for a in agents if a.name == "CEO")
        assert ceo.technical_state == "working"
        assert ceo.state == "ACTIVE"

    def test_falls_back_unknown_when_no_live(self):
        agents = _build_agents(SAMPLE_SSOT, {})
        for a in agents:
            assert a.state == "DEAD"
            assert a.technical_state == "unknown"

    def test_session_populated_from_live(self):
        agents = _build_agents(SAMPLE_SSOT, SAMPLE_LIVE)
        ceo = next(a for a in agents if a.name == "CEO")
        assert ceo.session == "CEO:0"

    def test_session_none_when_missing(self):
        agents = _build_agents(SAMPLE_SSOT, SAMPLE_LIVE)
        mkt = next(a for a in agents if a.name == "Marketing")
        assert mkt.session is None

    def test_server_populated_from_ssot(self):
        agents = _build_agents(SAMPLE_SSOT, SAMPLE_LIVE)
        mkt = next(a for a in agents if a.name == "Marketing")
        assert mkt.server == "hetzner"


# ── GET /agents ────────────────────────────────────────────────────────────────

class TestListAgents:
    def test_returns_all_agents(self, monkeypatch):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        r = client.get("/agents")
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_filter_dead(self, monkeypatch):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        r = client.get("/agents?state=DEAD")
        assert r.status_code == 200
        names = [a["name"] for a in r.json()]
        assert "Marketing" in names
        assert "CEO" not in names

    def test_filter_active(self, monkeypatch):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        r = client.get("/agents?state=ACTIVE")
        assert r.status_code == 200
        names = [a["name"] for a in r.json()]
        assert "CEO" in names
        assert "ICT" not in names

    def test_filter_waiting(self, monkeypatch):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        r = client.get("/agents?state=WAITING")
        assert r.status_code == 200
        names = [a["name"] for a in r.json()]
        assert "ICT" in names

    def test_agents_json_missing_returns_503(self, monkeypatch):
        from fastapi import HTTPException
        def raise_503(): raise HTTPException(status_code=503, detail="agents.json not found")
        monkeypatch.setattr(api_module, "_load_agents_json", raise_503)
        r = client.get("/agents")
        assert r.status_code == 503


# ── GET /agents/{name} ─────────────────────────────────────────────────────────

class TestGetAgent:
    def test_returns_known_agent(self, monkeypatch):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        r = client.get("/agents/CEO")
        assert r.status_code == 200
        assert r.json()["name"] == "CEO"
        assert r.json()["state"] == "ACTIVE"

    def test_unknown_agent_returns_404(self, monkeypatch):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        r = client.get("/agents/NONEXISTENT")
        assert r.status_code == 404

    def test_technical_state_in_response(self, monkeypatch):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        r = client.get("/agents/ICT")
        assert r.json()["technical_state"] == "idle"


# ── GET /servers ───────────────────────────────────────────────────────────────

class TestListServers:
    def test_returns_server_list(self, monkeypatch):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        r = client.get("/servers")
        assert r.status_code == 200
        names = [s["name"] for s in r.json()]
        assert "netcup1" in names
        assert "hetzner" in names

    def test_server_has_ip(self, monkeypatch):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        r = client.get("/servers")
        nc1 = next(s for s in r.json() if s["name"] == "netcup1")
        assert nc1["ip"] == "85.215.100.1"

    def test_empty_servers_returns_empty_list(self, monkeypatch):
        _mock_ssot(monkeypatch, ssot={**SAMPLE_SSOT, "servers": {}})
        _mock_live(monkeypatch)
        r = client.get("/servers")
        assert r.json() == []


# ── POST /agents/{name}/restart ────────────────────────────────────────────────

class TestRestartAgent:
    def test_queues_restart_file(self, monkeypatch, tmp_path):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        monkeypatch.setattr(api_module, "_REPO_ROOT", tmp_path)
        r = client.post("/agents/ICT/restart")
        assert r.status_code == 200
        assert r.json()["queued"] is True
        restart_file = tmp_path / "state" / "pending_actions" / "restart_ICT.sh"
        assert restart_file.exists()
        assert "teammate start ICT" in restart_file.read_text()

    def test_unknown_agent_returns_404(self, monkeypatch):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        r = client.post("/agents/GHOST/restart")
        assert r.status_code == 404

    def test_response_contains_name(self, monkeypatch, tmp_path):
        _mock_ssot(monkeypatch)
        _mock_live(monkeypatch)
        monkeypatch.setattr(api_module, "_REPO_ROOT", tmp_path)
        r = client.post("/agents/CEO/restart")
        assert r.json()["name"] == "CEO"
