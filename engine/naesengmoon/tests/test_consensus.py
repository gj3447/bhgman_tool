"""NCP-1 consensus hardening — admit() + decide() exhaustive / attack-branch coverage.

Regression guards for:
  FIX 1 — D20 fail-closed on JUDGMENT PASS/CONDITIONAL (empty executor/reviewer)
  FIX 2 — n_eff clean-PASS cap applies universally (self-labeled ORACLE is not exempt)
  (FIX 3 lives in engine/tpa/tests — TpaReverseRun.all_passed fail-closed)

# KG: naesengmoon-consensus-protocol-ncp1-2026-07-13
"""

from __future__ import annotations

from engine.naesengmoon.consensus import (
    MIN_EFF_FOR_CLEAN_PASS,
    Disposition,
    Escalation,
    LensClass,
    Policy,
    PolicyKind,
    Vote,
    VoteValue,
    admit,
    decide,
)


# ── helpers ──────────────────────────────────────────────────────────────────


def _j(
    lens: str,
    value: VoteValue = VoteValue.PASS,
    *,
    evidence: tuple[str, ...] = ("e1",),
    executor: str = "exec-a",
    reviewer: str = "rev-b",
    obligations: tuple[str, ...] = (),
    echo_suspect: bool = False,
    weight: float = 1.0,
) -> Vote:
    return Vote(
        lens=lens,
        lens_class=LensClass.JUDGMENT,
        value=value,
        evidence=evidence,
        executor=executor,
        reviewer=reviewer,
        obligations=obligations,
        echo_suspect=echo_suspect,
        weight=weight,
    )


def _o(
    lens: str,
    value: VoteValue = VoteValue.PASS,
    *,
    evidence: tuple[str, ...] = ("oracle-e",),
    executor: str = "",
    reviewer: str = "",
) -> Vote:
    return Vote(
        lens=lens,
        lens_class=LensClass.ORACLE,
        value=value,
        evidence=evidence,
        executor=executor,
        reviewer=reviewer,
    )


# ── FIX 1: D20 fail-closed ───────────────────────────────────────────────────


def test_d20_equal_executor_reviewer_dropped():
    """executor == reviewer (both non-empty) → DROPPED_D20, not admitted."""
    v = _j("math", executor="alice", reviewer="alice")
    ads = admit([v])
    assert ads[0].disposition is Disposition.DROPPED_D20
    assert ads[0].effective_value is VoteValue.ABSTAIN


def test_d20_judgment_pass_empty_executor_reviewer_unverified():
    """FIX 1 guard: JUDGMENT PASS with empty roles must NOT be admitted (fail-closed)."""
    v = _j("math", executor="", reviewer="")
    ads = admit([v])
    assert ads[0].disposition is Disposition.DROPPED_D20_UNVERIFIED
    assert ads[0].effective_value is VoteValue.ABSTAIN


def test_d20_judgment_pass_missing_reviewer_unverified():
    v = _j("math", executor="alice", reviewer="")
    ads = admit([v])
    assert ads[0].disposition is Disposition.DROPPED_D20_UNVERIFIED


def test_d20_judgment_pass_missing_executor_unverified():
    v = _j("math", executor="", reviewer="bob")
    ads = admit([v])
    assert ads[0].disposition is Disposition.DROPPED_D20_UNVERIFIED


def test_d20_judgment_conditional_empty_roles_unverified():
    v = _j(
        "math",
        VoteValue.CONDITIONAL,
        obligations=("fix-me",),
        executor="",
        reviewer="",
    )
    ads = admit([v])
    assert ads[0].disposition is Disposition.DROPPED_D20_UNVERIFIED


def test_d20_judgment_pass_distinct_executor_reviewer_admitted():
    v = _j("math", executor="alice", reviewer="bob")
    ads = admit([v])
    assert ads[0].disposition is Disposition.ADMITTED
    assert ads[0].effective_value is VoteValue.PASS


def test_d20_oracle_pass_empty_executor_reviewer_exempt():
    """ORACLE PASS is substrate-disjoint — no author/reviewer pair required."""
    v = _o("lean-goals", executor="", reviewer="")
    ads = admit([v])
    assert ads[0].disposition is Disposition.ADMITTED
    assert ads[0].effective_value is VoteValue.PASS


