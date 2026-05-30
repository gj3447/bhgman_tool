"""Durable dispatch 층 — google/ax (Agent Executor) durable execution 패턴 흡수.

TPA 흡수 사이클 tpa-ax-absorption-2026-05-30 (PROGRESSIVE, hard core only).
원본: https://github.com/google/ax (Go 분산 런타임). 여기선 hard core 4 invariant만 차용:

  1. append-only event log (SQLite, INSERT만 — UPDATE/DELETE 없음)
  2. cycle_id별 monotonic seq (재개점 O(1) 검증)
  3. history = spec_log replay (각 spec의 최신 행이 최종 상태)
  4. cycle_id별 single-writer 게이트 (in-process, AX inFlight map+mutex 1:1)

유보(protective belt — AX도 미성숙): snapshot / fork=slice / confirmation-pause / distributed.

`dispatch_parallel`을 *대체하지 않는다*. 장기 commander 작업(occam slice / longinus
drift audit / prom N>=50) 전용 opt-in 층. 단발 dispatch는 현행 ThreadPool 유지.

Orphan drift 해소: legion.measurement의 떠있던 HMAC 서명(`_sign`)을 durable backbone에
wire — 모든 event 행이 동일 `BHGMAN_DISPATCH_HMAC_SECRET`로 서명됨(forge 저항 audit이
영속 로그의 일부가 됨, 더 이상 floating 아님).

# KG: pattern-ax-durable-execution-2026-05-30, vp-bhgman-durable-dispatch-layer-2026-05-30,
#     dl-bhgman-durable-dispatch-approved-2026-05-30, driftaudit-bhgman-dispatch-vs-ax-2026-05-30
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import threading
from collections.abc import Callable
from datetime import datetime, timezone

from dispatch import SubagentResult, SubagentSpec, dispatch_parallel

# legion.measurement._sign과 동일 시크릿 — 서명 backbone 통합(Orphan drift 해소).
_HMAC_SECRET = os.environ.get(
    "BHGMAN_DISPATCH_HMAC_SECRET", "bhgman-dev-secret-2026-05-30"
).encode()


def _sign(payload: str) -> str:
    """HMAC-SHA256 — measurement.py와 동일 알고리즘/시크릿(provenance 통합)."""
    return hmac.new(_HMAC_SECRET, payload.encode(), hashlib.sha256).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CycleInFlight(RuntimeError):
    """동일 cycle_id가 이미 이 프로세스에서 실행 중 (single-writer 게이트 위반)."""


class EventLog:
    """append-only SQLite event log. AX 2-table 패턴(conversation_log/execution_log)을
    dispatch 단위(cycle_log/spec_log)로 적응. INSERT만 — UPDATE/DELETE 절대 없음."""

    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA busy_timeout = 10000")  # AX sqlite.go:35 1:1
        self._lock = threading.Lock()  # append 직렬화(같은 conn 멀티스레드 보호)
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cycle_log (
                cycle_id TEXT NOT NULL,
                seq      INTEGER NOT NULL,
                kind     TEXT NOT NULL,
                payload  TEXT NOT NULL,
                ts       TEXT NOT NULL,
                sig      TEXT NOT NULL,
                PRIMARY KEY (cycle_id, seq)
            );
            CREATE TABLE IF NOT EXISTS spec_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id  TEXT NOT NULL,
                spec_name TEXT NOT NULL,
                ok        INTEGER NOT NULL,
                text      TEXT NOT NULL,
                error     TEXT NOT NULL,
                ts        TEXT NOT NULL,
                sig       TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_spec_log_cycle ON spec_log (cycle_id);
            """
        )
        self._conn.commit()

    # --- invariant 1+2: append-only cycle event, monotonic seq ---
    def append_cycle_event(self, cycle_id: str, kind: str, payload: dict | None = None) -> int:
        """cycle-level event 추가. seq = 해당 cycle_id의 max(seq)+1 (1부터). 서명 후 INSERT."""
        body = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
        ts = _now()
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM cycle_log WHERE cycle_id = ?", (cycle_id,)
            ).fetchone()
            seq = row[0] + 1
            sig = _sign(f"{cycle_id}|{seq}|{kind}|{body}|{ts}")
            self._conn.execute(
                "INSERT INTO cycle_log (cycle_id, seq, kind, payload, ts, sig) VALUES (?,?,?,?,?,?)",
                (cycle_id, seq, kind, body, ts, sig),
            )
            self._conn.commit()
        return seq

    # --- invariant 1: append-only spec result (상태 전이마다 새 행) ---
    def record_spec(self, cycle_id: str, result: SubagentResult) -> None:
        """spec 결과를 새 행으로 append. 재시도 시 덮어쓰지 않고 행 추가(AX replay 패턴).
        최종 상태는 completed_specs가 spec_name별 최신(MAX id) 행으로 판정."""
        ts = _now()
        ok = 1 if result.ok else 0
        sig = _sign(f"{cycle_id}|{result.name}|{ok}|{result.text}|{result.error}|{ts}")
        with self._lock:
            self._conn.execute(
                "INSERT INTO spec_log (cycle_id, spec_name, ok, text, error, ts, sig) "
                "VALUES (?,?,?,?,?,?,?)",
                (cycle_id, result.name, ok, result.text, result.error, ts, sig),
            )
            self._conn.commit()

    # --- invariant 3: history = replay (spec_name별 최신 행, ok=True만 완료) ---
    def completed_specs(self, cycle_id: str) -> dict[str, SubagentResult]:
        """완료(ok=True)된 spec name→result. 각 spec_name의 최신 행만 본다(재시도 후 성공 반영).
        ok=False(실패)는 미완료 취급 → resume 시 재출격 대상."""
        rows = self._conn.execute(
            """
            SELECT s.spec_name, s.ok, s.text, s.error
            FROM spec_log s
            JOIN (SELECT spec_name, MAX(id) AS mid FROM spec_log WHERE cycle_id = ? GROUP BY spec_name) m
              ON s.id = m.mid
            """,
            (cycle_id,),
        ).fetchall()
        out: dict[str, SubagentResult] = {}
        for name, ok, text, error in rows:
            if ok:
                out[name] = SubagentResult(name, True, text, error)
        return out

    def cycle_events(self, cycle_id: str) -> list[dict]:
        """감사/디버그용 — cycle event 전체(seq 순)."""
        rows = self._conn.execute(
            "SELECT seq, kind, payload, ts, sig FROM cycle_log WHERE cycle_id = ? ORDER BY seq",
            (cycle_id,),
        ).fetchall()
        return [
            {"seq": s, "kind": k, "payload": json.loads(p), "ts": t, "sig": g}
            for s, k, p, t, g in rows
        ]

    @staticmethod
    def verify_cycle_event(ev: dict, cycle_id: str) -> bool:
        """cycle event 행의 HMAC 서명 검증(변조 탐지)."""
        body = json.dumps(ev["payload"], ensure_ascii=False, sort_keys=True)
        expected = _sign(f"{cycle_id}|{ev['seq']}|{ev['kind']}|{body}|{ev['ts']}")
        return hmac.compare_digest(expected, ev.get("sig", ""))

    def close(self) -> None:
        self._conn.close()


