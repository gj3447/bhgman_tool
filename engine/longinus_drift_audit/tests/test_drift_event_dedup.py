"""Regression: drift events dedup to one-per-file (path, kind).

Guards lesson-longinus-audit-sourceid-vs-name-pk-drift-inflation-2026-05-26:
a single drifted file cited by N concept-nodes (shared sourceId corpus label)
must report as 1 drift, not N.
"""

from __future__ import annotations

from audit_runner import _dedup_drift_events_by_file
from models import SourceCodeDriftEvent


def _ev(name: str, ref_site: str, path: str, kind: str = "SHA256_MISMATCH") -> SourceCodeDriftEvent:
    return SourceCodeDriftEvent(name=name, ref_site=ref_site, path=path, kind=kind)


def test_collapses_n_nodes_one_file_to_single_event():
    # 277 concept-nodes (distinct names) all citing one file with one corpus label
    events = [
        _ev(f"drift-canon-{i}", "mind-metahumotonic-canon", "METAHUMOTONIC/x.md")
        for i in range(277)
    ]
    out = _dedup_drift_events_by_file(events)
    assert len(out) == 1
    assert out[0].path == "METAHUMOTONIC/x.md"


def test_distinct_files_preserved():
    events = [
        _ev("d1", "label-a", "a.md"),
        _ev("d2", "label-b", "a.md"),  # same file, different sourceId label -> still 1
        _ev("d3", "label-c", "b.md"),
    ]
    out = _dedup_drift_events_by_file(events)
    assert {e.path for e in out} == {"a.md", "b.md"}
    assert len(out) == 2


def test_same_file_different_kind_kept_separate():
    events = [
        _ev("d1", "x", "a.md", kind="SHA256_MISMATCH"),
        _ev("d2", "x", "a.md", kind="FILE_MISSING"),
    ]
    out = _dedup_drift_events_by_file(events)
    assert len(out) == 2


def test_empty():
    assert _dedup_drift_events_by_file([]) == []
