"""부채 #2(재배맨) — jsonl 독립 dispatch 성공률.

재배맨 dispatch 효능을 KG 부재 신호(intent_n/actual_n는 DispatchEvent에 미기록) 대신
**jsonl tool_use 실측**으로 측정: Task/Agent subagent 출격이 에러 없이 완료됐나.
독립(jsonl=세션 실기록, 재배맨이 만든 라벨 아님) + 대량(157세션) + 비순환.

efficacy = dispatch 성공률 = 성공/(성공+실패). GH#29181의 intent==actual 충실도는
KG에 카운트가 없어 측정 불가(telemetry.py RunRecord가 적재 시작해야) — 정직 명시.

순수(scan) + IO(파일/KG) 분리.

# KG: efficacy-jaebaeman-2026-06-01, efficacy-measurement-line-2026-06-01,
#     ATOM_Skill_jaebaeman, finding-prom32-jaebaeman-J1-F2
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

_DISPATCH_TOOLS = {"Task", "Agent"}


@dataclass(frozen=True)
class DispatchStats:
    dispatched: int = 0
    succeeded: int = 0
    errored: int = 0
    pending: int = 0  # 결과 없음 (미완/중단)

    @property
    def success_rate(self) -> float:
        done = self.succeeded + self.errored
        return self.succeeded / done if done else 0.0


def _walk_blocks(record: dict, role: str) -> Iterable[dict]:
    msg = record.get("message")
    if not isinstance(msg, dict) or msg.get("role") != role:
        return
    content = msg.get("content")
    if isinstance(content, list):
        yield from (b for b in content if isinstance(b, dict))


def _collect_dispatched(rec: dict, dispatched: set[str]) -> None:
    for block in _walk_blocks(rec, "assistant"):
        if block.get("type") == "tool_use" and block.get("name") in _DISPATCH_TOOLS:
            tid = block.get("id")
            if isinstance(tid, str):
                dispatched.add(tid)


def _collect_results(rec: dict, dispatched: set[str], ok: set[str], err: set[str]) -> None:
    for block in _walk_blocks(rec, "user"):
        if block.get("type") != "tool_result":
            continue
        tid = block.get("tool_use_id")
        if isinstance(tid, str) and tid in dispatched:
            (err if block.get("is_error") else ok).add(tid)


def scan_dispatches(lines: Iterable[str]) -> DispatchStats:
    """jsonl 라인 → DispatchStats. Task/Agent tool_use id ↔ tool_result(is_error) 매칭."""
    dispatched: set[str] = set()
    succeeded: set[str] = set()
    errored: set[str] = set()
    for line in lines:
        if '"tool_use"' not in line and '"tool_result"' not in line:
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        _collect_dispatched(rec, dispatched)
        _collect_results(rec, dispatched, succeeded, errored)
    return DispatchStats(
        dispatched=len(dispatched),
        succeeded=len(succeeded),
        errored=len(errored),
        pending=len(dispatched - succeeded - errored),
    )


def scan_dir(jsonl_dir: str | Path) -> DispatchStats:
    """디렉터리 *.jsonl 합산 (스트리밍)."""
    d = DispatchStats()
    for path in sorted(Path(jsonl_dir).glob("*.jsonl")):
        with path.open(encoding="utf-8", errors="replace") as fh:
            s = scan_dispatches(fh)
        d = DispatchStats(
            dispatched=d.dispatched + s.dispatched,
            succeeded=d.succeeded + s.succeeded,
            errored=d.errored + s.errored,
            pending=d.pending + s.pending,
        )
    return d


_WRITE = (
    "MERGE (m:JaebaemanDispatchTelemetry {name: 'jaebaeman-dispatch-telemetry-2026-06-01'}) "
    "SET m.dispatched=$dispatched, m.succeeded=$succeeded, m.errored=$errored, "
    "m.pending=$pending, m.success_rate=$rate, m.oracle='jsonl tool_use/tool_result (독립)', "
    "m.recorded_at=datetime()"
)


def main() -> int:  # pragma: no cover — IO 진입점
    import os  # noqa: PLC0415

    from engine.cli.runtime import make_kg_runners  # noqa: PLC0415

    jsonl_dir = os.environ.get(
        "BHGMAN_JSONL_DIR", str(Path.home() / ".claude/projects/-Users-lagyeongjun-CD-SYMPOSIUM")
    )
    stats = scan_dir(jsonl_dir)
    print(
        f"jaebaeman dispatch: dispatched={stats.dispatched} succeeded={stats.succeeded} "
        f"errored={stats.errored} pending={stats.pending} success_rate={stats.success_rate:.3f}"
    )
    runners = make_kg_runners()
    if runners is None:
        print("neo4j 미연결 — KG 기록 skip", file=sys.stderr)
        return 0
    _run, write_cypher, close = runners
    try:
        write_cypher(
            _WRITE,
            {
                "dispatched": stats.dispatched,
                "succeeded": stats.succeeded,
                "errored": stats.errored,
                "pending": stats.pending,
                "rate": stats.success_rate,
            },
        )
        return 0
    finally:
        close()


__all__ = ["DispatchStats", "scan_dir", "scan_dispatches"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
