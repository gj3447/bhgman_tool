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

from dataclasses import dataclass, replace

from engine.legion.legion import GateFn  # noqa: F401 — re-export friendliness

CypherRunner = "Callable[[str, dict], list[dict]]"

# C(S) 5-predicate fields an AtomicSpan must carry to cross the Crystallization Frontier
# (apt-sp/SKILL.md §C(S)). A leaf AptSpan missing any of these blocks PH3_SP → PH4_ST.
_C_S_FIELDS = ("objective", "definition", "keyAssertion", "verification", "c_s_predicate")


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
class Blocker:
    """A concrete node blocking advance to the next phase (the *delta* to close). Deterministic —
    read straight off the KG, no reasoning. Mirrors OpenSpec delta-spec ('only what's changing'),
    grounded in the graph instead of a markdown file."""

    node: str
    reason: str


@dataclass(frozen=True)
class PhaseStatus:
    phase: str
    next_skill: str
    evidence: str
    blockers: tuple[Blocker, ...] = ()  # delta-gap; empty unless with_blockers requested (back-compat)


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


# ---- delta-gap blockers (the "what's blocking this phase" half) ----
# Each query lists the *specific* nodes that keep the current phase from advancing. LIMIT keeps a
# runaway span-count from flooding the terminal; a full count stays in evidence.
_BLOCKER_LIMIT = 20

# PH3_SP: leaf AptSpans that have NOT crossed the Crystallization Frontier — structural signal
# (leaf AND not AtomicSpan-labeled), schema-robust across KGs. The 5 C(S) null-flags *enrich* the
# reason when the KG populates them; where the C(S) convention isn't used the parser degrades to a
# coarse "needs crystallization" instead of falsely flagging all 5 as missing.
_Q_BLOCK_SP = (
    "MATCH (sa:SemanticAnchor {name:$target})-[:HAS_ROOT]->(root:AptSpan) "
    "MATCH (root)-[:DECOMPOSES_TO*0..6]->(s:AptSpan) "
    "WHERE NOT (s)-[:DECOMPOSES_TO]->() AND NOT s:AtomicSpan "
    "RETURN s.name AS node, "
    "s.objective IS NULL AS objective, s.definition IS NULL AS definition, "
    "s.keyAssertion IS NULL AS keyAssertion, s.verification IS NULL AS verification, "
    "s.c_s_predicate IS NULL AS c_s_predicate "
    "ORDER BY node LIMIT " + str(_BLOCKER_LIMIT)
)
# PH4_ST: AtomicSpan leaves with no crystallized Contract yet.
_Q_BLOCK_ST = (
    "MATCH (sa:SemanticAnchor {name:$target})-[:HAS_ROOT]->(:AptSpan)"
    "-[:DECOMPOSES_TO*1..6]->(leaf:AtomicSpan) "
    "WHERE NOT (leaf)-[:HAS_CONTRACT]->(:Contract) "
    "RETURN leaf.name AS node ORDER BY node LIMIT " + str(_BLOCKER_LIMIT)
)
# PH5_SCW: Contracts with no materialized SourceCodeNode (spec written, code not yet).
_Q_BLOCK_SCW = (
    "MATCH (sa:SemanticAnchor {name:$target})-[:HAS_ROOT]->(:AptSpan)"
    "-[:DECOMPOSES_TO*1..6]->(:AtomicSpan)-[:HAS_CONTRACT]->(c:Contract) "
    "WHERE NOT (c)-[:MATERIALIZES]->(:SourceCodeNode) "
    "RETURN c.name AS node ORDER BY node LIMIT " + str(_BLOCKER_LIMIT)
)

# Phases whose blockers are actionable (each has a defined delta query). Terminal/bootstrap phases
# (feedback, bootstrap, UNKNOWN) intentionally report no hard blockers.
_BLOCKABLE = frozenset({"PH3_SP", "PH4_ST", "PH5_SCW"})


def _parse_sp_blockers(rows) -> tuple[Blocker, ...]:
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        missing = [f for f in _C_S_FIELDS if r.get(f)]
        if len(missing) == len(_C_S_FIELDS):
            # all 5 null == KG doesn't populate C(S) here → coarse (avoid false "missing all 5" noise)
            reason = "needs crystallization (not yet AtomicSpan)"
        elif missing:
            reason = "missing C(S): " + ", ".join(missing)
        else:
            reason = "not atomic (no C(S) predicate missing but unlabeled)"
        out.append(Blocker(node=str(r.get("node")), reason=reason))
    return tuple(out)


def _simple_blockers(rows, reason: str) -> tuple[Blocker, ...]:
    return tuple(
        Blocker(node=str(r.get("node")), reason=reason) for r in rows if isinstance(r, dict)
    )


def fetch_blockers(target: str, phase: str, run_cypher) -> tuple[Blocker, ...]:
    """The specific nodes blocking advance from `phase`. Graceful: () on any backend error
    (unsupported/unreachable) — a missing delta is 'unknown', never a crash or false 'clear'."""
    params = {"target": target}
    try:
        if phase == "PH3_SP":
            return _parse_sp_blockers(run_cypher(_Q_BLOCK_SP, params))
        if phase == "PH4_ST":
            return _simple_blockers(
                run_cypher(_Q_BLOCK_ST, params), "no Contract (HAS_CONTRACT edge missing)"
            )
        if phase == "PH5_SCW":
            return _simple_blockers(
                run_cypher(_Q_BLOCK_SCW, params), "no code (MATERIALIZES→SourceCodeNode missing)"
            )
    except Exception:  # noqa: BLE001 — backend unsupported/unreachable => no delta, not a crash
        return ()
    return ()


def detect_phase(target: str, run_cypher, *, with_blockers: bool = False) -> PhaseStatus:
    """Phase + next skill. With `with_blockers`, also attach the delta-gap for actionable phases
    (default off so batch navigation and existing callers stay cheap / unchanged)."""
    status = classify_phase(fetch_facts(target, run_cypher))
    if with_blockers and status.phase in _BLOCKABLE:
        blockers = fetch_blockers(target, status.phase, run_cypher)
        if blockers:
            status = replace(status, blockers=blockers)
    return status


_Q_ALL_SA = (
    "MATCH (sa:SemanticAnchor) WHERE coalesce(sa.status,'active')='active' "
    "RETURN sa.name AS name ORDER BY sa.name"
)


def list_active_sas(run_cypher) -> list[str] | None:
    """All active SemanticAnchor names, or None if the backend can't answer."""
    try:
        rows = run_cypher(_Q_ALL_SA, {})
    except Exception:  # noqa: BLE001
        return None
    out = []
    for r in rows:
        name = r.get("name") if isinstance(r, dict) else None
        out.append(name if name is not None else next(iter(r.values())))
    return out


def detect_all(run_cypher) -> list[tuple[str, PhaseStatus]]:
    """Navigate every active SA → (name, PhaseStatus). Empty if backend can't answer."""
    names = list_active_sas(run_cypher)
    if names is None:
        return []
    return [(n, detect_phase(n, run_cypher)) for n in names]


__all__ = [
    "Blocker",
    "PhaseFacts",
    "PhaseStatus",
    "classify_phase",
    "detect_all",
    "detect_phase",
    "fetch_blockers",
    "fetch_facts",
    "list_active_sas",
]
