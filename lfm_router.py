"""LFM Router-Wrapper (CEO-Direktive 2026-07-23).

FastAPI service:
  POST /v1/route   → {target, confidence, reason, escalated_by_confidence?, escalated_by_error?}
  GET  /v1/metrics → {routed_local, routed_sonnet, estimated_savings_eur, ...}
  GET  /health     → 200 {"status":"ok"}

Backend: LFM2.5-8B-A1B via llama.cpp on http://127.0.0.1:11442 (gpu-server-1).

Safety rules:
  - confidence < CONFIDENCE_THRESHOLD (default 0.7)  → force target=sonnet
  - LFM returns invalid JSON                         → force target=sonnet
  - LFM timeout / HTTP error                          → force target=sonnet
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

LFM_ENDPOINT = os.environ.get("LFM_ENDPOINT", "http://127.0.0.1:11442/v1/chat/completions")
LFM_MODEL = os.environ.get("LFM_MODEL", "/mnt/models/lfm25-8b-a1b/LFM2.5-8B-A1B-Q4_K_M.gguf")
CONFIDENCE_THRESHOLD = float(os.environ.get("LFM_CONFIDENCE_THRESHOLD", "0.7"))

# Cost per call (EUR) for savings estimation. Sonnet ≈ €0.003 per short task, local ≈ €0.
COST_SONNET_EUR = float(os.environ.get("COST_SONNET_EUR", "0.003"))
COST_LOCAL_EUR = float(os.environ.get("COST_LOCAL_EUR", "0.0002"))

SYSTEM_PROMPT = """Du bist ein Escalation-Judge fuer Task-Routing in einer AI-driven Company.

Klassifiziere ob ein Task lokal (LFM/Gemma/GPT-OSS auf V100) oder in der Cloud (Claude Sonnet) bearbeitet werden soll.

Antworte AUSSCHLIESSLICH als JSON-Objekt mit genau drei Feldern (kein Fliesstext davor/danach):
  target       — Enum: entweder "local" oder "sonnet"
  confidence   — Zahl zwischen 0.0 und 1.0
  reason       — String: DEINE eigene Begruendung (KEIN Platzhalter kopieren, KEIN Vorlagen-Text)

Beispiel-Struktur (nur zur Illustration der Felder, Werte selbst ausfuellen):
  target="local", confidence=0.9, reason="Kurze Klassifikationsaufgabe, JSON-Output erwartet"
  target="sonnet", confidence=0.85, reason="§312f BGB verlangt mehrschrittige Legal-Analyse"

WICHTIG: reason muss dein eigener Satz sein basierend auf dem konkreten Task-Prompt.
Kopiere NIE Woerter wie 'kurz', 'Platzhalter' oder Beispiel-Reasons aus dieser Anweisung.

Kriterien fuer target=local:
  - Klassifikation (Dept, Prio, Intent, Sentiment)
  - Entity-Extraktion (IBAN, Email, Datum, Namen)
  - JSON-Output-Generation aus einfachem Input
  - Text-Zusammenfassung <500 Woerter
  - Einfacher Code <100 Zeilen (Utility, Helper)
  - Kurze Ja/Nein/Multi-Choice-Antworten

Kriterien fuer target=sonnet:
  - Mehrschritt-Reasoning (>3 Schritte)
  - Legal-Analyse (§, BGB, EStG, UWG, DSGVO)
  - Autonome Entscheidungen mit Business-Impact
  - Komplexer Code >100 Zeilen oder Architektur-Design
  - Multi-Turn-Konversation mit State
  - Fach-Compliance (Steuern, Vertraege, Buchhaltung)

