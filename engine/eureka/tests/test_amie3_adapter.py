"""amie3 어댑터 TDD — Horn rule ↔ FormalConcept 변환 (순수, Java 불필요).

amie3.py(Java)는 triples→Horn rule. 어댑터가 eureka FormalConcept(extent/intent/stability)로 통일.
보수적: high-PCA rule만, body+head atom=intent, intent 만족 객체=extent. 어설픈 변환은
apophenia이므로 후속 oracle/fidelity gate가 차단(PROPOSE only).

# KG: eureka-canonical-2026-05-26, consensus-eureka-academic-grounding-2026-05-26 (AMIE3)
"""

from __future__ import annotations

from engine.eureka.amie3_adapter import (
    formal_context_to_triples,
    horn_rules_to_concepts,
    induce_via_amie3,
)
from engine.eureka.induction_operators.amie3 import Amie3Result, HornRule


def _rule(body, head, pca):
    return HornRule(
        body=body,
        head=head,
        head_coverage=0.5,
        std_confidence=pca,
        pca_confidence=pca,
        positive_examples=10,
        body_size=10,
        pca_body_size=10,
    )


_CONTEXT = {
    "Topology": frozenset({"AXIS:Math", "DOMAIN:Algebra"}),
    "Group Theory": frozenset({"AXIS:Math", "DOMAIN:Algebra"}),
    "Algebra": frozenset({"AXIS:Math", "DOMAIN:Algebra"}),
    "Parser": frozenset({"AXIS:Machine", "DOMAIN:Lowering"}),
}


# ── context → triples ───────────────────────────────────────────────────────


def test_context_to_triples_splits_predicate_value():
    triples = formal_context_to_triples({"Topology": frozenset({"AXIS:Math"})})
    assert ("Topology", "AXIS", "Math") in triples


def test_context_to_triples_bare_attr_uses_has_attr():
    triples = formal_context_to_triples({"X": frozenset({"plain"})})
    assert ("X", "HAS_ATTR", "plain") in triples


# ── Horn rules → concepts ─────────────────────────────────────────────────────


def test_horn_rule_becomes_concept_with_satisfying_extent():
    # rule atoms reconstruct attrs AXIS:Math + DOMAIN:Algebra → 3 math objects satisfy
    rules = [_rule("?x AXIS Math", "?x DOMAIN Algebra", pca=0.9)]
    res = horn_rules_to_concepts(rules, _CONTEXT, min_pca_confidence=0.5, min_extent=2)
    assert len(res.concepts) == 1
    c = res.concepts[0]
    assert c.extent == frozenset({"Topology", "Group Theory", "Algebra"})
    assert c.intent == frozenset({"AXIS:Math", "DOMAIN:Algebra"})
    assert c.stability == 0.9  # pca_confidence proxy


def test_low_pca_rule_filtered():
    rules = [_rule("?x AXIS Math", "?x DOMAIN Algebra", pca=0.2)]
    res = horn_rules_to_concepts(rules, _CONTEXT, min_pca_confidence=0.5)
    assert res.concepts == ()


def test_small_extent_filtered():
    # only Parser has AXIS:Machine → extent 1 < min_extent 2
    rules = [_rule("?x AXIS Machine", "?x DOMAIN Lowering", pca=0.9)]
    res = horn_rules_to_concepts(rules, _CONTEXT, min_extent=2)
    assert res.concepts == ()


def test_duplicate_concepts_deduped():
    rules = [
        _rule("?x AXIS Math", "?x DOMAIN Algebra", pca=0.9),
        _rule("?x DOMAIN Algebra", "?x AXIS Math", pca=0.8),  # same intent set
    ]
    res = horn_rules_to_concepts(rules, _CONTEXT)
    assert len(res.concepts) == 1


# ── induce_via_amie3 (injectable Java fn) ─────────────────────────────────────


def test_induce_via_amie3_injects_fake_runner():
    captured = {}

    def fake_amie3(triples, **kw):
        captured["triples"] = list(triples)
        return Amie3Result(
            rules=(_rule("?x AXIS Math", "?x DOMAIN Algebra", 0.9),),
            triples_input=len(captured["triples"]),
            raw_stdout_lines=(),
            elapsed_sec=0.0,
        )

    res = induce_via_amie3(_CONTEXT, amie3_fn=fake_amie3, min_pca_confidence=0.5)
    assert captured["triples"], "context must be converted to triples and passed"
    assert len(res.concepts) == 1
    assert res.fallback_reason is None
