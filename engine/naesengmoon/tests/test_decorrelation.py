"""Tests for naesengmoon decorrelation — n_eff, echo detector, correlation-aware aggregation."""

import math

from engine.naesengmoon.decorrelation import (
    CriticKind,
    CriticVerdict,
    aggregate,
    effective_n,
    estimate_rho,
    flag_echo,
    prompt_echo_score,
)


def _j(lens, passed, echo=False):
    return CriticVerdict(lens, CriticKind.JUDGMENT, passed, "claude", echo)


def _o(lens, passed):
    return CriticVerdict(lens, CriticKind.ORACLE, passed, "cypher")


# ---- effective_n (Kish) ----


def test_neff_independent_when_rho_zero():
    assert effective_n(0, 3, 0.0) == 3.0


def test_neff_collapses_to_one_when_rho_one():
    assert effective_n(0, 3, 1.0) == 1.0


def test_neff_correlated_three_critics_near_one():
    # ρ=0.85, 3 judgment critics → ~1.2 effective votes (the session's finding)
    assert math.isclose(effective_n(0, 3, 0.85), 3 / (1 + 2 * 0.85), rel_tol=1e-9)
    assert effective_n(0, 3, 0.85) < 1.5


def test_oracle_counts_as_independent():
    # 1 oracle + 2 fully-correlated judgment → oracle stays 1, judgment→1 ⇒ 2.0
    assert effective_n(1, 2, 1.0) == 2.0


# ---- estimate_rho ----


def test_rho_identical_critics_is_one():
    votes = [[True, False, True, False], [True, False, True, False]]
    assert math.isclose(estimate_rho(votes), 1.0, rel_tol=1e-9)


def test_rho_anti_correlated_clamped_to_zero():
    votes = [[True, False, True, False], [False, True, False, True]]
    assert estimate_rho(votes) == 0.0  # -1 clamped to 0


def test_rho_none_when_too_few_critics():
    assert estimate_rho([[True, False]]) is None


# ---- prompt-echo ----


def test_echo_high_when_reasoning_restates_hint():
    hint = "attack the circularity and vacuity of the delegation claim"
    reasoning = "the delegation claim has clear circularity and vacuity, attack confirmed"
    assert prompt_echo_score(hint, reasoning) > 0.3


def test_echo_low_when_independent():
    hint = "attack the circularity and vacuity of the delegation claim"
    reasoning = "merrill 2024 shows non diagonal transitions escape tc0 per theorem five two"
    assert prompt_echo_score(hint, reasoning) < 0.1


def test_flag_echo_marks_suspect():
    vs = [_j("constitutional", True), _j("mathematical", True)]
    flag_echo(
        vs,
        "attack circularity here now",
        {"constitutional": "attack circularity here now indeed"},
        threshold=0.5,
    )
    assert vs[0].echo_suspect is True
    assert vs[1].echo_suspect is False


# ---- aggregate ----


def test_correlated_unanimous_does_not_yield_clean_pass():
    # 3 judgment critics all PASS but ρ=0.85 → n_eff<1.5, adjusted confidence collapses
    res = aggregate([_j("a", True), _j("b", True), _j("c", True)], rho=0.85)
    assert res.n_eff < 1.5
    assert res.raw_coverage == 1.0
    assert res.adjusted_confidence < 0.6
    assert res.verdict == "CONDITIONAL_PASS"  # not a clean PASS despite 3-of-3
    assert "n_eff≈" in res.summary


def test_oracle_fail_is_non_overridable():
    res = aggregate([_o("cypher", False), _j("a", True), _j("b", True)], rho=0.0)
    assert res.verdict == "FAIL"  # oracle veto overrides judgment PASSes


def test_oracle_pass_plus_independent_judgment_can_pass():
    res = aggregate([_o("cypher", True), _j("a", True), _j("b", True)], rho=0.0)
    assert res.n_eff == 3.0
    assert res.verdict == "PASS"


def test_echo_suspect_excluded_from_tally():
    res = aggregate([_j("a", True), _j("b", True, echo=True)], rho=0.0)
    assert res.n_judgment == 1 and res.n_echo_excluded == 1


def test_summary_reports_neff_honestly():
    res = aggregate([_j("a", True), _j("b", True), _j("c", True)], rho=0.85)
    assert "3 critics" in res.summary and "n_eff≈1.11" in res.summary  # 3/(1+2·0.85)