Bei Unsicherheit: target=sonnet, confidence=0.5, reason=konkreter Grund fuer die Unsicherheit."""

app = FastAPI(title="LFM Router")


# ── Metrics state (in-memory, persisted to disk on shutdown) ────────────────
_STATE_FILE = Path(os.environ.get("LFM_ROUTER_STATE", "/var/lib/lfm-router/state.json"))
_metrics = {
    "total_calls": 0,
    "routed_local": 0,
    "routed_sonnet": 0,
    "escalated_by_confidence": 0,
    "escalated_by_error": 0,
    "sum_latency_ms": 0,
    "sum_savings_eur": 0.0,
}


def _reset_metrics_for_test() -> None:
    global _metrics
    _metrics = {
        "total_calls": 0,
        "routed_local": 0,
        "routed_sonnet": 0,
        "escalated_by_confidence": 0,
        "escalated_by_error": 0,
        "sum_latency_ms": 0,
        "sum_savings_eur": 0.0,
    }


# ── LFM backend call ────────────────────────────────────────────────────────
def _call_lfm(system: str, user: str, max_tokens: int = 800) -> tuple[dict, int]:
    """POST to llama.cpp OpenAI-compat endpoint. Returns (body, latency_ms)."""
    payload = {
        "model": LFM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(LFM_ENDPOINT, data=data, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    return body, int((time.time() - t0) * 1000)


def _parse_lfm_output(content: str) -> dict | None:
    """Extract JSON from LFM response. Returns None on any parse failure."""
    s = content.strip()
    if s.startswith("```"):
        try:
            s = s.split("\n", 1)[1].rsplit("```", 1)[0]
        except IndexError:
            return None
    start = s.find("{")
    end = s.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return None


# ── Routes ──────────────────────────────────────────────────────────────────
class RouteRequest(BaseModel):
    task_prompt: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/route")
def route(req: RouteRequest) -> dict:
    _metrics["total_calls"] += 1

    escalated_by_confidence = False
    escalated_by_error = False
    reason = ""
    target = "sonnet"  # defensive default
    confidence = 0.0
    latency_ms = 0

    try:
        body, latency_ms = _call_lfm(SYSTEM_PROMPT, req.task_prompt)
        _metrics["sum_latency_ms"] += latency_ms
        content = body["choices"][0]["message"]["content"]
        parsed = _parse_lfm_output(content)
        if parsed is None or "target" not in parsed:
            target = "sonnet"
            escalated_by_error = True
            reason = "LFM returned unparsable JSON"
            _metrics["escalated_by_error"] += 1
        else:
            target = parsed.get("target", "sonnet")
            confidence = float(parsed.get("confidence", 0.0))
            reason = parsed.get("reason", "")
            if target not in ("local", "sonnet"):
                target = "sonnet"
                escalated_by_error = True
                reason = f"LFM returned invalid target: {target}"
                _metrics["escalated_by_error"] += 1
            elif confidence < CONFIDENCE_THRESHOLD:
                target = "sonnet"
                escalated_by_confidence = True
                _metrics["escalated_by_confidence"] += 1
    except Exception as e:
        target = "sonnet"
        escalated_by_error = True
        reason = f"LFM call failed: {type(e).__name__}"
        _metrics["escalated_by_error"] += 1

    if target == "local":
        _metrics["routed_local"] += 1
        _metrics["sum_savings_eur"] += (COST_SONNET_EUR - COST_LOCAL_EUR)
    else:
        _metrics["routed_sonnet"] += 1

    return {
        "target": target,
        "confidence": confidence,
        "reason": reason,
        "latency_ms": latency_ms,
        "escalated_by_confidence": escalated_by_confidence,
        "escalated_by_error": escalated_by_error,
    }


@app.get("/v1/metrics")
def metrics() -> dict:
    n = max(_metrics["total_calls"], 1)
    return {
        "total_calls": _metrics["total_calls"],
        "routed_local": _metrics["routed_local"],
        "routed_sonnet": _metrics["routed_sonnet"],
        "escalated_by_confidence": _metrics["escalated_by_confidence"],
        "escalated_by_error": _metrics["escalated_by_error"],
        "estimated_savings_eur": round(_metrics["sum_savings_eur"], 4),
        "avg_latency_ms": _metrics["sum_latency_ms"] // n,
        "local_share_pct": round(100 * _metrics["routed_local"] / n, 1),
        "confidence_threshold": CONFIDENCE_THRESHOLD,
    }
