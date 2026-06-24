"""Longinus CommanderEngine.

This is the first shared commander core wired through legion and MCP. It wraps
the production ``engine.longinus_drift_audit`` implementation so transport
adapters do not carry their own Longinus semantics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine.commander_engine import CommanderContext, CommanderOutput, DeterministicCommanderEngine
from engine.longinus_drift_audit import code_scanner
from engine.longinus_drift_audit.audit_runner import LonginusAudit
from engine.longinus_drift_audit.kg_client import KgClient, MockKgClient
from engine.longinus_drift_audit.models import Confidence, KgRefRecord


def degraded(key: str, reason: str) -> dict:
    """Standard graceful-degrade payload for commander adapters."""
    return {key: {"mode": "degraded", "reason": reason, "summary": f"{key}: degraded - {reason}"}}


def _line(source_path: str) -> int:
    try:
        return int(source_path.rsplit(":", 1)[1].split("-", 1)[0])
    except (IndexError, ValueError):
        return 0


def _refs_from_symbols(root: Path) -> list[dict[str, Any]]:
    symbols, _ = code_scanner.scan_root(root, parallel=False)
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for sym in symbols:
        for ref in sym.kg_refs:
            key = (sym.sourcePath, ref)
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                {
                    "file": sym.sourcePath.split(":", 1)[0],
                    "line": _line(sym.sourcePath),
                    "kg_id": ref,
                }
            )
    return refs


def _load_simulated_kg(root: Path) -> MockKgClient | None:
    path = root / "kg_simulated.json"
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return MockKgClient()
    if isinstance(raw, dict):
        names = sorted(str(k) for k in raw)
    elif isinstance(raw, list):
        names = sorted(str(v) for v in raw)
    else:
        names = []
    return MockKgClient(
        refs=[
            KgRefRecord(sourceId=name, sourcePath=f"kg_simulated.json:{i + 1}")
            for i, name in enumerate(names)
        ]
    )


def _mcp_default_kg(root: Path, refs: list[dict[str, Any]]) -> MockKgClient:
    """MCP compatibility backend.

    Without a live KG or ``kg_simulated.json``, the MCP audit reports discovered
    refs but avoids fabricating drift against an empty mock graph.
    """
    simulated = _load_simulated_kg(root)
    if simulated is not None:
        return simulated
    kg = MockKgClient()
    kg.other_nodes.update(str(r["kg_id"]) for r in refs)
    return kg


def summarize_report(report) -> dict[str, Any]:
    """Stable transport-friendly summary from the production AuditReport."""
    return {
        "audit_id": report.audit_id,
        "drifts_by_type": dict(report.drifts_by_type),
        "drift_records": [d.model_dump() for d in report.drift_records],
        "reverse_orphans": list(report.reverse_orphans),
        "forward_orphans": [o.model_dump() for o in report.forward_orphans],
        "sha256_drift_events": [e.model_dump() for e in report.sha256_drift_events],
        "sha256_baseline_count": report.sha256_baseline_count,
        "sha256_not_local_count": report.sha256_not_local_count,
        "ged": report.ged_report.model_dump() if report.ged_report is not None else None,
        "is_clean": report.is_clean,
    }


class LonginusEngine(DeterministicCommanderEngine):
    name = "longinus"
    verb = "연결"
    requires: tuple[str, ...] = ("run_cypher",)
    provides: tuple[str, ...] = ("bindings",)

    def deterministic_core(self, context: CommanderContext) -> CommanderOutput:
        kg = context.get("kg")
        code_root = context.get("code_root")
        if kg is not None and code_root is not None:
            return self.audit_context(context, kg=kg, code_root=code_root)
        return self.floating_context(context)

    def audit_context(
        self, context: CommanderContext, *, kg: KgClient, code_root: str | Path
    ) -> dict:
        try:
            report = LonginusAudit(
                kg=kg, code_root=code_root, repo_tag=context.get("repo_tag")
            ).run_full(verify_sha256=bool(context.get("verify_sha256", True)))
            summary = summarize_report(report)
            return {
                "bindings": {
                    "mode": "full-audit",
                    "drifts_by_type": summary["drifts_by_type"],
                    "is_clean": summary["is_clean"],
                    "summary": f"longinus[audit]: drift={summary['drifts_by_type']}",
                }
            }
        except Exception as e:  # noqa: BLE001 - commander floor must degrade, not crash the loop
            return degraded("bindings", f"full audit failed: {e}")

    def floating_context(self, context: CommanderContext) -> dict:
        rc = context["run_cypher"]
        try:
            rows = rc(
                "MATCH (c) WHERE c:Concept OR c:ResearchFinding OR c:Lesson "
                "WITH c WHERE NOT (c)-[:HAS_REFERENCE|BINDS_TO]->() "
                "RETURN count(c) AS n",
                {},
            )
            n = rows[0]["n"] if rows else 0
            return {
                "bindings": {
                    "mode": "kg-deterministic",
                    "floating_nodes": n,
                    "summary": f"longinus[kg]: {n} floating (unbound) concept nodes",
                }
            }
        except Exception as e:  # noqa: BLE001
            return degraded("bindings", f"float scan failed: {e}")

    def audit_repo_for_mcp(
        self, repo_path: str, confidence_threshold: str = "INFERRED"
    ) -> dict[str, Any]:
        try:
            Confidence(confidence_threshold)
        except ValueError as exc:
            raise ValueError(
                f"confidence_threshold must be one of {tuple(c.value for c in Confidence)}, "
                f"got {confidence_threshold!r}"
            ) from exc
        root = Path(repo_path).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"repo path not found: {repo_path}")
        if not root.is_dir():
            raise NotADirectoryError(f"not a directory: {repo_path}")
        refs = _refs_from_symbols(root)
        kg = _mcp_default_kg(root, refs)
        report = LonginusAudit(kg=kg, code_root=root).run_full(verify_sha256=False)
        summary = summarize_report(report)
        return {
            "audit_id": f"mcp-{summary['audit_id']}",
            "repo_path": str(root),
            "files_scanned": len({r["file"] for r in refs}) if refs else 0,
            "kg_refs_found": len(refs),
            "refs": refs,
            "drift_records": summary["drift_records"],
            "drifts_by_type": summary["drifts_by_type"],
            "confidence_threshold": confidence_threshold,
            "engine": "engine.longinus_engine.LonginusEngine",
            "note": "Production LonginusAudit core via CommanderEngine; kg_simulated.json is used when present.",
        }


__all__ = ["LonginusEngine", "degraded", "summarize_report"]
