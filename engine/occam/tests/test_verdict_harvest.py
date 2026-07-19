"""오캄 verdict 수확 테스트 — PROM 6 C6 폐합 (KG VR → decision_log 라벨).

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A5-2026-07-19
"""

from __future__ import annotations

import json

from engine.occam.calibration import load_decision_log
from engine.occam.verdict_harvest import HARVEST_CYPHER, harvest_and_apply, harvest_rows


class _Runner:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __call__(self, cypher, params=None):
        self.calls.append((cypher, params))
        return self.rows


def _log(tmp_path, records):
    p = tmp_path / "decisions.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return p


def test_harvest_cypher_covers_edge_and_property_subjects():
    up = HARVEST_CYPHER.upper()
    assert "UNION" in up
    assert "S.NAME AS SUBJECT" in up  # 엣지형
    assert "V.SUBJECT AS SUBJECT" in up  # 프로퍼티형 (nameless stale 용)
    for tok in ("DELETE", "DETACH", "REMOVE", "MERGE", "CREATE", "SET "):
        assert tok not in up, f"harvest must be read-only, found {tok}"


def test_harvest_rows_passes_through_runner():
    rows = [{"subject": "a.py", "verdict": "APPROVED", "vr": "vr-1"}]
    r = _Runner(rows)
    assert harvest_rows(r) == rows


def test_harvest_and_apply_fills_matching_open_labels(tmp_path):
    log = _log(
        tmp_path,
        [
            {"sigma": 0.9, "verdict_label": None, "normalized_path": "x.py",
             "features": {"stale": {"name": "a.py", "sha256": "s" * 64}}},
            {"sigma": 0.6, "verdict_label": None, "normalized_path": "y.py",
             "features": {"stale": {"name": None, "sha256": "b" * 64}}},
        ],
    )
    # a.py 는 엣지형, y.py:bbbbbbbbbbbb 는 프로퍼티형 subject 로 판정 도착
    rows = [
        {"subject": "a.py", "verdict": "APPROVED", "vr": "vr-1"},
        {"subject": "y.py:" + "b" * 12, "verdict": "REJECT", "vr": "vr-2"},
        {"subject": "unrelated-node", "verdict": "APPROVED", "vr": "vr-3"},
    ]
    rep = harvest_and_apply(_Runner(rows), log)
    assert rep.updated == 2
    assert "unrelated-node" in rep.unmatched_keys  # 무관 VR = 오류 아님
    pairs = load_decision_log(log)
    assert sorted(pairs) == [(0.6, 0), (0.9, 1)]  # REJECT→0, APPROVED→1


def test_harvest_is_idempotent_never_overwrites(tmp_path):
    log = _log(
        tmp_path,
        [{"sigma": 0.9, "verdict_label": "APPROVED", "normalized_path": "x.py",
          "features": {"stale": {"name": "a.py", "sha256": "s" * 64}}}],
    )
    # 재판정이 REJECT 로 와도 이미 라벨된 레코드는 불변 (None-only fill)
    rep = harvest_and_apply(_Runner([{"subject": "a.py", "verdict": "REJECT", "vr": "vr-9"}]), log)
    assert rep.updated == 0
    assert load_decision_log(log) == [(0.9, 1)]
