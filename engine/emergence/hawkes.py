"""Hawkes 지수감쇠 가중 동역학 + UCB 승격 점수 (순수 함수).

traffic → weight:  w ← w·exp(−λ·Δt) + κ_actor   (lazy decay, O(1), history-free)
승격:               score = w + c·√(ln Σn / n)    (UCB anti-Matthew)

핵심 성질:
- lazy: 감쇠는 접근 시점에만 계산 → 주기 tick 불필요 ("materialize not recompute").
- 평형: 접근율 r(간격 Δ=1/r) 정상 → 이벤트 직후 정상값
        w* = κ / (1 − exp(−λ·Δ)) = κ / (1 − exp(−λ/r))
        연속근사(λ≪r): w* ≈ κ·r/λ.  → weight ∝ 접근율.
"""
# KG: engineboy-emergence-engine-fsm-design-2026-07-13

from __future__ import annotations

import math


def decayed_weight(w: float, t_last: float, t: float, lam: float) -> float:
    """t_last → t 로 감쇠시킨 현재 weight. t < t_last (역행) 은 clamp."""
    dt = t - t_last
    if dt <= 0.0:
        return w
    return w * math.exp(-lam * dt)


def apply_access(
    w: float, t_last: float, t: float, lam: float, kappa: float
) -> tuple[float, float]:
    """접근 impulse 적용. 반환 (new_w, new_t_last)."""
    return decayed_weight(w, t_last, t, lam) + kappa, max(t, t_last)


def ucb_score(w: float, n: int, total_n: int, c: float) -> float:
    """UCB 승격 점수. n=0 (미방문) → +inf (cold-start 최대 우선).

    n 큼(과인기) → bonus → 0 → 순수 w. n 작음(cold-start) → bonus 큼 → 억제 탈출.
    """
    if n <= 0:
        return math.inf
    total = max(total_n, 1)
    return w + c * math.sqrt(math.log(total) / n)


def equilibrium_weight(kappa: float, rate: float, lam: float) -> float:
    """접근율 rate(간격 1/rate) 정상 시 이벤트 직후 정상 weight (해석해).

    F2 falsifier 의 ground truth. 연속근사 아님 — 이산 정확식.
    """
    if rate <= 0.0:
        return 0.0
    return kappa / (1.0 - math.exp(-lam / rate))


def equilibrium_weight_continuous(kappa: float, rate: float, lam: float) -> float:
    """연속근사 w* ≈ κ·r/λ (λ≪r 일 때만 유효). 참고용."""
    if lam <= 0.0:
        return math.inf
    return kappa * rate / lam
