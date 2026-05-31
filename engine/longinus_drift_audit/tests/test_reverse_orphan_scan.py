from __future__ import annotations

from engine.longinus_drift_audit import reverse_orphan_scan
from engine.longinus_drift_audit.models import CodeSymbol


def _sym(name, line, refs, kind="function"):
    return CodeSymbol(sourcePath=f"x.py:{line}", name=name, kind=kind, kg_refs=list(refs))


class TestReverseOrphan:
    def test_all_orphans_when_none_refed(self):
        syms = [_sym("a", 1, []), _sym("b", 2, [])]
        orphans = reverse_orphan_scan.scan_reverse_orphans(symbols=syms)
        assert len(orphans) == 2

    def test_no_orphans_when_all_refed(self):
        syms = [_sym("a", 1, ["x"]), _sym("b", 2, ["y"])]
        orphans = reverse_orphan_scan.scan_reverse_orphans(symbols=syms)
        assert orphans == []

    def test_mixed(self):
        syms = [_sym("a", 1, ["x"]), _sym("b", 2, [])]
        orphans = reverse_orphan_scan.scan_reverse_orphans(symbols=syms)
        assert orphans == ["x.py:2"]

    def test_skip_kinds(self):
        syms = [_sym("a", 1, [], kind="module"), _sym("b", 2, [], kind="function")]
        orphans = reverse_orphan_scan.scan_reverse_orphans(symbols=syms, skip_kinds={"module"})
        assert orphans == ["x.py:2"]


class TestRatio:
    def test_zero_total(self):
        assert reverse_orphan_scan.reverse_orphan_ratio(total_symbols=0, orphan_count=0) == 0.0

    def test_half(self):
        r = reverse_orphan_scan.reverse_orphan_ratio(total_symbols=10, orphan_count=5)
        assert r == 0.5

    def test_full_blind(self):
        r = reverse_orphan_scan.reverse_orphan_ratio(total_symbols=10, orphan_count=10)
        assert r == 1.0
