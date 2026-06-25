"""APT v27 A7 Gate Hook — FastAPI fail-closed HTTP endpoint.

Absorbed from SYMPOSIUM/THEORY/APT/gate_endpoint_prototype/gate_endpoint.py
(Wave 7 P3-H, 2026-05-14).

⚠ PROTOTYPE SCOPE — read before deploying:

  What runs in /gate/check today:
    * Layer 2 circuit breaker — REAL (Redis-backed 3-state FSM, restart-survivable).
    * OPA / Rego policy enforcement — WIRED, opt-in via APT_OPA_ENABLED=true. When
      OPA is enabled AND the gate maps to a policy (``_GATE_POLICY`` or an explicit
      ``context["_policy"]``), ``/gate/check`` calls ``opa.eval()`` and the Rego
      allow/deny IS the verdict — authoritative, replacing the stub for that gate.
      The request carries the structured policy ``input`` as ``context`` (input.sa.*,
      input.apt_progress.* per the Rego). OPA unreachable ⇒ fail-closed (FAIL/WOULD_FAIL).
    * The fallback verdict (OPA off):
        - For the 4 APT phase gates (sa_to_sp / sp_to_st / st_to_scw / fulfillment) with a
          KG runner configured (NEO4J_*), ``_decide`` now uses the REAL deterministic
          ``kg_materialize.decide_gate`` — Cypher-projects the KG into the Rego input doc and
          evaluates a Python mirror of the .rego. No live OPA sidecar needed (Phase B,
          adr-apt-tpa-engine-substrate-scope-2026-06-14).
        - For any other gate, OR when no KG runner is configured, it falls back to the legacy
          ``_call_kg_with_retry`` count-compare stub (``context.expected_count`` vs
          ``actual_count``) — still a stub, now the last resort only.

  Also stubbed: ``_audit`` is stderr print (no KG :GateAuditEntry yet); break-glass
  Slack/PagerDuty alert is a TODO. See engine/gate/README.md "상태" checklist.

POST /gate/check        circuit-breaker + OPA policy (if enabled) | else context stub
GET  /gate/health       Composition Root health
POST /gate/break-glass  Essential infra emergency override (audit + alert)

Polly v8 정책 chain (intended): rate-limiter → timeout → circuit-breaker → retry → fallback.

KG ref: rfc-apt-v27-A7-gate-hook-fail-closed-4-layer-2026-04-30
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import uuid
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .circuit_breaker import CircuitBreaker, State, build_redis_client


GATE_TIMEOUT_S = 0.5  # Resilience4j-style 500ms


class EnforcementMode(str, Enum):
    INFORMATIONAL = "informational"
    BLOCKER = "blocker"


class TransientGateError(Exception):
    """retry 대상."""


class GateRequest(BaseModel):
    gate_name: str = Field(..., description="G3.5, G6.5 등 APT gate ID")
    cycle_id: str
    actor: str
    context: dict = Field(default_factory=dict)


class GateResponse(BaseModel):
    verdict: str  # PASS | FAIL | WOULD_FAIL | OPEN_REFUSED
    reason: str = ""
    audit_id: str
    circuit_breaker_state: str
    enforcement_mode: str
    advisory_only: bool = False
    next_retry_at: str | None = None


class BreakGlassRequest(BaseModel):
    actor: str
    reason: str
    expires_at: dt.datetime
    covers_gates: list[str]


# ─── Composition Root ────────────────────────────────────────────────────


def _build_kg_runner() -> Any:
    """A run_cypher(cypher, params)->rows over Neo4j when NEO4J_* is set, else None
    (gate then falls back to the count-stub). Graceful: missing driver/unreachable → None."""
    uri = os.environ.get("NEO4J_URI")
    if not uri:
        return None
    try:
        from neo4j import GraphDatabase  # type: ignore  # noqa: PLC0415

        driver = GraphDatabase.driver(
            uri,
            auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", "")),
        )

        def run_cypher(cypher: str, params: dict) -> list[dict]:
            with driver.session() as s:
                return [dict(r) for r in s.run(cypher, **params)]

        return run_cypher
    except Exception as e:  # noqa: BLE001 — no driver / unreachable → count-stub fallback
        print(
            f"[BOOT] KG runner unavailable ({type(e).__name__}); gate uses count-stub",
            file=sys.stderr,
        )
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Redis
    redis = build_redis_client()
    app.state.redis = redis
    # 2. Neo4j run_cypher for the Phase B KG materializer (real APT phase-gate decisions).
    #    None when NEO4J_* is unset → _decide falls back to the legacy count-stub.
    app.state.kg_runner = _build_kg_runner()
    # 3. Allowlist KG node 로드 (stub)
    app.state.allowlist = {"cluster-autoscaler", "essential-infra-pod"}
    # 4. Enforcement mode (KG slot, stub: env override 가능)
    mode = os.environ.get("APT_GATE_MODE", EnforcementMode.INFORMATIONAL.value)
    app.state.enforcement_mode = EnforcementMode(mode)
    # 5. OPA client (PROM 16 A6 sidecar pattern, opt-in via APT_OPA_ENABLED)
    if os.environ.get("APT_OPA_ENABLED", "false").lower() == "true":
        from .opa_client import OPAClient

        app.state.opa = OPAClient()
        await app.state.opa.__aenter__()
        opa_healthy = await app.state.opa.health()
        print(f"[BOOT OPA] enabled, health={opa_healthy}", file=sys.stderr)
    else:
        app.state.opa = None
    print(
        f"[BOOT OK] redis ✓, allowlist {len(app.state.allowlist)} entries, "
        f"mode={app.state.enforcement_mode.value}, opa={'on' if app.state.opa else 'off'}",
        file=sys.stderr,
    )
    try:
        yield
    finally:
        if app.state.opa:
            await app.state.opa.__aexit__(None, None, None)


app = FastAPI(title="APT v27 A7 Gate Endpoint", lifespan=lifespan)


# ─── routes ──────────────────────────────────────────────────────────────


@app.get("/gate/health")
def health(req: Request):
    redis = req.app.state.redis
    return {
        "redis": redis.ping(),
        "enforcement_mode": req.app.state.enforcement_mode.value,
        "allowlist_size": len(req.app.state.allowlist),
    }


def _fail_verdict(mode: EnforcementMode) -> str:
    return "FAIL" if mode is EnforcementMode.BLOCKER else "WOULD_FAIL"


def _fail_response(
    verdict: str, reason: str, audit_id: str, cb_state: str, mode: EnforcementMode
) -> GateResponse:
    """Shared FAIL/WOULD_FAIL/OPEN_REFUSED response (advisory in informational mode)."""
    return GateResponse(
        verdict=verdict,
        reason=reason,
        audit_id=audit_id,
        circuit_breaker_state=cb_state,
        enforcement_mode=mode.value,
        advisory_only=(mode is EnforcementMode.INFORMATIONAL),
    )


@app.post("/gate/check", response_model=GateResponse)
async def gate_check(payload: GateRequest, req: Request) -> GateResponse:
    redis = req.app.state.redis
    cb = CircuitBreaker(redis, payload.gate_name)

    # Layer 2: circuit breaker
    decision = cb.check()
    audit_id = f"audit-{payload.gate_name}-{uuid.uuid4().hex[:12]}"
    mode: EnforcementMode = req.app.state.enforcement_mode
    kg_runner = getattr(req.app.state, "kg_runner", None)

    if not decision.allow_request:
        # circuit OPEN → 즉시 거부 (단, informational 모드에선 advisory)
        verdict = "OPEN_REFUSED" if mode is EnforcementMode.BLOCKER else "WOULD_FAIL"
        _audit(audit_id, payload, verdict, decision.reason, mode, kg_runner)
        return _fail_response(verdict, decision.reason, audit_id, decision.state.value, mode)

    # Resolve verdict: OPA policy (authoritative, opt-in), else the real KG materializer
    # for an APT phase gate (Phase B), else the context sanity stub.
    try:
        ok, reason = await _decide(req.app.state.opa, payload, kg_runner)
    except Exception as e:  # noqa: BLE001 — fail-closed on any gate-backend error
        new_state = cb.record_failure()
        _audit(audit_id, payload, _fail_verdict(mode), f"gate backend error: {e}", mode, kg_runner)
        return _fail_response(
            _fail_verdict(mode), f"gate backend unreachable: {e}", audit_id, new_state.value, mode
        )

    if ok:
        cb.record_success()
        _audit(audit_id, payload, "PASS", reason, mode, kg_runner)
        return GateResponse(
            verdict="PASS",
            reason=reason,
            audit_id=audit_id,
            circuit_breaker_state=State.CLOSED.value,
            enforcement_mode=mode.value,
        )

    new_state = cb.record_failure()
    _audit(audit_id, payload, _fail_verdict(mode), reason, mode, kg_runner)
    return _fail_response(_fail_verdict(mode), reason, audit_id, new_state.value, mode)


@app.post("/gate/break-glass")
def break_glass(payload: BreakGlassRequest, req: Request):
    """Essential infra emergency override. Audit + Slack/PagerDuty 알림 의무."""
    if not (set(payload.covers_gates) & req.app.state.allowlist):
        raise HTTPException(
            status_code=400,
            detail="break-glass는 allowlist gate에만 허용 (KG :BreakGlassAllowlist)",
        )
    # break_glass.rego also requires a substantive reason + a live (non-expired) session;
    # the route validated neither (W3-H). (Actor-allowlist enforcement is the OPA path,
    # W1-C; replicated here are the two checks that don't change the allowlist semantics.)
    if len(payload.reason.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="break-glass override reason must be ≥ 20 chars (break_glass.rego E-SA-Drift-2)",
        )
    if payload.expires_at <= dt.datetime.now(dt.timezone.utc):
        raise HTTPException(
            status_code=400, detail="break-glass session expired (expires_at must be in the future)"
        )
    audit_id = f"breakglass-{uuid.uuid4().hex[:12]}"
    _audit_break_glass(audit_id, payload)
    # TODO: Slack/PagerDuty webhook
    return {
        "audit_id": audit_id,
        "expires_at": payload.expires_at.isoformat(),
        "warning": "audit 강제 + quarterly review 대상",
    }


# ─── retry-wrapped KG call (Polly v8 chain) ──────────────────────────────


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.1, max=2.0, jitter=0.5),
    retry=retry_if_exception_type(TransientGateError),
)
def _call_kg_with_retry(payload: GateRequest) -> tuple[bool, str]:
    """Legacy count-compare for non-phase count gates when OPA is off. Fail-closed on missing
    context. APT phase gates are decided by the Phase B KG materializer
    (kg_materialize.decide_gate), NOT here — _decide refuses to route a phase gate to this stub."""
    # context-based count sanity check (caller supplies expected/actual); fail-closed if absent.
    expected = payload.context.get("expected_count")
    actual = payload.context.get("actual_count")
    if expected is None or actual is None:
        return False, f"context 누락: expected={expected}, actual={actual}"
    if expected != actual:
        return False, f"count mismatch: expected={expected}, actual={actual}"
    return True, f"PASS: expected={expected}, actual={actual}"


# ─── OPA policy decision (opt-in via APT_OPA_ENABLED) ─────────────────────

# gate_name → Rego policy package. An explicit context["_policy"] overrides this.
# gate_name → (rego package, the rule name that signals allow). Different policies
# decide via different rule names — reading only `allow` made break_glass /
# kg_admission / taliban (allow_override / allow_mutation / approve) always DENY on
# valid input.
_GATE_POLICY: dict[str, tuple[str, str]] = {
    "sa_to_sp": ("apt.phase_gates.sa_to_sp", "allow"),
    "sp_to_st": ("apt.phase_gates.sp_to_st", "allow"),
    "st_to_scw": ("apt.phase_gates.st_to_scw", "allow"),
    "fulfillment_gate": ("apt.fulfillment_gate", "allow"),
    "fulfillment": ("apt.fulfillment_gate", "allow"),
    "break_glass": ("apt.break_glass", "allow_override"),
    "harness": ("apt.harness.constrain", "allow"),
    "taliban": ("apt.taliban.constitutional", "approve"),
    "naesengmoon": ("apt.taliban.constitutional", "approve"),
    "kg_admission": ("apt.kg.admission", "allow_mutation"),
}


def _opa_policy_path(payload: GateRequest) -> tuple[str, str] | None:
    """Resolve (rego package, decision rule) for a gate.

    Explicit ``context['_policy']`` wins (rule via ``context['_policy_rule']``, default
    ``allow``); else the gate→policy map.
    """
    explicit = payload.context.get("_policy")
    if isinstance(explicit, str) and explicit:
        rule = payload.context.get("_policy_rule")
        return explicit, (rule if isinstance(rule, str) and rule else "allow")
    return _GATE_POLICY.get(payload.gate_name)


async def _eval_opa(opa: Any, package: str, rule: str, context: dict) -> tuple[bool, str]:
    """Evaluate a Rego policy → (allow, reason). Reads the policy's actual decision rule
    (``allow`` / ``allow_override`` / ``approve`` / ``allow_mutation``), not a hardcoded
    ``allow``. Accepts both package-result-dict and bare-bool query shapes."""
    raw = await opa.eval(package, context)
    result = raw.get("result")
    if isinstance(result, bool):
        return result, f"OPA {package}: {'allow' if result else 'deny'}"
    result = result or {}
    allow = bool(result.get(rule, False))
    deny = [str(d) for d in (result.get("deny") or [])]
    if allow:
        return True, f"OPA {package}.{rule}: allow"
    return False, f"OPA {package}.{rule} deny: {'; '.join(deny) or '(no reason given)'}"


# the 4 APT phase gates the KG materializer (Phase B) can decide deterministically.
_APT_PHASE_GATES = frozenset(
    {"sa_to_sp", "sp_to_st", "st_to_scw", "fulfillment", "fulfillment_gate"}
)


async def _decide(opa: Any, payload: GateRequest, run_cypher: Any = None) -> tuple[bool, str]:
    """Gate verdict: OPA policy (authoritative) when enabled + mapped; else the real KG
    materializer for an APT phase gate (Phase B); else the legacy count-compare stub."""
    policy = _opa_policy_path(payload)
    if opa is not None and policy is not None:
        package, rule = policy
        return await _eval_opa(opa, package, rule, payload.context)
    if payload.gate_name in _APT_PHASE_GATES:
        if run_cypher is not None:
            from engine.gate.kg_materialize import decide_gate  # noqa: PLC0415

            return decide_gate(payload.gate_name, payload.cycle_id, run_cypher)
        # An APT phase gate must be decided by KG facts (materializer) or OPA — never by the
        # caller-supplied count-stub. No runner + no OPA → fail-closed (do not silently pass).
        return False, (
            f"{payload.gate_name}: APT phase gate needs a KG runner (set NEO4J_*) or OPA "
            "(APT_OPA_ENABLED); refusing legacy count-stub (fail-closed)"
        )
    return _call_kg_with_retry(payload)


# ─── audit (JFrog 패턴 — actor/timestamp/verdict) ────────────────────────


# Layer-3 mandatory-audit: durable, queryable verdict record (JFrog pattern). MERGE on
# auditId (idempotent under retry). Persisted when a kg_runner is wired; stderr otherwise.
_GATE_AUDIT_CYPHER = (
    "MERGE (e:GateAuditEntry {auditId: $audit_id}) "
    "SET e.gateName = $gate_name, e.actor = $actor, e.cycleId = $cycle_id, "
    "e.verdict = $verdict, e.mode = $mode, e.reason = $reason, e.recordedAt = $recorded_at "
    "RETURN e.auditId AS auditId"
)


def _audit(
    audit_id: str,
    payload: GateRequest,
    verdict: str,
    reason: str,
    mode: EnforcementMode,
    kg_runner: Any = None,
) -> None:
    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    print(
        f"[AUDIT {audit_id}] {ts} "
        f"{payload.gate_name} actor={payload.actor} cycle={payload.cycle_id} "
        f"verdict={verdict} mode={mode.value} reason={reason}",
        file=sys.stderr,
    )
    # Durable record: a :GateAuditEntry survives restart and is queryable (the stderr line
    # is not). Audit persistence must NEVER break the gate decision — degrade to the print
    # above on any failure (or when no runner is wired).
    if kg_runner is None:
        return
    try:
        kg_runner(
            _GATE_AUDIT_CYPHER,
            {
                "audit_id": audit_id,
                "gate_name": payload.gate_name,
                "actor": payload.actor,
                "cycle_id": payload.cycle_id,
                "verdict": verdict,
                "mode": mode.value,
                "reason": reason,
                "recorded_at": ts,
            },
        )
    except Exception as e:  # noqa: BLE001 — audit write must not fail the gate
        print(f"[AUDIT {audit_id}] KG persist degraded ({type(e).__name__}: {e})", file=sys.stderr)


def _audit_break_glass(audit_id: str, payload: BreakGlassRequest) -> None:
    print(
        f"[BREAK-GLASS {audit_id}] actor={payload.actor} reason={payload.reason} "
        f"covers={payload.covers_gates} expires={payload.expires_at.isoformat()}",
        file=sys.stderr,
    )


def main() -> None:
    import uvicorn

    uvicorn.run(
        "engine.gate.gate_endpoint:app",
        host=os.environ.get("APT_GATE_HOST", "127.0.0.1"),
        port=int(os.environ.get("APT_GATE_PORT", 8765)),
        reload=False,
    )


if __name__ == "__main__":
    main()
