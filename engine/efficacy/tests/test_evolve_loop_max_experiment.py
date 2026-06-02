"""FunSearch-loop 최대 스윕 실험 테스트 — α-단조성 + 구조없음서 0 + 이질성."""

from __future__ import annotations

from engine.efficacy.evolve_loop_max_experiment import (
    GradedOracle,
    evolve_loop_multiop,
    run_cell,
    run_hetero,
    run_sweep,
)
import random


def test_graded_oracle_endpoints():
    # α=1 완전 구조: target이 최대점. α=0: target이라고 최대 보장 안 됨(locality 없음).
    o1 = GradedOracle(alpha=1.0, target=100, salt=3)
    assert o1.score(100) == 24.0
    o0 = GradedOracle(alpha=0.0, target=100, salt=3)
    assert 0.0 <= o0.score(100) <= 24.0


def test_multiop_equal_budget():
    oracle = GradedOracle(alpha=1.0, target=55, salt=9)
    counted = []
    real = oracle.score
    object.__setattr__(oracle, "score", lambda g: (counted.append(g), real(g))[1])
    evolve_loop_multiop(oracle, budget=180, rng=random.Random(2), ops=(1, 2, 4))
    assert len(counted) == 180


def test_cell_structured_wins_nostructure_doesnt():
    win = run_cell(alpha=1.0, budget=256, n_seeds=15)
    flat = run_cell(alpha=0.0, budget=256, n_seeds=15)
    assert win.verdict == "REAL_WIN"
    assert flat.verdict == "NO_SIGNAL"
    assert win.delta_loop_vs_bon > flat.delta_loop_vs_bon


def test_sweep_monotone_and_zero_at_no_structure():
    sweep = run_sweep(alphas=(0.0, 0.5, 1.0), budgets=(128, 256), n_seeds=15)
    for b in (128, 256):
        assert sweep.monotone_in_alpha(b)
        assert sweep.zero_at_no_structure(b)


def test_hetero_runs():
    h = run_hetero(alpha=1.0, budget=256, n_seeds=15)
    # 이질성은 이득일 수도 미미할 수도 — 정직하게 둘 다 허용, 산출만 검증.
    assert h.homo_mean > 0 and h.hetero_mean > 0
    assert -5.0 < h.delta < 5.0
