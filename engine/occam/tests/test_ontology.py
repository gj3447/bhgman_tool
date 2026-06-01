"""오캄 온톨로지 DL 정합성 엔진 테스트 — 6종 위반 탐지 + scored 위생.

# KG: verdict-user-occam-gains-ontology-hygiene-responsibility-2026-05-27,
#     occam-pass-ontology-layer-hygiene-2026-05-27
"""

from __future__ import annotations

from engine.occam.ontology import (
    OntologyClassRecord,
    OntologyInstanceRecord,
    ViolationKind,
    ontology_pass,
)
from engine.occam.scoring import EntrenchmentTier, Verdict


def _cls(name, parents=(), disjoint=(), **kw):
    return OntologyClassRecord(
        name=name, parents=tuple(parents), disjoint_with=tuple(disjoint), **kw
    )


def _kinds(report):
    return {v.kind for v in report.violations}


# ── clean ontology ────────────────────────────────────────────────────────────


def test_clean_ontology_is_consistent_no_violations():
    classes = [
        _cls("Animal"),
        _cls("Dog", parents=["Animal"]),
        _cls("Cat", parents=["Animal"]),
    ]
    instances = [OntologyInstanceRecord("Rex", types=("Dog",))]
    r = ontology_pass(classes, instances)
    assert r.violation_count == 0
    assert r.is_consistent
    assert r.scanned_classes == 3
    assert r.scanned_instances == 1


# ── 1. subsumption cycle ──────────────────────────────────────────────────────


def test_subclass_cycle_detected_and_inconsistent():
    classes = [
        _cls("A", parents=["B"]),
        _cls("B", parents=["C"]),
        _cls("C", parents=["A"]),  # A ⊑ B ⊑ C ⊑ A
    ]
    r = ontology_pass(classes)
    assert ViolationKind.SUBSUMPTION_CYCLE in _kinds(r)
    assert not r.is_consistent
    cyc = [v for v in r.violations if v.kind == ViolationKind.SUBSUMPTION_CYCLE][0]
    assert set(cyc.witnesses) == {"A", "B", "C"}


def test_self_loop_subclass_is_cycle():
    r = ontology_pass([_cls("X", parents=["X"])])
    assert ViolationKind.SUBSUMPTION_CYCLE in _kinds(r)


def test_dag_no_cycle():
    classes = [_cls("A"), _cls("B", parents=["A"]), _cls("C", parents=["A", "B"])]
    r = ontology_pass(classes)
    assert ViolationKind.SUBSUMPTION_CYCLE not in _kinds(r)
    assert r.is_consistent


# ── 2/3. dangling parent / type (무결성 경고, 정합성과 분리) ──────────────────


def test_dangling_parent_flagged_but_not_inconsistency():
    r = ontology_pass([_cls("Dog", parents=["Ghost"])])
    assert ViolationKind.DANGLING_PARENT in _kinds(r)
    assert r.is_consistent  # 무결성 경고지 논리 비정합 아님


def test_dangling_type_flagged():
    r = ontology_pass(
        [_cls("Dog")],
        [OntologyInstanceRecord("Rex", types=("Phantom",))],
    )
    assert ViolationKind.DANGLING_TYPE in _kinds(r)
    assert r.is_consistent


# ── 4. punning (class ∧ instance 동명) ────────────────────────────────────────


def test_punning_detected():
    r = ontology_pass(
        [_cls("Eagle")],
        [OntologyInstanceRecord("Eagle", types=())],
    )
    assert ViolationKind.PUNNING in _kinds(r)
    pun = [v for v in r.violations if v.kind == ViolationKind.PUNNING][0]
    assert pun.subject == "Eagle"


# ── 5. unsatisfiable class (disjoint 상위 둘) ─────────────────────────────────


def test_unsatisfiable_class_subclass_of_two_disjoint():
    classes = [
        _cls("Plant", disjoint=["Animal"]),
        _cls("Animal", disjoint=["Plant"]),
        _cls("PlantAnimal", parents=["Plant", "Animal"]),  # ⊥
    ]
    r = ontology_pass(classes)
    assert ViolationKind.UNSATISFIABLE_CLASS in _kinds(r)
    assert not r.is_consistent
    unsat = [v for v in r.violations if v.kind == ViolationKind.UNSATISFIABLE_CLASS][0]
    assert unsat.subject == "PlantAnimal"
    assert set(unsat.witnesses) == {"Plant", "Animal"}


def test_unsatisfiable_via_transitive_ancestors():
    # 손자 클래스가 transitive하게 두 disjoint 상위를 물려받음
    classes = [
        _cls("Plant", disjoint=["Animal"]),
        _cls("Animal", disjoint=["Plant"]),
        _cls("Flora", parents=["Plant"]),
        _cls("Fauna", parents=["Animal"]),
        _cls("Chimera", parents=["Flora", "Fauna"]),  # ⊥ via ancestors
    ]
    r = ontology_pass(classes)
    unsat = {v.subject for v in r.violations if v.kind == ViolationKind.UNSATISFIABLE_CLASS}
    assert "Chimera" in unsat
    assert not r.is_consistent


