"""Tests — IPT (Isomorphic Perturbation Testing) lens.

A verifier that PASSes a claim in one surface form but flips on a logically-equivalent
restatement is exploiting the form, not verifying the relation (RLVR extensional shortcut,
arXiv:2604.15149). IPT reruns the verifier over isomorphs and ESCALATEs on variance.

# KG: finding-prom16-ipt-isomorphic-perturbation-lens-2026-07-13
"""

from __future__ import annotations

from engine.naesengmoon.ipt import (
    IptVerdict,
    generate_isomorphs,
    ipt_check,
    rename_placeholders,
    reorder_commutative,
)


def test_robust_pass_when_verifier_invariant() -> None:
    # a genuine verifier gives the same answer regardless of surface form
    verdict = ipt_check("x > 0", ["a > 0", "0 < a"], verify_fn=lambda _c: True)
    assert verdict.verdict is IptVerdict.ROBUST_PASS
    assert verdict.invariant is True
    assert verdict.flipped == ()


def test_robust_fail_when_invariantly_rejected() -> None:
    verdict = ipt_check("x > 0", ["a > 0"], verify_fn=lambda _c: False)
    assert verdict.verdict is IptVerdict.ROBUST_FAIL
    assert verdict.base_passed is False


def test_escalate_when_verdict_flips_on_isomorph() -> None:
    # verifier passes ONLY the exact base string → surface-form exploit
    passes_only_base = {"x > 0"}
    verdict = ipt_check(
        "x > 0", ["a > 0", "0 < a"], verify_fn=lambda c: c in passes_only_base
    )
    assert verdict.verdict is IptVerdict.ESCALATE
    assert verdict.invariant is False
    assert set(verdict.flipped) == {"a > 0", "0 < a"}


def test_no_variants_still_reports_base() -> None:
    verdict = ipt_check("x > 0", [], verify_fn=lambda _c: True)
    assert verdict.verdict is IptVerdict.ROBUST_PASS
    assert verdict.n_variants == 0


def test_rename_placeholders_consistent() -> None:
    assert rename_placeholders("f(x) = x + x", {"x": "y", "f": "g"}) == "g(y) = y + y"
    # non-mapped tokens and numbers untouched
    assert rename_placeholders("x + 1 > x", {"x": "z"}) == "z + 1 > z"


def test_reorder_commutative_reverses_clauses() -> None:
    assert reorder_commutative("A and B and C", " and ") == "C and B and A"
    assert reorder_commutative("p, q", ", ") == "q, p"


def test_generate_isomorphs_combines_transforms() -> None:
    isos = generate_isomorphs(
        "a and b", renames={"a": "x", "b": "y"}, commutative_sep=" and "
    )
    assert "x and y" in isos  # renamed
    assert "b and a" in isos  # reordered
    assert "a and b" not in isos  # base itself excluded


def test_ipt_end_to_end_catches_enumeration_shortcut() -> None:
    # a verifier that only 'knows' the literal claim strings it memorised
    memorised = {"forall n: even(2*n)"}
    isos = generate_isomorphs(
        "forall n: even(2*n)", renames={"n": "k"}, commutative_sep=None
    )
    result = ipt_check(
        "forall n: even(2*n)", isos, verify_fn=lambda c: c in memorised
    )
    assert result.verdict is IptVerdict.ESCALATE
