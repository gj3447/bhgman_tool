"""오캄 escalation TDD — '불certainty면 자동 escalation' 게이트.

비판 #4: orphan / MEDIUM-confidence / VERIFY-verdict / semantic-dup 를 flag/report로만
두지 말고 나생문(/tlb)·Longinus audit 로 명시 routing. HIGH-confidence SUPERSEDE 는
escalation 없이 통과(자동 supersede 안전).

# KG: occam-kam-canonical-2026-05-26, verdict-user-occam-gains-ontology-hygiene-responsibility-2026-05-27
"""

from __future__ import annotations

from engine.occam.escalation import (
    TARGET_LONGINUS,
    TARGET_NAESENGMOON,
    build_escalation_plan,
)
from engine.occam.occam_models import (
    Confidence,
    NodeRecord,
    OccamReport,
    SupersessionCandidate,
)
from engine.occam.semantic_dedup import NearDupPair


def _cand(name, *, confidence, verdict=None):
    stale = NodeRecord(name, f"bhgman_tool/{name}.py", "sha_stale", 10)
    current = NodeRecord(f"{name}_cur", f"bhgman_tool/{name}.py", "sha_cur", 20)
    return SupersessionCandidate(
        stale=stale,
        current=current,
        normalized_path=f"{name}.py",
        reason="dup",
        confidence=confidence,
        verdict=verdict,
    )


def test_exact_duplicate_is_escalated_not_silently_dropped():
    """Tier-3: apply 가 REFUSE 하는 exact-dup(동일 sourcePath+sha256)은 indistinguishable —
    여태 is_confident_supersede 가 same-sha 만 보고 True 를 반환해 escalation 에서도 skip →
    apply·escalation 어디에도 안 가고 notes 로만 사라졌다. disk-truth 가 HIGH 로 current 를
    확정해도 두 동일 KG 노드는 못 가르므로, 확신이 아니라 escalate 돼야(silent drop 금지)."""
    stale = NodeRecord("dup", "bhgman_tool/dup.py", "same_sha", 10)
    current = NodeRecord("dup_twin", "bhgman_tool/dup.py", "same_sha", 10)
    cand = SupersessionCandidate(
        stale=stale,
        current=current,
        normalized_path="dup.py",
        reason="exact duplicate node (identical sha) — redundant",
        confidence=Confidence.HIGH,  # disk-truth 확정이어도 KG-노드 중복은 못 가름
        verdict=None,
    )
    plan = build_escalation_plan(OccamReport(candidates=(cand,)))
    assert any(
        i.subject == "dup" and i.target == TARGET_NAESENGMOON for i in plan.items
    ), "exact-dup 은 나생문으로 escalate 돼야 (silent drop 금지)"


def test_high_confidence_supersede_does_not_escalate():
    # disk-sha 확정 + SUPERSEDE = 자동 supersede 안전, escalation 불필요
    report = OccamReport(candidates=(_cand("a", confidence=Confidence.HIGH, verdict="SUPERSEDE"),))
    plan = build_escalation_plan(report)
    assert plan.count == 0


def test_medium_confidence_candidate_escalates_to_naesengmoon():
    # disk truth 부재 → line-count 휴리스틱(MEDIUM) → 자동 supersede 전 나생문 검증
    report = OccamReport(candidates=(_cand("b", confidence=Confidence.MEDIUM),))
    plan = build_escalation_plan(report)
    assert plan.count == 1
    item = plan.items[0]
    assert item.target == TARGET_NAESENGMOON
    assert item.lens == "constitutional"
    assert "/tlb" in item.command


def test_verify_verdict_escalates_even_when_high_confidence():
    # σ 회색지대(VERIFY)면 confidence 무관하게 나생문 dispatch
    report = OccamReport(candidates=(_cand("c", confidence=Confidence.HIGH, verdict="VERIFY"),))
    plan = build_escalation_plan(report)
    assert plan.count == 1
    assert plan.items[0].target == TARGET_NAESENGMOON


def test_high_confidence_but_non_supersede_verdict_escalates():
    # disk가 current를 확정(HIGH)했지만 σ가 SUPERSEDE가 아니면(KEEP/VERIFY) 불일치 → escalate.
    report = OccamReport(candidates=(_cand("d", confidence=Confidence.HIGH, verdict="KEEP"),))
    plan = build_escalation_plan(report)
    assert plan.count == 1
    assert plan.items[0].target == TARGET_NAESENGMOON


def test_orphan_escalates_to_longinus():
    # disk-orphan = flag-only(machloket) → Longinus drift audit 로 '진짜 dead인지' 검증
    orphan = NodeRecord("ghost", "bhgman_tool/ghost.py", "sha_g", 5)
    report = OccamReport(orphans=(orphan,))
    plan = build_escalation_plan(report)
    assert plan.count == 1
    item = plan.items[0]
    assert item.target == TARGET_LONGINUS
    assert "ghost" in item.subject


def test_semantic_pairs_escalate_to_naesengmoon_not_auto_supersede():
    # semantic near-dup 은 byte identity 없음 → 단독 supersede 금지, 나생문 검증 필수
    report = OccamReport()
    pairs = [NearDupPair(keep_id="keep1", drop_id="drop1", similarity=0.97)]
    plan = build_escalation_plan(report, semantic_pairs=pairs)
    assert plan.count == 1
    item = plan.items[0]
    assert item.target == TARGET_NAESENGMOON
    assert "drop1" in item.subject
    assert "0.97" in item.reason or "semantic" in item.reason.lower()


def test_mixed_report_routes_each_case_to_right_weapon():
    report = OccamReport(
        candidates=(
            _cand("safe", confidence=Confidence.HIGH, verdict="SUPERSEDE"),  # no escalation
            _cand("gray", confidence=Confidence.MEDIUM),  # → naesengmoon
        ),
        orphans=(NodeRecord("ghost", "bhgman_tool/ghost.py", "g", 5),),  # → longinus
    )
    plan = build_escalation_plan(report)
    targets = sorted(i.target for i in plan.items)
    assert targets == [TARGET_LONGINUS, TARGET_NAESENGMOON]
    assert "2" in plan.summary  # 2 escalations


def test_empty_report_empty_plan():
    plan = build_escalation_plan(OccamReport())
    assert plan.count == 0
    assert plan.items == ()
