"""③ Visibility FSM — 상계/하계 ACL (직교, 순수 함수).

PRIVATE ──publish_request ∧ acl_gate(pass)──▶ PUBLISHED

불변식 (load-bearing, D3 3중공격 차단):
  공유 tier 배정 ⟺ s_vis == PUBLISHED.
  PRIVATE element 은 per-tenant 파티션에만 존재 → 공유 HNSW 진입 불가.
  이 한 줄이 embedding inversion / semantic collision / timing side-channel 을
  구조적으로 무력화 (private 임베딩이 애초에 공유 캐시에 없음).
"""
# KG: engineboy-emergence-engine-fsm-design-2026-07-13, rf-engineboy-caching-D3-2026-07-13

from __future__ import annotations

from typing import Callable

from engine.emergence.protocols import VisibilityState

Vis = VisibilityState

# ACL gate: (element_key, requester) → 허용 여부. 정책 주입.
AclGate = Callable[[str, str], bool]


def deny_all_gate(key: str, requester: str) -> bool:
    return False


def can_enter_shared_tier(s: VisibilityState) -> bool:
    """공유 tier 배정 가드. PRIVATE 면 절대 False."""
    return s is Vis.PUBLISHED


def on_publish_request(
    s: VisibilityState, key: str, requester: str, gate: AclGate
) -> VisibilityState:
    if s is Vis.PUBLISHED:
        return s
    return Vis.PUBLISHED if gate(key, requester) else Vis.PRIVATE
