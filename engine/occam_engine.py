"""Occam CommanderEngine.

Shared deterministic core for occam cleanup. CLI, MCP, and legion should call
this layer instead of reimplementing dedup semantics at each transport edge.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.commander_engine import CommanderContext, CommanderOutput, DeterministicCommanderEngine
from engine.longinus_engine import degraded
from engine.occam.escalation import _ident, build_escalation_plan
from engine.occam.occam_runner import run_occam


def summarize_occam_result(result) -> dict[str, Any]:
    report = result.report
    apply_result = result.apply_result
    # '불확실하면 자동 escalation': uncertain 후보 → 나생문, disk-orphan → Longinus.
    plan = build_escalation_plan(report)
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
        "deferred_count": len(apply_result.deferred),
        "deferred": list(apply_result.deferred),
        # per-candidate continuous σ + verdict (occam.py computes these and attaches them to
        # every candidate, but every surface dropped them — the safety value was invisible).
        "candidates": [
            {
                "stale": _ident(c.stale),
                "current": _ident(c.current),
                "sigma": c.score,
                "verdict": c.verdict,
                "confidence": c.confidence.value,
            }
            for c in report.candidates
        ],
        "escalation_count": plan.count,
        "escalations": [
            {
                "target": i.target,
                "subject": i.subject,
                "reason": i.reason,
                "command": i.command,
                "lens": i.lens,
            }
            for i in plan.items
        ],
        "notes": list(report.notes) + list(apply_result.notes),
        "summary": f"{result.summary} | {plan.summary}",
    }


class OccamEngine(DeterministicCommanderEngine):
    name = "occam"
    verb = "정리"
    requires: tuple[str, ...] = ("run_cypher",)
    provides: tuple[str, ...] = ("hygiene",)

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

    def run_remote(
        self,
        *,
        scope: str | None = None,
        apply: bool = False,
        repo_root: str | Path | None = None,
    ) -> dict[str, Any]:
        """Run Occam against the operational neo4j KG via the shared runner factory.

        Same OccamEngine surface as run_local — only the CypherRunner backend differs
        (mcp-neo4j-cypher HTTP gateway when BHGMAN_KG_MCP_URL is set, else bolt). This
        is the CLI/MCP/legion parity path: MCP is no longer local-only.

        Degrades (no raise) when no backend is reachable — set BHGMAN_KG_MCP_URL (HTTP
        gateway, bolt-firewall safe) or NEO4J_PASSWORD. KG: bhgman-engine-mcp-kg-backend.
        """
        from engine.cli.runtime import make_kg_runners  # noqa: PLC0415

        runners = make_kg_runners()
        if runners is None:
            return degraded(
                "hygiene",
                "no neo4j/MCP KG backend reachable — set BHGMAN_KG_MCP_URL (HTTP gateway) "
                "or NEO4J_PASSWORD",
            )["hygiene"]
        run_cypher, write_cypher, close = runners
        try:
            return self.run(
                {
                    "run_cypher": run_cypher,
                    "write_cypher": write_cypher,
                    "scope": scope,
                    "apply": apply,
                    "repo_root": str(repo_root) if repo_root is not None else None,
                }
            )["hygiene"]
        finally:
            close()


__all__ = ["OccamEngine", "summarize_occam_result"]
