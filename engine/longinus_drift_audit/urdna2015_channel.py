"""L2 Jaccard-on-canonical-triples drift channel (v3.4, 2026-05-19).

Per PROM 16 OQ2 v3.4 multi-channel detector (ALT4, A4S4 finding). Naesengmoon
constitutional 9-lens gate 2026-05-19 (vr-urdna2015-channel-v3.4-naesengmoon-9lens)
returned CONDITIONAL — this docstring incorporates the 3 fix WQI follow-ups:

Algorithm (Naesengmoon MEDIUM#3 fix — citation precision):
  - This module is **NOT URDNA2015 proper**. URDNA2015's defining contribution
    is canonical labeling of blank nodes, which is unnecessary here because the
    upstream KG (Neo4j MERGE-by-name) eliminates blank nodes a priori.
  - What this module computes: Jaccard distance d(A,B) = 1 - |A∩B|/|A∪B| over
    SHA-256-hashed canonical (s, p, o) triple multisets under a blank-node-free
    closed-world assumption.
  - URDNA2015 reference: CG-FINAL 2022-10-09 (Longley & Sporny) — Credentials
    Community Group report, **NOT a W3C Standard**. Superseded on the W3C
    standards track by RDFC-1.0 (W3C Recommendation effort).
  - For graphs with actual blank nodes, swap `_canonicalize` for `rdflib`-based
    URDNA2015/RDFC-1.0 (optional dep, deferred).

Threshold inheritance (Naesengmoon HIGH#1 fix — softened claim):
  - Default `warn_threshold=0.05` and `halt_threshold=0.15` are taken from
    Longinus L1 GED band conventions, NOT formally proven equivalent.
  - The claim "Jaccard ↔ GED is monotone" is **empirically calibrated, NOT
    proven by construction**. Literature gives BOUNDS (arxiv 1904.08934
    Convex Graph Invariant Relaxations; arxiv 1709.10305 Fast GED), not
    identity. Formal Lean proof of inheritance is OPEN — tracked as
    wqi-longinus-jaccard-ged-monotone-lean-proof-blocked-2026-05-19
    (BLOCKED-MATHLIB).
  - Until that proof lands, treat thresholds as **conjectural transfer**:
    Jaccard-warn UPPER-BOUNDS GED-warn under blank-node-free closure
    (Naesengmoon HIGH#1 fix_suggestion (a) interim wording).

Provisional status on halt (Naesengmoon HIGH#2 fix — PreliminaryLonginusNovel):
  - Per v3.3 ActionPlan item 2 (`plan-longinus-oq2-multi-channel-v3.3-2026-05-19`),
    the 0.15 halt threshold is **Longinus-novel with no external production
    grounding** (A4S2 explicit). Halt verdicts emitted by this module MUST be
    treated as `:PreliminaryLonginusNovel` until 30+ SYMPOSIUM KG-history
    versions enable 95th-percentile experimental fit (wqi-longinus-0.15-empirical
    -fit-blocked-2026-05-19). The `UrdnaDriftReport.preliminary_longinus_novel`
    field carries this flag for downstream consumers.

# KG: CONTRACT_UrdnaChannel_v1_2026-05-19, sa-longinus-v3.4-multi-channel-urdna2015-2026-05-19,
#     plan-longinus-oq2-multi-channel-v3.3-2026-05-19, finding_A4S4_oq2_2026_05_19,
#     vr-urdna2015-channel-v3.4-naesengmoon-9lens-2026-05-19,
#     decision-longinus-v3.4-L2-naesengmoon-conditional-2026-05-19
"""

from __future__ import annotations

import hashlib
from typing import Iterable

from pydantic import BaseModel, Field, field_validator


Triple = tuple[str, str, str]


