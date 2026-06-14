"""engine.tpa — TPA reverse cycle as a composed deterministic engine (Phase C).

The mirror of `engine/legion` in reverse: TCW→ST→SP→TA. It IMPORTS the existing
deterministic engines (code_to_kg AST extraction, eureka structural grouping,
longinus_drift_audit) and composes them as Contract-bound CommanderStages on the same
`legion.Legion.run()` loop — it does NOT fork them.

Engine the VERBS (extract / recover-structure / group / measure-drift). The semantic
JUDGMENT (intent recovery — what a symbol *means*, Unknown→ResearchProvider, out-of-library
NovelPattern induction) stays SKILL.md orchestration (Rice-bound), per
`adr-apt-tpa-engine-substrate-scope-2026-06-14`.

# KG: adr-apt-tpa-engine-substrate-scope-2026-06-14, plan-apt-tpa-engine-substrate-2026-06-14
"""

from __future__ import annotations

from engine.tpa.reverse_phase_detect import (
    ReversePhaseFacts,
    ReversePhaseStatus,
    classify_reverse_phase,
    detect_reverse_phase,
)
from engine.tpa.tpa_orchestrator import build_tpa_legion, run_tpa

__all__ = [
    "ReversePhaseFacts",
    "ReversePhaseStatus",
    "build_tpa_legion",
    "classify_reverse_phase",
    "detect_reverse_phase",
    "run_tpa",
]
