"""apt run — deterministic phase navigation (item ⑤, the "user doesn't manage phases" half).

Mirrors apt/SKILL.md §2.1 per-branch phase detection as engine code: given a project (SemanticAnchor),
query the KG for the SA→decompose→crystallize→materialize chain and report *where the work is* and
*what runs next*. This is the deterministic SUBSTRATE — the reasoning content of SP/ST/SCW stays with
the LLM/skill layer (engine covenant: deterministic core, LLM optional). Honest boundary: the runtime
*navigates and gates*; it does not *do* the decomposition.

  no SemanticAnchor          -> PH1/2 bootstrap   (/apt-sa)
  SA, no AtomicSpan leaves    -> PH3 decompose      (/apt-sp)
  AtomicSpan, no Contract     -> PH4 crystallize     (/apt-st)
  Contract, no SourceCodeNode -> PH5 implement       (/apt-scw)
  SourceCodeNode exists       -> PH5/6 feedback       (/apt-scw)

Backend-honest: the bundled local KG (feature-substring dispatcher) raises UnsupportedLocalQuery for
these analytic queries; fetch_facts catches that and returns an *unusable* fact set (phase=UNKNOWN)
rather than a false "bootstrap". Real navigation runs against neo4j.

# KG: project-apt-ultracode-roadmap-2026-06-02 (⑤ phase navigation),
#     lesson-ai-skipped-kg-check-before-framing-2026-04-29 (KG-first)
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.legion.legion import GateFn  # noqa: F401 — re-export friendliness

CypherRunner = "Callable[[str, dict], list[dict]]"


@dataclass(frozen=True)
class PhaseFacts:
    sa_exists: bool | None  # None = backend could not answer
    atomic_count: int | None = None
    contract_count: int | None = None
    source_count: int | None = None

    @property
    def usable(self) -> bool:
        return self.sa_exists is not None


@dataclass(frozen=True)
class PhaseStatus:
    phase: str
    next_skill: str
    evidence: str


def classify_phase(facts: PhaseFacts) -> PhaseStatus:
    """Pure: KG facts -> (phase, next skill, evidence). Highest-progress branch wins."""
    if not facts.usable:
        return PhaseStatus("UNKNOWN", "(none)", "backend could not answer phase queries")
    if not facts.sa_exists:
        return PhaseStatus(
            "PH1_2_BOOTSTRAP", "/apt-sa", "no SemanticAnchor — establish identity first"
        )
    if (facts.source_count or 0) > 0:
        return PhaseStatus(
            "PH5_6_SCW_FEEDBACK",
            "/apt-scw",
            f"code materialized ({facts.source_count} SourceCodeNode) — implement/feedback loop",
        )
    if (facts.contract_count or 0) > 0:
        return PhaseStatus(
            "PH5_SCW",
            "/apt-scw",
            f"Contract crystallized ({facts.contract_count}), no code yet — implement",
        )
    if (facts.atomic_count or 0) > 0:
        return PhaseStatus(
            "PH4_ST",
            "/apt-st",
            f"AtomicSpan ready ({facts.atomic_count}), no Contract — crystallize",
        )
    return PhaseStatus("PH3_SP", "/apt-sp", "SA exists but not decomposed — decompose into spans")


# ---- KG fetch (neo4j; graceful on backends that can't answer) ----
_Q_SA = "MATCH (sa:SemanticAnchor {name:$target}) RETURN count(sa) AS c"
_Q_ATOMIC = (
    "MATCH (sa:SemanticAnchor {name:$target})-[:HAS_ROOT]->(:AptSpan)"
    "-[:DECOMPOSES_TO*1..6]->(leaf:AtomicSpan) RETURN count(leaf) AS c"
)
_Q_CONTRACT = (
    "MATCH (sa:SemanticAnchor {name:$target})-[:HAS_ROOT]->(:AptSpan)"
    "-[:DECOMPOSES_TO*1..6]->(:AtomicSpan)-[:HAS_CONTRACT]->(c:Contract) RETURN count(c) AS c"
)
_Q_SOURCE = (
    "MATCH (sa:SemanticAnchor {name:$target})-[:HAS_ROOT]->(:AptSpan)"
    "-[:DECOMPOSES_TO*1..6]->(:AtomicSpan)-[:HAS_CONTRACT]->(:Contract)"
    "-[:MATERIALIZES]->(s:SourceCodeNode) RETURN count(s) AS c"
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


def fetch_facts(target: str, run_cypher) -> PhaseFacts:
    params = {"target": target}
    sa = _count(run_cypher, _Q_SA, params)
    if sa is None:  # backend cannot answer the very first query -> unusable
        return PhaseFacts(sa_exists=None)
    return PhaseFacts(
        sa_exists=sa > 0,
        atomic_count=_count(run_cypher, _Q_ATOMIC, params),
        contract_count=_count(run_cypher, _Q_CONTRACT, params),
        source_count=_count(run_cypher, _Q_SOURCE, params),
    )


def detect_phase(target: str, run_cypher) -> PhaseStatus:
    return classify_phase(fetch_facts(target, run_cypher))


__all__ = [
    "PhaseFacts",
    "PhaseStatus",
    "classify_phase",
    "detect_phase",
    "fetch_facts",
]
