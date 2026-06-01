"""mutation_oracle 순수부 — 변이 생성."""

from __future__ import annotations

from engine.efficacy.mutation_oracle import MutationResult, generate_mutants


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
