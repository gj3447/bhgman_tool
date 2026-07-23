"""오캄 dirty-set 큐 테스트 — durable/coalescing/debounce/ack/재-open (PROM 6 P2 tail).

시계 주입 결정론: 모든 시각은 리터럴 ms 로 주입 — 라이브러리는 시계를 읽지 않는다.

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A2-2026-07-19
"""

from __future__ import annotations

import inspect
import sqlite3

import engine.occam.dirty_queue as dirty_queue_module
from engine.occam.dirty_queue import DirtyEntry, DirtyQueue, enqueue_from_drift


def _q(tmp_path):
    return DirtyQueue(db_path=tmp_path / "occam_dirty.db")


def test_enqueue_and_pending_roundtrip(tmp_path):
    q = _q(tmp_path)
    q.enqueue("engine/occam/a.py", "file-event", at_ms=1_000)
    assert q.count() == 1
    got = q.pending(now_ms=10_000)
    assert got == [DirtyEntry(path="engine/occam/a.py", reason="file-event", enqueued_at_ms=1_000)]


def test_coalescing_same_path_is_one_entry_with_updated_timestamp(tmp_path):
    q = _q(tmp_path)
    q.enqueue("x.py", "file-event", at_ms=1_000)
    q.enqueue("x.py", "sha-drift", at_ms=2_000)  # 같은 path 재enqueue = UPSERT
    assert q.count() == 1  # row 는 하나만
    [entry] = q.pending(now_ms=100_000)
    assert entry.enqueued_at_ms == 2_000  # timestamp 최신으로 갱신
    assert entry.reason == "sha-drift"  # 사유도 최신으로 갱신


def test_debounce_boundary_exact_not_returned_strictly_older_returned(tmp_path):
    q = _q(tmp_path)
    now = 10_000
    q.enqueue("boundary.py", "e", at_ms=now - 500)  # 정확히 경계 (now - debounce)
    q.enqueue("older.py", "e", at_ms=now - 501)  # 경계보다 strictly older
    got = q.pending(now_ms=now, debounce_ms=500)
    assert [e.path for e in got] == ["older.py"]  # 경계 항목은 미반환


def test_debounce_default_is_500ms(tmp_path):
    q = _q(tmp_path)
    q.enqueue("hot.py", "e", at_ms=9_500)
    q.enqueue("cold.py", "e", at_ms=9_499)
    got = q.pending(now_ms=10_000)  # debounce_ms 생략 → default 500
    assert [e.path for e in got] == ["cold.py"]


def test_pending_ordering_oldest_first_path_tiebreak(tmp_path):
    q = _q(tmp_path)
    q.enqueue("b.py", "e", at_ms=100)
    q.enqueue("a.py", "e", at_ms=100)  # 동시각 → path tie-break
    q.enqueue("c.py", "e", at_ms=50)
    got = q.pending(now_ms=100_000)
    assert [e.path for e in got] == ["c.py", "a.py", "b.py"]


def test_ack_removes_only_processed_paths(tmp_path):
    q = _q(tmp_path)
    q.enqueue("a.py", "e", at_ms=1)
    q.enqueue("b.py", "e", at_ms=2)
    q.enqueue("c.py", "e", at_ms=3)
    removed = q.ack(["a.py", "c.py", "ghost.py"])  # 없는 경로는 무시
    assert removed == 2
    assert q.count() == 1
    assert [e.path for e in q.pending(now_ms=100_000)] == ["b.py"]


def test_ack_empty_is_noop(tmp_path):
    q = _q(tmp_path)
    q.enqueue("a.py", "e", at_ms=1)
    assert q.ack([]) == 0
    assert q.count() == 1


def test_persistence_across_reopen(tmp_path):
    db = tmp_path / "occam_dirty.db"
    q1 = DirtyQueue(db_path=db)
    q1.enqueue("survivor.py", "e", at_ms=1_000)
    del q1  # 인스턴스 폐기 (연결은 호출-단위라 잡고 있는 핸들 없음)

    q2 = DirtyQueue(db_path=db)  # safe re-open — 같은 경로 재-생성
    assert q2.count() == 1
    [entry] = q2.pending(now_ms=10_000)
    assert entry == DirtyEntry(path="survivor.py", reason="e", enqueued_at_ms=1_000)
    q2.ack(["survivor.py"])

    q3 = DirtyQueue(db_path=db)  # ack 도 durable
    assert q3.count() == 0


def test_wal_mode_enabled(tmp_path):
    db = tmp_path / "occam_dirty.db"
    DirtyQueue(db_path=db).enqueue("a.py", "e", at_ms=1)
    with sqlite3.connect(db) as conn:
        [(mode,)] = conn.execute("PRAGMA journal_mode").fetchall()
    assert mode.lower() == "wal"


def test_enqueue_from_drift_helper_coalesces_and_defaults_reason(tmp_path):
    q = _q(tmp_path)
    n = enqueue_from_drift(q, ["a.py", "b.py", "a.py"], at_ms=5_000)  # 입력 중복 포함
    assert n == 3  # 처리한 입력 경로 수 (중복 포함)
    assert q.count() == 2  # 큐에는 coalesce 되어 distinct path 만
    for e in q.pending(now_ms=100_000):
        assert e.reason == "sha-drift"  # default reason
        assert e.enqueued_at_ms == 5_000


def test_library_reads_no_clock():
    # 결정론 트립와이어: 모든 시각은 호출자 주입 — 모듈 소스에 시계 읽기가 없어야 한다.
    src = inspect.getsource(dirty_queue_module)
    for forbidden in ("import time", "time.time", "datetime.now", "monotonic", "timestamp()"):
        assert forbidden not in src, f"clock read leaked into dirty_queue: {forbidden}"