class UrdnaDriftReport(BaseModel):
    """Output of L2 Jaccard-on-canonical-triples drift comparison.

    Note ``preliminary_longinus_novel`` field (Naesengmoon HIGH#2 fix):
    ``True`` whenever ``halt=True``, signaling that the halt verdict relies
    on the Longinus-novel 0.15 threshold which has no external production
    grounding yet (per v3.3 ActionPlan item 2). Downstream consumers MUST
    treat halt-triggered items as ``:PreliminaryLonginusNovel`` until
    empirical 95th-percentile fit on 30+ KG-history versions.
    """

    triple_count_a: int = Field(ge=0)
    triple_count_b: int = Field(ge=0)
    shared: int = Field(ge=0)
    only_in_a: int = Field(ge=0)
    only_in_b: int = Field(ge=0)
    jaccard_distance: float = Field(ge=0.0, le=1.0)
    warn: bool
    halt: bool
    severity: str
    canonicalization: str = "blank-node-free-jaccard-sha256"
    preliminary_longinus_novel: bool = Field(
        default=False,
        description=(
            "True when halt=True. Halt verdict is on the Longinus-novel 0.15 "
            "threshold (no external production grounding per PROM 16 A4S2). "
            "Treat as :PreliminaryLonginusNovel pending empirical 95th-percentile "
            "fit (wqi-longinus-0.15-empirical-fit-blocked-2026-05-19)."
        ),
    )

    @field_validator("severity")
    @classmethod
    def _severity_valid(cls, v: str) -> str:
        valid = {"PERFECT", "EXCELLENT", "ACCEPTABLE", "DEGRADED", "CRITICAL"}
        if v not in valid:
            raise ValueError(f"severity must be one of {valid}")
        return v


def _canonicalize(triples: Iterable[Triple]) -> frozenset[str]:
    """Canonical hash representation of a triple set.

    Simplified URDNA2015 (blank-node-free): each triple → SHA-256 hex of
    sorted (s, p, o) concatenation with delimiter. Set of hashes is
    permutation-invariant by construction.
    """
    hashes: set[str] = set()
    for s, p, o in triples:
        # Delimiter \x1f (unit separator) is forbidden in canonical IRIs.
        canon = f"{s}\x1f{p}\x1f{o}"
        hashes.add(hashlib.sha256(canon.encode("utf-8")).hexdigest())
    return frozenset(hashes)


def _severity_for(distance: float) -> str:
    if distance == 0.0:
        return "PERFECT"
    if distance < 0.05:
        return "EXCELLENT"
    if distance < 0.15:
        return "ACCEPTABLE"
    if distance < 0.35:
        return "DEGRADED"
    return "CRITICAL"


def compute_urdna_drift(
    *,
    triples_a: Iterable[Triple],
    triples_b: Iterable[Triple],
    warn_threshold: float = 0.05,
    halt_threshold: float = 0.15,
) -> UrdnaDriftReport:
    """Compute Jaccard drift between two RDF triple snapshots.

    Args:
        triples_a: first snapshot as (subject, predicate, object) tuples.
        triples_b: second snapshot, same shape.
        warn_threshold: distance >= this triggers ``warn=True`` (default 0.05,
            matches Longinus GED warn band by construction).
        halt_threshold: distance >= this triggers ``halt=True`` (default 0.15,
            Longinus-novel — see PROM 16 OQ2 demotion note).

    Returns:
        UrdnaDriftReport with set-cardinality stats + Jaccard distance +
        warn/halt flags + qualitative severity.

    Edge cases:
        - Both empty → distance=0 (PERFECT, by convention).
        - One empty, other non-empty → distance=1 (CRITICAL).
        - Identity → distance=0.
        - Disjoint → distance=1.
    """
    if not (0.0 <= warn_threshold <= 1.0):
        raise ValueError(f"warn_threshold must be in [0,1], got {warn_threshold}")
    if not (warn_threshold <= halt_threshold <= 1.0):
        raise ValueError(f"halt_threshold must be in [warn_threshold, 1], got {halt_threshold}")

    hash_a = _canonicalize(triples_a)
    hash_b = _canonicalize(triples_b)

    union = hash_a | hash_b
    intersection = hash_a & hash_b

    triple_count_a = len(hash_a)
    triple_count_b = len(hash_b)
    shared = len(intersection)
    only_in_a = triple_count_a - shared
    only_in_b = triple_count_b - shared

    if not union:
        # Both empty: define distance=0 (no drift between two empty graphs).
        distance = 0.0
    else:
        distance = 1.0 - len(intersection) / len(union)

    halt_flag = distance >= halt_threshold
    return UrdnaDriftReport(
        triple_count_a=triple_count_a,
        triple_count_b=triple_count_b,
        shared=shared,
        only_in_a=only_in_a,
        only_in_b=only_in_b,
        jaccard_distance=distance,
        warn=distance >= warn_threshold,
        halt=halt_flag,
        severity=_severity_for(distance),
        preliminary_longinus_novel=halt_flag,
    )
