"""anti_unify TDD — Plotkin LGG (code backend) + 가드 (over-general/Rule of Three/구조불일치).

# KG: consensus-eureka-academic-grounding-2026-05-26 (C5 anti-unification, Plotkin 1970)
"""

from __future__ import annotations

from engine.eureka.anti_unify import anti_unify, propose_template, tokenize


def test_lgg_keeps_common_holes_diff():
    # 3 클론: 공통 구조 + 1 위치만 다름
    seqs = [tokenize("x = foo ( 1 )"), tokenize("x = foo ( 2 )"), tokenize("x = foo ( 3 )")]
    lgg = anti_unify(seqs)
    assert lgg is not None and lgg.aligned
    assert lgg.holes == 1  # 숫자 위치만 변수
    assert lgg.over_general is False
    assert lgg.template[:4] == ["x", "=", "foo", "("]
    assert lgg.template[4].startswith("·")


def test_lgg_structural_mismatch_returns_none():
    seqs = [tokenize("a = 1"), tokenize("a = foo ( 1 )")]  # 길이 다름
    assert anti_unify(seqs) is None


def test_lgg_over_general_flagged():
    # 거의 다 다름 → hole_ratio > 0.5
    seqs = [tokenize("a b c d"), tokenize("e f g h"), tokenize("i j k l")]
    lgg = anti_unify(seqs)
    assert lgg.hole_ratio == 1.0
    assert lgg.over_general is True


def test_propose_rule_of_three():
    r = propose_template(["x = f ( 1 )", "x = f ( 2 )"], min_instances=3)
    assert r["status"] == "INSUFFICIENT"


def test_propose_emits_template():
    r = propose_template(["x = f ( 1 )", "x = f ( 2 )", "x = f ( 3 )"])
    assert r["status"] == "PROPOSED"
    assert "·0" in r["template"]
    assert r["holes"] == 1
    assert "하데스" in r["note"]  # materialize 경계 명시


def test_propose_rejects_over_general():
    r = propose_template(["a b c", "d e f", "g h i"])
    assert r["status"] == "REJECTED"
    assert "over-generalization" in r["reason"]


def test_propose_rejects_structural_mismatch():
    r = propose_template(["a = 1", "a = foo ( 1 )", "a = 2"])
    assert r["status"] == "REJECTED"
    assert "구조" in r["reason"]
