"""오캄 end-to-end runner TDD — fetch → occam_pass → apply. dry-run 기본.

# KG: occam-pass-kg-wide-2026-05-27, occam-kam-canonical-2026-05-26
"""

from __future__ import annotations

from occam_runner import run_occam


class _Runner:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        return self.rows


_DUP_ROWS = [
    {"name": "old", "source_path": "bhgman_tool/x.py", "sha256": "o", "line_count": 10},
    {"name": "new", "source_path": "bhgman_tool/x.py", "sha256": "n", "line_count": 99},
]
_CLEAN_ROWS = [
    {"name": "solo", "source_path": "bhgman_tool/solo.py", "sha256": "s", "line_count": 50},
]


def test_run_occam_dry_run_detects_but_does_not_write():
    read = _Runner(_DUP_ROWS)
    write = _Runner()
    res = run_occam(read, write_cypher=write)  # apply defaults False
    assert res.report.superseded_count == 1
    assert res.apply_result.dry_run is True
    assert write.calls == []  # covenant


def test_run_occam_apply_writes_supersession():
    read = _Runner(_DUP_ROWS)
    write = _Runner()
    res = run_occam(read, write_cypher=write, apply=True)
    assert res.apply_result.applied_count == 1
    assert len(write.calls) == 1


def test_run_occam_clean_kg_no_candidates_no_write_even_with_apply():
    read = _Runner(_CLEAN_ROWS)
    write = _Runner()
    res = run_occam(read, write_cypher=write, apply=True)
    assert res.report.superseded_count == 0
    assert write.calls == []  # twin 없으면 손 안 댐 (GUARD)


def test_run_occam_scope_passed_to_fetch():
    read = _Runner(_CLEAN_ROWS)
    run_occam(read, scope="engine/occam")
    assert read.calls[0][1] == {"scope": "engine/occam"}
