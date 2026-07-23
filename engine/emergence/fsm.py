"""① Activity FSM — 순수 전이 함수.

가중치가 이미 갱신된(Hawkes) element 를 받아 다음 상태 + commit action 을 결정.
부작용 없음 — engine.py 가 반환된 (state, action) 을 적용한다.

불변식:
- hard-delete terminal 없음 (DORMANT = revivable archive, 오캄 삭제금지).
- hysteresis(h) 로 HOT⇄COOLING flapping 차단.
"""
# KG: engineboy-emergence-engine-fsm-design-2026-07-13

from __future__ import annotations

from engine.emergence.protocols import (
    Action,
    ActivityState,
    Element,
    EmergenceConfig,
)

S = ActivityState


def next_state(
    elem: Element,
    t: float,
    score: float,
    l1_has_capacity: bool,
    cfg: EmergenceConfig,
) -> tuple[ActivityState, Action]:
    """(elem.w/n 은 호출 전 Hawkes 로 갱신됨) → (new_state, action).

    state 불변이면 (같은 state, Action.NONE).
    """
    st = elem.state
    w = elem.w
    n = elem.n
    age = t - elem.created_ts
    dwell = t - elem.state_since

    if st is S.NASCENT:
        if n >= cfg.n_est and w >= cfg.theta_warm:
            return S.WARM, Action.INSERT_L2
        if age > cfg.t_grace and n < cfg.n_est:
            return S.DORMANT, Action.ARCHIVE          # cold-start 실패 (오캄)
        return S.NASCENT, Action.NONE

    if st is S.WARM:
        if score >= cfg.theta_hot and l1_has_capacity:
            return S.HOT, Action.PROMOTE_L1           # 롱기누스 bind
        if w < cfg.theta_warm - cfg.hysteresis:
            return S.COLD, Action.DEMOTE_COLD
        return S.WARM, Action.NONE

    if st is S.HOT:
        if w < cfg.theta_hot - cfg.hysteresis:
            return S.COOLING, Action.MARK_COOLING
        return S.HOT, Action.NONE

    if st is S.COOLING:
        if w >= cfg.theta_hot:
            return S.HOT, Action.PROMOTE_L1           # re-burst 재승격
        if w < cfg.theta_cool and dwell >= cfg.t_cool:
            return S.COLD, Action.DEMOTE_COLD
        return S.COOLING, Action.NONE

    if st is S.COLD:
        if w >= cfg.theta_warm:
            return S.WARM, Action.REEMERGE            # 재창발
        if w < cfg.eps and dwell >= cfg.t_dormant:
            return S.DORMANT, Action.ARCHIVE          # 오캄 (삭제 아님)
        return S.COLD, Action.NONE

    if st is S.DORMANT:
        # 접근으로 여기 도달 → w 는 이미 bump 됨. revive.
        if w >= cfg.theta_warm:
            return S.WARM, Action.REEMERGE
        return S.NASCENT, Action.REEMERGE

    return st, Action.NONE
