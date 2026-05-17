"""bhgman_tool umbrella CLI — `bhgman-tool` entry point.

Subcommands:
  install-skills  Copy skills/ into ~/.claude/skills/ (replaces manual cp -R)
  verify          Run pytest + lean checks (smoke verification)
  version         Print version + repo layout summary
  daemon          Delegate to engine.longinus_drift_audit.daemon_cli

KG: SPAN_bhgman_tool_phase3_CLI (Phase 3 L1 branch A)
APT: sa-bhgman_tool-ruflo-utility-parity-2026-05-13
"""

from .main import cli

__all__ = ["cli"]
