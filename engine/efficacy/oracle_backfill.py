"""효능 측정 부채 #1 백필 — invocation_count + disk_present 를 SourceCodeNode에.

효능맵이 7군단장 전부 UNMEASURABLE이었던 원인 중 두 신호 결손을 메운다:
  · invocation_count — jsonl tool_use(Read/Edit/Write…)의 file_path 실측 카운트.
    (lesson-occam-proxy-strength-needs-empirical-spot-check-2026-05-28: KG mention proxy
     말고 실제 invocation log 봐야 한다.)
  · disk_present — scan_disk_paths 로 파일이 실제 디스크에 있나. **순환성을 깨는 독립 oracle**
    (occam status 라벨은 occam이 만들지만, 디스크 실존은 occam과 무관).

순수 함수(카운트/플랜) + IO(neo4j) 분리. 순수부만 테스트.

# KG: efficacy-measurement-line-2026-06-01, efficacy-occam-sigma-ab-2026-06-01,
#     lesson-occam-proxy-strength-needs-empirical-spot-check-2026-05-28,
#     feedback_occam_needs_invocation_log_not_kg_proxy
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from engine.occam.occam import normalize_path

# file_path를 갖는 tool_use 도구들 (파일 접촉 = invocation 신호).
_FILE_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit"}


def _iter_tool_uses(record: dict) -> Iterable[dict]:
    """한 jsonl 레코드(assistant message)에서 tool_use 블록들을 뽑는다."""
    msg = record.get("message")
    if not isinstance(msg, dict):
        return
    content = msg.get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            yield block


def count_invocations(jsonl_lines: Iterable[str]) -> dict[str, int]:
    """jsonl 라인들 → {normalized_repo_path: invocation_count}. bhgman_tool 파일만.

    file_path 없는 라인은 빠르게 skip. 손상 라인은 방어적 무시."""
    counts: dict[str, int] = defaultdict(int)
    for line in jsonl_lines:
        if "file_path" not in line:
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        for block in _iter_tool_uses(rec):
            if block.get("name") not in _FILE_TOOLS:
                continue
            fp = (block.get("input") or {}).get("file_path")
            if isinstance(fp, str) and "bhgman_tool/" in fp:
                counts[normalize_path(fp)] += 1
    return dict(counts)


def count_invocations_in_dir(jsonl_dir: str | Path) -> dict[str, int]:
    """디렉터리의 모든 *.jsonl 스트리밍 카운트 (885M도 라인 단위라 안전)."""
    counts: dict[str, int] = defaultdict(int)
    for path in sorted(Path(jsonl_dir).glob("*.jsonl")):
        with path.open(encoding="utf-8", errors="replace") as fh:
            for norm, c in count_invocations(fh).items():
                counts[norm] += c
    return dict(counts)


def build_backfill_plan(
    nodes: list[dict], invocations: dict[str, int], live_paths: frozenset[str]
) -> list[dict]:
    """노드별 {name, invocation_count, disk_present} 플랜. bhgman_tool 소속만.

    nodes: [{name, sourcePath}, ...] (KG fetch). 외부 노드(marker 없음)는 제외 —
    이 repo 디스크/로그로 판정 불가."""
    plan: list[dict] = []
    for n in nodes:
        sp = n.get("sourcePath") or ""
        if "bhgman_tool/" not in sp:
            continue
        norm = normalize_path(sp)
        plan.append(
            {
                "name": n["name"],
                "invocation_count": invocations.get(norm, 0),
                "disk_present": norm in live_paths,
            }
        )
    return plan


_FETCH = (
    "MATCH (s:SourceCodeNode) WHERE s.sourcePath CONTAINS 'bhgman_tool/' "
    "RETURN s.name AS name, s.sourcePath AS sourcePath"
)
_WRITE = (
    "UNWIND $plan AS p "
    "MATCH (s:SourceCodeNode {name: p.name}) "
    "SET s.invocation_count = p.invocation_count, s.disk_present = p.disk_present, "
    "s.invocation_backfilled_at = datetime()"
)


def main() -> int:  # pragma: no cover — IO 진입점
    from engine.cli.runtime import make_kg_runners  # noqa: PLC0415
    from engine.occam.occam_runner import scan_disk_paths  # noqa: PLC0415

    runners = make_kg_runners()
    if runners is None:
        print("neo4j 미연결 (NEO4J_PASSWORD?) — 백필 중단", file=sys.stderr)
        return 2
    run_cypher, write_cypher, close = runners
    try:
        jsonl_dir = os.environ.get(
            "BHGMAN_JSONL_DIR",
            str(Path.home() / ".claude/projects/-Users-lagyeongjun-CD-SYMPOSIUM"),
        )
        repo_root = os.environ.get("BHGMAN_REPO_ROOT", ".")
        invocations = count_invocations_in_dir(jsonl_dir)
        live = scan_disk_paths(repo_root)
        nodes = run_cypher(_FETCH, {})
        plan = build_backfill_plan(nodes, invocations, live)
        write_cypher(_WRITE, {"plan": plan})
        present = sum(1 for p in plan if p["disk_present"])
        touched = sum(1 for p in plan if p["invocation_count"] > 0)
        print(
            f"backfilled {len(plan)} nodes: disk_present={present}, "
            f"invocation>0={touched}, invocations_indexed={len(invocations)}"
        )
        return 0
    finally:
        close()


__all__ = [
    "build_backfill_plan",
    "count_invocations",
    "count_invocations_in_dir",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
