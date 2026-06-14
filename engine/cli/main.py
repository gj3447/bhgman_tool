"""bhgman-tool CLI entry point — stdlib argparse, zero new dependencies.

This module wires the top-level `bhgman-tool` console script registered in the
parent `pyproject.toml`. Subcommands span two cohorts:

A. bhgman_tool native (Phase 3 SCW):
    bhgman-tool install-skills [--target DIR] [--dry-run] [--force]
    bhgman-tool verify [--scope engine|lean|all]
    bhgman-tool version
    bhgman-tool daemon ...                    (delegates to engine.longinus_drift_audit.daemon_cli)

B. SYMPOSIUM-absorbed (Wave 7 P2-A 2026-05-14, KG rs-cli-symposium-absorb-2026-05-14):
    bhgman-tool apt <task>                    — APT cycle dispatch (SA → SP → ST → SCW)
    bhgman-tool tpa <path>                    — TPA reverse cycle (TCW → ST → SP → TA)
    bhgman-tool prom <N> <topic>              — Prometheus N-subagent research
    bhgman-tool tlb <target> [--lens NAME]    — Taliban adversarial verification
    bhgman-tool longinus <op>                 — Longinus reference binding (bind/sha256/ged/reverse-scan)
    bhgman-tool harness <action>              — Harness 3-tier scaffolding diagnose
    bhgman-tool status                        — KG audit (local cypher-shell → ssh dgx fallback)

C. SYMPOSIUM resolver/gate (Wave 7 P3-H 2026-05-14, KG span-bhgman-resolver-gate-absorption-wave7-2026-05-14):
    bhgman-tool resolver render --input X --output Y    — APT v27 A6 pre-prompt resolver render
    bhgman-tool resolver validate <SKILL.md>            — KG ↔ SKILL drift check
    bhgman-tool gate serve                              — start FastAPI gate endpoint (uvicorn)
    bhgman-tool gate check --gate NAME ...              — POST /gate/check oneshot
    Modules: engine.resolver.resolver (9 pytest absorbed) + engine.gate.gate_endpoint (6 pytest absorbed)
    OPA Rego policies: engine/gate/policies/ (4 bundle dirs preserved from SYMPOSIUM opa_rego_skeleton).

Routing convention for cohort B: each verb resolves a SKILL.md via `skills/<name>/`
and prints the routing intent (stderr) + the SKILL.md path (stdout). Actual phase
logic lives in the SKILL.md (drift prevention).

Honest limitations (Goodhart safeguard — no headline metric promotion):
  - install-skills does not check skill content integrity (no sha256 audit yet)
  - verify is *smoke* level — does not enumerate the full theorem set or
    re-derive coverage figures
  - daemon delegation passes through argv; no parameter translation
  - argparse error messages are not internationalized (README is 4-lang, CLI is en-only)
  - cohort B verbs `apt/tpa/prom/tlb/longinus/harness` only emit the SKILL.md path
    — the parent Claude harness consumes the body. They do NOT execute phase logic.
  - `status` prefers local `cypher-shell`; if absent, it falls back to `ssh dgx`.
"""

from __future__ import annotations

import sys

from engine.cli.parser import build_parser
from engine.cli.runtime import _repo_root, make_kg_runners  # re-export (test/import compat)

__all__ = ["build_parser", "cli", "_repo_root", "make_kg_runners"]


def cli(argv: list[str] | None = None) -> int:
    """Entry point registered in parent pyproject.toml [project.scripts]."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(cli())
