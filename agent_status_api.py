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
import threading
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


# Ergebnis von agent-status.py zwischenspeichern und im HINTERGRUND aktuell
# halten. Der Lauf dauert gemessen 90 s (04.10.2026; war 29,2 s am 06.09.2026
# -- waechst mit toten Servern, deren SSH-Proben in Timeouts laufen). Solange er
# synchron im Request lief, blockierte JEDER Seitenaufruf bis zu 90 s und die
# Agent-Terminals-Ansicht blieb solange leer ("Loading agents...").
# Jetzt laeuft agent-status.py in einem Daemon-Thread in Dauerschleife und
# schreibt das Ergebnis in _LIVE_CACHE (+ Datei fuer warmen Neustart);
# /agents liefert den Cache in Millisekunden und blockiert NIE.
_LIVE_CACHE: dict[str, object] = {"zeit": 0.0, "daten": {}}
_LIVE_CACHE_FILE = Path(__file__).resolve().parent / ".agents_cache.json"
_REFRESH_INTERVAL_SEKUNDEN = 20.0   # Pause zwischen zwei Hintergrund-Laeufen
_PROBE_TIMEOUT_SEKUNDEN = 120       # agent-status.py darf bis dahin brauchen
_refresher_gestartet = False
_refresher_lock = threading.Lock()


def _run_probe() -> dict[str, dict]:
    """agent-status.py --json EINMAL ausfuehren und als {name: eintrag} parsen.
    Laeuft ausschliesslich im Hintergrund-Thread, nie im Request."""
    if not _AGENT_STATUS_PY.exists():
        return {}
    result = subprocess.run(
        [sys.executable, str(_AGENT_STATUS_PY), "--json"],
        capture_output=True, text=True, timeout=_PROBE_TIMEOUT_SEKUNDEN,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    # agent-status.py --json liefert JSON LINES: ein Objekt je Zeile, kein
    # einzelnes Dokument. json.loads() darauf ergibt "Extra data: line 2
    # column 1" -- deshalb Zeile fuer Zeile als Fallback (gemessen 06.09.2026).
    roh = result.stdout.strip()
    try:
        data = json.loads(roh)
    except json.JSONDecodeError:
        data = [json.loads(z) for z in roh.splitlines() if z.strip()]
    if isinstance(data, list):
        data = {entry["name"]: entry for entry in data if "name" in entry}
    return data


def _cache_setzen(daten: dict[str, dict]) -> None:
    _LIVE_CACHE["daten"] = daten
    _LIVE_CACHE["zeit"] = time.time()
    try:
        _LIVE_CACHE_FILE.write_text(
            json.dumps({"zeit": _LIVE_CACHE["zeit"], "daten": daten}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass  # Datei-Cache ist nur Komfort fuer warmen Neustart; nicht kritisch.


def _cache_aus_datei_laden() -> None:
    try:
        roh = json.loads(_LIVE_CACHE_FILE.read_text(encoding="utf-8"))
        if isinstance(roh.get("daten"), dict):
            _LIVE_CACHE["daten"] = roh["daten"]
            _LIVE_CACHE["zeit"] = float(roh.get("zeit", 0.0))
    except (OSError, json.JSONDecodeError, ValueError, AttributeError):
        pass


def _refresher_loop() -> None:
    while True:
        try:
            daten = _run_probe()
            if daten:                       # Leeres nie cachen -- sonst alle DEAD.
                _cache_setzen(daten)
        except Exception:
            pass                            # Schleife ueberlebt jeden Einzelfehler.
        time.sleep(_REFRESH_INTERVAL_SEKUNDEN)


def _refresher_starten() -> None:
    """Startet den Hintergrund-Thread genau einmal (idempotent, thread-sicher)."""
    global _refresher_gestartet
    with _refresher_lock:
        if _refresher_gestartet:
            return
        _refresher_gestartet = True
    _cache_aus_datei_laden()                # warmer Start aus letzter Datei
    threading.Thread(target=_refresher_loop, name="agent-status-refresher",
                     daemon=True).start()


def _get_live_states() -> dict[str, dict]:
    """Liefert den zuletzt im Hintergrund ermittelten Stand -- sofort, nie blockierend.
    Beim allerersten Start ohne Datei-Cache ist er leer, bis der erste
    Hintergrundlauf fertig ist; dann erscheinen Agenten kurz als DEAD."""
    _refresher_starten()
    return _LIVE_CACHE["daten"]  # type: ignore[return-value]


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
