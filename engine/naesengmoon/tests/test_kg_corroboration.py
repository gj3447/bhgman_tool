"""kg-corroboration oracle — the separate-source verdict leg (q-naesengmoon-single-authority).

Dep-free (no neo4j/LLM/torch): a LocalGroundingSource over an in-memory store of canonical facts.
"""

from __future__ import annotations

import types

from engine.agents.grounding import LocalGroundingSource
from engine.naesengmoon.decorrelation import CriticKind, CriticVerdict, aggregate
from engine.naesengmoon.kg_corroboration import kg_corroboration_oracle
from engine.naesengmoon.verify import verify


def _store(*nodes: dict):
    return types.SimpleNamespace(nodes=list(nodes))


def _lesson(text: str) -> dict:
    # 'claim' is one of grounding._TEXT_PROPS, so the GroundingSource actually indexes it.
    return {"labels": ["Lesson"], "props": {"name": "canon-lesson", "claim": text}}


_CONTRADICTED = "self-scoring counts as external verification"
# a canonical Lesson that directly NEGATES the claim (opposite polarity, high term overlap)
_CANON_NEGATION = _lesson("self-scoring is not external verification — it is derived-self")


def test_contradicting_canonical_fact_fails_corroboration():
    source = LocalGroundingSource(_store(_CANON_NEGATION))
    v = kg_corroboration_oracle(source).evaluate(_CONTRADICTED)
    assert isinstance(v, CriticVerdict)
    assert v.kind is CriticKind.ORACLE
    assert v.passed is False  # canon contradicts the claim → not corroborated


def test_consistent_claim_passes_corroboration():
    source = LocalGroundingSource(_store(_CANON_NEGATION))
    # same polarity as canon (both negated) → no contradiction
    v = kg_corroboration_oracle(source).evaluate("self-scoring is not external verification")
    assert v.passed is True


def test_claim_absent_from_canon_passes_by_abstention():
    source = LocalGroundingSource(_store(_lesson("the planning legion runs a contract DAG")))
    v = kg_corroboration_oracle(source).evaluate("octopuses have three hearts")
    assert v.passed is True  # canon is silent → abstain (no false contradiction)


def test_non_canonical_negation_does_not_veto():
    # a NON-canonical node (plain label) carrying the negation must NOT contradict — only
    # canon is authoritative (else any stray note could veto).
    plain = {"labels": ["Note"], "props": {"claim": "self-scoring is not external verification"}}
    source = LocalGroundingSource(_store(plain))
    assert kg_corroboration_oracle(source).evaluate(_CONTRADICTED).passed is True


def test_oracle_leg_vetoes_the_ensemble():
    # 3 same-model JUDGMENT critics all PASS, but the separate-source oracle contradicts →
    # oracle veto flips the ensemble to FAIL (this is the leg the ensemble previously lacked).
    source = LocalGroundingSource(_store(_CANON_NEGATION))
    oracle_leg = kg_corroboration_oracle(source).evaluate(_CONTRADICTED)
    judges = [
        CriticVerdict(lens=f"j{i}", kind=CriticKind.JUDGMENT, passed=True, model_family="same")
        for i in range(3)
    ]
    without = aggregate(judges)
    withleg = aggregate([*judges, oracle_leg])
    assert without.verdict != "FAIL"
    assert withleg.verdict == "FAIL"


def test_verify_kind_kg_corroborate():
    store = _store(_CANON_NEGATION)
    v = verify("kg-corroborate", _CONTRADICTED, kg=store)
    assert v.kind == "kg-corroborate"
    assert v.passed is False
    v_ok = verify("kg-corroborate", "self-scoring is not external verification", kg=store)
    assert v_ok.passed is True
