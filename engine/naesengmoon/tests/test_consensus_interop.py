"""decorrelation.aggregate ↔ consensus.decide 상호운용 계약 (T1-1).

두 대수의 관계를 코드로 고정한다:
  1. naive thin-adapter 위임(vote_from_critic → decide)은 UNSOUND — CriticVerdict 는
     admissibility gate 가 요구하는 evidence(HR11)·executor/reviewer(D20)를 공급할 수 없어
     4개 정준 케이스 중 3개에서 verdict 가 갈라진다 (2026-07-15 falsifier 실측). 이 테스트가
     그 refutation 을 영구 고정 — 미래에 누가 aggregate 를 decide 로 맹목 재배선하면 여기가
     그 divergence 를 다시 들이댄다. 건전한 위임 = evidence/role plumbing 선행
     (OQ: q-naesengmoon-vote-evidence-plumbing).
  2. 두 대수는 보편 n_eff clean-PASS floor 를 공유한다 (자칭-oracle 면제 없음, T0-1) —
     floor drift 재발 시 여기서 RED.
  3. consensus 는 패키지 공개 표면이다 (죽은 자본 가시화).

# KG: naesengmoon-consensus-protocol-ncp1-2026-07-13, consensus-prom8-naesengmoon-decorrelation-2026-05-31
"""

from __future__ import annotations

from engine.naesengmoon.consensus import decide, vote_from_critic
from engine.naesengmoon.decorrelation import CriticKind, CriticVerdict, aggregate


def _o(lens: str, passed: bool) -> CriticVerdict:
    return CriticVerdict(lens, CriticKind.ORACLE, passed, "cypher")


def _j(lens: str, passed: bool, family: str = "fam") -> CriticVerdict:
    return CriticVerdict(lens, CriticKind.JUDGMENT, passed, family)


def test_naive_thin_adapter_delegation_diverges():
    """T1-1 refutation pin: bare CriticVerdict → Vote 위임은 aggregate 와 다른 verdict 를 낸다.

    이 테스트가 GREEN 인 한 'aggregate 를 decide 로 thin-adapter 위임' 제안은 사전 조건
    (evidence/role plumbing) 없이는 성립하지 않는다. 만약 언젠가 이 테스트가 RED 가 되면
    (두 대수가 bare input 에서 수렴하면) 그때가 위임을 재검토할 시점이다."""
    diverged = []
    for name, critics, rho in [
        ("lone_oracle_pass", [_o("cypher", True)], 0.0),
        ("oracle_plus_judgments", [_o("cypher", True), _j("a", True, "fa"), _j("b", True, "fb")], 0.0),
        ("correlated_judgments", [_j("a", True), _j("b", True), _j("c", True)], 0.85),
    ]:
        agg = aggregate(critics, rho=rho)
        dec = decide([vote_from_critic(c) for c in critics], rho=rho)
        if agg.verdict != dec.verdict:
            diverged.append(name)
    assert diverged == ["lone_oracle_pass", "oracle_plus_judgments", "correlated_judgments"], (
        f"divergence set changed: {diverged} — thin-adapter 전제가 바뀌었는지 재검토"
    )


def test_oracle_veto_agrees_across_algebras():
    """진짜 oracle FAIL 은 두 대수 모두에서 HARD GATE — 유일하게 항상 일치하는 케이스."""
    critics = [_o("cypher", False), _j("a", True)]
    assert aggregate(critics, rho=0.0).verdict == "FAIL"
    assert decide([vote_from_critic(c) for c in critics]).verdict == "FAIL"


def test_universal_floor_shared_by_both_algebras():
    """T0-1 floor 정렬: 단독 자칭 oracle 은 어느 대수에서도 clean PASS 를 mint 못 한다.

    decide 쪽은 evidence + 유효표를 갖춰 quorum 까지 도달시켜도 n_eff floor 가 cap 한다
    (consensus.py:331 'self-labeled ORACLE is not an exemption')."""
    from engine.naesengmoon.consensus import LensClass, Vote, VoteValue

    assert aggregate([_o("cypher", True)]).verdict == "CONDITIONAL_PASS"
    lone = Vote(
        lens="cypher", lens_class=LensClass.ORACLE, value=VoteValue.PASS,
        evidence=("recount matched",),
    )
    assert decide([lone]).verdict != "PASS"


def test_consensus_is_public_surface():
    """NCP-1 이 패키지 표면에서 import 가능 — 죽은 자본(미export) 상태 재발 방지."""
    import engine.naesengmoon as nm

    for sym in ("decide", "vote_from_critic", "Vote", "Policy", "ConsensusResult",
                "MIN_EFF_FOR_CLEAN_PASS"):
        assert hasattr(nm, sym), f"engine.naesengmoon.{sym} 미export"
        assert sym in nm.__all__
