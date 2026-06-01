"""operational scale curve — longinus(결정론) vs base-LLM(컨텍스트 벽) 정량.

cognitive lift는 0(ab-longinus-vs-baseLLM)이지만 operational 가치는 scale에서 발생:
base-LLM은 노드 수에 비례해 prompt 토큰이 늘어 ~10^4에서 컨텍스트 벽(실행 불가) +
선형 비용. longinus는 임의 N에서 flat 정확도 + O(N) 미미한 시간 + 0 토큰.

순수(scale_point) + 측정(run_curve). 토큰 모델 = serialize_task 길이/4 (대략).

# KG: ab-longinus-scale-curve-2026-06-01, ab-longinus-vs-baseLLM-2026-06-01,
#     efficacy-longinus-2026-06-01, consensus-effmeas-2026-06-01 (c5 operational vs cognitive)
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from engine.efficacy.longinus_ab_experiment import (
    build_sandbox,
    longinus_detect,
    score_arm,
    serialize_task,
)

CHARS_PER_TOKEN = 4  # 대략적 영문/기호 비율
DEFAULT_CONTEXT_LIMIT = 200_000  # 토큰 (전형적 대형 컨텍스트 윈도)
COST_PER_MTOK = 3.0  # USD / 1M input tokens (예시 단가)


@dataclass(frozen=True)
class ScalePoint:
    n: int
    longinus_classification: float
    longinus_seconds: float
    base_llm_prompt_tokens: int  # base-LLM 1회 실행 prompt 토큰
    base_llm_context_overflow: bool  # 컨텍스트 한도 초과 = 실행 불가
    base_llm_cost_usd: float  # 1회 실행 비용


def _composition(n: int) -> tuple[int, int, int, int, int]:
    c = int(n * 0.48)
    e = int(n * 0.16)
    m = int(n * 0.16)
    d = int(n * 0.12)
    return c, e, m, d, n - c - e - m - d


def scale_point(n: int, seed: int = 42, context_limit: int = DEFAULT_CONTEXT_LIMIT) -> ScalePoint:
    """N 한 점 측정. longinus 실측 + base-LLM 토큰/벽/비용 모델."""
    sb = build_sandbox(*_composition(n), seed=seed)
    t0 = time.perf_counter()
    sc = score_arm(longinus_detect(sb), sb.ledger)
    dt = time.perf_counter() - t0
    tokens = len(serialize_task(sb)) // CHARS_PER_TOKEN
    return ScalePoint(
        n=n,
        longinus_classification=sc.classification_accuracy,
        longinus_seconds=dt,
        base_llm_prompt_tokens=tokens,
        base_llm_context_overflow=tokens > context_limit,
        base_llm_cost_usd=tokens / 1_000_000 * COST_PER_MTOK,
    )


def run_curve(ns: tuple[int, ...] = (100, 1000, 10000, 100000)) -> list[ScalePoint]:
    return [scale_point(n) for n in ns]


def main() -> int:  # pragma: no cover
    print("N        longinus_cls  time      base-LLM_tokens  overflow  cost")
    for p in run_curve():
        print(
            f"{p.n:<8} {p.longinus_classification:.3f}        {p.longinus_seconds:.4f}s  "
            f"{p.base_llm_prompt_tokens:>12}    "
            f"{'OVERFLOW' if p.base_llm_context_overflow else 'ok':<8}  ${p.base_llm_cost_usd:.4f}"
        )
    return 0


__all__ = ["ScalePoint", "run_curve", "scale_point"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
