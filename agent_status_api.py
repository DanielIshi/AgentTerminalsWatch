"""
agent_status_api — FastAPI backend for AgentTerminalsWatch.

Wraps SCRIPTS/ops/agent-status.py data via agents.json and subprocess.

Routes:
  GET  /agents                  — all agents (optional ?state= filter: ACTIVE|WAITING|DEAD)
  GET  /agents/{name}           — single agent by name
  GET  /servers                 — server list with host/ip
  POST /agents/{name}/restart   — queue restart command (writes to state/pending_actions/)
  POST /agents/{name}/kill      — queue teammate kill command
  POST /agents/{name}/respawn   — queue teammate start command

ntfy integration:
  ntfy_dead_alert(dead_agents, ntfy_url, bearer_token) — POST to ntfy when agents are DEAD
  Raises RuntimeError on HTTP failure (fail fast — no silent fallback per Daniel-Direktive).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import requests
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


# KillResponse and RespawnResponse share the same shape as RestartResponse.
KillResponse = RestartResponse
RespawnResponse = RestartResponse


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_agents_json() -> dict:
    if not _AGENTS_JSON.exists():
        raise HTTPException(status_code=503, detail="agents.json not found")
    try:
        with _AGENTS_JSON.open() as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=503, detail=f"agents.json malformed: {exc}") from exc


# Ergebnis von agent-status.py fuer kurze Zeit halten. Gemessen 06.09.2026:
# der Lauf dauert 29,2 s bei 30 s Timeout -- ohne Cache wartet jeder
# Seitenaufruf fast eine halbe Minute, und zwei Nutzer starten ihn doppelt.
_LIVE_CACHE: dict[str, object] = {"zeit": 0.0, "daten": {}}
_LIVE_CACHE_SEKUNDEN = 20.0


def _get_live_states() -> dict[str, dict]:
    """Run agent-status.py --json and return parsed output dict keyed by agent name.

    Das Ergebnis wird _LIVE_CACHE_SEKUNDEN lang wiederverwendet.
    """
    if not _AGENT_STATUS_PY.exists():
        return {}

    jetzt = time.monotonic()
    if _LIVE_CACHE["daten"] and jetzt - float(_LIVE_CACHE["zeit"]) < _LIVE_CACHE_SEKUNDEN:
        return _LIVE_CACHE["daten"]  # type: ignore[return-value]
    try:
        result = subprocess.run(
            [sys.executable, str(_AGENT_STATUS_PY), "--json"],
            capture_output=True, text=True, timeout=90  # 06.09.2026: agent-status.py braucht gemessen 29,2 s; bei 30 s lief
            # der Aufruf regelmaessig in den Timeout, lieferte {} und alle
            # Agenten erschienen als DEAD. Leeres wird nicht gecacht, also
            # wiederholte sich das bei jedem Seitenaufruf.
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {}
        # agent-status.py --json liefert JSON LINES: ein Objekt je Zeile, kein
        # einzelnes Dokument. json.loads() darauf ergibt "Extra data: line 2
        # column 1" -- die Ausnahme wurde unten still verschluckt, _get_live_states
        # gab {} zurueck und JEDER Agent erschien als DEAD. Gemessen 06.09.2026.
        roh = result.stdout.strip()
        try:
            data = json.loads(roh)
        except json.JSONDecodeError:
            data = [json.loads(z) for z in roh.splitlines() if z.strip()]
        if isinstance(data, list):
            data = {entry["name"]: entry for entry in data if "name" in entry}
        _LIVE_CACHE["zeit"] = time.monotonic()
        _LIVE_CACHE["daten"] = data
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


def _agenten_paare(ssot: dict) -> list[tuple[str, dict]]:
    """(name, agent) aus agents.json -- vertraegt Dict- und Listenform.

    Die SSOT fuehrt "agents" als Objekt Name -> Agent. Aelterer Code hier ging
    von einer Liste aus und lief deshalb ueber die Schluessel: 'str' object has
    no attribute 'get' (gemessen 06.09.2026, GET /agents gab 500).
    """
    roh = ssot.get("agents", {})
    if isinstance(roh, dict):
        return [(name, obj if isinstance(obj, dict) else {})
                for name, obj in roh.items()]
    paare = []
    for eintrag in roh or []:
        if isinstance(eintrag, dict):
            paare.append((eintrag.get("name", ""), eintrag))
    return paare


def _build_agents(ssot: dict, live: dict[str, dict]) -> list[AgentInfo]:
    agents = []
    for name, agent in _agenten_paare(ssot):
        live_entry = live.get(name, {})
        technical = live_entry.get("technical_state", live_entry.get("state", "unknown"))
        agents.append(AgentInfo(
            name=name,
            # "or" statt Default: agents.json fuehrt "server": null fuer Agenten
            # ohne eigenen Host (WEB, WIN, CODEX-WEB). .get(k, "") liefert dann
            # None, nicht "" -- und pydantic lehnt None fuer ein str-Feld ab.
            # Gemessen 06.09.2026: ValidationError, GET /agents gab 500.
            server=agent.get("server") or "",
            state=_manager_state(technical),
            technical_state=technical,
            role=agent.get("role") or "",
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
    known = {n for n, _ in _agenten_paare(ssot)}
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


@app.post("/agents/{name}/kill", response_model=KillResponse)
def kill_agent(name: str):
    """Queue a teammate kill command for the given agent."""
    ssot = _load_agents_json()
    known = {n for n, _ in _agenten_paare(ssot)}
    if name not in known:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    pending_dir = _REPO_ROOT / "state" / "pending_actions"
    pending_dir.mkdir(parents=True, exist_ok=True)
    kill_file = pending_dir / f"kill_{name}.sh"
    kill_file.write_text(
        f"#!/bin/bash\n# Auto-generated kill request for {name}\n"
        f"teammate kill {name}\n"
    )
    return KillResponse(
        name=name,
        queued=True,
        message=f"Kill queued at {kill_file.name} — run new_session_startup.sh to execute",
    )


@app.post("/agents/{name}/respawn", response_model=RespawnResponse)
def respawn_agent(name: str):
    """Queue a teammate start command to respawn the given agent."""
    ssot = _load_agents_json()
    known = {n for n, _ in _agenten_paare(ssot)}
    if name not in known:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    pending_dir = _REPO_ROOT / "state" / "pending_actions"
    pending_dir.mkdir(parents=True, exist_ok=True)
    respawn_file = pending_dir / f"respawn_{name}.sh"
    respawn_file.write_text(
        f"#!/bin/bash\n# Auto-generated respawn request for {name}\n"
        f"teammate start {name}\n"
    )
    return RespawnResponse(
        name=name,
        queued=True,
        message=f"Respawn queued at {respawn_file.name} — run new_session_startup.sh to execute",
    )


# ── ntfy integration ──────────────────────────────────────────────────────────

def ntfy_dead_alert(
    dead_agents: list[str],
    ntfy_url: str,
    bearer_token: str,
) -> None:
    """Send a push notification to ntfy when agents are in DEAD state.

    Raises RuntimeError on HTTP failure — fail fast, no silent fallback
    (Daniel-Direktive: EHRLICHES SCHEITERN).

    Args:
        dead_agents: List of agent names in DEAD state. No-op if empty.
        ntfy_url: Full ntfy topic URL, e.g. https://ntfy.agentic-movers.com/agent-alerts
        bearer_token: ntfy bearer token for Authorization header.
    """
    if not dead_agents:
        return

    agent_list = ", ".join(dead_agents)
    message = f"DEAD agents detected: {agent_list}"

    response = requests.post(
        ntfy_url,
        data=message.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Title": "AgentTerminalsWatch Alert",
            "Priority": "high",
            "Tags": "warning,robot",
        },
    )

    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError(
            f"ntfy POST failed: HTTP {response.status_code} — {response.text}"
        )
