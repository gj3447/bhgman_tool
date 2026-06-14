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
            "reason": "essential-infra-pod recovery after node failure",  # ≥ 20 chars
            "expires_at": "2099-01-01T00:00:00+00:00",  # future
            "covers_gates": ["essential-infra-pod"],
        },
    )
    assert r.status_code == 200
    assert "audit_id" in r.json()


def test_break_glass_rejects_short_reason(client):
    """W3-H: break_glass.rego requires reason ≥ 20 chars; the route now enforces it."""
    r = client.post(
        "/gate/break-glass",
        json={
            "actor": "ops",
            "reason": "oops",  # too short
            "expires_at": "2099-01-01T00:00:00+00:00",
            "covers_gates": ["essential-infra-pod"],
        },
    )
    assert r.status_code == 400
    assert "20" in r.json()["detail"]


def test_break_glass_rejects_expired_session(client):
    """W3-H: an expired break-glass session must be refused."""
    r = client.post(
        "/gate/break-glass",
        json={
            "actor": "ops",
            "reason": "essential-infra-pod recovery after node failure",
            "expires_at": "2000-01-01T00:00:00+00:00",  # past
            "covers_gates": ["essential-infra-pod"],
        },
    )
    assert r.status_code == 400
    assert "expired" in r.json()["detail"]


# ─── health ──────────────────────────────────────────────────────────────


def test_health_endpoint(client):
    r = client.get("/gate/health")
    assert r.status_code == 200
    body = r.json()
    assert body["redis"] is True
    assert body["enforcement_mode"] == "informational"


# ─── OPA policy enforcement (opt-in, APT_OPA_ENABLED=true) ────────────────


class _FakeOPA:
    """Stand-in OPA sidecar — canned allow/deny, no httpx/process needed."""

    def __init__(self, *, allow: bool = True, raise_on_eval: bool = False, rule: str = "allow"):
        self._allow = allow
        self._raise = raise_on_eval
        self._rule = rule  # the decision rule this policy signals allow through

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def health(self):
        return True

    async def eval(self, policy_path, input_doc):
        if self._raise:
            raise RuntimeError("OPA sidecar down")
        return {
            "result": {self._rule: self._allow, "deny": [] if self._allow else ["V-SA3 NoRoot"]}
        }


def _opa_client(monkeypatch, **kw):
    """gate TestClient with OPA enabled + a fake OPA injected (informational mode)."""
    monkeypatch.setenv("APT_GATE_MODE", "informational")
    monkeypatch.setenv("APT_OPA_ENABLED", "true")
    from engine.gate import circuit_breaker, opa_client

    monkeypatch.setattr(circuit_breaker, "build_redis_client", lambda: fakeredis.FakeRedis())
    monkeypatch.setattr(opa_client, "OPAClient", lambda *a, **k: _FakeOPA(**kw))
    from engine.gate import gate_endpoint

    return TestClient(gate_endpoint.app)


def test_opa_allow_yields_pass(monkeypatch):
    with _opa_client(monkeypatch, allow=True) as client:
        r = client.post(
            "/gate/check",
            json={
                "gate_name": "sa_to_sp",
                "cycle_id": "c",
                "actor": "a",
                "context": {"sa": {"name": "X", "status": "active"}},
            },
        )
    body = r.json()
    assert body["verdict"] == "PASS"
    assert "apt.phase_gates.sa_to_sp" in body["reason"]  # OPA was the authority


def test_opa_deny_yields_would_fail_with_reason(monkeypatch):
    with _opa_client(monkeypatch, allow=False) as client:
        r = client.post(
            "/gate/check",
            json={"gate_name": "sa_to_sp", "cycle_id": "c", "actor": "a", "context": {}},
        )
    body = r.json()
    assert body["verdict"] == "WOULD_FAIL"
    assert body["advisory_only"] is True
    assert "deny" in body["reason"].lower()
    assert "V-SA3" in body["reason"]  # the Rego deny reason surfaced


def test_opa_unreachable_fails_closed(monkeypatch):
    with _opa_client(monkeypatch, raise_on_eval=True) as client:
        r = client.post(
            "/gate/check",
            json={"gate_name": "sa_to_sp", "cycle_id": "c", "actor": "a", "context": {}},
        )
    body = r.json()
    assert body["verdict"] == "WOULD_FAIL"  # fail-closed, not a silent PASS
    assert "unreachable" in body["reason"].lower()


@pytest.mark.parametrize(
    "gate_name,package,rule",
    [
        ("break_glass", "apt.break_glass", "allow_override"),
        ("kg_admission", "apt.kg.admission", "allow_mutation"),
        ("taliban", "apt.taliban.constitutional", "approve"),
        ("naesengmoon", "apt.taliban.constitutional", "approve"),
    ],
)
def test_opa_non_allow_decision_rules_can_pass(monkeypatch, gate_name, package, rule):
    """W1-C: break_glass / kg_admission / taliban decide via allow_override /
    allow_mutation / approve. Reading only `allow` made them always DENY on valid input;
    they must now be able to PASS when their actual rule is true."""
    with _opa_client(monkeypatch, allow=True, rule=rule) as client:
        r = client.post(
            "/gate/check",
            json={"gate_name": gate_name, "cycle_id": "c", "actor": "a", "context": {}},
        )
    body = r.json()
    assert body["verdict"] == "PASS", body
    assert package in body["reason"]


def test_opa_non_allow_rule_false_would_fail(monkeypatch):
    """And when the policy's real rule is false, the gate WOULD_FAIL (not silently pass)."""
    with _opa_client(monkeypatch, allow=False, rule="allow_override") as client:
        r = client.post(
            "/gate/check",
            json={"gate_name": "break_glass", "cycle_id": "c", "actor": "a", "context": {}},
        )
    assert r.json()["verdict"] == "WOULD_FAIL"


def test_opa_enabled_unmapped_gate_falls_back_to_stub(monkeypatch):
    """A gate with no policy mapping uses the context stub even when OPA is on."""
    with _opa_client(monkeypatch, allow=False) as client:  # OPA would deny, but G3.5 is unmapped
        r = client.post(
            "/gate/check",
            json={
                "gate_name": "G3.5",
                "cycle_id": "c",
                "actor": "a",
                "context": {"expected_count": 16, "actual_count": 16},
            },
        )
    body = r.json()
    assert body["verdict"] == "PASS"  # stub passed; OPA not consulted for an unmapped gate


def test_circuit_breaker_recovers_after_open_window_wall_clock():
    """W3-G: opened_at is wall-clock (time.time), so OPEN→HALF_OPEN survives a restart
    instead of being stuck OPEN forever on a stale monotonic timestamp."""
    import time as _t

    from engine.gate.circuit_breaker import OPEN_DURATION_S, CircuitBreaker, State

    cb = CircuitBreaker(fakeredis.FakeRedis(), "g-w3g")
    for _ in range(3):
        cb.record_failure()
    assert cb.check().state == State.OPEN
    # backdate opened_at past the OPEN window (wall clock) → must promote to HALF_OPEN
    cb._r.set(cb._key("opened_at"), str(_t.time() - OPEN_DURATION_S - 1))
    assert cb.check().state == State.HALF_OPEN
