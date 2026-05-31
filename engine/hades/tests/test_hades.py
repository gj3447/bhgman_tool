"""하데스 TDD — 실현(realize) 가드: ACCEPTED만 / reversible / ≤5 site / dry-run 기본.

# KG: hades-canonical-2026-05-27, consensus-eureka-engine-impl-2026-05-26 (c6 danger)
"""

from __future__ import annotations

from engine.hades.hades import realize_code_template, realize_kg_abstraction
from engine.hades.hades_models import RealizeStatus


def test_kg_realize_refuses_provisional():
    v = realize_kg_abstraction("c", "PROVISIONAL", ["a", "b", "c"])
    assert v.status == RealizeStatus.REFUSED
    assert "ACCEPTED만" in v.reason


def test_kg_realize_refuses_rejected():
    v = realize_kg_abstraction("c", "REJECTED", ["a", "b"])
    assert v.status == RealizeStatus.REFUSED


def test_kg_realize_accepted_plans_dry_run():
    v = realize_kg_abstraction("c", "ACCEPTED", ["a", "b", "c"])
    assert v.status == RealizeStatus.PLANNED  # dry-run 기본, apply 안 함
    assert v.applied is False
    assert v.plan is not None and v.plan.reversible
    assert v.plan.undo  # reversibility-first
    assert any("INSTANCE_OF" in op for op in v.plan.operations)


def test_kg_realize_applies_when_not_dry_run():
    calls = []

    def fake_apply(q, p):
        calls.append((q, p))
        return []

    v = realize_kg_abstraction("c", "ACCEPTED", ["a", "b"], dry_run=False, apply_cypher=fake_apply)
    assert v.status == RealizeStatus.APPLIED
    assert v.applied is True
    assert len(calls) == 2  # MERGE concept + INSTANCE_OF


def test_kg_realize_empty_extent_refused():
    v = realize_kg_abstraction("c", "ACCEPTED", [])
    assert v.status == RealizeStatus.REFUSED


def test_kg_realize_uses_parameterized_cypher_no_injection():
    # concept_name이 cypher 문자열에 직접 박히지 않는다 ($concept 파라미터).
    calls = []

    def fake_apply(q, p):
        calls.append((q, p))
        return []

    name = "ac'; MATCH (n) DETACH DELETE n //"  # injection 시도용 악성 이름
    v = realize_kg_abstraction(name, "ACCEPTED", ["a", "b"], dry_run=False, apply_cypher=fake_apply)
    assert v.status == RealizeStatus.APPLIED
    # 악성 이름이 cypher 본문에 들어가지 않고 params로만 전달돼야 한다.
    for q, p in calls:
        assert name not in q
        assert "DETACH DELETE" not in q
        assert p.get("concept") == name


def test_kg_realize_instance_of_binds_named_abstractclass_not_anonymous():
    # op1이 AbstractClass를 재-MATCH해서 같은 노드에 INSTANCE_OF를 건다 (익명 (a) 버그 회귀 방지).
    v = realize_kg_abstraction("my-concept", "ACCEPTED", ["x", "y"])
    instance_op = next(op for op in v.plan.operations if "INSTANCE_OF" in op)
    assert "MATCH (a:AbstractClass {name:$concept})" in instance_op
    # undo도 named AbstractClass로 한정 (전역 INSTANCE_OF 삭제 금지).
    assert all("$concept" in u for u in v.plan.undo)


def test_code_realize_refuses_over_max_sites():
    v = realize_code_template("c", "tmpl", [f"s{i}" for i in range(6)], max_sites=5)
    assert v.status == RealizeStatus.REFUSED
    assert "점진 rollout 초과" in v.reason


def test_code_realize_plans_dry_run_only():
    v = realize_code_template("c", "x = f ( ·0 )", ["site1", "site2", "site3"])
    assert v.status == RealizeStatus.PLANNED  # 코드는 항상 dry-run
    assert v.plan.reversible and v.plan.undo
    assert "characterization test" in v.reason
