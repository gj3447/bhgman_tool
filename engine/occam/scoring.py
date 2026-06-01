"""오캄 정량 scoring — 연속 가중치 + 시간 decay supersession score σ ∈ [0,1].

순수 함수 (KG/IO 없음). occam.py(dedup 분류)가 후보를 뽑으면 여기서 *얼마나 안전하게
아카이브 가능한가*를 [0,1] 연속값으로 매긴다. 기존 HIGH/MEDIUM enum을 대체하지 않고
*정밀화*한다 (enum = 디스크 sha 확정도, σ = 아카이브 안전도).

학문 정전 grounding (consensus-occam-entropy-truth-2026-05-26 "entropy selects, truth-guard gates"):

  ── candidacy C (선별 신호, "entropy selects") = noisy-OR of 3 독립 obsolescence 증거 ──
  · redundancy r   — MDL / Kolmogorov (Rissanen 1978; Solomonoff): 동일 sha twin = 완전 중복(r=1),
                     부분 중복은 description-length 절감 비율. "compressible = clutter".
  · staleness  s   — 망각곡선 / 지수감쇠 (Ebbinghaus 1885): s = 1 − 2^(−age/halflife).
                     age=halflife → s=0.5. 시간이 흐를수록 단조 증가, age=0이면 0.
  · deadness   d   — 사용기반 (lesson-occam-needs-invocation-log-2026-05-28): d = 2^(−inv/scale).
                     invocation=0 → d=1 (dead), 호출 많을수록 →0.
  noisy-OR (Pearl 1988): C = 1 − (1−r)(1−s)(1−d). 한 신호만 강해도 C↑.

  ── guard G (거부권, "truth-guard gates") = entrenchment × twin-gate ──
  · entrenchment e — AGM belief revision의 epistemic entrenchment (Gärdenfors–Makinson 1988):
                     canonical/lesson/contract/verdict = e=1.0 ⇒ G=0 ⇒ never archive (정전 tier).
  · twin-gate      — AGM contraction은 후속자 없이 믿음을 버리지 않는다. 살아있는 twin/후속
                     노드 없으면 gate=0 ⇒ σ=0 (machloket / Eilu va-Eilu: flag만, supersede 금지).

  ── 최종 score ── σ = C · G ∈ [0,1].  (canonical e=1 → σ=0 / twin 부재 → σ=0)

  ── verdict (KG dt-occam-* threshold grounded) ──
  · σ ≥ θ_supersede (0.7, dt-occam-naesengmoon-confidence) → SUPERSEDE
  · θ_keep ≤ σ < θ_supersede                              → VERIFY (나생문 dispatch)
  · σ < θ_keep (0.3)                                      → KEEP
  · e=1.0 (never-archive tier)                            → PROTECTED
  · twin/후속 부재                                         → FLAG_ONLY (orphan, machloket)

# KG: occam-kam-canonical-2026-05-26, consensus-occam-entropy-truth-2026-05-26,
#     dt-occam-naesengmoon-confidence, dt-occam-dead-node-count-grounded,
#     dt-occam-twin-status-score-grounded, verdict-user-occam-gains-ontology-hygiene-responsibility-2026-05-27
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

# 산출물 스케일 — 모든 score는 [0,1] 실수. (Lean 형식화는 0..SCALE 정수 basis-point로 mirror)


class EntrenchmentTier(str, Enum):
    """AGM epistemic entrenchment tier → guard 패널티 e ∈ [0,1].

    canonical/lesson/contract/verdict = never-archive (e=1.0, consensus c3 정전).
    아래로 갈수록 archive 가능. PLAIN = SourceCodeNode 같은 일반 노드(e=0, dedup 대상)."""

    CANONICAL = "CANONICAL"
    LESSON = "LESSON"
    CONTRACT = "CONTRACT"
    VERDICT = "VERDICT"
    PRINCIPLE = "PRINCIPLE"
    ONTOLOGY_CLASS = "ONTOLOGY_CLASS"
    REFERENCE = "REFERENCE"
    FINDING = "FINDING"
    PLAIN = "PLAIN"


# never-archive 코어 = e=1.0 (정전 tier). 나머지는 ordinal 패널티 (단조 감소).
_ENTRENCHMENT: dict[EntrenchmentTier, float] = {
    EntrenchmentTier.CANONICAL: 1.0,
    EntrenchmentTier.LESSON: 1.0,
    EntrenchmentTier.CONTRACT: 1.0,
    EntrenchmentTier.VERDICT: 1.0,
    EntrenchmentTier.PRINCIPLE: 0.8,
    EntrenchmentTier.ONTOLOGY_CLASS: 0.7,
    EntrenchmentTier.REFERENCE: 0.5,
    EntrenchmentTier.FINDING: 0.3,
    EntrenchmentTier.PLAIN: 0.0,
}

NEVER_ARCHIVE_TIERS = frozenset(t for t, e in _ENTRENCHMENT.items() if e >= 1.0)


class Verdict(str, Enum):
    SUPERSEDE = "SUPERSEDE"  # σ ≥ θ_supersede: 아카이브 후보 확정
    VERIFY = "VERIFY"  # 회색지대: 나생문에 검증 dispatch
    KEEP = "KEEP"  # σ 낮음: 손대지 않음
    PROTECTED = "PROTECTED"  # never-archive tier (e=1.0)
    FLAG_ONLY = "FLAG_ONLY"  # twin/후속 부재 — machloket, flag만


@dataclass(frozen=True)
class ScoringConfig:
    """모든 자유 파라미터 한 곳. magic number 금지 (MethodologyConfig 정신)."""

    halflife_days: float = 90.0  # staleness 반감기: 90일 미사용 → s=0.5
    invocation_scale: float = 3.0  # deadness 반감: 호출 3회마다 d 절반
    theta_supersede: float = 0.7  # dt-occam-naesengmoon-confidence
    theta_keep: float = 0.3  # 이 아래는 KEEP

    def __post_init__(self) -> None:
        if self.halflife_days <= 0:
            raise ValueError("halflife_days must be > 0")
        if self.invocation_scale <= 0:
            raise ValueError("invocation_scale must be > 0")
        if not (0.0 <= self.theta_keep <= self.theta_supersede <= 1.0):
            raise ValueError("require 0 ≤ theta_keep ≤ theta_supersede ≤ 1")


@dataclass(frozen=True)
class NodeScoreMeta:
    """한 노드의 scoring 입력. occam.py NodeRecord 옆에 붙는 메타데이터.

    occam의 dedup 결과(redundancy)와 KG 메타(age/invocation/tier)를 모은다."""

    redundancy: float  # [0,1] — 동일 sha=1.0, line_count 비율 기반 등
    age_days: float  # last_validated(없으면 created) 이후 경과 일수, ≥0
    invocation_count: int  # tool_use 실측 호출수 (≥0)
    tier: EntrenchmentTier = EntrenchmentTier.PLAIN
    has_successor: bool = True  # 살아있는 twin/후속 노드 존재 (없으면 σ=0)

    def __post_init__(self) -> None:
        if not (0.0 <= self.redundancy <= 1.0):
            raise ValueError(f"redundancy must be in [0,1], got {self.redundancy}")
        if self.age_days < 0:
            raise ValueError("age_days must be ≥ 0")
        if self.invocation_count < 0:
            raise ValueError("invocation_count must be ≥ 0")


@dataclass(frozen=True)
class SupersessionScore:
    """scoring 결과 — 연속 σ + 3 성분 + verdict (감사 가능)."""

    sigma: float
    candidacy: float
    guard: float
    redundancy: float
    staleness: float
    deadness: float
    entrenchment: float
    verdict: Verdict


# ── 성분 함수 (Lean 형식화와 1:1 mirror) ──────────────────────────────────────


def staleness(age_days: float, halflife_days: float) -> float:
    """시간 decay: s = 1 − 2^(−age/halflife) ∈ [0,1). age=halflife → 0.5, age=0 → 0.

    age로 단조 증가, halflife로 단조 감소. Ebbinghaus 망각곡선 형."""
    if age_days <= 0:
        return 0.0
    return 1.0 - math.pow(2.0, -age_days / halflife_days)


def deadness(invocation_count: int, invocation_scale: float) -> float:
    """사용기반 deadness: d = 2^(−inv/scale) ∈ (0,1]. inv=0 → 1.0(dead), 많을수록 →0."""
    return math.pow(2.0, -invocation_count / invocation_scale)


def candidacy(redundancy: float, staleness_v: float, deadness_v: float) -> float:
    """noisy-OR: C = 1 − (1−r)(1−s)(1−d) ∈ [0,1]. 한 신호만 강해도 C↑ (Pearl 1988)."""
    return 1.0 - (1.0 - redundancy) * (1.0 - staleness_v) * (1.0 - deadness_v)


def entrenchment_penalty(tier: EntrenchmentTier) -> float:
    """AGM epistemic entrenchment e ∈ [0,1]. canonical 등 = 1.0 → guard=0."""
    return _ENTRENCHMENT[tier]


def guard(entrenchment_v: float, has_successor: bool) -> float:
    """truth-guard 거부권: G = (1−e)·twin_gate ∈ [0,1]. e=1 또는 twin 부재 → G=0."""
    twin_gate = 1.0 if has_successor else 0.0
    return (1.0 - entrenchment_v) * twin_gate


# ── 최종 score ────────────────────────────────────────────────────────────────


def score_node(meta: NodeScoreMeta, config: ScoringConfig | None = None) -> SupersessionScore:
    """σ = candidacy · guard ∈ [0,1] + verdict 판정.

    안전 불변식 (Lean 형식화):
      · σ ∈ [0,1]
      · tier ∈ NEVER_ARCHIVE → σ = 0 (PROTECTED)
      · has_successor=False  → σ = 0 (FLAG_ONLY, machloket)
      · σ는 r·s·d로 단조 증가, e로 단조 감소
    """
    cfg = config or ScoringConfig()

    r = meta.redundancy
    s = staleness(meta.age_days, cfg.halflife_days)
    d = deadness(meta.invocation_count, cfg.invocation_scale)
    e = entrenchment_penalty(meta.tier)

    c_val = candidacy(r, s, d)
    g_val = guard(e, meta.has_successor)
    sigma = c_val * g_val

    verdict = _verdict(sigma, e, meta.has_successor, cfg)

    return SupersessionScore(
        sigma=sigma,
        candidacy=c_val,
        guard=g_val,
        redundancy=r,
        staleness=s,
        deadness=d,
        entrenchment=e,
        verdict=verdict,
    )


def _verdict(
    sigma: float, entrenchment_v: float, has_successor: bool, cfg: ScoringConfig
) -> Verdict:
    # 거부권 사유를 먼저 (σ=0인 두 원인을 구분해 보고)
    if entrenchment_v >= 1.0:
        return Verdict.PROTECTED
    if not has_successor:
        return Verdict.FLAG_ONLY
    if sigma >= cfg.theta_supersede:
        return Verdict.SUPERSEDE
    if sigma >= cfg.theta_keep:
        return Verdict.VERIFY
    return Verdict.KEEP


__all__ = [
    "EntrenchmentTier",
    "NEVER_ARCHIVE_TIERS",
    "NodeScoreMeta",
    "ScoringConfig",
    "SupersessionScore",
    "Verdict",
    "candidacy",
    "deadness",
    "entrenchment_penalty",
    "guard",
    "score_node",
    "staleness",
]
