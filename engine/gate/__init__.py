"""APT v27 A7 Gate Hook — fail-closed HTTP endpoint (4-layer Polly v8 chain).

Absorbed from SYMPOSIUM/THEORY/APT/gate_endpoint_prototype/ (Wave 7 P3-H, 2026-05-14).

4-Layer Architecture:
    [1] Resilience4j-style timeout (500ms)
    [2] Redis-backed circuit breaker state (3-state FSM, restart-survivable)
    [3] Mandatory audit log (JFrog pattern — actor/timestamp/verdict)
    [4] 3 consecutive fail → fallback + alert

Public API:
    app                                FastAPI instance (gate_endpoint:app)
    CircuitBreaker / State              Redis-backed FSM
    OPAClient                           OPA Data API client (PROM 16 A6 sidecar)

KG ref: rfc-apt-v27-A7-gate-hook-fail-closed-4-layer-2026-04-30
"""
from .circuit_breaker import (
    CircuitBreaker,
    CircuitDecision,
    State,
    FAIL_THRESHOLD,
    OPEN_DURATION_S,
    build_redis_client,
)
from .opa_client import OPAClient, build_opa_client

__all__ = [
    "CircuitBreaker",
    "CircuitDecision",
    "State",
    "FAIL_THRESHOLD",
    "OPEN_DURATION_S",
    "build_redis_client",
    "OPAClient",
    "build_opa_client",
]
