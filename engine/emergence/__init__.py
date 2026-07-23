"""engineboy 창발 엔진 (emergence engine) — traffic → weight 창발기.

검색/탐색 traffic(사람+AI)이 시멘틱 하이퍼그래프의 가중치와 계층을 *설계 없이*
창발시킨다. FSM = 직교 3 sub-FSM 곱 (engineboy 3직교축 동형):
  ① Activity  (NASCENT→WARM→HOT⇄COOLING→COLD→DORMANT)  — 계층 창발
  ② Validity  (FRESH⇄STALE→REVALIDATING)                — 신선도 (SWR)
  ③ Visibility(PRIVATE→PUBLISHED)                        — 상계/하계 ACL (D3 차단)

가중=Hawkes 지수감쇠(O(1) lazy). 승격=UCB anti-Matthew. RESOLVE=시맨틱 nearest.
울프람 렌즈: 단순 국소 규칙 → 창발 복잡성, 하이퍼그래프 재작성 오토마톤.

설계: METAHUMOTONIC/ORBITAL_MOTION_CLOUD/engineboy/
      EMERGENCE_ENGINE_FSM_DESIGN_PRELIMINARY_2026-07-13.md
"""
# KG: engineboy-emergence-engine-fsm-design-2026-07-13, engineboy-caching-traffic-weighted-hierarchy-2026-07-13

from engine.emergence.protocols import (
    AccessEvent,
    Action,
    ActivityState,
    Element,
    EmergenceConfig,
    ServingPolicy,
    ValidityState,
    VisibilityState,
)
from engine.emergence.engine import EmergenceEngine, Transition, tier_of
from engine.emergence.activation import (
    Activation,
    SeedFn,
    spreading_activation,
    two_stage_retrieve,
)
from engine.emergence.resolver import (
    IdentityResolver,
    InMemoryVectorResolver,
    Neo4jVectorResolver,
    VectorResolver,
)

__all__ = [
    "AccessEvent",
    "Action",
    "ActivityState",
    "Element",
    "EmergenceConfig",
    "ServingPolicy",
    "ValidityState",
    "VisibilityState",
    "EmergenceEngine",
    "Transition",
    "tier_of",
    "Activation",
    "SeedFn",
    "spreading_activation",
    "two_stage_retrieve",
    "IdentityResolver",
    "InMemoryVectorResolver",
    "Neo4jVectorResolver",
    "VectorResolver",
]
