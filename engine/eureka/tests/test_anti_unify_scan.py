"""scan_fragments — the missing PRODUCER for the Plotkin-LGG anti-unifier.

``anti_unify`` + ``propose_template`` are built and tested, but stranded: nothing SCANS a
corpus to find structurally-similar fragment families and propose templates. The Red artifact
(test-first): ``scan_fragments`` groups fragments by structural skeleton (literal values
wildcarded, identifiers/operators kept) and PROPOSEs one LGG template per Rule-of-Three family
— PROPOSE-only (materialize is hades' job). RED until ``scan_fragments`` exists.

# KG: eureka-canonical-2026-05-26
"""

from __future__ import annotations

from engine.eureka.anti_unify import scan_fragments


def test_empty_corpus_proposes_nothing():
    assert scan_fragments([]) == []


def test_rule_of_three_family_proposes_one_template():
    corpus = ["f(1)", "f(2)", "f(3)", "return x"]  # 3 similar calls + 1 unrelated line
    proposals = scan_fragments(corpus)
    assert len(proposals) == 1
    p = proposals[0]
    assert p["status"] == "PROPOSED"
    assert p["holes"] == 1
    assert p["hole_ratio"] == 0.25  # 1 hole / 4 tokens
    assert p["instances"] == 3


def test_below_rule_of_three_proposes_nothing():
    assert scan_fragments(["f(1)", "f(2)"]) == []  # only 2 instances


def test_over_general_family_is_not_proposed():
    # every position varies => hole_ratio 1.0 > 0.5 => REJECTED, dropped from PROPOSE output.
    assert scan_fragments(["1 2", "3 4", "5 6"]) == []


def test_two_distinct_families_each_propose():
    corpus = ["f(1)", "f(2)", "f(3)", "g(7)", "g(8)", "g(9)"]
    proposals = scan_fragments(corpus)
    assert len(proposals) == 2
    assert all(p["status"] == "PROPOSED" and p["holes"] == 1 for p in proposals)
