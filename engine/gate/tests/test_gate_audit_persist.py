"""Gate Layer-3 'mandatory audit log' must persist a queryable :GateAuditEntry.

gate_endpoint._audit was a stderr print() stub (TODO): every verdict was logged to stderr
and lost on restart — unqueryable, defeating the JFrog-pattern mandatory-audit invariant —
even though app.state.kg_runner is wired. The runner was never handed to _audit.

Unit tests below pin the durable-audit contract on _audit directly (no fastapi/fakeredis
needed); the endpoint test additionally pins the call-site wiring (skipped where the
optional [gate] deps are absent, runs in CI's --all-extras).

# KG: finding-gate-audit-log-print-stub-no-kg-entry-2026-06-26
"""
from __future__ import annotations

import datetime as dt

import pytest

from engine.gate.gate_endpoint import (
    BreakGlassRequest,
    EnforcementMode,
    GateRequest,
    _audit,
    _audit_break_glass,
)


def _payload() -> GateRequest:
    return GateRequest(gate_name="G3.5", cycle_id="audit-cycle", actor="haiku-test", context={})


_INFORMATIONAL = EnforcementMode("informational")


def test_audit_persists_gate_audit_entry_when_runner_present() -> None:
    calls: list[tuple[str, dict]] = []

    def runner(cypher, params):
        calls.append((cypher, params))
        return []

    _audit("audit-G3.5-abc123", _payload(), "PASS", "ok", _INFORMATIONAL, kg_runner=runner)

    writes = [p for cy, p in calls if "GateAuditEntry" in cy]
    assert len(writes) == 1  # exactly one durable entry
    assert writes[0]["audit_id"] == "audit-G3.5-abc123"
    assert writes[0]["verdict"] == "PASS"
    assert writes[0]["gate_name"] == "G3.5"
    assert writes[0]["actor"] == "haiku-test"


def test_audit_degrades_to_print_without_runner(capsys) -> None:
    # no kg_runner wired → must NOT raise; still emits the stderr log line.
    _audit("audit-no-runner", _payload(), "FAIL", "nope", _INFORMATIONAL, kg_runner=None)
    assert "audit-no-runner" in capsys.readouterr().err


def test_audit_never_raises_on_runner_failure(capsys) -> None:
    # a KG write failure must never break the gate decision path.
    def boom(cypher, params):
        raise RuntimeError("neo4j down")

    _audit("audit-boom", _payload(), "PASS", "ok", _INFORMATIONAL, kg_runner=boom)
    # degraded, not raised — the audit_id still surfaces on stderr.
    assert "audit-boom" in capsys.readouterr().err


# ── break-glass override audit (the more security-critical sibling) ──────────
def _bg_payload() -> BreakGlassRequest:
    return BreakGlassRequest(
        actor="oncall-eng",
        reason="cluster-autoscaler wedged; overriding G6.5 to unblock the prod rollback",
        expires_at=dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc),
        covers_gates=["G6.5"],
    )


def test_break_glass_audit_persists_entry_when_runner_present() -> None:
    calls: list[tuple[str, dict]] = []

    def runner(cypher, params):
        calls.append((cypher, params))
        return []

    _audit_break_glass("breakglass-xyz", _bg_payload(), kg_runner=runner)

    writes = [p for cy, p in calls if "BreakGlassEntry" in cy]
    assert len(writes) == 1  # the override left a durable, queryable record
    assert writes[0]["audit_id"] == "breakglass-xyz"
    assert writes[0]["actor"] == "oncall-eng"
    assert writes[0]["covers_gates"] == ["G6.5"]


def test_break_glass_audit_degrades_to_print_without_runner(capsys) -> None:
    _audit_break_glass("breakglass-no-runner", _bg_payload(), kg_runner=None)
    assert "breakglass-no-runner" in capsys.readouterr().err


def test_break_glass_audit_never_raises_on_runner_failure(capsys) -> None:
    def boom(cypher, params):
        raise RuntimeError("neo4j down")

    _audit_break_glass("breakglass-boom", _bg_payload(), kg_runner=boom)
    assert "breakglass-boom" in capsys.readouterr().err


# ── call-site wiring (CI: needs the optional [gate] deps) ────────────────────
def test_gate_check_persists_audit_entry_to_kg(monkeypatch) -> None:
    fakeredis = pytest.importorskip("fakeredis")
    tc = pytest.importorskip("fastapi.testclient")

    monkeypatch.setenv("APT_GATE_MODE", "informational")
    from engine.gate import circuit_breaker, gate_endpoint

    monkeypatch.setattr(circuit_breaker, "build_redis_client", lambda: fakeredis.FakeRedis())
    app = gate_endpoint.app

    calls: list[tuple[str, dict]] = []
    with tc.TestClient(app) as c:
        app.state.kg_runner = lambda cy, p: calls.append((cy, p)) or []
        r = c.post(
            "/gate/check",
            json={
                "gate_name": "G3.5",
                "cycle_id": "audit-cycle",
                "actor": "haiku-test",
                "context": {"expected_count": 16, "actual_count": 16},
            },
        )
        assert r.status_code == 200
        audit_id = r.json()["audit_id"]

    writes = [p for cy, p in calls if "GateAuditEntry" in cy]
    assert len(writes) == 1
    assert writes[0]["audit_id"] == audit_id
    assert writes[0]["verdict"] == "PASS"
