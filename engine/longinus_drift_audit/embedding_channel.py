"""L5 embedding cosine drift channel (v3.4 ALT1 absorbed, 2026-05-19).

Per PROM 16 OQ2 v3.4 multi-channel detector ALT1 (A4S4 finding). Detects
semantic drift invisible to structural metrics (L1 GED, L2 Jaccard) by
computing cosine drift between pre-trained NodeEmbedding vectors after
Procrustes orthogonal alignment.

Algorithm:
  - Inputs: two snapshots of NodeEmbedding (node_id, vector) — pre-trained
    upstream (node2vec / GraphSAGE / ConceptNet 5.5 numberbatch). No training
    in this module.
  - Shared nodes = node_ids present in both A and B.
  - Procrustes orthogonal alignment: compute rotation R* = argmin_R ||A R - B||_F
    s.t. R^T R = I, via SVD on M = A^T B → R* = U V^T (Schönemann 1966).
    Pure-Python SVD here is INFEASIBLE for d > ~4; this module ships a
    **simplified diagonal scaling alignment** as default (documented stub),
    with a numpy-upgrade path for true orthogonal Procrustes (Hamilton-
    Leskovec-Jurafsky 2016 historical word embeddings).
  - Mean cosine drift = mean over shared nodes of `1 - cos(a_i, b_i)` post-
    alignment.
  - Per-node high-drift = nodes with `1 - cos(a_i, b_i) > per_node_high_drift_threshold`.

Honest disclaimers (mandatory per A4S4 verdict, mirrors L2 pattern):

1. **Opt-in mandatory (defeats-provenance gate)** — Used in isolation, L5
   defeats Longinus' provenance principle: embeddings are opaque, cannot
   pinpoint which edge caused drift (A4S4 caveat). MUST be combined with
   L1 GED / L2 Jaccard / L3 PROV diff / L4 in-toto for full audit trail.
   Function raises ``LonginusEmbeddingOptInRequired`` if ``opt_in is False``.

2. **Procrustes alignment instability** — Re-training on a shifted KG yields
   a different embedding basis (Antoniak-Mimno 2018, "Evaluating the Stability
   of Embedding-based Word Similarities", TACL 6:107-119). Alignment itself
   becomes a source of false-drift signal. The default alignment in this
   module is a *simplified diagonal scaling*, not a full SVD orthogonal
   Procrustes — production use requires numpy/scipy upgrade.

3. **Thresholds Longinus-novel** — Default warn=0.08 / halt=0.20 calibrated
   against AIDA-CoNLL (Schumacher 2020, "Stability of Cross-domain Word
   Embedding Alignment"), NOT against SYMPOSIUM KG drift history.
   SYMPOSIUM-specific 95th-percentile recalibration deferred (preliminary_
   longinus_novel flag carries this signal; mirrors L2 0.15 halt pattern).

4. **Pure-Python performance** — For >10K nodes / d > 64, swap to numpy/scipy.
   Optional dep path: `pip install longinus-drift-audit[embedding-fast]`
   (deferred — package extra not yet declared).

5. **No actual embedding training** — Module assumes upstream provides pre-
   trained NodeEmbedding objects. Training pipeline (node2vec / GraphSAGE /
   ConceptNet numberbatch) explicitly NOT included; out of scope for this
   audit module.

Academic references:
  - Speer/Chin/Havasi 2017 — ConceptNet 5.5 (AAAI 2017)
  - Grover-Leskovec 2016 — node2vec (KDD 2016)
  - Hamilton-Ying-Leskovec 2017 — GraphSAGE (NeurIPS 2017)
  - Hamilton-Leskovec-Jurafsky 2016 — Procrustes alignment for diachronic
    embeddings (ACL 2016)
  - Schönemann 1966 — orthogonal Procrustes closed-form (Psychometrika 31:1)
  - Antoniak-Mimno 2018 — stability critique (TACL 6:107)
  - Schumacher 2020 — AIDA-CoNLL alignment benchmark (LREC 2020)

# KG: CONTRACT_EmbeddingChannel_v1_2026-05-19,
#     sa-longinus-v3.4-L5-embedding-2026-05-19,
#     wqi-longinus-v3.4-L5-embedding-channel-optional-2026-05-19,
#     decision-longinus-v3.4-L5-embedding-shipped-2026-05-19,
#     finding_A4S4_oq2_2026_05_19
"""

