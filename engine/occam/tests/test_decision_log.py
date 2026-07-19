"""오캄 결정 로그 테스트 — PROM 6 C6 (σ feature-vector 영속화, A5 unlock).

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A5-2026-07-19
"""

from __future__ import annotations

import json

from engine.occam.decision_log import append_decision_records, build_decision_record
from engine.occam.occam_models import Confidence, NodeRecord, SupersessionCandidate


def _cand():
    stale = NodeRecord("old", "bhgman_tool/x.py", "sha_old", 10, inbound_edges=1)
    current = NodeRecord("new", "bhgman_tool/x.py", "sha_new", 99, inbound_edges=7)
    return SupersessionCandidate(
        stale=stale,
        current=current,
        normalized_path="bhgman_tool/x.py",
        reason="superseded: 10L -> current 99L",
        confidence=Confidence.HIGH,
        score=0.91,
        verdict="SUPERSEDE",
    )


def test_record_captures_sigma_verdict_and_open_label():
    rec = build_decision_record(_cand(), decided_at="2026-07-19T00:00:00Z", run_id="r1")
    assert rec["sigma"] == 0.91
    assert rec["verdict"] == "SUPERSEDE"
    assert rec["verdict_label"] is None  # 크리틱이 나중에 채우는 calibration label
    assert rec["confidence"] == "HIGH"
    assert rec["run_id"] == "r1"


def test_features_expose_derived_signals():
    rec = build_decision_record(_cand(), decided_at="t")
    f = rec["features"]
    assert f["line_count_delta"] == 89  # 99 - 10
    assert f["inbound_delta"] == 6  # 7 - 1
    assert f["same_sha"] is False
    assert f["stale"]["name"] == "old" and f["current"]["name"] == "new"


def test_record_is_json_serializable():
    rec = build_decision_record(_cand(), decided_at="t")
    json.dumps(rec)  # must not raise


def test_append_writes_jsonl(tmp_path):
    recs = [build_decision_record(_cand(), decided_at="t", run_id="r")]
    p = tmp_path / "sub" / "decisions.jsonl"
    n = append_decision_records(recs, p)
    assert n == 1
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    back = json.loads(lines[0])
    assert back["sigma"] == 0.91 and back["verdict_label"] is None
    # append 는 누적 (덮어쓰기 아님)
    append_decision_records(recs, p)
    assert len(p.read_text(encoding="utf-8").strip().splitlines()) == 2
