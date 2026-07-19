"""daemon → occam dirty-set 배선 테스트 — PROM 6 C7/A2 (2026-07-19).

drift 이벤트가 _drain_drift_queue 에서 occam DirtyQueue 로 영속 enqueue 되는지.
# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A2-2026-07-19
"""

from __future__ import annotations

import queue
from pathlib import Path

from engine.longinus_drift_audit.daemon import LonginusDaemon
from engine.occam.dirty_queue import DirtyQueue


def _daemon(tmp_path) -> LonginusDaemon:
    d = LonginusDaemon(tmp_path / "watch.toml", occam_dirty_db=tmp_path / "dirty.db")
    # mp.Queue 는 feeder-thread 라 put 직후 get_nowait 가 레이스 — 테스트는 동기 큐로
    # 치환해 drain 로직만 결정론 검증 (인터페이스 동일: put/get_nowait/queue.Empty).
    d.drift_queue = queue.Queue()
    return d


def test_drain_enqueues_drift_into_occam_dirty_queue(tmp_path):
    d = _daemon(tmp_path)
    d.drift_queue.put(
        {"repo_alias": "bhgman", "path": "/r/engine/a.py", "old_hash": "o", "new_hash": "n",
         "bytes_len": 10, "detected_at": 1700000000.5}
    )
    events = d._drain_drift_queue()
    assert len(events) == 1
    q = DirtyQueue(tmp_path / "dirty.db")
    assert q.count() == 1
    pending = q.pending(now_ms=1700000000500 + 10_000)
    assert pending and pending[0].path == "/r/engine/a.py"
    assert pending[0].reason == "sha-drift"


def test_drain_coalesces_same_path(tmp_path):
    d = _daemon(tmp_path)
    for ts in (1700000000.0, 1700000001.0):
        d.drift_queue.put({"path": "/r/x.py", "detected_at": ts})
    d._drain_drift_queue()
    assert DirtyQueue(tmp_path / "dirty.db").count() == 1  # coalesced


def test_empty_drain_touches_nothing(tmp_path):
    d = _daemon(tmp_path)
    assert d._drain_drift_queue() == []
    assert not Path(tmp_path / "dirty.db").exists()  # 이벤트 0 → 큐 파일 생성 안 함


def test_enqueue_failure_does_not_kill_daemon(tmp_path):
    # occam 측 오류 → daemon 은 살아서 이벤트 반환 (fail-open)
    d = LonginusDaemon(tmp_path / "watch.toml", occam_dirty_db=Path("/dev/null/impossible/x.db"))
    d.drift_queue = queue.Queue()
    d.drift_queue.put({"path": "/r/y.py", "detected_at": 1.0})
    events = d._drain_drift_queue()  # must not raise
    assert len(events) == 1
