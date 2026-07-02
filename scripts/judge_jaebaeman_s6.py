"""Deterministic judge for LakatosTree_BhgmanJaebaeman_20260702 / jbm_s6_orphan_wire_or_prune.

Recomputes both pre-registered metrics — one by grepping the source tree, one by
driving the routing seam — never from a self-report:

  improve  orphan_module_consumer_count
      Of the two WIRE-designated orphans (htn.py, llm_decompose.py): how many have a
      production consumer outside engine/jaebaeman/ (grep over engine/**/*.py,
      excluding tests/ and bench/). Baseline 0 (audit wf_376c327b-8f3 G6: zero
      consumers beyond their own tests+bench; llm_decompose unreachable from any
      cmd_jaebaeman flag).

  novel    method_flag_discrimination   (judge-P2 independent axis: routing)
      1.0 iff the SAME node decomposes pairwise-differently under
      --method auto / kg-htn / llm (auto delegates, kg-htn yields the KG method
      subgoals, llm yields the gated LLM proposal) — the flag is real routing,
      not cosmetics. Independent of any consumer count.

Prints one JSON line; exit 0 (the VALUES carry the verdict).
Run from the repo root:  .venv/bin/python scripts/judge_jaebaeman_s6.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from engine.cli.commands import _jaebaeman_decompose  # noqa: E402
from engine.jaebaeman.jaebaeman_models import GerminationMethod, PlanNode  # noqa: E402

_WIRE_TARGETS = ("engine.jaebaeman.htn", "engine.jaebaeman.llm_decompose")

_NODE = PlanNode(
    name="judge-s6-root",
    objective="routing probe",
    task_type="research",
    target_domain="",
    depth=0,
    anchor="judge-s6-root",
    germination_method=GerminationMethod.DECOMPOSE,
)

_METHOD_ROWS = [
    {
        "method": "m-split",
        "ord": 0,
        "subgoals": [
            {"name": "sub-a", "objective": "A"},
            {"name": "sub-b", "objective": "B"},
        ],
    }
]


def _kg(cypher: str, params: dict) -> list[dict]:
    if "HAS_METHOD" in cypher:
        return list(_METHOD_ROWS) if params.get("task") == "judge-s6-root" else []
    return []


def _llm(_prompt: str) -> str:
    return '[{"name": "llm-a", "objective": "제안"}]'


def _production_consumers(target: str) -> int:
    """engine/**/*.py 중 engine/jaebaeman/ 밖 + tests/bench 제외에서 target을 import하는 파일 수."""
    hits = 0
    for py in (_REPO / "engine").rglob("*.py"):
        rel = py.relative_to(_REPO).as_posix()
        if rel.startswith("engine/jaebaeman/") or "/tests/" in rel or "/bench/" in rel:
            continue
        if target in py.read_text(encoding="utf-8"):
            hits += 1
    return hits


def main() -> int:
    # ── improve: grep-measured production consumers of the wire targets ─────
    orphan_module_consumer_count = sum(1 for t in _WIRE_TARGETS if _production_consumers(t) >= 1)

    # ── novel: the routing seam discriminates pairwise ──────────────────────
    auto, _ = _jaebaeman_decompose("auto", _kg)
    kg_htn, _ = _jaebaeman_decompose("kg-htn", _kg)
    llm, _ = _jaebaeman_decompose("llm", _kg, llm_complete=_llm)
    routes = {
        "auto": frozenset() if auto is None else frozenset(g.name for g in auto(_NODE)),
        "kg-htn": frozenset() if kg_htn is None else frozenset(g.name for g in kg_htn(_NODE)),
        "llm": frozenset() if llm is None else frozenset(g.name for g in llm(_NODE)),
    }
    method_flag_discrimination = (
        1.0
        if (
            auto is None
            and routes["kg-htn"] == {"sub-a", "sub-b"}
            and routes["llm"] == {"llm-a"}
            and len(set(routes.values())) == 3
        )
        else 0.0
    )

    print(
        json.dumps(
            {
                "orphan_module_consumer_count": orphan_module_consumer_count,
                "method_flag_discrimination": method_flag_discrimination,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
