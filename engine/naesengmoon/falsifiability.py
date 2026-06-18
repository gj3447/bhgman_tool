"""나생문 falsifiability 렌즈 — 주장을 '참-거짓 대상인지' 가르고 외부 오라클로 라우팅.

외부 리뷰 비판 #4 자동화의 *전반부*: 나생문이 "참"을 밝히려면 먼저 주장이 *외부에서 거짓일 수
있는 예측*을 하나라도 하는지 가려야 한다. 안 하면 그건 참이 아니라 정의(consistency-only) →
truth-apt 아님으로 강등. 한다면 *가장 싼 외부 falsifier*로 보내고, 판정은 **저자가 못 만든
기질(substrate)**에 맡긴다 (같은 LLM의 자기 채점 ≠ 외부 검증).

정직 공시: 이건 *키워드 routing heuristic*이지 똑똑한 분류기가 아니다 — 개수=품질로 파는 그
Goodhart를 피하려 일부러 단순·투명하게 둔다. 가치는 "어디로 보낼지/누가 판정해야 하는지"의
*라우팅*이지 분류 정확도가 아니다. 최종 판정은 라우팅된 외부 오라클이 한다.

# KG: 외부 리뷰 tension #4 (in-system validation), formal-cathedral-detection-2026-05-27
"""

from __future__ import annotations

from dataclasses import dataclass

# 주장 클래스 → (판정 가능한 외부 기질, 가장 싼 falsifier). 저자의 LLM은 어디에도 없음.
_EMPIRICAL_HINTS = (
    "faster",
    "f1",
    "passes",
    "reproduce",
    "%",
    "x faster",
    "benchmark",
    "latency",
    "throughput",
    "measured",
    "실측",
    "재현",
    "통과",
    "배",
    "초",
)
_EFFICACY_HINTS = (
    "improves",
    "better than",
    "beats",
    "outperform",
    "vs base",
    "baseline",
    "개선",
    "더 낫",
    "우위",
    "능가",
)
_CONSISTENCY_HINTS = (
    "theorem",
    "lemma",
    "by definition",
    "well-typed",
    "type-checks",
    "consistent",
    "compiles",
    "정리",
    "정의상",
    "일관",
    "컴파일",
)
_UNFALSIFIABLE_HINTS = (
    "is the foundation",
    "should be adopted",
    "is the true",
    "the essence",
    "by nature",
    "토대",
    "본질",
    "참 자체",
    "채택해야",
    "근본적으로 옳",
)


@dataclass(frozen=True)
class ClaimRouting:
    # KG: naesengmoon-canonical-2026-05-19
    claim: str
    claim_class: str  # empirical | efficacy | consistency-only | unfalsifiable
    truth_apt: bool  # 외부에서 거짓일 수 있나
    oracle: str  # 판정 가능한 외부 기질
    cheapest_falsifier: str


def _has(text: str, hints: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(h in low for h in hints)


def classify(claim: str) -> ClaimRouting:
    # KG: naesengmoon-canonical-2026-05-19
    """주장 → 라우팅. 우선순위: unfalsifiable > consistency > efficacy > empirical (보수적)."""
    if _has(claim, _UNFALSIFIABLE_HINTS):
        return ClaimRouting(
            claim,
            "unfalsifiable",
            False,
            "none (metaphysical / axiom choice)",
            "no external test exists → demote: not truth-apt, adopt-or-not by fruitfulness",
        )
    if _has(claim, _CONSISTENCY_HINTS):
        return ClaimRouting(
            claim,
            "consistency-only",
            False,
            "compiler / Lean / type-checker (substrate-disjoint)",
            "run the checker — but PASS = consistent-given-axioms, NOT true",
        )
    if _has(claim, _EFFICACY_HINTS):
        return ClaimRouting(
            claim,
            "efficacy",
            True,
            "external A/B oracle (planted ground truth, equal tool budget)",
            "A/B vs base model — if no separation, claim is false (value is operational, not capability)",
        )
    if _has(claim, _EMPIRICAL_HINTS):
        return ClaimRouting(
            claim,
            "empirical",
            True,
            "real-world referent execution OR independent reproduction",
            "run the referent / a different-vendor agent reproduces — one counterexample refutes",
        )
    # 매핑/현실 주장 default: 외부 referent 실행으로만 falsify 가능
    return ClaimRouting(
        claim,
        "empirical",
        True,
        "real-world referent execution (different substrate than author)",
        "execute the mapped real system and compare to the model's prediction",
    )


__all__ = ["ClaimRouting", "classify"]
