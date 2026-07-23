"""창발 엔진 상태·이벤트·설정 정의 (phase1).

frozen dataclass + enum. engine.py 가 이들을 orchestrate 한다.
"""
# KG: engineboy-emergence-engine-fsm-design-2026-07-13

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional


class ActivityState(enum.Enum):
    """① Activity FSM 상태. tier 는 이 상태에서 derive.

    NASCENT  — 맹아. 첫 traffic, establish 미달. cold-start 보호 (T_grace).
    WARM     — 확립. L2 index. 승격 대상.
    HOT      — 승격. L1 / HNSW top layer. fast-path.
    COOLING  — 냉각. HOT 에서 감쇠, demotion 후보 (hysteresis 완충).
    COLD     — L3/disk. 인덱스 유지, slow-path. 삭제 아님.
    DORMANT  — 동면. 오캄 archive (active/log 분리). 재접근 시 revive.
    """

    NASCENT = "NASCENT"
    WARM = "WARM"
    HOT = "HOT"
    COOLING = "COOLING"
    COLD = "COLD"
    DORMANT = "DORMANT"


class ValidityState(enum.Enum):
    """② Validity FSM (직교, 신선도). Activity 와 독립 전이.

    FRESH        — 소스와 일치.
    STALE        — source_changed 신호. 재검증 대기.
    REVALIDATING — 재크롤/재계산 진행 중. last-good 서빙.
    """

    FRESH = "FRESH"
    STALE = "STALE"
    REVALIDATING = "REVALIDATING"


class VisibilityState(enum.Enum):
    """③ Visibility FSM (직교, 상계/하계 ACL).

    PRIVATE   — 하계. per-tenant 파티션에만. 공유 캐시 진입 금지.
    PUBLISHED — 상계. 공유 HNSW 진입 허용.
    """

    PRIVATE = "PRIVATE"
    PUBLISHED = "PUBLISHED"


class ServingPolicy(enum.Enum):
    """Validity 상태에 따른 서빙 정책 (A3 coherence)."""

    SERVE_FRESH = "SERVE_FRESH"
    SERVE_STALE_REVALIDATE = "SERVE_STALE_REVALIDATE"  # SWR
    SERVE_LAST_GOOD = "SERVE_LAST_GOOD"


class Action(enum.Enum):
    """FSM 전이가 방출하는 commit action. 각 action = 한 커맨더 동사."""

    NONE = "NONE"
    CREATE = "CREATE"          # 유레카: 신규 노드 생성 (NASCENT)
    INSERT_L2 = "INSERT_L2"    # WARM 승격, HNSW L2 insert
    PROMOTE_L1 = "PROMOTE_L1"  # HOT 승격 + 롱기누스 bind
    MARK_COOLING = "MARK_COOLING"
    DEMOTE_COLD = "DEMOTE_COLD"
    REEMERGE = "REEMERGE"      # COLD/DORMANT → WARM 재창발
    ARCHIVE = "ARCHIVE"        # 오캄: DORMANT soft-archive (삭제 금지)


@dataclass(frozen=True)
class EmergenceConfig:
    """엔진 파라미터. thresholds.toml 로 외부화 가능 (phase2)."""

    # Hawkes 가중 동역학
    lam: float = 0.1                         # 감쇠율 λ (per time-unit)
    kappa: float = 1.0                       # 기본 impulse κ (actor별 override 가능)
    kappa_by_actor: dict[str, float] = field(default_factory=dict)  # {'human':.., 'ai':..}
    # 승격 (UCB anti-Matthew)
    ucb_c: float = 1.4                       # exploration 계수
    # Activity FSM threshold
    n_est: int = 3                           # NASCENT→WARM 최소 distinct-access
    theta_warm: float = 1.0                  # WARM 진입 weight
    theta_hot: float = 3.0                   # HOT 진입 score
    theta_cool: float = 0.8                  # COOLING→COLD weight
    eps: float = 0.05                        # COLD→DORMANT weight 하한
    hysteresis: float = 0.5                  # HOT⇄COOLING 완충 h (flap 방지)
    # 시간 게이트 (time-unit)
    t_grace: float = 100.0                   # NASCENT cold-start 유예
    t_cool: float = 50.0                     # COOLING→COLD 지속시간
    t_dormant: float = 500.0                 # COLD→DORMANT 지속시간
    # tier 용량
    l1_capacity: int = 100                   # HOT 동시 최대 (top-K)

    def kappa_for(self, actor: str) -> float:
        return self.kappa_by_actor.get(actor, self.kappa)


@dataclass(frozen=True)
class AccessEvent:
    """traffic 신호 1건. engine.ingest() 의 입력."""

    event_id: str            # 멱등 dedup 키
    element_key: str         # 접근된 element 식별자
    actor: str               # 'human' | 'ai'
    ts: float                # 논리 시각 (Date.now 미사용 — 외부 주입)
    co_keys: tuple[str, ...] = ()   # 공동접근 (Hebbian 엣지 후보)
    acl: str = "public"      # phase2 Visibility FSM 용
    embed: Optional[tuple[float, ...]] = None  # phase2 HNSW RESOLVE 용


@dataclass
class Element:
    """persistent element 상태 (node 또는 hyperedge)."""

    key: str
    w: float = 0.0
    t_last: float = 0.0
    n: int = 0                       # distinct-access support
    state: ActivityState = ActivityState.NASCENT
    created_ts: float = 0.0
    state_since: float = 0.0         # 현재 state 진입 시각 (dwell-time 게이트)
    is_edge: bool = False
    # hyperedge endpoints (is_edge=True only) — store keys of the two co-accessed nodes.
    # Explicit so spreading-activation can build adjacency without parsing the "::"-joined
    # edge key (ambiguous under tenant namespaces). None for nodes.
    src: Optional[str] = None
    dst: Optional[str] = None
    # ② Validity / ③ Visibility (직교)
    s_val: ValidityState = ValidityState.FRESH
    s_vis: VisibilityState = VisibilityState.PUBLISHED
    namespace: str = "shared"        # 'shared' | 'tenant:<id>'
    acl: str = "public"
