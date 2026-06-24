"""Occam CommanderEngine.

Shared deterministic core for occam cleanup. CLI, MCP, and legion should call
this layer instead of reimplementing dedup semantics at each transport edge.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.commander_engine import CommanderContext, CommanderOutput, DeterministicCommanderEngine
from engine.longinus_engine import degraded
from engine.occam.occam_runner import run_occam


def summarize_occam_result(result) -> dict[str, Any]:
    report = result.report
    apply_result = result.apply_result
    return {
        "mode": "occam",
        "scope": result.scope,
        "scanned_nodes": report.scanned_nodes,
        "groups_with_dups": report.groups_with_dups,
        "superseded_candidates": report.superseded_count,
        "orphan_count": report.orphan_count,
        "applied": apply_result.applied_count,
        "dry_run": apply_result.dry_run,
        "planned": len(apply_result.planned_cyphers),
        "superseded": list(apply_result.superseded),
        "notes": list(report.notes) + list(apply_result.notes),
        "summary": result.summary,
    }


class OccamEngine(DeterministicCommanderEngine):
    name = "occam"
    verb = "정리"
    requires = ("run_cypher",)
    provides = ("hygiene",)

    def deterministic_core(self, context: CommanderContext) -> CommanderOutput:
        run_cypher = context["run_cypher"]
        try:
            result = run_occam(
                run_cypher,
                write_cypher=context.get("write_cypher"),
                scope=context.get("scope"),
                apply=bool(context.get("apply", False)),
                repo_root=context.get("repo_root"),
            )
            return {"hygiene": summarize_occam_result(result)}
        except Exception as e:  # noqa: BLE001 - keep legion/MCP fail-soft at the commander boundary
            return degraded("hygiene", f"occam failed: {e}")

    def run_local(
        self,
        *,
        kg_path: str | None = None,
        scope: str | None = None,
        apply: bool = False,
        repo_root: str | Path | None = None,
    ) -> dict[str, Any]:
        from engine.kg_local.runner import make_local_runner  # noqa: PLC0415
        from engine.kg_local.store import LocalKgStore  # noqa: PLC0415

        store = LocalKgStore(kg_path) if kg_path else LocalKgStore()
        runner = make_local_runner(store)
        return self.run(
            {
                "run_cypher": runner,
                "write_cypher": runner,
                "scope": scope,
                "apply": apply,
                "repo_root": str(repo_root) if repo_root is not None else None,
            }
        )["hygiene"]


__all__ = ["OccamEngine", "summarize_occam_result"]