def test_d20_judgment_fail_empty_roles_not_subject():
    """FAIL is not gameable into agreement — presence check does not apply."""
    v = _j("math", VoteValue.FAIL, evidence=("counter",), executor="", reviewer="")
    ads = admit([v])
    assert ads[0].disposition is Disposition.ADMITTED
    assert ads[0].effective_value is VoteValue.FAIL


def test_d20_judgment_abstain_empty_roles_not_subject():
    v = _j("math", VoteValue.ABSTAIN, evidence=(), executor="", reviewer="")
    ads = admit([v])
    assert ads[0].disposition is Disposition.ADMITTED
    assert ads[0].effective_value is VoteValue.ABSTAIN


def test_d20_equal_still_drops_oracle_when_both_filled():
    """Equal-pair drop remains universal when both roles are non-empty."""
    v = _o("lean-goals", executor="same", reviewer="same")
    ads = admit([v])
    assert ads[0].disposition is Disposition.DROPPED_D20


# ── admit: dup-lens / echo / evidence / obligations ─────────────────────────


def test_dup_lens_second_dropped():
    a = _j("math", evidence=("e1",))
    b = _j("math", evidence=("e2",), executor="x", reviewer="y")
    ads = admit([a, b])
    assert ads[0].disposition is Disposition.ADMITTED
    assert ads[1].disposition is Disposition.DROPPED_DUP_LENS


def test_echo_suspect_judgment_dropped():
    v = _j("math", echo_suspect=True)
    ads = admit([v])
    assert ads[0].disposition is Disposition.DROPPED_ECHO


def test_echo_suspect_oracle_not_dropped():
    v = Vote(
        lens="oracle-x",
        lens_class=LensClass.ORACLE,
        value=VoteValue.PASS,
        evidence=("e",),
        echo_suspect=True,
    )
    ads = admit([v])
    assert ads[0].disposition is Disposition.ADMITTED


def test_pass_without_evidence_downgraded():
    v = _j("math", evidence=())
    ads = admit([v])
    assert ads[0].disposition is Disposition.DOWNGRADED_NO_EVIDENCE
    assert ads[0].effective_value is VoteValue.ABSTAIN


def test_conditional_without_obligations_downgraded():
    v = _j("math", VoteValue.CONDITIONAL, obligations=())
    ads = admit([v])
    assert ads[0].disposition is Disposition.DOWNGRADED_NO_OBLIGATIONS
    assert ads[0].effective_value is VoteValue.ABSTAIN


def test_conditional_with_obligations_and_evidence_admitted():
    v = _j("math", VoteValue.CONDITIONAL, obligations=("ship-doc",))
    ads = admit([v])
    assert ads[0].disposition is Disposition.ADMITTED
    assert ads[0].effective_value is VoteValue.CONDITIONAL


def test_admit_order_d20_before_dup_lens():
    """D20 equal runs before dup-lens so both drops are recorded distinctly."""
    a = _j("math", executor="same", reviewer="same")
    b = _j("math", executor="a", reviewer="b")
    ads = admit([a, b])
    assert ads[0].disposition is Disposition.DROPPED_D20
    # first math was dropped before seen_lens, so second math is still first of lens
    assert ads[1].disposition is Disposition.ADMITTED


# ── decide(): oracle veto / empty / collapse / n_eff / policies ──────────────


def test_decide_oracle_fail_hard_gate():
    votes = [
        _o("lean-goals", VoteValue.FAIL, evidence=("proof-broken",)),
        _j("math", evidence=("looks-ok",)),
        _j("solid", evidence=("ok-solid",), executor="e2", reviewer="r2"),
        _j("const", evidence=("ok-c",), executor="e3", reviewer="r3"),
    ]
    r = decide(votes, rho=0.0)
    assert r.verdict == "FAIL"
    assert r.oracle_veto is True
    assert r.escalation is Escalation.NONE
    assert "ORACLE_VETO" in r.flags


def test_decide_no_effective_votes_escalates_add_lenses():
    # all abstain after admission (empty roles on PASS → D20 unverified)
    votes = [
        _j("math", executor="", reviewer=""),
        _j("solid", executor="", reviewer=""),
    ]
    r = decide(votes)
    assert r.verdict == "ESCALATE"
    assert r.escalation is Escalation.ADD_LENSES
    assert "NO_EFFECTIVE_VOTES" in r.flags


