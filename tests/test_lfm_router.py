"""R145 TDD — LFM Router-Wrapper contract tests.

FastAPI service that:
  - POST /v1/route  → {target: local|sonnet, confidence: float, reason: str, response_if_local?: str}
  - GET  /v1/metrics → {routed_local, routed_sonnet, estimated_savings_eur, total_calls}
  - GET  /health    → 200 {"status":"ok"}
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import lfm_router as lr


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(lr, "_STATE_FILE", tmp_path / "router_state.json")
    lr._reset_metrics_for_test()
    return TestClient(lr.app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_route_local_task_classifies_local(client, monkeypatch):
    """Given a trivial classification task, LFM must respond with target=local."""
    fake_lfm_response = {
        "choices": [{
            "message": {
                "content": '{"target":"local","confidence":0.92,"reason":"Kurze Klassifikation, JSON-Output"}',
            },
            "finish_reason": "stop",
        }],
        "usage": {"completion_tokens": 30},
        "timings": {"predicted_ms": 350, "predicted_per_second": 260},
    }
    monkeypatch.setattr(lr, "_call_lfm", lambda system, user, max_tokens=500: (fake_lfm_response, 350))

    r = client.post("/v1/route", json={"task_prompt": "Klassifiziere: 'DNS fehlt' als Dept + Prio."})
    assert r.status_code == 200
    body = r.json()
    assert body["target"] == "local"
    assert 0 <= body["confidence"] <= 1
    assert body["confidence"] == 0.92


def test_route_sonnet_task_classifies_sonnet(client, monkeypatch):
    fake_lfm_response = {
        "choices": [{
            "message": {
                "content": '{"target":"sonnet","confidence":0.88,"reason":"§312f BGB, mehrstufige Legal-Analyse"}',
            },
            "finish_reason": "stop",
        }],
        "usage": {"completion_tokens": 40},
        "timings": {"predicted_ms": 420, "predicted_per_second": 260},
    }
    monkeypatch.setattr(lr, "_call_lfm", lambda system, user, max_tokens=500: (fake_lfm_response, 420))

    r = client.post("/v1/route", json={"task_prompt": "Erstelle §312f BGB Bestätigungsmail mit vollständigem Widerrufs-Text"})
    assert r.status_code == 200
    assert r.json()["target"] == "sonnet"


def test_route_low_confidence_defaults_to_sonnet(client, monkeypatch):
    """confidence < 0.7 must escalate to sonnet regardless of LFM's target choice."""
    fake_lfm_response = {
        "choices": [{
            "message": {"content": '{"target":"local","confidence":0.55,"reason":"unklar"}'},
            "finish_reason": "stop",
        }],
        "usage": {"completion_tokens": 20},
        "timings": {"predicted_ms": 300, "predicted_per_second": 260},
    }
    monkeypatch.setattr(lr, "_call_lfm", lambda system, user, max_tokens=500: (fake_lfm_response, 300))

    r = client.post("/v1/route", json={"task_prompt": "irgendwas unklares"})
    assert r.status_code == 200
    body = r.json()
    assert body["target"] == "sonnet", "low confidence should defensive-escalate"
    assert body["escalated_by_confidence"] is True


def test_metrics_endpoint_reflects_route_counts(client, monkeypatch):
    fake_local = {
        "choices": [{"message": {"content": '{"target":"local","confidence":0.9,"reason":"x"}'}, "finish_reason": "stop"}],
        "usage": {"completion_tokens": 20},
        "timings": {"predicted_ms": 300, "predicted_per_second": 260},
    }
    fake_sonnet = {
        "choices": [{"message": {"content": '{"target":"sonnet","confidence":0.95,"reason":"x"}'}, "finish_reason": "stop"}],
        "usage": {"completion_tokens": 20},
        "timings": {"predicted_ms": 350, "predicted_per_second": 260},
    }

    calls = [fake_local, fake_local, fake_sonnet]
    def _rr(system, user, max_tokens=500):
        return calls.pop(0), 300
    monkeypatch.setattr(lr, "_call_lfm", _rr)

    for prompt in ["a", "b", "c"]:
        client.post("/v1/route", json={"task_prompt": prompt})

    m = client.get("/v1/metrics").json()
    assert m["total_calls"] == 3
    assert m["routed_local"] == 2
    assert m["routed_sonnet"] == 1
    assert m["estimated_savings_eur"] > 0
    assert "avg_latency_ms" in m


def test_system_prompt_does_not_leak_template_values():
    """Regression: SYSTEM_PROMPT must not use '1 Satz' as example VALUE.

    Bug 2026-07-23: LFM copied '1 Satz' verbatim into the reason field
    because it looked like a JSON value hint in the template.
    """
    assert '"reason": "1 Satz"' not in lr.SYSTEM_PROMPT, \
        "Template must not embed '1 Satz' as JSON value — LFM will copy it verbatim"
    assert '"reason":"1 Satz"' not in lr.SYSTEM_PROMPT
    # Positive check: 'reason' field must be described somewhere in the prompt
    assert "reason" in lr.SYSTEM_PROMPT.lower()


def test_route_reason_is_not_template_bleedthrough(client, monkeypatch):
    """If LFM returns the literal template hint '1 Satz', wrapper should keep it
    (that's an LFM-side issue), but system-prompt design must prevent it in the first place.

    This test locks in the design: system-prompt separates schema from instructions.
    """
    # We just assert the shape — no llm call needed
    assert "AUSSCHLIESSLICH als JSON" in lr.SYSTEM_PROMPT or "nur JSON" in lr.SYSTEM_PROMPT.lower()


def test_route_invalid_lfm_response_falls_back_to_sonnet(client, monkeypatch):
    """LFM returns malformed JSON → wrapper must defensive-escalate."""
    fake_bad = {
        "choices": [{"message": {"content": "not-a-json-at-all"}, "finish_reason": "stop"}],
        "usage": {"completion_tokens": 10},
        "timings": {"predicted_ms": 200, "predicted_per_second": 260},
    }
    monkeypatch.setattr(lr, "_call_lfm", lambda system, user, max_tokens=500: (fake_bad, 200))

    r = client.post("/v1/route", json={"task_prompt": "irgendwas"})
    assert r.status_code == 200
    assert r.json()["target"] == "sonnet"
    assert r.json()["escalated_by_error"] is True
