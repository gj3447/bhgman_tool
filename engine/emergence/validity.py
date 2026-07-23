"""② Validity FSM — 신선도 (직교, 순수 함수).

FRESH ──source_changed──▶ STALE ──revalidate_start──▶ REVALIDATING ──revalidated──▶ FRESH
                                                          │ source_changed
                                                          ▼ STALE

serving 정책 (A3 coherence):
- FRESH        → SERVE_FRESH (fast path)
- STALE        → SERVE_STALE_REVALIDATE (SWR: stale 서빙 + 재검증 트리거)
- REVALIDATING → SERVE_LAST_GOOD
"""
# KG: engineboy-emergence-engine-fsm-design-2026-07-13

from __future__ import annotations

from engine.emergence.protocols import ServingPolicy, ValidityState

V = ValidityState


def on_source_changed(s: ValidityState) -> ValidityState:
    return V.STALE


def on_revalidate_start(s: ValidityState) -> ValidityState:
    return V.REVALIDATING if s is V.STALE else s


def on_revalidated(s: ValidityState) -> ValidityState:
    return V.FRESH if s is V.REVALIDATING else s


def serving_policy(s: ValidityState) -> ServingPolicy:
    return {
        V.FRESH: ServingPolicy.SERVE_FRESH,
        V.STALE: ServingPolicy.SERVE_STALE_REVALIDATE,
        V.REVALIDATING: ServingPolicy.SERVE_LAST_GOOD,
    }[s]
