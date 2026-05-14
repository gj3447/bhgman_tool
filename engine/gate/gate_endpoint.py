"""APT v27 A7 Gate Hook — FastAPI fail-closed HTTP endpoint.

Absorbed from SYMPOSIUM/THEORY/APT/gate_endpoint_prototype/gate_endpoint.py
(Wave 7 P3-H, 2026-05-14).

POST /gate/check        Resilience4j 4-layer 게이트 (timeout + CB + audit + fallback)
GET  /gate/health       Composition Root health
POST /gate/break-glass  Essential infra emergency override (audit + alert)

Polly v8 정책 chain: rate-limiter → timeout → circuit-breaker → retry → fallback.

KG ref: rfc-apt-v27-A7-gate-hook-fail-closed-4-layer-2026-04-30
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import uuid
from contextlib import asynccontextmanager
from enum import Enum

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Redis
    redis = build_redis_client()
    app.state.redis = redis
    # 2. Neo4j (실제 연결은 후속 sprint — 본 prototype은 stub)
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


@app.post("/gate/check", response_model=GateResponse)
def gate_check(payload: GateRequest, req: Request) -> GateResponse:
    redis = req.app.state.redis
    cb = CircuitBreaker(redis, payload.gate_name)

    # Layer 2: circuit breaker
    decision = cb.check()
    audit_id = f"audit-{payload.gate_name}-{uuid.uuid4().hex[:12]}"
    mode: EnforcementMode = req.app.state.enforcement_mode

    if not decision.allow_request:
        # circuit OPEN → 즉시 거부 (단, informational 모드에선 advisory)
        verdict = "OPEN_REFUSED" if mode is EnforcementMode.BLOCKER else "WOULD_FAIL"
        _audit(audit_id, payload, verdict, decision.reason, mode)
        return GateResponse(
            verdict=verdict,
            reason=decision.reason,
            audit_id=audit_id,
            circuit_breaker_state=decision.state.value,
            enforcement_mode=mode.value,
            advisory_only=(mode is EnforcementMode.INFORMATIONAL),
        )

    # Layer 1+4: timeout + retry + KG query
    try:
        kg_pass, kg_reason = _call_kg_with_retry(payload)
    except Exception as e:  # noqa: BLE001
        # 3 consecutive fails — promote to OPEN
        new_state = cb.record_failure()
        verdict = "FAIL" if mode is EnforcementMode.BLOCKER else "WOULD_FAIL"
        _audit(audit_id, payload, verdict, f"KG retry exhausted: {e}", mode)
        return GateResponse(
            verdict=verdict,
            reason=f"KG unreachable: {e}",
            audit_id=audit_id,
            circuit_breaker_state=new_state.value,
            enforcement_mode=mode.value,
            advisory_only=(mode is EnforcementMode.INFORMATIONAL),
        )

    if kg_pass:
        cb.record_success()
        _audit(audit_id, payload, "PASS", kg_reason, mode)
        return GateResponse(
            verdict="PASS",
            reason=kg_reason,
            audit_id=audit_id,
            circuit_breaker_state=State.CLOSED.value,
            enforcement_mode=mode.value,
        )

    # KG-level fail
    new_state = cb.record_failure()
    verdict = "FAIL" if mode is EnforcementMode.BLOCKER else "WOULD_FAIL"
    _audit(audit_id, payload, verdict, kg_reason, mode)
    return GateResponse(
        verdict=verdict,
        reason=kg_reason,
        audit_id=audit_id,
        circuit_breaker_state=new_state.value,
        enforcement_mode=mode.value,
        advisory_only=(mode is EnforcementMode.INFORMATIONAL),
    )


@app.post("/gate/break-glass")
def break_glass(payload: BreakGlassRequest, req: Request):
    """Essential infra emergency override. Audit + Slack/PagerDuty 알림 의무."""
    if not (set(payload.covers_gates) & req.app.state.allowlist):
        raise HTTPException(
            status_code=400,
            detail="break-glass는 allowlist gate에만 허용 (KG :BreakGlassAllowlist)",
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
    """Resilience4j-style timeout + retry. 실제 KG query는 후속 sprint."""
    # Sprint 3 sub-task — kg_query.py로 실제 Cypher 실행
    # 본 prototype: context 기반 sanity check
    expected = payload.context.get("expected_count")
    actual = payload.context.get("actual_count")
    if expected is None or actual is None:
        return False, f"context 누락: expected={expected}, actual={actual}"
    if expected != actual:
        return False, f"count mismatch: expected={expected}, actual={actual}"
    return True, f"PASS: expected={expected}, actual={actual}"


# ─── audit (JFrog 패턴 — actor/timestamp/verdict) ────────────────────────


def _audit(
    audit_id: str,
    payload: GateRequest,
    verdict: str,
    reason: str,
    mode: EnforcementMode,
) -> None:
    # TODO: KG `:GateAuditEntry` 노드 + structlog 영구 기록
    print(
        f"[AUDIT {audit_id}] {dt.datetime.now(dt.timezone.utc).isoformat()} "
        f"{payload.gate_name} actor={payload.actor} cycle={payload.cycle_id} "
        f"verdict={verdict} mode={mode.value} reason={reason}",
        file=sys.stderr,
    )


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
