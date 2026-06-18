"""eureka 개념명명 A/B — FCA-floor(Arm A) vs FCA + vLLM 개념명명(Arm B), preflight-gated.

VERDICT.md §3·ADR seven-commander-engine-cli-mcp-vllm-2026-06-18 §OQ1 의 *유일 미측정·그럴듯*
locus를 닫는 rig: eureka는 "발견·창조" 동사이고, deterministic FCA floor(Galois closure)는
*conjunctive 잠재구조*만 복원한다. ADR이 OPEN으로 남긴 가설 = "vLLM이 FCA가 구조적으로 못 만드는
자연어 개념(이름·proposal)을 더해 floor를 이긴다". 이 rig가 그 delta를 *측정*한다.

  Arm A (floor)  = deterministic FCA induction only (engine.eureka induce_fca). 외부 LLM 0.
  Arm B (enrich) = FCA + 주입된 LLM 클라이언트가 자연어 추상을 proposal (FCA가 못 잡는 것).

핵심 비순환 분리 (오캄 σ A/B에서 배운 것):
  - **Scorer = eureka_oracle (독립)**. 채점 ground-truth = planted 개념(내가 author, eureka·LLM 무관).
    각 후보 추상 → LabeledItem(is_positive = planted를 복원했나, signal = recovery 품질).
  - **preflight 3-falsifier 먼저**(CIRCULARITY/SIGNAL_ABSENT/SIGNAL_INVERTED). 통과 못하면 delta를
    날조하지 말고 UNMEASURABLE + 사유. LLM이 제 proposal을 제 라벨로 채점하면 = 순환 → CIRCULARITY 발화.

offline-falsifiable by design: LLM 호출은 주입식 클라이언트(Protocol/Callable)를 통과하므로
테스트는 결정론 fake를 넘긴다 — 라이브 dgx vLLM 없이 게이트가 *양방향 발화*함을 증명. 라이브 run은
그 위 경험 층(dgx 가용 시). 클라이언트 미주입이면 Arm A만 돌고 Arm B는 DEFERRED로 정직 보고.

# KG: efficacy-measurement-line-2026-06-01, project_bhgman_ab_falsifier_2026_05_30,
#     adr-seven-commander-engine-cli-mcp-vllm-2026-06-18
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from engine.efficacy.falsifier import run_preflight
from engine.efficacy.metrics import auc_mann_whitney
from engine.efficacy.models import (
    Direction,
    LabeledItem,
    PreflightReport,
)
from engine.eureka.induction_operators import induce_fca
from engine.efficacy.eureka_oracle import (
    _jaccard,
    build_planted_context,
    recovery_recall,
)

# planted 개념 복원 매칭 임계 (eureka_oracle.recovery_recall과 동일).
RECOVERY_THRESH = 0.8
# circularity keyword: provenance에 이게 있으면 *LLM 제 proposal*(군단장-생성) 라벨 = 순환.
CIRCULARITY_KEYWORDS = ("self_proposed", "llm_self_label", "naming_self")


@dataclass(frozen=True)
class NamedAbstraction:
    """한 후보 추상. extent = 묶은 객체집합, name = 자연어 개념명(LLM 산출, FCA는 ""), source = arm."""

    extent: frozenset[str]
    name: str
    source: str  # "fca" | "vllm"


class NamingClient(Protocol):
    """주입식 vLLM 개념명명 클라이언트. 라이브 = engine.agents.client.AgentClient 래핑,

    테스트 = 결정론 fake. context(formal context) + FCA가 이미 만든 extent들을 받아,
    FCA가 *놓친* 자연어 추상을 proposal 한다 (extent + 이름)."""

    def propose(
        self,
        context: dict[str, frozenset[str]],
        fca_extents: Sequence[frozenset[str]],
    ) -> list[NamedAbstraction]: ...


def _fca_abstractions(context: dict[str, frozenset[str]]) -> list[NamedAbstraction]:
    """Arm A — deterministic FCA induction. extent만, 이름 없음(FCA는 명명 못 함)."""
    res = induce_fca(context, min_extent=2, min_stability=0.0)
    return [NamedAbstraction(extent=c.extent, name="", source="fca") for c in res.concepts]


def _label_abstractions(
    abstractions: Sequence[NamedAbstraction],
    planted: Sequence[frozenset[str]],
    thresh: float = RECOVERY_THRESH,
) -> list[LabeledItem]:
    """각 후보 추상 → LabeledItem (독립 oracle 채점, 비순환).

    is_positive = 어떤 planted 개념을 thresh 이상으로 복원했나 (ground-truth = planted, eureka 무관).
    signal      = best Jaccard (복원 품질, HIGHER = 더 잘 복원).
    provenance  = "<source>:<name>" — LLM이 *제 proposal을 제 라벨로* 우길 때만 circularity keyword 포함.
    """
    items: list[LabeledItem] = []
    for i, ab in enumerate(abstractions):
        best = max((_jaccard(g, ab.extent) for g in planted), default=0.0)
        items.append(
            LabeledItem(
                item_id=f"{ab.source}_{i}",
                is_positive=best >= thresh,
                signal=best,
                provenance=f"{ab.source}:{ab.name}",
            )
        )
    return items


def _arm_score(
    abstractions: Sequence[NamedAbstraction],
    planted: Sequence[frozenset[str]],
    thresh: float = RECOVERY_THRESH,
) -> float:
    """한 arm의 점수 = planted 복원 recall (독립 oracle). 0..1."""
    extents = [ab.extent for ab in abstractions]
    return recovery_recall(extents, planted, thresh)


@dataclass(frozen=True)
class EurekaNamingResult:
    """eureka 개념명명 A/B 결과 — 정직 출력.

    verdict:
      MEASURABLE_LIFT — preflight PASS + delta > 0 (Arm B가 floor를 이김).
      MEASURABLE_NULL — preflight PASS + delta <= 0 (이득 없음 실측 — vLLM이 floor를 못 이김).
      UNMEASURABLE    — preflight FAIL (순환/신호부재/역전) — delta 날조 금지.
      DEFERRED        — client 미주입 — Arm A floor만, Arm B는 라이브 dgx vLLM 대기.
    """

    preflight: PreflightReport | None
    arm_a_score: float
    arm_b_score: float | None
    delta: float | None
    n: int
    verdict: str
    auc_b_vs_a: float | None = None
    reason: str = ""
    diagnostics: dict = field(default_factory=dict)

    @property
    def summary(self) -> str:
        b = f"{self.arm_b_score:.3f}" if self.arm_b_score is not None else "n/a"
        d = f"{self.delta:+.3f}" if self.delta is not None else "n/a"
        return (
            f"[eureka_naming] {self.verdict} arm_a={self.arm_a_score:.3f} arm_b={b} "
            f"delta={d} (n={self.n}) — {self.reason}"
        )


def run_eureka_naming_ab(
    client: NamingClient | None = None,
    *,
    k: int = 6,
    objects_per: int = 4,
    thresh: float = RECOVERY_THRESH,
    floor_fn: Callable[[dict[str, frozenset[str]]], list[NamedAbstraction]] | None = None,
) -> EurekaNamingResult:
    """eureka 개념명명 A/B. client=None 이면 Arm A(floor)만 돌고 Arm B는 DEFERRED.

    1. planted context 구성 (ground-truth = 내가 author).
    2. Arm A = deterministic FCA. client 있으면 Arm B = FCA + vLLM naming.
    3. *결합 후보셋*을 독립 oracle로 라벨링 → preflight 3-falsifier 게이트.
    4. PASS면 delta(arm_b - arm_a) + AUC. FAIL이면 UNMEASURABLE(날조 금지).

    floor_fn 주입점 = 테스트에서 floor를 *handicap*해(일부 planted 누락) lift를 정직히 시험하는
    seam. default(None) = 실 FCA induction. 라이브 run은 floor_fn 미지정 → 실 FCA floor.
    """
    context, planted = build_planted_context(k=k, objects_per=objects_per)
    n = len(planted)

    fca_abs = (floor_fn or _fca_abstractions)(context)
    arm_a = _arm_score(fca_abs, planted, thresh)

    if client is None:  # deterministic-core-runnable: Arm A만, Arm B 라이브 대기.
        return EurekaNamingResult(
            preflight=None,
            arm_a_score=arm_a,
            arm_b_score=None,
            delta=None,
            n=n,
            verdict="DEFERRED",
            reason=(
                "client 미주입 — Arm A(FCA floor)만 측정. Arm B(vLLM 개념명명)는 "
                "dgx vLLM 가용 시 라이브."
            ),
            diagnostics={"n_fca_abstractions": len(fca_abs)},
        )

    proposed = client.propose(context, [ab.extent for ab in fca_abs])
    enrich_abs = list(fca_abs) + list(proposed)
    arm_b = _arm_score(enrich_abs, planted, thresh)

    # preflight: *결합 후보셋* 라벨로 게이트. LLM이 제 proposal을 제 라벨로 우기면 CIRCULARITY 발화.
    items = _label_abstractions(enrich_abs, planted, thresh)
    preflight = run_preflight(items, CIRCULARITY_KEYWORDS, Direction.HIGHER)

    if not preflight.passed:
        return EurekaNamingResult(
            preflight=preflight,
            arm_a_score=arm_a,
            arm_b_score=arm_b,
            delta=None,
            n=n,
            verdict="UNMEASURABLE",
            reason=(
                "preflight FAIL "
                + "/".join(f.value for f in preflight.failures)
                + " — delta 날조 금지. (순환=LLM 자기채점 / 신호부재 / 역전)"
            ),
            diagnostics={
                "n_fca_abstractions": len(fca_abs),
                "n_vllm_proposed": len(proposed),
                "circularity_ratio": preflight.circularity_ratio,
                "signal_availability": preflight.signal_availability,
            },
        )

    delta = arm_b - arm_a
    # AUC: Arm B proposal의 신호가 Arm A(FCA-only) 후보보다 planted를 잘 복원하나 (보조 진단).
    a_sig = [it.signal for it in _label_abstractions(fca_abs, planted, thresh) if it.signal is not None]
    b_sig = [
        it.signal
        for it in _label_abstractions(list(proposed), planted, thresh)
        if it.signal is not None
    ]
    auc = auc_mann_whitney(b_sig, a_sig) if (a_sig and b_sig) else None

    verdict = "MEASURABLE_LIFT" if delta > 0 else "MEASURABLE_NULL"
    reason = (
        "Arm B(FCA+vLLM 개념명명)가 floor를 이김 — vLLM이 FCA가 못 잡는 추상 복원."
        if delta > 0
        else "vLLM 개념명명이 FCA floor를 못 이김 (이득 없음 실측 — 날조 아님)."
    )
    return EurekaNamingResult(
        preflight=preflight,
        arm_a_score=arm_a,
        arm_b_score=arm_b,
        delta=delta,
        n=n,
        verdict=verdict,
        auc_b_vs_a=auc,
        reason=reason,
        diagnostics={
            "n_fca_abstractions": len(fca_abs),
            "n_vllm_proposed": len(proposed),
            "circularity_ratio": preflight.circularity_ratio,
            "signal_availability": preflight.signal_availability,
        },
    )


__all__ = [
    "CIRCULARITY_KEYWORDS",
    "RECOVERY_THRESH",
    "EurekaNamingResult",
    "NamedAbstraction",
    "NamingClient",
    "run_eureka_naming_ab",
]