def test_disjoint_siblings_alone_are_satisfiable():
    # disjoint한 두 클래스 자체는 satisfiable (공통 하위만 ⊥)
    classes = [_cls("Plant", disjoint=["Animal"]), _cls("Animal", disjoint=["Plant"])]
    r = ontology_pass(classes)
    assert ViolationKind.UNSATISFIABLE_CLASS not in _kinds(r)
    assert r.is_consistent


# ── 6. disjointness violation (instance가 두 disjoint type) ───────────────────


def test_instance_typed_to_disjoint_classes():
    classes = [_cls("Plant", disjoint=["Animal"]), _cls("Animal", disjoint=["Plant"])]
    inst = [OntologyInstanceRecord("Weird", types=("Plant", "Animal"))]
    r = ontology_pass(classes, inst)
    assert ViolationKind.DISJOINTNESS_VIOLATION in _kinds(r)
    assert not r.is_consistent


def test_instance_disjoint_via_ancestors():
    classes = [
        _cls("Plant", disjoint=["Animal"]),
        _cls("Animal", disjoint=["Plant"]),
        _cls("Rose", parents=["Plant"]),
        _cls("Dog", parents=["Animal"]),
    ]
    inst = [OntologyInstanceRecord("Mix", types=("Rose", "Dog"))]
    r = ontology_pass(classes, inst)
    assert ViolationKind.DISJOINTNESS_VIOLATION in _kinds(r)


# ── 위생 scoring (covenant: 삭제 0, twin 없으면 flag) ──────────────────────────


def test_low_tier_stale_redundant_class_becomes_supersession_candidate():
    # 낮은 entrenchment(FINDING, e=0.3) + 완전중복 + 오래됨 → σ = 1·(1−0.3) = 0.7 → SUPERSEDE.
    classes = [
        _cls("Current"),
        _cls(
            "OldDup",
            parents=["Current"],
            age_days=3650,
            invocation_count=0,
            tier=EntrenchmentTier.FINDING,
            redundancy=1.0,
            has_successor=True,
        ),
    ]
    r = ontology_pass(classes)
    names = {n for n, _ in r.supersession_candidates}
    assert "OldDup" in names
    sc = dict(r.supersession_candidates)["OldDup"]
    assert sc.verdict == Verdict.SUPERSEDE
    assert sc.sigma >= 0.7


def test_ontology_class_tier_caps_at_verify_never_auto_supersede():
    # ONTOLOGY_CLASS(e=0.7): 완전 stale·중복이어도 σ 최대 0.3 → 절대 자동삭제 안 됨, VERIFY로.
    # 의도된 보수성 — 온톨로지 클래스는 entrenched, 나생문 gate 거쳐야 (covenant 마구잡이 금지).
    classes = [
        _cls("Current"),
        _cls(
            "EntrenchedDup",
            parents=["Current"],
            age_days=3650,
            invocation_count=0,
            tier=EntrenchmentTier.ONTOLOGY_CLASS,
            redundancy=1.0,
            has_successor=True,
        ),
    ]
    r = ontology_pass(classes)
    assert not r.supersession_candidates  # auto-supersede 0
    flagged = dict(r.flagged)
    assert "EntrenchedDup" in flagged
    assert flagged["EntrenchedDup"].verdict == Verdict.VERIFY
    assert flagged["EntrenchedDup"].sigma <= 0.3 + 1e-9  # σ 상한 1·(1−0.7), float 반올림 허용


def test_stale_class_without_successor_is_flagged_not_superseded():
    classes = [
        _cls(
            "OrphanOld",
            age_days=3650,
            invocation_count=0,
            tier=EntrenchmentTier.ONTOLOGY_CLASS,
            redundancy=1.0,
            has_successor=False,
        ),
    ]
    r = ontology_pass(classes)
    assert not r.supersession_candidates  # supersede 안 함 (machloket)
    flagged = {n for n, _ in r.flagged}
    assert "OrphanOld" in flagged
    assert dict(r.flagged)["OrphanOld"].verdict == Verdict.FLAG_ONLY


def test_canonical_tier_class_never_superseded_even_if_stale():
    classes = [
        _cls(
            "AncientCanon",
            age_days=99999,
            invocation_count=0,
            tier=EntrenchmentTier.CANONICAL,
            redundancy=1.0,
            has_successor=True,
        ),
    ]
    r = ontology_pass(classes)
    assert not r.supersession_candidates
    assert not r.flagged  # PROTECTED는 보고 안 함 (near-clean)


def test_fresh_active_class_not_in_hygiene():
    classes = [_cls("Live", invocation_count=20, age_days=1.0)]
    r = ontology_pass(classes)
    assert not r.supersession_candidates
    assert not r.flagged


def test_already_superseded_skipped():
    classes = [_cls("Done", status="SUPERSEDED", redundancy=1.0, age_days=9999, invocation_count=0)]
    r = ontology_pass(classes)
    assert not r.supersession_candidates
    assert not r.flagged


# ── covenant: 보고서에 delete 표현 부재 ───────────────────────────────────────


def test_report_has_no_delete_surface():
    r = ontology_pass([_cls("A")])
    assert not hasattr(r, "deleted")
    assert any("no delete" in n for n in r.notes)
