"""추가전용 JSONL 저널 (GAP-3 기반 모듈) — run scope / append-only / crash-tail 관용.

# KG: prom16-harness-loop-standard (durable state / append-only journal)
"""

from __future__ import annotations

import pytest

from engine.legion.journal import KIND_TICK, JournalEntry, JsonlJournal


def test_disabled_journal_is_a_noop():
    """path=None = 저널 비활성 — 읽기/쓰기 전부 무해한 no-op (현행 동작 경로)."""
    j = JsonlJournal(None)
    assert not j.enabled
    j.append(KIND_TICK, "r1", unit="1", payload={"a": 1})
    assert j.entries() == []
    assert j.completed_units(KIND_TICK, "r1") == set()
    assert j.last_run_id() is None
    assert not j.has(KIND_TICK, "r1")


def test_append_only_preserves_order_and_never_rewrites(tmp_path):
    jp = tmp_path / "j.jsonl"
    j = JsonlJournal(jp)
    for i in range(3):
        j.append(KIND_TICK, "r1", unit=str(i), payload={"i": i})
    assert [e.unit for e in j.entries()] == ["0", "1", "2"]
    first = jp.read_text(encoding="utf-8")
    j.append(KIND_TICK, "r1", unit="3", payload={"i": 3})
    assert jp.read_text(encoding="utf-8").startswith(first)  # 기존 줄은 그대로 남는다


def test_entries_are_scoped_by_run_and_kind(tmp_path):
    j = JsonlJournal(tmp_path / "j.jsonl")
    j.append(KIND_TICK, "r1", unit="1")
    j.append(KIND_TICK, "r2", unit="1")
    j.append("other", "r1", unit="9")
    assert j.completed_units(KIND_TICK, "r1") == {"1"}
    assert j.completed_units(KIND_TICK, "r2") == {"1"}
    assert {e.unit for e in j.entries(run_id="r1")} == {"1", "9"}


def test_last_run_id_tracks_most_recent_marker(tmp_path):
    j = JsonlJournal(tmp_path / "j.jsonl")
    assert j.last_run_id() is None
    j.append("run_start", "r1")
    j.append("run_start", "r2")
    assert j.last_run_id() == "r2"


def test_corrupt_and_partial_lines_are_skipped(tmp_path):
    """크래시로 반쪽 기록된 줄은 미완료 단위 — 파싱 실패가 저널 전체를 죽이지 않는다."""
    jp = tmp_path / "j.jsonl"
    j = JsonlJournal(jp)
    j.append(KIND_TICK, "r1", unit="1")
    with jp.open("a", encoding="utf-8") as fh:
        fh.write("\n")  # 빈 줄
        fh.write("not json at all\n")
        fh.write('{"kind": "tick", "run_id": "r1", "unit": "2", "payl')  # 반쪽
    assert j.completed_units(KIND_TICK, "r1") == {"1"}  # 2 는 완료로 치지 않는다


def test_non_dict_and_malformed_records_are_ignored(tmp_path):
    jp = tmp_path / "j.jsonl"
    jp.write_text('[1,2,3]\n{"kind": 5, "run_id": "r"}\n{"run_id": "r"}\n', encoding="utf-8")
    assert JsonlJournal(jp).entries() == []


def test_unserializable_payload_raises_and_writes_nothing(tmp_path):
    """직렬화 불가 payload 는 명시적으로 터진다 — 뭉개면 재개가 다른 객체를 되살린다."""
    jp = tmp_path / "j.jsonl"
    j = JsonlJournal(jp)
    with pytest.raises(TypeError):
        j.append(KIND_TICK, "r1", unit="1", payload={"fn": lambda: None})
    assert not jp.exists()  # 실패한 append 가 파일을 오염시키지 않는다


def test_parent_directory_is_created(tmp_path):
    jp = tmp_path / "nested" / "deep" / "j.jsonl"
    JsonlJournal(jp).append(KIND_TICK, "r1", unit="1")
    assert jp.exists()


def test_entry_roundtrips_through_json():
    e = JournalEntry(kind=KIND_TICK, run_id="r1", unit="3", payload={"a": [1, 2], "b": None})
    import json

    back = JournalEntry.from_obj(json.loads(e.to_json()))
    assert back == e
