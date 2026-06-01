"""효능 하네스 + KG runner 테스트 — verdict 분기 + fake CypherRunner."""

from __future__ import annotations


from engine.efficacy.commanders import COMMANDERS, get_commander
from engine.efficacy.harness import run_efficacy
from engine.efficacy.kg_runner import evaluate_all, evaluate_commander
from engine.efficacy.models import (
    CommanderEfficacySpec,
    Direction,
    LabeledItem,
    Verdict,
)


def _spec(**kw):
    base = dict(
        commander="t", verb="v", task="t", metric="AUC", oracle_source="o",
        required_signal="s", expected_direction=Direction.HIGHER,
        circularity_keywords=("occam",), label_cypher="MATCH ...", known_falsifier="",
    )
    base.update(kw)
    return CommanderEfficacySpec(**base)


def _it(pos, sig, prov="manual"):
    return LabeledItem(item_id="x", is_positive=pos, signal=sig, provenance=prov)


def test_empty_items_unmeasurable():
    r = run_efficacy(_spec(), [])
    assert r.verdict == Verdict.UNMEASURABLE
    assert "oracle" in r.reason


def test_clean_separation_measured():
    items = [_it(True, 0.9) for _ in range(6)] + [_it(False, 0.1) for _ in range(6)]
    r = run_efficacy(_spec(), items)
    assert r.verdict == Verdict.MEASURED
    assert r.auc == 1.0
    assert r.baselines["random"] == 0.5


def test_circular_labels_unmeasurable():
    items = [_it(True, 0.9, "occam dup") for _ in range(6)] + [_it(False, 0.1) for _ in range(6)]
    r = run_efficacy(_spec(), items)
    assert r.verdict == Verdict.UNMEASURABLE
    assert "동어반복" in r.reason


def test_inverted_signal_unmeasurable():
    items = [_it(True, 0.0) for _ in range(8)] + [_it(False, 1.0) for _ in range(8)]
    r = run_efficacy(_spec(circularity_keywords=("z",)), items)
    assert r.verdict == Verdict.UNMEASURABLE
    assert "반대 방향" in r.reason


def test_passed_gate_but_chance_is_below_chance():
    # 게이트 통과(신호 있고 순환 아님)지만 AUC 정확히 0.5 → BELOW_CHANCE
    items = [_it(True, 0.5) for _ in range(6)] + [_it(False, 0.5) for _ in range(6)]
    r = run_efficacy(_spec(circularity_keywords=("z",)), items)
    assert r.verdict == Verdict.BELOW_CHANCE


# ── KG runner (fake CypherRunner) ─────────────────────────────────────────────


def test_runner_no_oracle_unmeasurable():
    spec = _spec(label_cypher=None, known_falsifier="외부 held-out 필요")
    r = evaluate_commander(spec, lambda q, p: [])
    assert r.verdict == Verdict.UNMEASURABLE
    assert "oracle 미구축" in r.reason


def test_runner_small_sample_unmeasurable():
    spec = _spec(circularity_keywords=("z",))
    rows = [{"item_id": "a", "is_positive": True, "signal": 0.9, "provenance": "m"},
            {"item_id": "b", "is_positive": False, "signal": 0.1, "provenance": "m"}]
    r = evaluate_commander(spec, lambda q, p: rows)
    assert r.verdict == Verdict.UNMEASURABLE
    assert "소표본" in r.reason


def test_runner_circular_rows_unmeasurable():
    rows = ([{"item_id": f"p{i}", "is_positive": True, "signal": 1.0, "provenance": "occam dup"}
             for i in range(6)]
            + [{"item_id": f"n{i}", "is_positive": False, "signal": 0.0, "provenance": "x"}
               for i in range(6)])
    r = evaluate_commander(_spec(), lambda q, p: rows)
    assert r.verdict == Verdict.UNMEASURABLE


def test_runner_clean_rows_measured():
    rows = ([{"item_id": f"p{i}", "is_positive": True, "signal": 0.9, "provenance": "manual"}
             for i in range(6)]
            + [{"item_id": f"n{i}", "is_positive": False, "signal": 0.1, "provenance": "manual"}
               for i in range(6)])
    r = evaluate_commander(_spec(circularity_keywords=("z",)), lambda q, p: rows)
    assert r.verdict == Verdict.MEASURED
    assert r.auc == 1.0


def test_runner_null_signal_rows_handled():
    rows = [{"item_id": "a", "is_positive": True, "signal": None, "provenance": ""}]
    r = evaluate_commander(_spec(circularity_keywords=("z",)), lambda q, p: rows)
    # n<10 이거나 신호부재 — 어느 쪽이든 UNMEASURABLE
    assert r.verdict == Verdict.UNMEASURABLE


# ── registry ──────────────────────────────────────────────────────────────────


def test_seven_commanders_registered():
    names = {c.commander for c in COMMANDERS}
    assert names == {"occam", "longinus", "prometheus", "eureka", "naesengmoon", "jaebaeman", "hades"}


def test_only_occam_longinus_have_cypher():
    with_cypher = {c.commander for c in COMMANDERS if c.label_cypher is not None}
    assert with_cypher == {"occam", "longinus"}


def test_evaluate_all_returns_seven():
    results = evaluate_all(lambda q, p: [])
    assert len(results) == 7
    # label_cypher 없는 5는 oracle 미구축, occam/longinus는 빈 fetch → UNMEASURABLE
    assert all(r.verdict == Verdict.UNMEASURABLE for r in results)


def test_get_commander():
    assert get_commander("occam").verb == "정리"
    assert get_commander("nonexistent") is None
