"""추가전용(append-only) JSONL 체크포인트 저널 — 크래시 후 재개 시 끝낸 일을 재지불하지 않는다.

durable.py 는 DBOS seam 이다: HAS_DBOS=False 인 현 환경에선 in-process fallback 이라
*실제 내구성이 0* 이다 (`_run_durable_dbos` 는 pragma: no cover — 미검증). 그래서 봇이
tick 40에서 죽으면 재시작이 tick 1부터 LLM 비용을 전부 다시 낸다. DBOS+Postgres 없이,
새 의존성 0으로 지금 당장 얻을 수 있는 내구성이 이 저널이다 — durable.py 의 seam 은
그대로 두고(교체 아님, 병행) 파일 한 개로 crash→resume 을 만든다.

계약:
  - append-only. 기록은 절대 수정/삭제하지 않는다 (W3C PROV 정신 + 크래시 안전).
  - 한 줄 = 한 JSON object = 한 완료 단위. 줄 단위 fsync 없이도 부분 기록된 마지막 줄은
    파싱 실패로 그냥 무시된다 (crash-tail tolerance) — 그 단위는 미완료로 간주되어 재실행.
  - run_id 로 scope. 저널 파일 하나에 여러 run 이 누적돼도 서로를 오염시키지 않는다.
  - payload 는 JSON 직렬화 가능해야 한다. 저널을 켠 호출자의 책임 (직렬화 불가 payload 를
    문자열로 뭉개면 재개가 *다른* 객체를 되살려 조용히 틀리므로, 그렇게 하지 않는다).

# KG: prom16-harness-loop-standard (durable state / append-only journal, resume idempotent),
#     durable-legion-fallback-2026-06-27 (DBOS seam 은 유지 — 이 저널은 그 아래의 무의존 층)
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# 저널 레코드 종류 (kind).
KIND_RUN_START = "run_start"  # 한 run 의 시작 마커 (run_id 발급)
KIND_TICK = "tick"  # daemon tick 1회 완료
KIND_BOT_DONE = "bot_done"  # daemon 루프 정상 종료 마커
KIND_EVOLVE_GEN = "evolve_gen"  # evolve 세대 1회 완료 (gen 0 = seed 평가)
KIND_EVOLVE_DONE = "evolve_done"  # evolve 루프 종료 마커


@dataclass(frozen=True)
class JournalEntry:
    """저널 한 줄. unit = run_id 안에서 이 단위를 유일하게 식별하는 키."""

    kind: str
    run_id: str
    unit: str
    payload: dict

    def to_json(self) -> str:
        return json.dumps(
            {"kind": self.kind, "run_id": self.run_id, "unit": self.unit, "payload": self.payload},
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def from_obj(obj: Any) -> "JournalEntry | None":
        """dict → JournalEntry. 형태가 안 맞으면 None (손상된 줄은 미완료로 간주)."""
        if not isinstance(obj, dict):
            return None
        kind, run_id = obj.get("kind"), obj.get("run_id")
        if not isinstance(kind, str) or not isinstance(run_id, str):
            return None
        payload = obj.get("payload")
        return JournalEntry(
            kind=kind,
            run_id=run_id,
            unit=str(obj.get("unit", "")),
            payload=payload if isinstance(payload, dict) else {},
        )


class JsonlJournal:
    """파일 기반 추가전용 저널. path=None 이면 아무것도 안 하는 no-op (저널 비활성)."""

    def __init__(self, path: str | os.PathLike[str] | None) -> None:
        self._path = Path(path) if path is not None else None

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def enabled(self) -> bool:
        return self._path is not None

    def append(self, kind: str, run_id: str, unit: str = "", payload: dict | None = None) -> None:
        """한 단위 완료를 기록. 호출 후 프로세스가 죽어도 이 단위는 재실행되지 않는다.

        Raises:
            TypeError: payload 가 JSON 직렬화 불가 (저널 사용자의 계약 위반 — 조용히
                뭉개면 재개가 다른 객체를 되살리므로 명시적으로 터뜨린다).
        """
        if self._path is None:
            return
        entry = JournalEntry(kind=kind, run_id=run_id, unit=unit, payload=payload or {})
        line = entry.to_json()  # 직렬화 실패는 여기서 raise — 파일은 건드리지 않음
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())  # 크래시 내구성 — 기록했다면 정말 디스크에 있다

    def entries(self, *, run_id: str | None = None, kind: str | None = None) -> list[JournalEntry]:
        """기록된 순서대로 읽는다. 손상/부분 기록된 줄은 조용히 건너뛴다 (미완료로 간주)."""
        return list(self._iter(run_id=run_id, kind=kind))

    def _iter(self, *, run_id: str | None, kind: str | None) -> Iterator[JournalEntry]:
        if self._path is None or not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue  # crash-tail: 반쪽 줄 = 미완료 단위
                entry = JournalEntry.from_obj(obj)
                if entry is None:
                    continue
                if run_id is not None and entry.run_id != run_id:
                    continue
                if kind is not None and entry.kind != kind:
                    continue
                yield entry

    def completed_units(self, kind: str, run_id: str) -> set[str]:
        """이 run 에서 이미 끝난 unit 키들 — 재개 시 skip 판정의 근거."""
        return {e.unit for e in self._iter(run_id=run_id, kind=kind)}

    def has(self, kind: str, run_id: str) -> bool:
        """이 run 에 해당 kind 의 마커가 있는가 (예: evolve_done / bot_done)."""
        return any(True for _ in self._iter(run_id=run_id, kind=kind))

    def last_run_id(self, *, kind: str = KIND_RUN_START) -> str | None:
        """가장 최근 run_start 의 run_id — 명시 run_id 없이 재개할 때의 기본 대상."""
        last: str | None = None
        for e in self._iter(run_id=None, kind=kind):
            last = e.run_id
        return last


__all__ = [
    "KIND_BOT_DONE",
    "KIND_EVOLVE_DONE",
    "KIND_EVOLVE_GEN",
    "KIND_RUN_START",
    "KIND_TICK",
    "JournalEntry",
    "JsonlJournal",
]
