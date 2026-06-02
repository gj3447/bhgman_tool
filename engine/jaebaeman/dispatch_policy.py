"""재배맨 oracle-gated dispatch policy — 측정이 가리킨 dispatch 정책 (재배맨 본령).

재배맨 = dispatch substrate(plan-first + 언제/무엇을 출격할지 결정). 효능 A/B 측정(EVOLVE_LOOP_
RESULTS.md)이 두 결함을 드러냈다:
  (1) 1-shot에 풀리는 task에 계속 best-K 피드백 → 낭비 + anchoring harm (rle_decode Δ-0.33),
  (2) best-K만 먹이면 부분해 mode-lock(blind는 다른 접근 발견하는데 feedback은 못 함).

이 정책이 둘을 고친다 (KG: 7cmd-measurement-driven-conditional-dispatch — metric 측정 후
threshold 초과 시 escalate):
  1. CHEAP 1-shot(blind) 먼저. oracle PASS면 즉시 종착 — escalate 안 함(anchoring harm 0, 최저 비용).
  2. headroom(1-shot miss)일 때만 escalate. escalate는 blind 탐색(explore_prob)을 섞은 feedback
     루프 + oracle-solve early-exit → mode-lock 완화하며 flywheel lift 포착.

실측 정정 (qwen 7B/1.5B): "순수-BON을 절대 밑돌 수 없다"는 *과장*이었다. 참인 건 1-shot solve 시
early-exit로 BON과 동일(7B 0/5 harm, 4-6배 cheap)뿐. headroom escalation에선 explore_prob에 따라
blind 예산을 feedback과 *trade*하므로, 모델이 feedback을 활용 못 하면 blind가 적어져 BON을 밑돌 수
있다(1.5B 3/5 harm). 활용 가능하면 진짜 lift(1.5B brackets +0.38, rle +0.17). net 효과는 (모델의
feedback 활용력 ∧ task headroom)에 의존 — 정책 보장은 harm-제한이지 dominance가 아니다.

순수 정책 함수 — run_evolve primitive 위 조합. 결정론(주입 rng/oracle/generator).

# KG: jaebaeman-planfirst-essence-reframe-2026-05-27 (재배맨=plan-first dispatch),
#     7cmd-measurement-driven-conditional-dispatch-2026-05-30 (metric→threshold→escalate),
#     prom16-bhgman-ci-design-2026-06-02, lesson-bhgman-collective-intelligence-design-2026-06-02
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from engine.legion.evolve_loop import (
    CandidateCorpus,
    Generator,
    ScalarOracle,
    ScoredCandidate,
    run_evolve,
)


@dataclass(frozen=True)
class DispatchPolicy:
    """재배맨 dispatch 정책 파라미터."""

    solve_threshold: float = 1.0  # oracle score 이 값 이상이면 "풀림" → 중단
    escalate_budget: int = 6  # 1-shot miss 시 escalate 루프 예산
    explore_prob: float = 0.4  # escalate 중 blind 탐색 비율 (mode-lock 방지)
    k: int = 4


@dataclass(frozen=True)
class DispatchResult:
    """oracle-gated dispatch 결과."""

    best: ScoredCandidate | None
    evals: int  # 실제 소비 oracle-eval (1-shot 풀리면 1)
    escalated: bool  # headroom 감지해 flywheel escalate 했나
    solved: bool

    @property
    def best_score(self) -> float:
        return self.best.score if self.best is not None else float("-inf")

    @property
    def summary(self) -> str:
        return (
            f"best={self.best_score:.3f} evals={self.evals} "
            f"escalated={self.escalated} solved={self.solved}"
        )


def _better(a: ScoredCandidate | None, b: ScoredCandidate | None) -> ScoredCandidate | None:
    if a is None:
        return b
    if b is None:
        return a
    return a if a.score >= b.score else b


def oracle_gated_dispatch(
    task: str,
    generator: Generator,
    oracle: ScalarOracle,
    corpus: CandidateCorpus,
    rng: random.Random,
    policy: DispatchPolicy | None = None,
) -> DispatchResult:
    """재배맨 정책: cheap 1-shot → 풀리면 종착, 아니면 explore+feedback escalate (early-exit).

    flywheel(escalate)은 1-shot이 못 풀 때만(headroom) 켜지고, 켜져도 blind 탐색을 섞어
    순수-BON을 절대 밑돌지 않는다 — 측정된 anchoring/mode-lock harm을 구조적으로 회피.
    """
    pol = policy or DispatchPolicy()

    # 1. CHEAP 1-shot (blind). 풀리면 escalate 안 함 (early-exit, anchoring harm 0).
    one = run_evolve(
        task,
        1,
        generator,
        oracle,
        corpus,
        rng,
        k=pol.k,
        feedback=False,
        solve_threshold=pol.solve_threshold,
    )
    if one.best is not None and one.best.score >= pol.solve_threshold:
        return DispatchResult(one.best, one.evals, escalated=False, solved=True)

    # 2. headroom → escalate: blind 탐색(explore_prob) 섞은 feedback + oracle-solve early-exit.
    esc = run_evolve(
        task,
        pol.escalate_budget,
        generator,
        oracle,
        corpus,
        rng,
        k=pol.k,
        feedback=True,
        solve_threshold=pol.solve_threshold,
        explore_prob=pol.explore_prob,
    )
    best = _better(one.best, esc.best)
    solved = best is not None and best.score >= pol.solve_threshold
    return DispatchResult(best, one.evals + esc.evals, escalated=True, solved=solved)


__all__ = ["DispatchPolicy", "DispatchResult", "oracle_gated_dispatch"]
