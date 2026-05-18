"""Parallel ≡ sequential invariant — audit output must be byte-equal across both codepaths.

L1 (code_scanner.scan_root parallel=True/False) and L2 (LonginusAudit parallel=True/False)
must produce identical AuditReport fields (modulo non-deterministic fields:
audit_id / completed_at / *_detected_at / pierced_at / last_validated).

# KG: longinus-parallel-scan-2026-05-18
# KG: longinus-parallel-fanout-2026-05-18
"""

from __future__ import annotations

from pathlib import Path

import code_scanner
from audit_runner import LonginusAudit
from kg_client import MockKgClient
from models import KgRefRecord


def _seed_n_files(tmp: Path, n: int) -> None:
    """Generate n synthetic .py files with mixed KG refs (some valid, some missing,
    some orphan-inducing). Used to push past the parallel threshold."""
    for i in range(n):
        if i % 7 == 0:
            body = f"def f_{i}(x): pass\n"  # reverse orphan (no KG ref)
        elif i % 3 == 0:
            body = f"def f_{i}(x): pass  # KG: kg-ref-{i}\n"  # has KG ref
        else:
            body = (
                f"class C_{i}:  # KG: kg-class-{i}\n"
                f"    pass\n"
                f"def helper_{i}(): pass  # KG: kg-helper-{i}\n"
            )
        (tmp / f"mod_{i:04d}.py").write_text(body)


def _build_kg(n: int) -> MockKgClient:
    """KG matching ~half of generated refs. Triggers Missing/Orphan/clean mix."""
    refs = []
    for i in range(n):
        if i % 3 == 0 and i % 7 != 0:
            refs.append(KgRefRecord(sourceId=f"kg-ref-{i}", sourcePath=f"mod_{i:04d}.py:1"))
        elif i % 3 != 0 and i % 7 != 0:
            refs.append(KgRefRecord(sourceId=f"kg-class-{i}", sourcePath=f"mod_{i:04d}.py:1"))
            # Intentionally skip kg-helper-{i} every other time → Missing drift
            if i % 2 == 0:
                refs.append(KgRefRecord(sourceId=f"kg-helper-{i}", sourcePath=f"mod_{i:04d}.py:3"))
    # Inject KG-only refs → Orphan drift
    for i in range(10):
        refs.append(KgRefRecord(sourceId=f"orphan-only-kg-{i}", sourcePath="??:0"))
    return MockKgClient(refs=refs)


def _normalize_report(report) -> dict:
    """Strip non-deterministic fields for diff comparison."""
    d = report.model_dump(mode="json")
    d.pop("audit_id", None)
    d.pop("completed_at", None)
    for r in d.get("drift_records", []):
        r.pop("detected_at", None)
    for o in d.get("forward_orphans", []):
        o.pop("detected_at", None)
    for e in d.get("sha256_drift_events", []):
        e.pop("created_at", None)
    # Sort lists for stable comparison
    d["drift_records"] = sorted(
        d["drift_records"],
        key=lambda r: (r["drift_type"], r["sourceId"], r.get("sourcePath") or ""),
    )
    d["reverse_orphans"] = sorted(d["reverse_orphans"])
    d["forward_orphans"] = sorted(
        d["forward_orphans"], key=lambda r: (r["hub_name"], r["missing_field"])
    )
    return d


class TestL1ScanInvariant:
    """code_scanner.scan_root: parallel == sequential output."""

    def test_small_corpus_below_threshold(self, tmp_path):
        _seed_n_files(tmp_path, 20)  # < default 100 threshold
        syms_p, refs_p = code_scanner.scan_root(tmp_path, parallel=True)
        syms_s, refs_s = code_scanner.scan_root(tmp_path, parallel=False)
        assert [s.model_dump() for s in syms_p] == [s.model_dump() for s in syms_s]
        assert refs_p == refs_s

    def test_large_corpus_above_threshold(self, tmp_path):
        _seed_n_files(tmp_path, 150)  # > default 100 threshold → parallel codepath
        syms_p, refs_p = code_scanner.scan_root(tmp_path, parallel=True, threshold=100)
        syms_s, refs_s = code_scanner.scan_root(tmp_path, parallel=False)
        assert [s.model_dump() for s in syms_p] == [s.model_dump() for s in syms_s]
        assert refs_p == refs_s

    def test_force_parallel_low_threshold(self, tmp_path):
        _seed_n_files(tmp_path, 10)
        syms_p, refs_p = code_scanner.scan_root(tmp_path, parallel=True, threshold=1)
        syms_s, refs_s = code_scanner.scan_root(tmp_path, parallel=False)
        assert [s.model_dump() for s in syms_p] == [s.model_dump() for s in syms_s]
        assert refs_p == refs_s

    def test_threshold_keeps_sequential_codepath(self, tmp_path, monkeypatch):
        """Below threshold, ProcessPoolExecutor must NOT be invoked."""
        _seed_n_files(tmp_path, 50)
        invoked = {"count": 0}

        original = code_scanner.ProcessPoolExecutor

        class _SpyPool(original):  # type: ignore[misc, valid-type]
            def __init__(self, *a, **kw):
                invoked["count"] += 1
                super().__init__(*a, **kw)

        monkeypatch.setattr(code_scanner, "ProcessPoolExecutor", _SpyPool)
        code_scanner.scan_root(tmp_path, parallel=True, threshold=100)
        assert invoked["count"] == 0


class TestL2RunFullInvariant:
    """LonginusAudit.run_full: parallel == sequential."""

    def test_small_corpus(self, tmp_path):
        _seed_n_files(tmp_path, 30)
        report_p = LonginusAudit(kg=_build_kg(30), code_root=tmp_path, parallel=True).run_full()
        report_s = LonginusAudit(kg=_build_kg(30), code_root=tmp_path, parallel=False).run_full()
        assert _normalize_report(report_p) == _normalize_report(report_s)

    def test_large_corpus_above_threshold(self, tmp_path):
        _seed_n_files(tmp_path, 150)
        report_p = LonginusAudit(kg=_build_kg(150), code_root=tmp_path, parallel=True).run_full()
        report_s = LonginusAudit(kg=_build_kg(150), code_root=tmp_path, parallel=False).run_full()
        assert _normalize_report(report_p) == _normalize_report(report_s)

    def test_drift_counts_match(self, tmp_path):
        _seed_n_files(tmp_path, 50)
        rp = LonginusAudit(kg=_build_kg(50), code_root=tmp_path, parallel=True).run_full()
        rs = LonginusAudit(kg=_build_kg(50), code_root=tmp_path, parallel=False).run_full()
        assert rp.drifts_by_type == rs.drifts_by_type
        assert rp.ged_report.ged_total == rs.ged_report.ged_total
        assert rp.ged_report.normalized_score == rs.ged_report.normalized_score
        assert sorted(rp.reverse_orphans) == sorted(rs.reverse_orphans)
