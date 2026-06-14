"""tpa_orchestrator — the reverse legion loop (TCW→ST→SP→TA) as Contract-bound stages.

The mirror of `engine/legion/commanders.py` in reverse. Each stage IMPORTS an existing
deterministic engine (it does NOT fork):

  TCW 추출   code_root            -> tcw_result    engine.code_to_kg.extract_python_file
  ST  복원   tcw_result           -> contracts     deterministic signature projection
  SP  복원   tcw_result+contracts -> patterns      deterministic structural grouping
  TA  측정   tcw_result           -> drift_report  engine.longinus_drift_audit.detect_all

It reuses `engine.legion.Legion.run()` for the Contract-bound handoff (requires⊆provides) and
the same graceful-degrade covenant (a failed engine still provides its key so the loop closes).

Honest boundary (ADR `adr-apt-tpa-engine-substrate-scope-2026-06-14`): these four are the
deterministic EXTRACT/MEASURE verbs. The SEMANTIC recovery — what a recovered symbol *means*,
intent recovery, Unknown→ResearchProvider, out-of-library NovelPattern induction — is NOT here;
it stays SKILL.md orchestration (Rice-bound). Engining it would be determinism theater.

# KG: adr-apt-tpa-engine-substrate-scope-2026-06-14, plan-apt-tpa-engine-substrate-2026-06-14,
#     bihaenggiman-legioncommanders-2026-05-26
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.legion.legion import GateFn, Legion, LegionRun
from engine.legion.legion_models import CommanderStage


def _degraded(key: str, reason: str) -> dict:
    """Engine failure / unsupported input -> graceful degrade (loop always provides its key)."""
    return {key: {"mode": "degraded", "reason": reason, "summary": f"{key}: degraded — {reason}"}}


# ── 추출 (TCW) — code_to_kg AST extraction ──────────────────────────────────
def _iter_py_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix == ".py" else []
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _run_tcw(ctx: dict) -> dict:
    """Extract the target code world into `:CodeSymbol` records (real engine)."""
    from engine.code_to_kg.ts_extractor import extract_python_file  # noqa: PLC0415

    root = Path(str(ctx.get("code_root") or "")).expanduser()
    if not root.exists():
        return _degraded("tcw_result", f"code_root not found: {root}")
    symbols: list[Any] = []
    files = _iter_py_files(root)
    for f in files:
        try:
            symbols.extend(extract_python_file(f).nodes)
        except Exception:  # noqa: BLE001 — one unparseable file must not sink the cycle
            continue
    return {
        "tcw_result": {
            "source_path": str(root),
            "files_scanned": len(files),
            "symbol_count": len(symbols),
            "symbols": symbols,
            "summary": f"TCW: {len(symbols)} CodeSymbol from {len(files)} file(s)",
        }
    }


# ── 복원-구조 (ST) — deterministic contract candidates from symbols ──────────
_CONTRACT_KINDS = frozenset({"function", "method", "class"})


def _run_recover_structure(ctx: dict) -> dict:
    """Project callable/class symbols into recovered Contract candidates (deterministic)."""
    syms = (ctx.get("tcw_result") or {}).get("symbols") or []
    candidates = [
        {
            "name": s.name,
            "qualname": s.qualname,
            "kind": s.kind,
            "source_path": s.source_path,
            "symbol_id": s.symbol_id,
        }
        for s in syms
        if getattr(s, "kind", None) in _CONTRACT_KINDS
    ]
    return {
        "contracts": {
            "candidates": candidates,
            "count": len(candidates),
            "summary": f"ST: {len(candidates)} Contract candidate(s) recovered from structure",
        }
    }


# ── 복원-피라미드 (SP) — deterministic structural grouping ───────────────────
def _run_recover_pyramid(ctx: dict) -> dict:
    """Cluster recovered symbols by kind into a pattern pyramid (deterministic)."""
    syms = (ctx.get("tcw_result") or {}).get("symbols") or []
    groups: dict[str, int] = {}
    for s in syms:
        kind = getattr(s, "kind", "unknown")
        groups[kind] = groups.get(kind, 0) + 1
    return {
        "patterns": {
            "groups": groups,
            "count": len(groups),
            "summary": "SP: pyramid " + ", ".join(f"{k}={v}" for k, v in sorted(groups.items())),
        }
    }


# ── 측정 (TA) — real longinus 5-drift over the recovered symbols ─────────────
def _to_code_symbol(s: Any):
    from engine.longinus_drift_audit.models import CodeSymbol  # noqa: PLC0415

    return CodeSymbol(
        sourcePath=f"{getattr(s, 'source_path', '?')}:{getattr(s, 'start_line', 0)}",
        name=getattr(s, "qualname", None) or getattr(s, "name", "?"),
        kind=getattr(s, "kind", "unknown"),
        kg_refs=list(getattr(s, "kg_refs", []) or []),
    )


def _run_measure_drift(ctx: dict) -> dict:
    """Run the 5-drift detector over the recovered symbols vs the injected KG ref registry."""
    try:
        from engine.longinus_drift_audit.drift_detector import detect_all  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        return _degraded("drift_report", f"drift engine import failed: {e}")
    syms = (ctx.get("tcw_result") or {}).get("symbols") or []
    kg_refs = ctx.get("kg_refs") or {}
    try:
        drifts = detect_all(symbols=[_to_code_symbol(s) for s in syms], kg_refs=kg_refs)
    except Exception as e:  # noqa: BLE001
        return _degraded("drift_report", f"detect_all failed: {e}")
    by_type: dict[str, int] = {}
    for d in drifts:
        key = getattr(d.drift_type, "value", str(d.drift_type))
        by_type[key] = by_type.get(key, 0) + 1
    return {
        "drift_report": {
            "drift_count": len(drifts),
            "by_type": by_type,
            "summary": f"TA: {len(drifts)} drift(s) over {len(syms)} symbol(s)",
        }
    }


# ── stage roster + 합성 ──────────────────────────────────────────────────────
_STAGES: tuple[CommanderStage, ...] = (
    CommanderStage("tcw", "추출", ("code_root",), ("tcw_result",), _run_tcw),
    CommanderStage("st", "복원", ("tcw_result",), ("contracts",), _run_recover_structure),
    CommanderStage("sp", "복원", ("tcw_result", "contracts"), ("patterns",), _run_recover_pyramid),
    CommanderStage("ta", "측정", ("tcw_result",), ("drift_report",), _run_measure_drift),
)


def build_tpa_legion() -> Legion:
    """The 4 reverse stages registered in TCW→ST→SP→TA order (one run() = one reverse loop)."""
    legion = Legion()
    for stage in _STAGES:
        legion.register(stage)
    return legion


def run_tpa(
    code_root: str | Path, *, kg_refs: dict | None = None, gate: GateFn | None = None
) -> LegionRun:
    """Recover design from `code_root`: extract → recover structure → recover pyramid → measure drift."""
    ctx: dict = {"code_root": str(code_root)}
    if kg_refs is not None:
        ctx["kg_refs"] = kg_refs
    return build_tpa_legion().run(ctx, gate=gate)


__all__ = ["build_tpa_legion", "run_tpa"]