class DurableDispatcher:
    """resume 가능한 dispatch. run()은 멱등 — 이미 완료(ok=True)된 spec은 로그에서 replay,
    미완료/실패만 재출격. 입력 specs 순서 보존. crash 후 같은 (cycle_id, specs)로 run 재호출 = resume.

    single-writer 게이트(invariant 4): in-process lock per (db_path, cycle_id) — AX inFlight
    map+mutex 1:1. 같은 프로세스에서 동일 cycle_id 동시 run = CycleInFlight. (cross-process는
    protective belt 유보.)"""

    _gates: dict[str, threading.Lock] = {}
    _gates_guard = threading.Lock()

    def __init__(self, event_log: EventLog, db_key: str = "default") -> None:
        self._log = event_log
        self._db_key = db_key

    def _gate_for(self, cycle_id: str) -> threading.Lock:
        key = f"{self._db_key}::{cycle_id}"
        with DurableDispatcher._gates_guard:
            return DurableDispatcher._gates.setdefault(key, threading.Lock())

    def run(
        self,
        cycle_id: str,
        specs: list[SubagentSpec],
        client,
        max_workers: int = 8,
        dispatcher: Callable = dispatch_parallel,
    ) -> list[SubagentResult]:
        """specs를 durable하게 출격. 완료분 replay + 미완료분만 재출격, 순서 보존."""
        gate = self._gate_for(cycle_id)
        if not gate.acquire(blocking=False):
            raise CycleInFlight(f"cycle '{cycle_id}' already in flight (single-writer gate)")
        try:
            done = self._log.completed_specs(cycle_id)
            is_resume = bool(done)
            self._log.append_cycle_event(
                cycle_id,
                "CYCLE_RESUMED" if is_resume else "CYCLE_STARTED",
                {"total": len(specs), "already_done": len(done)},
            )
            pending = [s for s in specs if s.name not in done]
            if pending:
                fresh = dispatcher(pending, client, max_workers=max_workers)
                for r in fresh:
                    self._log.record_spec(cycle_id, r)
                    if r.ok:
                        done[r.name] = r
                fresh_by_name = {r.name: r for r in fresh}
            else:
                fresh_by_name = {}
            # invariant 3: 최종 결과 = 입력 순서대로 (완료 replay + 이번 출격) 병합
            ordered: list[SubagentResult] = []
            for s in specs:
                if s.name in done:
                    ordered.append(done[s.name])
                else:  # 이번에도 실패한 spec — 실패 결과 그대로
                    ordered.append(
                        fresh_by_name.get(
                            s.name, SubagentResult(s.name, False, "", "not dispatched")
                        )
                    )
            all_ok = all(r.ok for r in ordered)
            self._log.append_cycle_event(
                cycle_id, "CYCLE_COMPLETED", {"ok": all_ok, "n": len(ordered)}
            )
            return ordered
        finally:
            gate.release()


__all__ = ["CycleInFlight", "DurableDispatcher", "EventLog"]
