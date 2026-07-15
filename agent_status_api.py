"""
agent_status_api — FastAPI backend for AgentTerminalsWatch.

Wraps SCRIPTS/ops/agent-status.py data via agents.json and subprocess.

Routes:
  GET  /agents              — all agents (optional ?state= filter: ACTIVE|WAITING|DEAD)
  GET  /agents/{name}       — single agent by name
  GET  /servers             — server list with host/ip
  POST /agents/{name}/restart — queue restart command (writes to state/pending_actions/)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# Resolve repo root by walking up until agents.json is found.
# The file lives at /home/claude/projects/AgentTerminalsWatch/agent_status_api.py
# but agents.json is in /home/claude/clawd — hard-coded parent counts break.
def _find_repo_root() -> Path:
    # Prefer explicit env var (deployment / tests), then walk up, then fall back
    # to the known clawd location.
    import os
    if env := os.environ.get("CLAWD_REPO_ROOT"):
        return Path(env)
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if (candidate / "agents.json").exists():
            return candidate
    return Path("/home/claude/clawd")

_REPO_ROOT = _find_repo_root()
_AGENTS_JSON = _REPO_ROOT / "agents.json"
_AGENT_STATUS_PY = _REPO_ROOT / "SCRIPTS" / "ops" / "agent-status.py"

app = FastAPI(title="AgentTerminalsWatch API", version="0.1.0")


# ── Models ────────────────────────────────────────────────────────────────────

class AgentInfo(BaseModel):
    name: str
    server: str
    state: str           # ACTIVE | WAITING | DEAD (manager-facing)
    technical_state: str
    role: str
    session: Optional[str] = None


class ServerInfo(BaseModel):
    name: str
    host: str
    ip: str


class RestartResponse(BaseModel):
    name: str
    queued: bool
    message: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_agents_json() -> dict:
    if not _AGENTS_JSON.exists():
        raise HTTPException(status_code=503, detail="agents.json not found")
    try:
        with _AGENTS_JSON.open() as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=503, detail=f"agents.json malformed: {exc}") from exc


def _get_live_states() -> dict[str, dict]:
    """Run agent-status.py --json and return parsed output dict keyed by agent name."""
    if not _AGENT_STATUS_PY.exists():
        return {}
    try:
        result = subprocess.run(
            [sys.executable, str(_AGENT_STATUS_PY), "--json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {}
        data = json.loads(result.stdout)
        if isinstance(data, list):
            return {entry["name"]: entry for entry in data if "name" in entry}
        return data
    except Exception:
        return {}


def _manager_state(technical: str) -> str:
    mapping = {
        "working": "ACTIVE", "starting": "ACTIVE",
        "idle": "WAITING", "stuck": "WAITING",
        "down": "DEAD", "offline": "DEAD", "missing": "DEAD", "unknown": "DEAD",
    }
    return mapping.get(technical, "DEAD")


def _build_agents(ssot: dict, live: dict[str, dict]) -> list[AgentInfo]:
    agents = []
    for agent in ssot.get("agents", []):
        name = agent.get("name", "")
        live_entry = live.get(name, {})
        technical = live_entry.get("technical_state", live_entry.get("state", "unknown"))
        agents.append(AgentInfo(
            name=name,
            server=agent.get("server", ""),
            state=_manager_state(technical),
            technical_state=technical,
            role=agent.get("role", ""),
            session=live_entry.get("session"),
        ))
    return agents


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/agents", response_model=list[AgentInfo])
def list_agents(state: Optional[str] = Query(None, description="Filter: ACTIVE|WAITING|DEAD")):
    ssot = _load_agents_json()
    live = _get_live_states()
    agents = _build_agents(ssot, live)
    if state:
        agents = [a for a in agents if a.state == state.upper()]
    return agents


@app.get("/agents/{name}", response_model=AgentInfo)
def get_agent(name: str):
    ssot = _load_agents_json()
    live = _get_live_states()
    agents = _build_agents(ssot, live)
    for agent in agents:
        if agent.name == name:
            return agent
    raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")


@app.get("/servers", response_model=list[ServerInfo])
def list_servers():
    ssot = _load_agents_json()
    servers = ssot.get("servers", {})
    return [
        ServerInfo(name=name, host=cfg.get("host", name), ip=cfg.get("ip", ""))
        for name, cfg in servers.items()
    ]


@app.post("/agents/{name}/restart", response_model=RestartResponse)
def restart_agent(name: str):
    ssot = _load_agents_json()
    known = {a.get("name") for a in ssot.get("agents", [])}
    if name not in known:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    pending_dir = _REPO_ROOT / "state" / "pending_actions"
    pending_dir.mkdir(parents=True, exist_ok=True)
    restart_file = pending_dir / f"restart_{name}.sh"
    restart_file.write_text(
        f"#!/bin/bash\n# Auto-generated restart request for {name}\n"
        f"teammate start {name}\n"
    )
    return RestartResponse(
        name=name,
        queued=True,
        message=f"Restart queued at {restart_file.name} — run new_session_startup.sh to execute",
    )
