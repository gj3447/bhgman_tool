"""오캄 verdict 피드백 테스트 — PROM 6 P2 tail / rf-occam-adv-A5 (calibration 루프 봉합).

결정론 / no network / no DB — 파일 IO 는 tmp_path, KG rows 는 fake 리스트 주입.

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A5-2026-07-19
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from engine.occam.calibration import label_to_bool, load_decision_log
from engine.occam.decision_log import append_decision_records, build_decision_record
from engine.occam.occam_models import Confidence, NodeRecord, SupersessionCandidate
from engine.occam.verdict_feedback import (
    FeedbackReport,
    apply_verdicts,
    match_key,
    vr_to_verdicts,
)


def _cand(stale_name="old", path="bhgman_tool/x.py", stale_sha="sha_old_000000ff"):
    stale = NodeRecord(stale_name, path, stale_sha, 10, inbound_edges=1)
    current = NodeRecord("new", path, "sha_new", 99, inbound_edges=7)
    return SupersessionCandidate(
        stale=stale,
        current=current,
        normalized_path=path,
        reason="superseded: 10L -> current 99L",
        confidence=Confidence.HIGH,
        score=0.91,
        verdict="SUPERSEDE",
    )


def _log(tmp_path, cands, name="decisions.jsonl"):
    recs = [build_decision_record(c, decided_at="2026-07-19T00:00:00Z", run_id="r1") for c in cands]
    p = tmp_path / name
    append_decision_records(recs, p)
    return p


# ── match_key ───────────────────────────────────────────────────────────────


def test_match_key_prefers_stale_name():
    rec = build_decision_record(_cand(), decided_at="t")
    assert match_key(rec) == "old"


def test_match_key_falls_back_to_path_and_sha_prefix():
    rec = build_decision_record(_cand(stale_name=None), decided_at="t")
    # name 부재 → normalized_path + ':' + sha256[:12]
    assert match_key(rec) == "bhgman_tool/x.py:sha_old_0000"


def test_match_key_defensive_on_missing_fields():
    # 어떤 결손 dict 가 와도 raise 없이 str
    assert match_key({}) == ":"
    assert match_key({"normalized_path": "a.py"}) == "a.py:"
    assert match_key({"features": {"stale": {"sha256": "abcdef1234567890"}}}) == ":abcdef123456"
    assert match_key({"features": None}) == ":"
    assert match_key({"features": {"stale": "not-a-dict"}}) == ":"


# ── apply_verdicts ──────────────────────────────────────────────────────────


def test_apply_fills_only_open_labels(tmp_path):
    p = _log(tmp_path, [_cand("a"), _cand("b")])
    report = apply_verdicts(p, {"a": "APPROVED", "b": "REJECT"})
    assert report == FeedbackReport(updated=2, unmatched_keys=(), total_records=2)
    recs = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()]
    by_key = {match_key(r): r for r in recs}
    assert by_key["a"]["verdict_label"] == "APPROVED"
    assert by_key["b"]["verdict_label"] == "REJECT"
    # write-back 이 다른 필드를 건드리지 않음
    assert by_key["a"]["sigma"] == 0.91 and by_key["a"]["verdict"] == "SUPERSEDE"


def test_apply_never_overwrites_existing_label(tmp_path):
    p = _log(tmp_path, [_cand("a")])
    apply_verdicts(p, {"a": "APPROVED"})
    report = apply_verdicts(p, {"a": "REJECT"})  # 재판정 시도 → 덮어쓰기 금지
    assert report.updated == 0
    assert report.unmatched_keys == ()  # 매칭은 됐음 (unknown 아님) — 갱신만 안 함
    rec = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    assert rec["verdict_label"] == "APPROVED"


def test_apply_reports_unknown_keys_as_unmatched(tmp_path):
    p = _log(tmp_path, [_cand("a")])
    report = apply_verdicts(p, {"a": "PASS", "ghost-z": "FAIL", "ghost-a": "PASS"})
    assert report.updated == 1
    assert report.unmatched_keys == ("ghost-a", "ghost-z")  # 정렬 보고


def test_apply_missing_file_is_noop_all_unmatched(tmp_path):
    p = tmp_path / "absent.jsonl"
    report = apply_verdicts(p, {"a": "PASS"})
    assert report == FeedbackReport(updated=0, unmatched_keys=("a",), total_records=0)
    assert not p.exists()  # 파일을 만들어내지 않음


def test_apply_rewrite_is_in_place_and_preserves_order_and_corrupt_lines(tmp_path):
    p = _log(tmp_path, [_cand("a"), _cand("b")])
    with p.open("a", encoding="utf-8") as fh:
        fh.write("{corrupt not-json\n")  # 손상 줄 주입
    before = [ln for ln in p.read_text(encoding="utf-8").splitlines()]
    report = apply_verdicts(p, {"b": "APPROVED"})
    assert report.updated == 1
    assert report.total_records == 2  # 손상 줄은 레코드로 세지 않음
    after = p.read_text(encoding="utf-8").splitlines()
    assert len(after) == 3
    assert after[0] == before[0]  # 미변경 레코드는 byte-stable
    assert after[2] == "{corrupt not-json"  # 손상 줄 보존 (유실 금지)
    assert json.loads(after[1])["verdict_label"] == "APPROVED"  # 순서 보존
    # 원자 교체 잔재(tempfile) 없음
    assert sorted(f.name for f in tmp_path.iterdir()) == ["decisions.jsonl"]


def test_apply_noop_leaves_file_untouched(tmp_path):
    p = _log(tmp_path, [_cand("a")])
    raw = p.read_bytes()
    mtime = p.stat().st_mtime_ns
    report = apply_verdicts(p, {"ghost": "PASS"})  # 매칭 0 → 갱신 0
    assert report.updated == 0 and report.unmatched_keys == ("ghost",)
    assert p.read_bytes() == raw and p.stat().st_mtime_ns == mtime


def test_apply_is_idempotent(tmp_path):
    p = _log(tmp_path, [_cand("a")])
    verdicts = {"a": "APPROVED"}
    first = apply_verdicts(p, verdicts)
    raw = p.read_bytes()
    second = apply_verdicts(p, verdicts)
    assert (first.updated, second.updated) == (1, 0)
    assert p.read_bytes() == raw  # 두 번째는 no-op


def test_feedback_report_is_frozen():
    r = FeedbackReport(updated=0, unmatched_keys=(), total_records=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.updated = 1  # type: ignore[misc]


# ── vr_to_verdicts (KG rows 어댑터 — fake rows 주입, no DB) ─────────────────


def test_vr_to_verdicts_normalizes_uppercase_and_skips_defective_rows():
    rows = [
        {"subject": "a", "verdict": "approved"},
        {"subject": "b", "verdict": " fail "},
        {"subject": None, "verdict": "PASS"},  # 결손 skip
        {"subject": "c"},  # verdict 부재 skip
        "not-a-dict",  # 방어 skip
    ]
    assert vr_to_verdicts(rows) == {"a": "APPROVED", "b": "FAIL"}


def test_vr_to_verdicts_later_row_wins_on_duplicate_subject():
    rows = [{"subject": "a", "verdict": "REJECT"}, {"subject": "a", "verdict": "APPROVED"}]
    assert vr_to_verdicts(rows) == {"a": "APPROVED"}


def test_vr_to_verdicts_empty_and_none():
    assert vr_to_verdicts([]) == {}
    assert vr_to_verdicts(None) == {}  # type: ignore[arg-type]


# ── 루프 봉합 end-to-end: decision_log → verdict_feedback → calibration ─────


def test_feedback_loop_closes_into_calibration(tmp_path):
    """A5 acceptance: write-back 된 라벨을 calibration.load_decision_log 가 그대로 소비."""
    p = _log(tmp_path, [_cand("a"), _cand("b"), _cand("c")])
    # fake CypherRunner 결과 (KG ValidationResult rows) — 크리틱 판정 2건, 1건은 미판정
    rows = [
        {"subject": "a", "verdict": "approved"},
        {"subject": "b", "verdict": "reject"},
    ]
    report = apply_verdicts(p, vr_to_verdicts(rows))
    assert report.updated == 2
    pairs = load_decision_log(p)  # verdict_label 채워진 것만
    assert pairs == [(0.91, 1), (0.91, 0)]
    # 어휘 정합 재확인: 저장된 라벨이 label_to_bool 어휘에 그대로 꽂힌다
    assert label_to_bool("APPROVED") == 1 and label_to_bool("REJECT") == 0