def test_decide_correlated_identical_evidence_steelman():
    # three judgments, same evidence set → collapse to one; independence suspect
    votes = [
        _j("l1", evidence=("shared",), executor="e1", reviewer="r1"),
        _j("l2", evidence=("shared",), executor="e2", reviewer="r2"),
        _j("l3", evidence=("shared",), executor="e3", reviewer="r3"),
    ]
    r = decide(votes, rho=0.0)
    assert r.verdict == "ESCALATE"
    assert r.escalation is Escalation.STEELMAN_OPPOSITE
    assert "CORRELATED_EVIDENCE_COLLAPSED" in r.flags
    assert "INDEPENDENCE_SUSPECT" in r.flags


def test_decide_single_self_labeled_oracle_pass_is_conditional():
    """FIX 2 regression guard: lone self-labeled ORACLE PASS cannot mint clean PASS.

    Old code: `if n_eff < min_eff and not oracles` exempted any admitted oracle → PASS.
    New code: n_eff floor applies universally → CONDITIONAL_PASS.
    """
    votes = [_o("fake-oracle-pass", VoteValue.PASS, evidence=("i-say-so",))]
    r = decide(votes)
    assert r.n_eff < MIN_EFF_FOR_CLEAN_PASS
    assert r.verdict == "CONDITIONAL_PASS"
    assert r.verdict != "PASS"
    assert "N_EFF_BELOW_CLEAN_PASS" in r.flags
    assert r.oracle_veto is False  # FAIL veto path unchanged; this is a PASS vote


def test_decide_healthy_three_judgment_unanimous_pass():
    """Distinct evidence + executor/reviewer + independent rho → clean PASS."""
    votes = [
        _j("math", evidence=("proof-a",), executor="e1", reviewer="r1"),
        _j("solid", evidence=("srp-ok",), executor="e2", reviewer="r2"),
        _j("const", evidence=("amend-ok",), executor="e3", reviewer="r3"),
    ]
    r = decide(votes, rho=0.0)
    assert r.n_eff >= MIN_EFF_FOR_CLEAN_PASS
    assert r.verdict == "PASS"
    assert r.escalation is Escalation.NONE
    assert r.oracle_veto is False


def test_decide_bft_quorum_nj_short_escalates():
    # f=1 requires N_j >= 4; only 2 judgment votes → ADD_LENSES
    votes = [
        _j("l1", evidence=("a",), executor="e1", reviewer="r1"),
        _j("l2", evidence=("b",), executor="e2", reviewer="r2"),
    ]
    r = decide(votes, Policy(kind=PolicyKind.BFT_QUORUM, f=1), rho=0.0)
    assert r.verdict == "ESCALATE"
    assert r.escalation is Escalation.ADD_LENSES
    assert any(f.startswith("BFT_INFEASIBLE_NJ_") for f in r.flags)


def test_decide_bft_quorum_happy_path():
    # f=1 → need N_j >= 4 and pass_j >= 3
    votes = [
        _j(f"l{i}", evidence=(f"e{i}",), executor=f"e{i}", reviewer=f"r{i}")
        for i in range(4)
    ]
    r = decide(votes, Policy(kind=PolicyKind.BFT_QUORUM, f=1), rho=0.0)
    assert r.verdict == "PASS"
    assert r.escalation is Escalation.NONE


def test_decide_majority_happy():
    votes = [
        _j("l1", evidence=("a",), executor="e1", reviewer="r1"),
        _j("l2", evidence=("b",), executor="e2", reviewer="r2"),
        _j("l3", VoteValue.FAIL, evidence=("c",), executor="e3", reviewer="r3"),
    ]
    r = decide(votes, Policy(kind=PolicyKind.MAJORITY), rho=0.0)
    # 2 pass vs 1 fail → majority ok; n_eff with rho=0 is 3 >= 1.5
    assert r.verdict == "PASS"


def test_decide_majority_edge_tie_not_quorum():
    votes = [
        _j("l1", evidence=("a",), executor="e1", reviewer="r1"),
        _j("l2", VoteValue.FAIL, evidence=("b",), executor="e2", reviewer="r2"),
    ]
    r = decide(votes, Policy(kind=PolicyKind.MAJORITY), rho=0.0)
    # 1 pass vs 1 fail → not strict majority; evidenced fail → FAIL
    assert r.verdict == "FAIL"