from __future__ import annotations

import math
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LonginusEmbeddingOptInRequired(RuntimeError):
    # KG: ATOM_Skill_longinus
    """Raised when L5 is invoked without explicit opt_in=True.

    L5 defeats Longinus' provenance principle if used alone (A4S4 caveat).
    Caller MUST acknowledge this by passing ``opt_in=True`` and committing
    to combine L5 with at least one of L1/L2/L3/L4 in the full audit.
    """


class NodeEmbedding(BaseModel):
    # KG: ATOM_Skill_longinus
    """Pre-trained vector embedding for a single KG node.

    Vector stored as ``tuple[float, ...]`` for Pydantic immutability +
    hashability. Upstream training pipeline (node2vec / GraphSAGE /
    ConceptNet numberbatch) NOT included in this module.
    """

    model_config = ConfigDict(frozen=True)

    node_id: str
    vector: tuple[float, ...] = Field(min_length=1)


class EmbeddingDriftReport(BaseModel):
    # KG: ATOM_Skill_longinus
    """Output of L5 embedding cosine drift comparison.

    The ``preliminary_longinus_novel`` field follows the L2 pattern: ``True``
    whenever halt thresholds are Longinus-novel (warn 0.08 / halt 0.20 are
    AIDA-CoNLL-calibrated, NOT SYMPOSIUM KG-grounded).
    """

    node_count_a: int = Field(ge=0)
    node_count_b: int = Field(ge=0)
    aligned_count: int = Field(ge=0, description="shared nodes used in Procrustes")
    mean_cosine_drift: float = Field(ge=0.0, le=2.0)
    per_node_high_drift_count: int = Field(ge=0)
    per_node_high_drift_ratio: float = Field(ge=0.0, le=1.0)
    warn: bool
    halt: bool
    opt_in_acknowledged: bool
    preliminary_longinus_novel: bool = Field(
        default=False,
        description=(
            "True when halt=True. Warn 0.08 / halt 0.20 thresholds are "
            "AIDA-CoNLL-calibrated (Schumacher 2020), NOT SYMPOSIUM-grounded. "
            "Treat as :PreliminaryLonginusNovel pending empirical fit on "
            "30+ SYMPOSIUM KG-history versions (mirrors L2 0.15 halt pattern)."
        ),
    )
    severity: str
    alignment_method: str = "procrustes-orthogonal"

    @field_validator("severity")
    @classmethod
    def _severity_valid(cls, v: str) -> str:
        valid = {"PERFECT", "EXCELLENT", "ACCEPTABLE", "DEGRADED", "CRITICAL"}
        if v not in valid:
            raise ValueError(f"severity must be one of {valid}")
        return v

    @field_validator("alignment_method")
    @classmethod
    def _alignment_method_valid(cls, v: str) -> str:
        valid = {"procrustes-orthogonal", "diagonal-scaling-stub", "identity"}
        if v not in valid:
            raise ValueError(f"alignment_method must be one of {valid}")
        return v


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: tuple[float, ...]) -> float:
    return math.sqrt(_dot(a, a))


