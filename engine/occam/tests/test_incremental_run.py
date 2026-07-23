"""오캄 증분 실행 테스트 — PROM 6 C7 / A2.

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A2-2026-07-19
"""

from __future__ import annotations

from engine.occam.incremental import (
    advance_watermark,
    read_watermark,
    run_incremental,
)


class _Dispatch:
    """cypher 내용으로 canned 응답 라우팅하는 fake runner."""

    def __init__(self, *, wm=0, mx=None, delta_rows=None):
        self.wm = wm
        self.mx = mx
        self.delta_rows = delta_rows or []
        self.writes = []

    def __call__(self, cypher, params=None):
        if "OccamCheckpoint" in cypher and "MERGE" in cypher:
            return [{"wm": self.wm}]
        if "max(s.updatedAt)" in cypher:
            return [{"mx": self.mx}]
        if "SET c.watermark" in cypher:
            self.writes.append(params)
            return [{"wm": params["wm"]}]
        if "RETURN s.name AS name" in cypher:  # fetch_cypher_since
            return self.delta_rows
        return []


def test_read_and_advance_watermark():
    r = _Dispatch(wm=42)
    assert read_watermark(r) == 42
    assert advance_watermark(r, 100) == 100
    assert r.writes[-1]["wm"] == 100


def test_empty_delta_is_noop():
    r = _Dispatch(wm=10, mx=None, delta_rows=[])
    res = run_incremental(r, r, apply=True)
    assert res.delta_nodes == 0
    assert res.watermark_after == 10  # 불변
    assert res.run is None


def test_delta_runs_occam_and_advances_after_apply():
    rows = [
        {"name": "old", "source_path": "bhgman_tool/x.py", "sha256": "o", "line_count": 10},
        {"name": "new", "source_path": "bhgman_tool/x.py", "sha256": "n", "line_count": 99},
    ]
    r = _Dispatch(wm=5, mx=555, delta_rows=rows)
    res = run_incremental(r, r, apply=True)
    assert res.delta_nodes == 2
    assert res.run is not None
    assert res.run.report.candidates  # 증분 delta 에서 중복 검출
    assert res.watermark_after == 555  # commit 이후 max updatedAt 로 전진


def test_dry_run_does_not_advance_watermark():
    rows = [
        {"name": "old", "source_path": "bhgman_tool/y.py", "sha256": "o", "line_count": 10},
        {"name": "new", "source_path": "bhgman_tool/y.py", "sha256": "n", "line_count": 99},
    ]
    r = _Dispatch(wm=7, mx=999, delta_rows=rows)
    res = run_incremental(r, None, apply=False)
    assert res.watermark_after == 7  # dry-run: 전진 안 함
