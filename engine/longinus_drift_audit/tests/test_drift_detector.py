from __future__ import annotations

from engine.longinus_drift_audit import drift_detector
from engine.longinus_drift_audit.models import CodeSymbol, DriftType, KgRefRecord


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

    def test_ref_exists_predicate_clears_non_referencesite_anchor(self):
        # Anchor exists in KG but NOT as a ReferenceSite (e.g. a :Lesson node).
        # Default kg_refs-membership check false-flags it MISSING; a has_node-style
        # predicate clears it. Naesengmoon ensemble finding deeper refinement
        # (ac-bhgman-5f5a905-goodhart-self-audit-mock-zero-drift).
        syms = [_sym("foo", 1, kg_refs=["lesson-exists-as-non-refsite"])]
        kgs: dict = {}  # empty ReferenceSite snapshot
        # default predicate (membership) → flagged MISSING
        assert len(drift_detector.detect_missing(symbols=syms, kg_refs=kgs)) == 1
        # has_node-style predicate (node exists by name/sourceId) → cleared
        out = drift_detector.detect_missing(
            symbols=syms, kg_refs=kgs, ref_exists=lambda r: r == "lesson-exists-as-non-refsite"
        )
        assert out == []

    def test_ref_exists_memoized_one_query_per_unique_ref(self):
        # ac-bhgman-cd3eeaa-detect_missing-n-unmemoized-fullscan: 같은 hub ref가 여러 symbol에
        # 걸쳐 반복돼도 ref_exists는 *유니크 ref당 1회*만 호출돼야 (label-less full-scan 비용 절감).
        calls: list[str] = []

        def counting_exists(ref: str) -> bool:
            calls.append(ref)
            return True  # 전부 존재 → MISSING 0

        # hub-A가 3 symbol, hub-B가 2 symbol에서 반복 (총 5 occurrence, 2 unique).
        syms = [
            _sym("s1", 1, kg_refs=["hub-A", "hub-B"]),
            _sym("s2", 2, kg_refs=["hub-A"]),
            _sym("s3", 3, kg_refs=["hub-A", "hub-B"]),
        ]
        out = drift_detector.detect_missing(symbols=syms, kg_refs={}, ref_exists=counting_exists)
        assert out == []
        assert sorted(calls) == ["hub-A", "hub-B"]  # 5 occurrence → 2 query (memoized)


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


class TestSigMismatchStructural:
    """expected_signature → structural ast comparison (real PutGet drift)."""

    def test_added_param_is_drift(self):
        syms = [_sym("f", 1, kg_refs=["r"], sig="a, b")]
        kgs = {"r": KgRefRecord(sourceId="r", sourcePath="p", expected_signature="a")}
        out = drift_detector.detect_sig_mismatch(symbols=syms, kg_refs=kgs)
        assert len(out) == 1 and out[0].drift_type == DriftType.SIG_MISMATCH

    def test_annotation_change_is_drift(self):
        syms = [_sym("f", 1, kg_refs=["r"], sig="a: int")]
        kgs = {"r": KgRefRecord(sourceId="r", sourcePath="p", expected_signature="a: str")}
        out = drift_detector.detect_sig_mismatch(symbols=syms, kg_refs=kgs)
        assert len(out) == 1

    def test_whitespace_only_difference_is_not_drift(self):
        syms = [_sym("f", 1, kg_refs=["r"], sig="a:int ,  b")]
        kgs = {"r": KgRefRecord(sourceId="r", sourcePath="p", expected_signature="a: int, b")}
        out = drift_detector.detect_sig_mismatch(symbols=syms, kg_refs=kgs)
        assert out == []  # structurally identical

    def test_return_type_change_is_drift(self):
        syms = [_sym("f", 1, kg_refs=["r"], sig="a -> bool")]
        kgs = {"r": KgRefRecord(sourceId="r", sourcePath="p", expected_signature="a -> int")}
        out = drift_detector.detect_sig_mismatch(symbols=syms, kg_refs=kgs)
        assert len(out) == 1

    def test_parse_sig_is_memoized(self):
        """Repeated signature strings must not re-run ast.parse — the hot-path
        optimization (was 40k parses for 10 distinct signatures)."""
        drift_detector._parse_sig.cache_clear()
        for _ in range(50):
            drift_detector._parse_sig("a: int, b: str -> bool")
        info = drift_detector._parse_sig.cache_info()
        assert info.misses == 1  # parsed exactly once
        assert info.hits == 49  # other 49 served from cache
