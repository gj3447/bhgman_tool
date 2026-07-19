"""오캄 dirty-set 큐 — durable sqlite 큐: 변경 이벤트 → 표적 재감사 (풀스캔 회피).

PROM 6 P2 tail (rf-occam-adv-A2): 파일/KG 변경 이벤트를 durable 큐에 적재해 두고,
오캄이 그 dirty set 만 표적 재감사한다. `incremental.run_incremental`(C7 watermark
delta) 의 이벤트-구동 앞단 — 소비 측이 ``pending()`` 으로 꺼낸 경로를 scope 로 넘겨
targeted pass 를 돌리고, 성공 후 ``ack()`` 로 소거한다.

설계 원칙:
  - **durable**: stdlib sqlite3 (WAL journal). 프로세스 재시작·크래시 생존. DB 경로는
    주입식(default ``~/.bhgman/occam_dirty.db``), 연결은 호출-단위 open/close 라
    같은 경로로 재-생성(safe re-open)해도 상태가 그대로 보인다.
  - **coalescing**: path PRIMARY KEY + UPSERT — 같은 경로를 두 번 enqueue 하면 row 는
    1개 유지 + enqueue 타임스탬프/사유만 갱신 (이벤트 폭주 O(events)→O(distinct paths)).
  - **debounce**: ``pending(now_ms, debounce_ms)`` 는 ``enqueued_at_ms < now_ms -
    debounce_ms`` (strict) 인 항목만 반환 — 경계에 정확히 걸린 항목은 아직 '식지 않은'
    것으로 보류. 연쇄 저장 중인 파일에 대한 재감사 스톰을 막는다.
  - **no clock reads**: 라이브러리 함수는 시계를 읽지 않는다. 모든 타임스탬프
    (at_ms/now_ms)는 호출자 주입 — 테스트 결정론 + 시간 의미론을 호출자(데몬/CLI)에 위임.
  - **covenant 각주**: archive-only covenant(DELETE/DETACH/REMOVE 금지)는 *KG 노드*에
    대한 규약이다(kg_adapter 참조). 이 큐의 row 는 KG 정본이 아니라 소모성 이벤트
    티켓 — ``ack`` = 처리 완료 티켓 소거가 큐 의미론이며 covenant 위반이 아니다.
    KG 쪽 supersede 는 여전히 kg_adapter 의 archive-only 경로만 사용한다.

**배선 지점 (future producer = longinus 데몬, daemon.py 는 아직 수정하지 않음)**:
  `engine/longinus_drift_audit/daemon.py` 의 ``LonginusDaemon._drain_drift_queue()`` 가
  drift 이벤트 dict(``{"path": ..., "repo_alias": ..., "new_hash": ..., ...}``) 리스트를
  반환한다. 후속 sprint 에서 부모 데몬 루프가 그 반환값을 받아

      enqueue_from_drift(queue, [ev["path"] for ev in events], at_ms=...)

  를 호출하면 배선 완료 — 의존 방향은 daemon→dirty_queue 단방향이고, 이 모듈은
  daemon 을 import 하지 않는다. 소비 측: occam 데몬/CLI 가 주기적으로
  ``pending(now_ms)`` → 경로별 ``incremental.run_incremental(..., scope=...)`` →
  성공 시 ``ack([e.path for e in batch])``.

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A2-2026-07-19,
#     occam-kam-canonical-2026-05-26, longinus-drift-daemon-pattern-2026-05-13
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB_PATH = Path("~/.bhgman/occam_dirty.db")
DEFAULT_DEBOUNCE_MS = 500

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS dirty ("
    " path TEXT PRIMARY KEY,"  # coalescing 키 — 같은 경로는 항상 1 row
    " reason TEXT NOT NULL,"
    " enqueued_at_ms INTEGER NOT NULL"
    ")"
)
_UPSERT = (
    "INSERT INTO dirty (path, reason, enqueued_at_ms) VALUES (?, ?, ?) "
    "ON CONFLICT(path) DO UPDATE SET "
    "reason = excluded.reason, enqueued_at_ms = excluded.enqueued_at_ms"
)
# debounce: strict `<` — 경계(enqueued == now - debounce)에 정확히 걸린 항목은 보류.
_PENDING = (
    "SELECT path, reason, enqueued_at_ms FROM dirty "
    "WHERE enqueued_at_ms < ? ORDER BY enqueued_at_ms ASC, path ASC"
)
_ACK = "DELETE FROM dirty WHERE path = ?"  # 큐 티켓 소거 (KG 노드 아님 — covenant 무관)
_COUNT = "SELECT count(*) AS n FROM dirty"


@dataclass(frozen=True)
class DirtyEntry:
    # KG: rf-occam-adv-A2-2026-07-19
    """큐 항목 value object — 경로 + 적재 사유 + enqueue 시각(ms, 호출자 주입)."""

    path: str
    reason: str
    enqueued_at_ms: int


class DirtyQueue:
    # KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A2-2026-07-19
    """sqlite-backed durable dirty-set 큐 (coalescing UPSERT + debounce read).

    시계를 읽지 않는다 — enqueue/pending 의 시각은 전부 파라미터. 연결은 메서드
    호출마다 열고 닫으므로 인스턴스를 버리고 같은 경로로 다시 만들어도 안전하다.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """db_path 주입 (None → ``~/.bhgman/occam_dirty.db``). 스키마는 멱등 생성."""
        raw = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.db_path = raw.expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        """호출-단위 연결. WAL journal(재시작 생존 + 동시 reader) + busy timeout."""
        conn = sqlite3.connect(self.db_path, isolation_level=None)  # autocommit
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def enqueue(self, path: str, reason: str, at_ms: int) -> None:
        """path 를 dirty 로 적재. 이미 있으면 coalesce — timestamp/사유만 갱신 (UPSERT)."""
        with closing(self._connect()) as conn:
            conn.execute(_UPSERT, (path, reason, int(at_ms)))

    def pending(self, now_ms: int, debounce_ms: int = DEFAULT_DEBOUNCE_MS) -> list[DirtyEntry]:
        """debounce 창을 지난(strictly older) 항목만 — 오래된 것부터, path 로 tie-break.

        경계 항목(enqueued_at_ms == now_ms - debounce_ms)은 반환하지 **않는다**.
        """
        cutoff = int(now_ms) - int(debounce_ms)
        with closing(self._connect()) as conn:
            rows = conn.execute(_PENDING, (cutoff,)).fetchall()
        return [
            DirtyEntry(path=r["path"], reason=r["reason"], enqueued_at_ms=int(r["enqueued_at_ms"]))
            for r in rows
        ]

    def ack(self, paths: list[str]) -> int:
        """처리 완료 경로들의 티켓을 소거. 없는 경로는 무시. 소거된 row 수 반환."""
        if not paths:
            return 0
        with closing(self._connect()) as conn:
            cur = conn.executemany(_ACK, [(p,) for p in paths])
            return cur.rowcount if cur.rowcount > 0 else 0

    def count(self) -> int:
        """현재 큐에 남은 dirty 항목 수 (debounce 무관 전체)."""
        with closing(self._connect()) as conn:
            row = conn.execute(_COUNT).fetchone()
        return int(row["n"]) if row is not None else 0


def enqueue_from_drift(
    queue: DirtyQueue,
    drift_paths: list[str],
    at_ms: int,
    reason: str = "sha-drift",
) -> int:
    # KG: longinus-drift-daemon-pattern-2026-05-13, rf-occam-adv-A2-2026-07-19
    """longinus drift 이벤트 경로 묶음을 일괄 enqueue (데몬 배선용 얇은 helper).

    중복 경로는 UPSERT 로 자연 coalesce. 처리한 입력 경로 수(중복 포함)를 반환.
    """
    for p in drift_paths:
        queue.enqueue(p, reason, at_ms)
    return len(drift_paths)


__all__ = [
    "DEFAULT_DB_PATH",
    "DEFAULT_DEBOUNCE_MS",
    "DirtyEntry",
    "DirtyQueue",
    "enqueue_from_drift",
]
