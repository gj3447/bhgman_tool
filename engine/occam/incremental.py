"""오캄 증분 실행 — watermark checkpoint + delta run (PROM 6 C7 / rf-occam-adv-A2).

풀스캔(O(all)) 대신 `updatedAt > watermark` 인 노드만 occam pass(O(changed)). checkpoint
는 **advance-after-commit** = at-least-once + 멱등 destination = 사실상 exactly-once,
크래시/재시작 생존. 항상-켜진 dirty-set 데몬(file-event→enqueue)은 Longinus sha256 데몬에
배선하는 후속 — 이 모듈은 그 데몬이 호출할 '한 번의 증분 pass' 코어다.

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A2-2026-07-19,
#     occam-kam-canonical-2026-05-26
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engine.occam.kg_adapter import (
    CypherRunner,
    apply_supersessions,
    fetch_cypher_since,
    parse_node_records,
)
from engine.occam.occam import occam_pass
from engine.occam.occam_runner import (
    OccamRunResult,
    _build_score_meta,
    _compute_disk_truth,
    is_confident_supersede,
    scan_disk_paths,
)

_CKPT = "occam-watermark"
_READ_CKPT = (
    "MERGE (c:OccamCheckpoint {name:$ckpt}) "
    "ON CREATE SET c.watermark = 0, c.createdAt = timestamp() "
    "RETURN coalesce(c.watermark, 0) AS wm"
)
_ADVANCE_CKPT = (
    "MATCH (c:OccamCheckpoint {name:$ckpt}) "
    "SET c.watermark = $wm, c.lastRunAt = timestamp() RETURN c.watermark AS wm"
)
_MAX_SINCE = (
    "MATCH (s:SourceCodeNode) WHERE s.updatedAt IS NOT NULL AND s.updatedAt > $watermark "
    "RETURN max(s.updatedAt) AS mx"
)


def read_watermark(run_cypher: CypherRunner) -> int:
    """현재 watermark (없으면 0으로 초기화)."""
    rows = run_cypher(_READ_CKPT, {"ckpt": _CKPT})
    return int(rows[0]["wm"]) if rows and rows[0].get("wm") is not None else 0


def advance_watermark(write_cypher: CypherRunner, wm: int) -> int:
    """watermark 를 wm 으로 전진(commit 이후 호출)."""
    rows = write_cypher(_ADVANCE_CKPT, {"ckpt": _CKPT, "wm": int(wm)})
    return int(rows[0]["wm"]) if rows and rows[0].get("wm") is not None else int(wm)


def max_updatedat_since(run_cypher: CypherRunner, watermark: int) -> int:
    """delta(updatedAt>watermark) 의 max updatedAt — 처리 *전* 스냅샷용."""
    rows = run_cypher(_MAX_SINCE, {"watermark": watermark})
    mx = rows[0].get("mx") if rows else None
    return int(mx) if mx is not None else watermark


@dataclass(frozen=True)
class IncrementalResult:
    watermark_before: int
    watermark_after: int
    delta_nodes: int
    run: OccamRunResult | None

    @property
    def summary(self) -> str:
        return (
            f"occam[incremental]: delta={self.delta_nodes} node(s) "
            f"(wm {self.watermark_before}→{self.watermark_after})"
        )


def run_incremental(
    run_cypher: CypherRunner,
    write_cypher: CypherRunner | None = None,
    *,
    scope: str | None = None,
    apply: bool = False,
    repo_root: str | Path | None = None,
) -> IncrementalResult:
    """watermark 이후 변경 노드만 occam. apply 시 supersede 후 watermark 전진(after-commit).

    delta 가 비면 no-op(watermark 불변). 멱등: :ARCHIVED 는 fetch_cypher_since 가 이미 제외.
    """
    wm = read_watermark(run_cypher)
    new_wm = max_updatedat_since(run_cypher, wm)  # 처리 전 스냅샷 (경계 이후 write 는 다음 pass)
    cypher, params = fetch_cypher_since(wm, scope)
    nodes = parse_node_records(run_cypher(cypher, params))
    if not nodes:
        return IncrementalResult(wm, wm, 0, None)

    disk_paths = scan_disk_paths(repo_root) if repo_root is not None else None
    disk_truth = _compute_disk_truth(repo_root, nodes) if repo_root is not None else None
    report = occam_pass(
        nodes, disk_truth=disk_truth, disk_paths=disk_paths, score_meta=_build_score_meta(nodes)
    )
    apply_result = apply_supersessions(
        report, write_cypher=write_cypher, dry_run=not apply, should_apply=is_confident_supersede
    )
    after = wm
    if apply and write_cypher is not None:
        after = advance_watermark(write_cypher, new_wm)  # commit 이후에만 전진
    return IncrementalResult(
        wm, after, len(nodes), OccamRunResult(report=report, apply_result=apply_result, scope=scope)
    )


__all__ = [
    "IncrementalResult", "advance_watermark", "max_updatedat_since",
    "read_watermark", "run_incremental",
]