def test_decide_weighted_happy():
    votes = [
        _j("l1", evidence=("a",), executor="e1", reviewer="r1", weight=0.95),
        _j("l2", VoteValue.FAIL, evidence=("b",), executor="e2", reviewer="r2", weight=0.05),
    ]
    r = decide(votes, Policy(kind=PolicyKind.WEIGHTED, theta=0.9), rho=0.0)
    assert r.verdict == "PASS"


def test_decide_weighted_below_theta_evidenced_fail():
    votes = [
        _j("l1", evidence=("a",), executor="e1", reviewer="r1", weight=0.5),
        _j("l2", VoteValue.FAIL, evidence=("b",), executor="e2", reviewer="r2", weight=0.5),
    ]
    r = decide(votes, Policy(kind=PolicyKind.WEIGHTED, theta=0.9), rho=0.0)
    assert r.verdict == "FAIL"


def test_decide_evidenced_fail_quorum_short():
    """UNANIMOUS with a dissenting evidenced FAIL → FAIL (not escalate)."""
    votes = [
        _j("l1", evidence=("a",), executor="e1", reviewer="r1"),
        _j("l2", VoteValue.FAIL, evidence=("counterexample",), executor="e2", reviewer="r2"),
    ]
    r = decide(votes, rho=0.0)
    assert r.verdict == "FAIL"
    assert r.escalation is Escalation.NONE


def test_decide_unevidenced_dissent_escalates():
    """FAIL without evidence is still counted for quorum but triggers ESCALATE path."""
    votes = [
        _j("l1", evidence=("a",), executor="e1", reviewer="r1"),
        Vote(
            lens="l2",
            lens_class=LensClass.JUDGMENT,
            value=VoteValue.FAIL,
            evidence=(),  # unevidenced FAIL is admitted (HR11 only gates PASS/COND)
            executor="e2",
            reviewer="r2",
        ),
    ]
    r = decide(votes, rho=0.0)
    assert r.verdict == "ESCALATE"
    assert r.escalation is Escalation.TO_ORACLE  # no oracle admitted
    assert "DISSENT_UNEVIDENCED" in r.flags


def test_decide_conditional_pass_carries_obligations():
    votes = [
        _j(
            "l1",
            VoteValue.CONDITIONAL,
            evidence=("a",),
            obligations=("fix-x",),
            executor="e1",
            reviewer="r1",
        ),
        _j("l2", evidence=("b",), executor="e2", reviewer="r2"),
        _j("l3", evidence=("c",), executor="e3", reviewer="r3"),
    ]
    r = decide(votes, rho=0.0)
    assert r.verdict == "CONDITIONAL_PASS"
    assert "fix-x" in r.obligations


def test_decide_judgment_pass_d20_bypass_cannot_mint_pass():
    """Attack: empty-role JUDGMENT PASS must not contribute to a clean PASS."""
    votes = [
        _j("attacker", evidence=("looks-fine",), executor="", reviewer=""),
    ]
    r = decide(votes)
    # vote dropped as D20_UNVERIFIED → no effective votes
    assert r.verdict == "ESCALATE"
    assert r.escalation is Escalation.ADD_LENSES
    ads = admit(votes)
    assert ads[0].disposition is Disposition.DROPPED_D20_UNVERIFIED


def test_decide_n_eff_cap_with_default_rho_three_judgments():
    """Default ρ=0.7 yields n_eff≈1.25 for 3 judgments → CONDITIONAL_PASS cap."""
    votes = [
        _j("l1", evidence=("a",), executor="e1", reviewer="r1"),
        _j("l2", evidence=("b",), executor="e2", reviewer="r2"),
        _j("l3", evidence=("c",), executor="e3", reviewer="r3"),
    ]
    r = decide(votes)  # default rho
    assert r.n_eff < MIN_EFF_FOR_CLEAN_PASS
    assert r.verdict == "CONDITIONAL_PASS"
    assert "N_EFF_BELOW_CLEAN_PASS" in r.flags


def test_decide_oracle_fail_still_vetoes_despite_n_eff_change():
    """FIX 2 must not weaken oracle FAIL hard gate."""
    votes = [_o("checker", VoteValue.FAIL, evidence=("broken",))]
    r = decide(votes)
    assert r.verdict == "FAIL"
    assert r.oracle_veto is True
