from __future__ import annotations

import drift_detector
from models import CodeSymbol, DriftType, KgRefRecord


def _sym(name: str, line: int, *, kg_refs=None, sig="", kind="function") -> CodeSymbol:
    return CodeSymbol(
        sourcePath=f"src/{name}.py:{line}",
        name=name,
        kind=kind,
        signature=sig,
        kg_refs=list(kg_refs or []),
    )


def _kg(ref: str, path: str = "src/x.py:1", label: str = "") -> KgRefRecord:
    return KgRefRecord(sourceId=ref, sourcePath=path, label=label)


class TestMissing:
    def test_code_ref_not_in_kg(self):
        syms = [_sym("foo", 1, kg_refs=["lesson-missing-1"])]
        kgs = {"lesson-other-1": _kg("lesson-other-1")}
        out = drift_detector.detect_missing(symbols=syms, kg_refs=kgs)
        assert len(out) == 1
        assert out[0].drift_type == DriftType.MISSING
        assert out[0].lens_law_violated == "PutGet"

    def test_clean_no_missing(self):
        syms = [_sym("foo", 1, kg_refs=["lesson-x"])]
        kgs = {"lesson-x": _kg("lesson-x")}
        out = drift_detector.detect_missing(symbols=syms, kg_refs=kgs)
        assert out == []


class TestOrphan:
    def test_kg_ref_not_in_code(self):
        syms = [_sym("foo", 1, kg_refs=["lesson-x"])]
        kgs = {"lesson-x": _kg("lesson-x"), "lesson-orphan": _kg("lesson-orphan")}
        out = drift_detector.detect_orphan(symbols=syms, kg_refs=kgs)
        assert len(out) == 1
        assert out[0].sourceId == "lesson-orphan"
        assert out[0].lens_law_violated == "GetPut"

    def test_clean_no_orphans(self):
        syms = [_sym("foo", 1, kg_refs=["lesson-x", "lesson-y"])]
        kgs = {"lesson-x": _kg("lesson-x"), "lesson-y": _kg("lesson-y")}
        out = drift_detector.detect_orphan(symbols=syms, kg_refs=kgs)
        assert out == []


class TestSigMismatch:
    def test_label_not_in_signature(self):
        syms = [_sym("foo", 1, kg_refs=["lesson-x"], sig="x, y")]
        kgs = {"lesson-x": _kg("lesson-x", label="UNEXPECTED")}
        out = drift_detector.detect_sig_mismatch(symbols=syms, kg_refs=kgs)
        assert len(out) == 1
        assert out[0].drift_type == DriftType.SIG_MISMATCH

    def test_label_in_signature_ok(self):
        syms = [_sym("foo", 1, kg_refs=["lesson-x"], sig="x: int, y: str")]
        kgs = {"lesson-x": _kg("lesson-x", label="int")}
        out = drift_detector.detect_sig_mismatch(symbols=syms, kg_refs=kgs)
        assert out == []


class TestPatternDiv:
    def test_excessive_refs_triggers(self):
        syms = [
            _sym("a", 1, kg_refs=["shared-x"]),
            _sym("b", 1, kg_refs=["shared-x"]),
            _sym("c", 1, kg_refs=["shared-x"]),
            _sym("d", 1, kg_refs=["shared-x"]),  # 4 > threshold 3
        ]
        out = drift_detector.detect_pattern_div(symbols=syms)
        assert len(out) == 1
        assert out[0].drift_type == DriftType.PATTERN_DIV

    def test_low_count_no_pattern_div(self):
        syms = [_sym("a", 1, kg_refs=["x"]), _sym("b", 1, kg_refs=["x"])]
        out = drift_detector.detect_pattern_div(symbols=syms)
        assert out == []


class TestLabelRot:
    def test_label_unrelated_to_symbol(self):
        syms = [_sym("renamed_func", 1, kg_refs=["lesson-old-name"])]
        kgs = {
            "lesson-old-name": _kg("lesson-old-name", label="old_func"),
        }
        out = drift_detector.detect_label_rot(symbols=syms, kg_refs=kgs)
        assert len(out) == 1
        assert out[0].drift_type == DriftType.LABEL_ROT

    def test_label_substring_match_ok(self):
        syms = [_sym("calculate_score", 1, kg_refs=["lesson-x"])]
        kgs = {"lesson-x": _kg("lesson-x", label="calculate")}
        out = drift_detector.detect_label_rot(symbols=syms, kg_refs=kgs)
        assert out == []


class TestDetectAll:
    def test_summary_counts(self):
        syms = [
            _sym("a", 1, kg_refs=["missing-1"]),  # MISSING (KG 부재)
            _sym("b", 1, kg_refs=[]),  # no decl, no drift detected here
        ]
        kgs = {"orphan-1": _kg("orphan-1")}  # ORPHAN (코드 부재)
        out = drift_detector.detect_all(symbols=syms, kg_refs=kgs)
        summary = drift_detector.summarize_drifts(out)
        assert summary.get("Missing", 0) >= 1
        assert summary.get("Orphan", 0) >= 1
