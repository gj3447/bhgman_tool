from __future__ import annotations

import ged_metric
from models import CodeSymbol, KgRefRecord


def _sym(name, line, refs):
    return CodeSymbol(
        sourcePath=f"x.py:{line}", name=name, kind="function", kg_refs=list(refs)
    )


class TestGED:
    def test_perfect_match_zero_drift(self):
        kg = {"a": KgRefRecord(sourceId="a", sourcePath="x.py:1")}
        syms = [_sym("a", 1, ["a"])]
        rep = ged_metric.compute_ged(kg_refs=kg, code_symbols=syms)
        assert rep.ged_total == 0
        assert rep.normalized_score == 0.0

    def test_insertion_in_kg_only(self):
        kg = {
            "a": KgRefRecord(sourceId="a", sourcePath="x.py:1"),
            "b": KgRefRecord(sourceId="b", sourcePath="x.py:2"),
        }
        syms = [_sym("a", 1, ["a"])]
        rep = ged_metric.compute_ged(kg_refs=kg, code_symbols=syms)
        assert rep.insertions == 1
        assert rep.ged_total == 1

    def test_deletion_in_code_only(self):
        kg = {"a": KgRefRecord(sourceId="a", sourcePath="x.py:1")}
        syms = [_sym("a", 1, ["a", "code-only"])]
        rep = ged_metric.compute_ged(kg_refs=kg, code_symbols=syms)
        assert rep.deletions == 1
        assert rep.ged_total == 1

    def test_relabel(self):
        kg = {"a": KgRefRecord(sourceId="a", sourcePath="x.py:99")}  # different path
        syms = [_sym("a", 1, ["a"])]
        rep = ged_metric.compute_ged(kg_refs=kg, code_symbols=syms)
        assert rep.relabels == 1
        assert rep.ged_total == 1

    def test_normalized_score_capped(self):
        kg = {f"k{i}": KgRefRecord(sourceId=f"k{i}", sourcePath="x.py:1") for i in range(100)}
        syms = []
        rep = ged_metric.compute_ged(kg_refs=kg, code_symbols=syms)
        assert rep.normalized_score == 1.0

    def test_severity(self):
        assert ged_metric.drift_score_to_severity(0.0) == "PERFECT"
        assert ged_metric.drift_score_to_severity(0.02) == "EXCELLENT"
        assert ged_metric.drift_score_to_severity(0.1) == "ACCEPTABLE"
        assert ged_metric.drift_score_to_severity(0.2) == "DEGRADED"
        assert ged_metric.drift_score_to_severity(0.5) == "CRITICAL"
