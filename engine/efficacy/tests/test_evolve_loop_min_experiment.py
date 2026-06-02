"""FunSearch-loop 최소 실험 테스트 — equal-budget + 구조-실현 게이트."""

from __future__ import annotations

from engine.efficacy.evolve_loop_min_experiment import (
    GateVerdict,
    Landscape,
    Oracle,
    evolve_loop,
    realization_gate,
    run_ab,
)
import random


def test_equal_budget_consumed():
    # LOOP는 정확히 budget oracle-eval을 써야 equal-compute 비교가 정직.
    oracle = Oracle(landscape=Landscape.STRUCTURED, target=12345, salt=99)
    real_score = oracle.score
    counted: list[int] = []
    object.__setattr__(oracle, "score", lambda g: (counted.append(g), real_score(g))[1])
    evolve_loop(oracle, budget=200, rng=random.Random(1))
    assert len(counted) == 200


def test_structured_loop_beats_bon():
    # 구조 있는 landscape: oracle-steering loop가 blind best-of-N을 이긴다.
    res = run_ab(Landscape.STRUCTURED, n_seeds=20, budget=256)
    assert res.delta_loop_vs_bon > 0.5
    assert res.perm_p_loop_vs_bon < 0.01


def test_shuffled_loop_does_not_beat_bon():
    # 구조 파괴(locality 없음): 이득이 사라져야 한다 (steering 신호 없음).
    res = run_ab(Landscape.SHUFFLED, n_seeds=20, budget=256)
    assert res.delta_loop_vs_bon < 0.5


def test_ablation_collapses_to_bon_on_structured():
    # 피드백 제거(무작위 부모) LOOP는 BoN 수준으로 붕괴해야 (피드백이 load-bearing).
    res = run_ab(Landscape.STRUCTURED, n_seeds=20, budget=256)
    assert res.delta_loop_vs_ablation > 0.5  # 진짜 LOOP가 ablation보다 확실히 높음


def test_realization_gate_real_win():
    structured = run_ab(Landscape.STRUCTURED, n_seeds=30, budget=256)
    shuffled = run_ab(Landscape.SHUFFLED, n_seeds=30, budget=256)
    gate = realization_gate(structured, shuffled)
    assert gate.verdict is GateVerdict.REAL_WIN


def test_oracle_deterministic():
    o1 = Oracle(landscape=Landscape.STRUCTURED, target=42, salt=7)
    o2 = Oracle(landscape=Landscape.STRUCTURED, target=42, salt=7)
    assert o1.score(13) == o2.score(13)
    # target 자신은 최대 점수 (n_bits).
    assert o1.score(42) == 24.0
