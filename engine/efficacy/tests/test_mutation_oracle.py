"""mutation_oracle 순수부 — 변이 생성."""

from __future__ import annotations

from engine.efficacy.mutation_oracle import (
    MutationResult,
    aggregate_catch_rates,
    generate_mutants,
)


def test_generates_mutant_per_applicable_pattern():
    src = "x = a > b\ny = c + d"
    muts = generate_mutants(src, mutations=((" > ", " >= ", "gt"), (" + ", " - ", "plus")))
    assert len(muts) == 2
    assert any("a >= b" in m.source for m in muts)
    assert any("c - d" in m.source for m in muts)


def test_only_first_occurrence_mutated():
    src = "a + b + c"
    muts = generate_mutants(src, mutations=((" + ", " - ", "p"),))
    assert muts[0].source == "a - b + c"  # 첫 출현만


def test_no_mutant_when_pattern_absent():
    assert generate_mutants("plain text", mutations=((" > ", " >= ", "g"),)) == []


def test_catch_rate():
    assert MutationResult(total=10, caught=8, escaped=2).catch_rate == 0.8
    assert MutationResult(total=0, caught=0, escaped=0).catch_rate == 0.0


def test_aggregate_empty_is_all_zero():
    agg = aggregate_catch_rates([])
    assert agg.n_runs == 0
    assert (agg.mean, agg.std, agg.minimum, agg.maximum) == (0.0, 0.0, 0.0, 0.0)


def test_aggregate_single_run_zero_std():
    agg = aggregate_catch_rates([0.6])
    assert agg.n_runs == 1
    assert agg.mean == 0.6 and agg.std == 0.0
    assert agg.minimum == 0.6 and agg.maximum == 0.6


def test_aggregate_distribution_stats():
    # 관측된 naesengmoon 분포 형태: 0.3~0.6 변동.
    agg = aggregate_catch_rates([0.3, 0.5, 0.5, 0.5, 0.5, 0.6])
    assert agg.n_runs == 6
    assert agg.minimum == 0.3 and agg.maximum == 0.6
    assert abs(agg.mean - 0.4833333) < 1e-6
    assert abs(agg.std - 0.089752) < 1e-4  # 모표준편차 pstdev
