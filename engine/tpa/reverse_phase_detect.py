"""tpa run — deterministic reverse phase navigation (the dual of engine/legion/phase_detect).

Forward APT builds DOWN (SA→span→Contract→code). TPA recovers UP from existing code:
extract symbols, recover structure/contracts, recover the pattern pyramid, recover the
design anchor. Given a target (a recovery cycle name), query the KG for how far the
reverse recovery chain has progressed and report *where the work is* and *what runs next*.

  no CodeSymbol            -> TCW recover-code-world  (/tpa-tcw)
  CodeSymbol, no Contract  -> ST  recover-structure   (/tpa-st)
  Contract, no Pattern     -> SP  recover-pyramid      (/tpa-sp)
  Pattern, no SemanticAnchor -> TA recover-anchor      (/tpa-ta)
  SemanticAnchor recovered -> COMPLETE                 (design intent recovered)

Honest boundary (same covenant as forward phase_detect): the runtime *navigates and gates*;
the SEMANTIC recovery (what a symbol *means*, the recovered anchor's intent) stays with the
LLM/skill layer. The deterministic substrate here is the EXTRACT half (`engine/code_to_kg`
symbols, `engine/longinus_drift_audit` drift) + the navigation. Backend-honest: a backend that
cannot answer the analytic queries yields phase=UNKNOWN, never a false "start at TCW".

# KG: adr-apt-tpa-engine-substrate-scope-2026-06-14, plan-apt-tpa-engine-substrate-2026-06-14,
#     lesson-ai-skipped-kg-check-before-framing-2026-04-29 (KG-first)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReversePhaseFacts:
    code_count: int | None  # None = backend could not answer
    contract_count: int | None = None
    pattern_count: int | None = None
    anchor_count: int | None = None

    @property
    def usable(self) -> bool:
        return self.code_count is not None


@dataclass(frozen=True)
class ReversePhaseStatus:
    phase: str
    next_skill: str
    evidence: str


def classify_reverse_phase(facts: ReversePhaseFacts) -> ReversePhaseStatus:
    """Pure: KG facts -> (phase, next skill, evidence). Highest-recovery branch wins."""
    if not facts.usable:
        return ReversePhaseStatus("UNKNOWN", "(none)", "backend could not answer reverse queries")
    if (facts.code_count or 0) <= 0:
        return ReversePhaseStatus(
            "TCW", "/tpa-tcw", "no CodeSymbol — extract the target code world first"
        )
    if (facts.anchor_count or 0) > 0:
        return ReversePhaseStatus(
            "COMPLETE",
            "(none)",
            f"design intent recovered ({facts.anchor_count} SemanticAnchor) — reverse loop closed",
        )
    if (facts.pattern_count or 0) > 0:
        return ReversePhaseStatus(
            "TA",
            "/tpa-ta",
            f"pattern pyramid recovered ({facts.pattern_count}), no anchor — recover design intent",
        )
    if (facts.contract_count or 0) > 0:
        return ReversePhaseStatus(
            "SP",
            "/tpa-sp",
            f"structure recovered ({facts.contract_count} Contract), no pattern — recover pyramid",
        )
    return ReversePhaseStatus(
        "ST", "/tpa-st", "CodeSymbol extracted but no structure — recover contracts/twins"
    )


# ---- KG fetch (neo4j; graceful on backends that can't answer) ----
# Recovery chain is keyed by a TpaTarget {name}; the TPA stages MERGE these as they recover.
_Q_CODE = "MATCH (t:TpaTarget {name:$target})-[:EXTRACTED]->(s:CodeSymbol) RETURN count(s) AS c"
_Q_CONTRACT = "MATCH (t:TpaTarget {name:$target})-[:RECOVERED]->(c:Contract) RETURN count(c) AS c"
_Q_PATTERN = "MATCH (t:TpaTarget {name:$target})-[:RECOVERED]->(p:Pattern) RETURN count(p) AS c"
_Q_ANCHOR = (
    "MATCH (t:TpaTarget {name:$target})-[:RECOVERED]->(a:SemanticAnchor) RETURN count(a) AS c"
)


def _count(run_cypher, cypher: str, params: dict) -> int | None:
    try:
        rows = run_cypher(cypher, params)
    except Exception:  # noqa: BLE001 — backend unsupported / unreachable => unknown, not crash
        return None
    if not rows:
        return 0
    val = next(iter(rows[0].values()))
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def fetch_reverse_facts(target: str, run_cypher) -> ReversePhaseFacts:
    params = {"target": target}
    code = _count(run_cypher, _Q_CODE, params)
    if code is None:  # backend cannot answer the very first query -> unusable
        return ReversePhaseFacts(code_count=None)
    return ReversePhaseFacts(
        code_count=code,
        contract_count=_count(run_cypher, _Q_CONTRACT, params),
        pattern_count=_count(run_cypher, _Q_PATTERN, params),
        anchor_count=_count(run_cypher, _Q_ANCHOR, params),
    )


def detect_reverse_phase(target: str, run_cypher) -> ReversePhaseStatus:
    return classify_reverse_phase(fetch_reverse_facts(target, run_cypher))


__all__ = [
    "ReversePhaseFacts",
    "ReversePhaseStatus",
    "classify_reverse_phase",
    "detect_reverse_phase",
    "fetch_reverse_facts",
]
