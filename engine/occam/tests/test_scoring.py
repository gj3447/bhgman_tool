"""오캄 정량 scoring 빡센 테스트 — decay 정확값 + 단조성 property + 경계 + guard.

# KG: consensus-occam-entropy-truth-2026-05-26, dt-occam-naesengmoon-confidence
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine.occam.scoring import (
    NEVER_ARCHIVE_TIERS,
    EntrenchmentTier,
    NodeScoreMeta,
    ScoringConfig,
    Verdict,
    candidacy,
    deadness,
    entrenchment_penalty,
    guard,
    score_node,
    staleness,
)

# ── 시간 decay 정확값 (망각곡선 s = 1 − 2^(−age/halflife)) ─────────────────────


def test_staleness_zero_age_is_zero():
    assert staleness(0.0, 90.0) == 0.0
    assert staleness(-5.0, 90.0) == 0.0  # 음수 age 방어


def test_staleness_at_halflife_is_exactly_half():
    assert staleness(90.0, 90.0) == pytest.approx(0.5)


def test_staleness_at_two_halflives_is_three_quarters():
    # 1 − 2^(−2) = 1 − 0.25 = 0.75
    assert staleness(180.0, 90.0) == pytest.approx(0.75)


def test_staleness_strictly_below_one_at_finite_age():
    # 수학적으로 s = 1 − 2^(−age/hl) < 1 (양수 항이 안 사라짐). 적당한 age에선 확인 가능.
    assert staleness(90.0, 90.0) < 1.0
    assert staleness(900.0, 90.0) < 1.0


def test_staleness_saturates_to_one_at_extreme_age_float_underflow():
    # age/hl 매우 크면 2^(−x)가 float underflow → 정확히 1.0으로 saturate (σ 상한 안전).
    assert staleness(9000.0, 90.0) == 1.0
    assert staleness(9000.0, 90.0) <= 1.0  # 경계 절대 안 넘음


def test_staleness_smaller_halflife_decays_faster():
    # 같은 age면 halflife 작을수록 더 stale
    assert staleness(90.0, 30.0) > staleness(90.0, 90.0)


# ── deadness d = 2^(−inv/scale) ───────────────────────────────────────────────


def test_deadness_zero_invocation_is_one():
    assert deadness(0, 3.0) == 1.0


def test_deadness_at_scale_is_half():
    assert deadness(3, 3.0) == pytest.approx(0.5)


def test_deadness_decreases_with_invocation():
    assert deadness(0, 3.0) > deadness(1, 3.0) > deadness(10, 3.0) > 0.0


# ── candidacy noisy-OR C = 1 − (1−r)(1−s)(1−d) ────────────────────────────────


def test_candidacy_all_zero_is_zero():
    assert candidacy(0.0, 0.0, 0.0) == 0.0


def test_candidacy_any_one_saturates():
    assert candidacy(1.0, 0.0, 0.0) == 1.0
    assert candidacy(0.0, 1.0, 0.0) == 1.0
    assert candidacy(0.0, 0.0, 1.0) == 1.0


def test_candidacy_noisy_or_formula():
    # r=.5 s=.5 d=.5 → 1 − .5*.5*.5 = 1 − .125 = .875
    assert candidacy(0.5, 0.5, 0.5) == pytest.approx(0.875)


def test_candidacy_ge_each_component():
    # noisy-OR ≥ max(component) — 증거 결합은 어느 한 신호 이상
    r, s, d = 0.3, 0.6, 0.2
    c = candidacy(r, s, d)
    assert c >= max(r, s, d) - 1e-12


# ── guard G = (1−e)·twin ──────────────────────────────────────────────────────


def test_guard_canonical_entrenchment_is_zero():
    assert guard(1.0, has_successor=True) == 0.0


def test_guard_no_successor_is_zero():
    assert guard(0.0, has_successor=False) == 0.0


def test_guard_plain_with_successor_is_one():
    assert guard(0.0, has_successor=True) == 1.0


# ── never-archive tier 정전 (canonical/lesson/contract/verdict = e=1.0) ───────


def test_never_archive_tiers_are_the_canon_four():
    assert NEVER_ARCHIVE_TIERS == frozenset(
        {
            EntrenchmentTier.CANONICAL,
            EntrenchmentTier.LESSON,
            EntrenchmentTier.CONTRACT,
            EntrenchmentTier.VERDICT,
        }
    )


def test_entrenchment_ordinal_monotone_nonincreasing():
    order = [
        EntrenchmentTier.CANONICAL,
        EntrenchmentTier.PRINCIPLE,
        EntrenchmentTier.ONTOLOGY_CLASS,
        EntrenchmentTier.REFERENCE,
        EntrenchmentTier.FINDING,
        EntrenchmentTier.PLAIN,
    ]
    vals = [entrenchment_penalty(t) for t in order]
    assert vals == sorted(vals, reverse=True)
    assert vals[0] == 1.0 and vals[-1] == 0.0


# ── score_node 안전 불변식 ────────────────────────────────────────────────────


def test_protected_tier_forces_sigma_zero():
    for tier in NEVER_ARCHIVE_TIERS:
        meta = NodeScoreMeta(redundancy=1.0, age_days=10000, invocation_count=0, tier=tier)
        sc = score_node(meta)
        assert sc.sigma == 0.0
        assert sc.verdict == Verdict.PROTECTED


def test_no_successor_forces_flag_only():
    meta = NodeScoreMeta(
        redundancy=1.0,
        age_days=10000,
        invocation_count=0,
        tier=EntrenchmentTier.PLAIN,
        has_successor=False,
    )
    sc = score_node(meta)
    assert sc.sigma == 0.0
    assert sc.verdict == Verdict.FLAG_ONLY


def test_dead_old_redundant_plain_with_twin_supersedes():
    # 완전중복 + 오래됨 + 미사용 + 일반tier + twin존재 → σ≈1 → SUPERSEDE
    meta = NodeScoreMeta(
        redundancy=1.0,
        age_days=3650,
        invocation_count=0,
        tier=EntrenchmentTier.PLAIN,
    )
    sc = score_node(meta)
    assert sc.sigma == pytest.approx(1.0)
    assert sc.verdict == Verdict.SUPERSEDE


def test_fresh_used_node_keeps():
    meta = NodeScoreMeta(
        redundancy=0.0,
        age_days=1.0,
        invocation_count=50,
        tier=EntrenchmentTier.PLAIN,
    )
    sc = score_node(meta)
    assert sc.sigma < 0.3
    assert sc.verdict == Verdict.KEEP


def test_gray_zone_triggers_verify():
    # σ를 θ_keep~θ_supersede 사이로 — 적당히 신선(45일)하고 적당히 쓰임(6회)
    # s=1−2^(−.5)≈.293, d=2^(−2)=.25, r=0 → C=1−.707*.75=.470, G=1 → σ≈.470 ∈ [.3,.7)
    cfg = ScoringConfig(halflife_days=90.0, invocation_scale=3.0)
    meta = NodeScoreMeta(
        redundancy=0.0,
        age_days=45.0,
        invocation_count=6,
        tier=EntrenchmentTier.PLAIN,
    )
    sc = score_node(meta, cfg)
    assert cfg.theta_keep <= sc.sigma < cfg.theta_supersede
    assert sc.verdict == Verdict.VERIFY


# ── property-based: 경계 + 단조성 ─────────────────────────────────────────────

_unit = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_age = st.floats(min_value=0.0, max_value=1e5, allow_nan=False, allow_infinity=False)
_inv = st.integers(min_value=0, max_value=10_000)
_tiers = st.sampled_from(list(EntrenchmentTier))


@given(r=_unit, age=_age, inv=_inv, tier=_tiers, succ=st.booleans())
def test_sigma_always_in_unit_interval(r, age, inv, tier, succ):
    meta = NodeScoreMeta(
        redundancy=r, age_days=age, invocation_count=inv, tier=tier, has_successor=succ
    )
    sc = score_node(meta)
    assert 0.0 <= sc.sigma <= 1.0
    assert 0.0 <= sc.candidacy <= 1.0
    assert 0.0 <= sc.guard <= 1.0


@given(age1=_age, age2=_age, hl=st.floats(min_value=1.0, max_value=1e4))
def test_staleness_monotone_in_age(age1, age2, hl):
    if age1 > age2:
        age1, age2 = age2, age1
    assert staleness(age1, hl) <= staleness(age2, hl) + 1e-12


@given(i1=_inv, i2=_inv, scale=st.floats(min_value=0.1, max_value=100.0))
def test_deadness_monotone_in_invocation(i1, i2, scale):
    if i1 > i2:
        i1, i2 = i2, i1
    assert deadness(i1, scale) >= deadness(i2, scale) - 1e-12


@given(r1=_unit, r2=_unit, age=_age, inv=_inv)
def test_sigma_monotone_increasing_in_redundancy(r1, r2, age, inv):
    if r1 > r2:
        r1, r2 = r2, r1
    base = dict(age_days=age, invocation_count=inv, tier=EntrenchmentTier.PLAIN)
    s1 = score_node(NodeScoreMeta(redundancy=r1, **base)).sigma
    s2 = score_node(NodeScoreMeta(redundancy=r2, **base)).sigma
    assert s1 <= s2 + 1e-12


@given(age1=_age, age2=_age, r=_unit, inv=_inv)
def test_sigma_monotone_increasing_in_age(age1, age2, r, inv):
    if age1 > age2:
        age1, age2 = age2, age1
    base = dict(redundancy=r, invocation_count=inv, tier=EntrenchmentTier.PLAIN)
    s1 = score_node(NodeScoreMeta(age_days=age1, **base)).sigma
    s2 = score_node(NodeScoreMeta(age_days=age2, **base)).sigma
    assert s1 <= s2 + 1e-12


@given(r=_unit, age=_age, inv=_inv)
def test_sigma_monotone_decreasing_in_entrenchment(r, age, inv):
    # 더 entrenched tier일수록 σ는 같거나 낮다 (truth-guard 보호)
    low = score_node(
        NodeScoreMeta(redundancy=r, age_days=age, invocation_count=inv, tier=EntrenchmentTier.PLAIN)
    ).sigma
    high = score_node(
        NodeScoreMeta(
            redundancy=r, age_days=age, invocation_count=inv, tier=EntrenchmentTier.PRINCIPLE
        )
    ).sigma
    assert high <= low + 1e-12


# ── config 검증 ───────────────────────────────────────────────────────────────


def test_config_rejects_bad_halflife():
    with pytest.raises(ValueError):
        ScoringConfig(halflife_days=0.0)


def test_config_rejects_inverted_thresholds():
    with pytest.raises(ValueError):
        ScoringConfig(theta_keep=0.9, theta_supersede=0.3)


def test_meta_rejects_out_of_range_redundancy():
    with pytest.raises(ValueError):
        NodeScoreMeta(redundancy=1.5, age_days=1, invocation_count=0)


def test_meta_rejects_negative_invocation():
    with pytest.raises(ValueError):
        NodeScoreMeta(redundancy=0.0, age_days=1, invocation_count=-1)
