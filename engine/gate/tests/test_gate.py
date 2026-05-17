"""APT v27 A7 Gate endpoint — unit tests with fakeredis.

Absorbed from SYMPOSIUM/THEORY/APT/gate_endpoint_prototype/tests/test_gate.py
(Wave 7 P3-H, 2026-05-14).
"""

from __future__ import annotations

import pytest

# Optional deps gate — skip whole module if fakeredis/fastapi missing.
fakeredis = pytest.importorskip("fakeredis")
fastapi_testclient = pytest.importorskip("fastapi.testclient")
TestClient = fastapi_testclient.TestClient


@pytest.fixture
def app(monkeypatch):
    """fakeredis 주입 + informational 모드."""
    monkeypatch.setenv("APT_GATE_MODE", "informational")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6379")

    # patch build_redis_client → fakeredis
    from engine.gate import circuit_breaker

    monkeypatch.setattr(
        circuit_breaker,
        "build_redis_client",
        lambda: fakeredis.FakeRedis(),
    )

    from engine.gate import gate_endpoint

    return gate_endpoint.app


@pytest.fixture
def client(app):
    # `with TestClient` triggers FastAPI lifespan → app.state.redis set
    with TestClient(app) as c:
        yield c


# ─── happy path ──────────────────────────────────────────────────────────


def test_gate_check_pass(client):
    r = client.post(
        "/gate/check",
        json={
            "gate_name": "G3.5",
            "cycle_id": "test-cycle",
            "actor": "haiku-test",
            "context": {"expected_count": 16, "actual_count": 16},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "PASS"
    assert body["circuit_breaker_state"] == "CLOSED"
    assert body["enforcement_mode"] == "informational"


def test_gate_check_count_mismatch_advisory(client):
    """informational 모드 → WOULD_FAIL + advisory_only=True."""
    r = client.post(
        "/gate/check",
        json={
            "gate_name": "G3.5",
            "cycle_id": "test-cycle",
            "actor": "haiku-test",
            "context": {"expected_count": 16, "actual_count": 12},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "WOULD_FAIL"
    assert body["advisory_only"] is True


# ─── circuit breaker ─────────────────────────────────────────────────────


def test_circuit_opens_after_3_consecutive_fails(client):
    payload = {
        "gate_name": "G_FAIL",
        "cycle_id": "test",
        "actor": "haiku",
        "context": {"expected_count": 16, "actual_count": 0},
    }
    # 3 fails — circuit OPEN
    for _ in range(3):
        client.post("/gate/check", json=payload)
    # 4th — circuit refuses
    r = client.post("/gate/check", json=payload)
    body = r.json()
    assert body["circuit_breaker_state"] == "OPEN"


# ─── break-glass ─────────────────────────────────────────────────────────


def test_break_glass_requires_allowlist_match(client):
    r = client.post(
        "/gate/break-glass",
        json={
            "actor": "ops",
            "reason": "test",
            "expires_at": "2026-04-30T13:00:00+00:00",
            "covers_gates": ["G3.5"],  # not in allowlist
        },
    )
    assert r.status_code == 400


def test_break_glass_allows_essential_infra(client):
    r = client.post(
        "/gate/break-glass",
        json={
            "actor": "ops",
            "reason": "essential-infra-pod recovery",
            "expires_at": "2026-04-30T13:00:00+00:00",
            "covers_gates": ["essential-infra-pod"],
        },
    )
    assert r.status_code == 200
    assert "audit_id" in r.json()


# ─── health ──────────────────────────────────────────────────────────────


def test_health_endpoint(client):
    r = client.get("/gate/health")
    assert r.status_code == 200
    body = r.json()
    assert body["redis"] is True
    assert body["enforcement_mode"] == "informational"
