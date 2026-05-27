"""오캄 end-to-end runner — fetch(KG) → occam_pass(순수 분류) → apply(supersede).

orchestration만. read/write IO = kg_adapter, 분류 로직 = occam.py. dry-run 기본.

KG-only 모드는 disk_truth 부재 → PICK_CURRENT가 max line_count 휴리스틱(MEDIUM confidence).
disk sha 확정(HIGH)이 필요하면 호출자가 disk_truth를 occam_pass에 직접 주입 (CLI 향후 enhancement).

# KG: occam-kam-canonical-2026-05-26, occam-pass-kg-wide-2026-05-27,
#     lesson-occam-must-query-kg-node-dedup-not-just-filesystem-2026-05-27
"""

from __future__ import annotations

from dataclasses import dataclass

from kg_adapter import ApplyResult, CypherRunner, apply_supersessions, fetch_source_nodes
from occam import occam_pass
from occam_models import OccamReport


@dataclass(frozen=True)
class OccamRunResult:
    report: OccamReport
    apply_result: ApplyResult
    scope: str | None = None

    @property
    def summary(self) -> str:
        r, a = self.report, self.apply_result
        mode = "DRY-RUN (no write)" if a.dry_run else f"APPLIED {a.applied_count}"
        scope = self.scope or "ALL"
        return (
            f"occam[{scope}]: scanned={r.scanned_nodes} dup_groups={r.groups_with_dups} "
            f"superseded_candidates={r.superseded_count} → {mode}"
        )


def run_occam(
    run_cypher: CypherRunner,
    write_cypher: CypherRunner | None = None,
    scope: str | None = None,
    apply: bool = False,
    disk_truth: dict[str, str] | None = None,
) -> OccamRunResult:
    """KG SourceCodeNode dedup pass. apply=False(기본) → dry-run, supersede write 없음."""
    nodes = fetch_source_nodes(run_cypher, scope)
    report = occam_pass(nodes, disk_truth=disk_truth)
    apply_result = apply_supersessions(report, write_cypher=write_cypher, dry_run=not apply)
    return OccamRunResult(report=report, apply_result=apply_result, scope=scope)


__all__ = ["OccamRunResult", "run_occam"]