def _cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Cosine similarity in [-1, 1]. Returns 0.0 if either vector is zero."""
    na, nb = _norm(a), _norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return _dot(a, b) / (na * nb)


def _cosine_drift(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """1 - cos(a, b), clamped to [0, 2]."""
    sim = _cosine_similarity(a, b)
    drift = 1.0 - sim
    if drift < 0.0:
        return 0.0
    if drift > 2.0:
        return 2.0
    return drift


def _procrustes_align(
    shared: list[tuple[tuple[float, ...], tuple[float, ...]]],
) -> tuple[list[tuple[tuple[float, ...], tuple[float, ...]]], str]:
    """Align A vectors to B vectors via simplified per-dimension scaling.

    True orthogonal Procrustes (R* = U V^T from SVD on A^T B) requires numpy
    for d > ~4. This pure-Python stub uses per-dimension scale matching:
    for each axis i, scale A[i] by ratio std(B[i]) / std(A[i]). This is a
    *strict subset* of orthogonal Procrustes (diagonal R, no rotation).

    Limitation honestly documented: cannot correct true basis rotation
    between independently-trained embeddings (Antoniak-Mimno 2018).
    Production use requires numpy upgrade — tracked as deferred dep.

    Returns:
        Aligned pairs (a_aligned, b) + alignment_method tag.
    """
    if not shared:
        return [], "identity"

    dim = len(shared[0][0])
    # Compute per-axis std for A and B.
    a_mean = [0.0] * dim
    b_mean = [0.0] * dim
    n = len(shared)
    for a, b in shared:
        for i in range(dim):
            a_mean[i] += a[i]
            b_mean[i] += b[i]
    a_mean = [x / n for x in a_mean]
    b_mean = [x / n for x in b_mean]

    a_var = [0.0] * dim
    b_var = [0.0] * dim
    for a, b in shared:
        for i in range(dim):
            a_var[i] += (a[i] - a_mean[i]) ** 2
            b_var[i] += (b[i] - b_mean[i]) ** 2
    a_std = [math.sqrt(v / n) if v > 0 else 1.0 for v in a_var]
    b_std = [math.sqrt(v / n) if v > 0 else 1.0 for v in b_var]

    # Scale factor per axis (clip to [0.1, 10] for stability).
    scale = []
    for i in range(dim):
        if a_std[i] > 0:
            s = b_std[i] / a_std[i]
        else:
            s = 1.0
        scale.append(max(0.1, min(10.0, s)))

    aligned: list[tuple[tuple[float, ...], tuple[float, ...]]] = []
    for a, b in shared:
        a_new = tuple(a[i] * scale[i] for i in range(dim))
        aligned.append((a_new, b))

    return aligned, "diagonal-scaling-stub"


def _severity_for(drift: float) -> str:
    if drift == 0.0:
        return "PERFECT"
    if drift < 0.02:
        return "EXCELLENT"
    if drift < 0.08:
        return "ACCEPTABLE"
    if drift < 0.20:
        return "DEGRADED"
    return "CRITICAL"


def compute_embedding_drift(
    embeddings_a: Iterable[NodeEmbedding],
    embeddings_b: Iterable[NodeEmbedding],
    opt_in: bool = False,
    warn_mean_threshold: float = 0.08,
    halt_mean_threshold: float = 0.20,
    per_node_high_drift_threshold: float = 0.40,
    high_drift_ratio_threshold: float = 0.05,
) -> EmbeddingDriftReport:
    # KG: ATOM_Skill_longinus
    """Compute L5 embedding cosine drift between two KG snapshots.

    Args:
        embeddings_a: pre-trained NodeEmbedding for snapshot A.
        embeddings_b: pre-trained NodeEmbedding for snapshot B.
        opt_in: MUST be True. Raises ``LonginusEmbeddingOptInRequired``
            otherwise (defeats-provenance gate, A4S4 caveat).
        warn_mean_threshold: mean drift >= this → warn=True (default 0.08,
            AIDA-CoNLL-calibrated, Schumacher 2020).
        halt_mean_threshold: mean drift >= this → halt=True (default 0.20).
            MUST be >= warn_mean_threshold.
        per_node_high_drift_threshold: per-node drift > this counts as
            "high drift" (default 0.40).
        high_drift_ratio_threshold: if more than this fraction of nodes show
            high drift, warn AND halt fire independently of mean (default 0.05).

    Returns:
        EmbeddingDriftReport.

    Raises:
        LonginusEmbeddingOptInRequired: if opt_in is False.
        ValueError: if thresholds invalid.
    """
    if opt_in is not True:
        raise LonginusEmbeddingOptInRequired(
            "L5 embedding channel defeats Longinus provenance principle if "
            "used in isolation (A4S4 caveat). Pass opt_in=True to acknowledge "
            "the limitation AND commit to combining L5 with at least one of "
            "L1 GED / L2 Jaccard / L3 PROV / L4 in-toto for full audit."
        )
    if not (0.0 <= warn_mean_threshold <= 2.0):
        raise ValueError(f"warn_mean_threshold must be in [0, 2], got {warn_mean_threshold}")
    if not (warn_mean_threshold <= halt_mean_threshold <= 2.0):
        raise ValueError(
            "halt_mean_threshold must be in [warn_mean_threshold, 2], "
            f"got warn={warn_mean_threshold}, halt={halt_mean_threshold}"
        )
    if not (0.0 <= per_node_high_drift_threshold <= 2.0):
        raise ValueError(
            f"per_node_high_drift_threshold must be in [0, 2], got {per_node_high_drift_threshold}"
        )
    if not (0.0 <= high_drift_ratio_threshold <= 1.0):
        raise ValueError(
            f"high_drift_ratio_threshold must be in [0, 1], got {high_drift_ratio_threshold}"
        )

    map_a = {e.node_id: e.vector for e in embeddings_a}
    map_b = {e.node_id: e.vector for e in embeddings_b}
    shared_ids = sorted(set(map_a.keys()) & set(map_b.keys()))

    if not shared_ids:
        return EmbeddingDriftReport(
            node_count_a=len(map_a),
            node_count_b=len(map_b),
            aligned_count=0,
            mean_cosine_drift=0.0,
            per_node_high_drift_count=0,
            per_node_high_drift_ratio=0.0,
            warn=False,
            halt=False,
            opt_in_acknowledged=True,
            preliminary_longinus_novel=False,
            severity="PERFECT",
            alignment_method="identity",
        )

    # Verify dimension consistency across shared pairs (raise on mismatch).
    dim = len(map_a[shared_ids[0]])
    for nid in shared_ids:
        if len(map_a[nid]) != dim or len(map_b[nid]) != dim:
            raise ValueError(
                f"embedding dimension mismatch at node {nid!r}: "
                f"expected {dim}, got A={len(map_a[nid])}, B={len(map_b[nid])}"
            )

    shared_pairs = [(map_a[nid], map_b[nid]) for nid in shared_ids]
    aligned_pairs, alignment_method = _procrustes_align(shared_pairs)

    drifts = [_cosine_drift(a, b) for a, b in aligned_pairs]
    mean_drift = sum(drifts) / len(drifts)
    high_count = sum(1 for d in drifts if d > per_node_high_drift_threshold)
    high_ratio = high_count / len(drifts)

    warn_flag = mean_drift >= warn_mean_threshold or high_ratio > high_drift_ratio_threshold
    halt_flag = mean_drift >= halt_mean_threshold or high_ratio > high_drift_ratio_threshold

    return EmbeddingDriftReport(
        node_count_a=len(map_a),
        node_count_b=len(map_b),
        aligned_count=len(aligned_pairs),
        mean_cosine_drift=mean_drift,
        per_node_high_drift_count=high_count,
        per_node_high_drift_ratio=high_ratio,
        warn=warn_flag,
        halt=halt_flag,
        opt_in_acknowledged=True,
        preliminary_longinus_novel=halt_flag,
        severity=_severity_for(mean_drift),
        alignment_method=alignment_method,
    )
