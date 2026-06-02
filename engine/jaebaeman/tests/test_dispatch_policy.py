"""재배맨 oracle-gated dispatch policy 테스트 — early-exit + mode-lock 회피.

측정된 두 결함(포화 task anchoring harm / best-K mode-lock)을 정책이 고치는지 결정론 검증.
"""

from __future__ import annotations

import random

from engine.jaebaeman.dispatch_policy import (
    DispatchPolicy,
    oracle_gated_dispatch,
)
from engine.legion.evolve_loop import (
    Candidate,
    InMemoryCorpus,
    ScoredCandidate,
    run_evolve,
)


class _SolveFirstGen:
    """1-shot(blind, best 비어있음)에 즉시 정답. feedback 받으면 *나쁜* 변형(mode-lock 모사)."""

    def propose(self, task, best, rng: random.Random) -> Candidate:
        if not best:  # cold/blind 1-shot → 정답
            return Candidate("1" * 10)
        return Candidate("0" * 10)  # best-K 받으면 최악 (anchoring harm 모사)


class _Popcount:
    def score(self, task, cand) -> ScoredCandidate:
        s = float(cand.payload.count("1"))
        return ScoredCandidate(cand, s, s >= 1.0)


def test_early_exit_on_solve_no_escalation():
    # 1-shot에 풀리면(score 10 ≥ solve_threshold) escalate 안 하고 1 eval만 — anchoring harm 0.
    pol = DispatchPolicy(solve_threshold=10.0, escalate_budget=6)
    res = oracle_gated_dispatch(
        "t", _SolveFirstGen(), _Popcount(), InMemoryCorpus(), random.Random(1), pol
    )
    assert res.solved
    assert res.escalated is False  # headroom 없음 → flywheel 안 켜짐
    assert res.evals == 1  # cheap 1-shot만
    assert res.best_score == 10.0


def test_run_evolve_solve_threshold_early_exit():
    # primitive: solve_threshold 도달 시 budget 다 안 쓰고 중단.
    gen = _SolveFirstGen()
    run = run_evolve(
        "t",
        20,
        gen,
        _Popcount(),
        InMemoryCorpus(),
        random.Random(1),
        feedback=False,
        solve_threshold=10.0,
    )
    assert run.best_score == 10.0
    assert run.evals < 20  # 첫 시도에 풀려 조기 종료
    assert run.evals == 1


class _ModeLockGen:
    """부분해(score 5)를 cold로 내고, feedback 받으면 그 부분해에 갇힘(score 5 반복).
    단 blind(explore, best 빈 context)면 정답(score 10) 발견 가능 — exploration이 탈출구."""

    def propose(self, task, best, rng: random.Random) -> Candidate:
        if not best:
            # blind: 절반은 정답(10), 절반은 부분해(5) — 탐색하면 정답 도달
            return Candidate("1" * 10) if rng.random() < 0.5 else Candidate("1" * 5 + "0" * 5)
        return Candidate("1" * 5 + "0" * 5)  # feedback 받으면 부분해 mode-lock


def test_exploration_escapes_mode_lock():
    # 순수 feedback(explore_prob=0)은 부분해(5)에 갇히고, explore 섞으면 blind가 정답(10) 발견.
    # 부분해를 corpus에 미리 심어 cold 1-shot도 best로 그걸 봄.
    seeded = InMemoryCorpus()
    seeded.record("t", ScoredCandidate(Candidate("1" * 5 + "0" * 5), 5.0, True))
    pure = run_evolve(
        "t",
        8,
        _ModeLockGen(),
        _Popcount(),
        seeded,
        random.Random(3),
        feedback=True,
        explore_prob=0.0,
    )
    assert pure.best_score == 5.0  # mode-lock: feedback만 → 부분해 갇힘

    seeded2 = InMemoryCorpus()
    seeded2.record("t", ScoredCandidate(Candidate("1" * 5 + "0" * 5), 5.0, True))
    mixed = run_evolve(
        "t",
        8,
        _ModeLockGen(),
        _Popcount(),
        seeded2,
        random.Random(3),
        feedback=True,
        explore_prob=0.5,
    )
    assert mixed.best_score == 10.0  # exploration이 mode-lock 탈출 → 정답


def test_explore_prob_zero_is_byte_identical():
    # explore_prob=0.0이면 rng 소비 안 함 → 기존 동작과 동일(회귀 방지).
    g1, g2 = _Popcount(), _Popcount()

    class G:
        def propose(self, task, best, rng):
            return Candidate("1" * rng.randint(1, 9))

    r0 = run_evolve("t", 5, G(), g1, InMemoryCorpus(), random.Random(7), feedback=True)
    r1 = run_evolve(
        "t", 5, G(), g2, InMemoryCorpus(), random.Random(7), feedback=True, explore_prob=0.0
    )
    assert [t for t in r0.trace] == [t for t in r1.trace]
