"""L3 PROV-based causal-flow drift channel (v3.4, 2026-05-19).

Per PROM 16 OQ2 ALT5 (PROV-based diff, A4S4 finding). Models KG mutations
as W3C PROV-DM 2013 (Moreau-Missier 2013) Activity / Agent / Entity
triples and detects bursts in the activity rate via EWMA baseline.

Background:
  - W3C PROV-DM 2013 defines :Activity (a time-bounded action), :Agent
    (responsible party), :Entity (mutated artifact), and
    ``prov:wasDerivedFrom`` / ``prov:wasInvalidatedBy`` relations.
  - This channel is **orthogonal** to L1 GED (structural edit distance)
    and L2 URDNA2015 Jaccard (triple-set overlap). L3 measures *causal
    flow burstiness* — a graph can be structurally identical to a prior
    snapshot yet show a 10x burst of authoring activity (e.g., a
    runaway agent commits + rolls back a 1000 mutations in a window).
    Do NOT claim L3 is monotone-related to GED (A4S4 explicit caveat).

Heuristics (NOT formally derived from PROV-DM spec):
  - ``activity_rate >= 2x EWMA baseline`` → warn.
  - ``activity_rate >= 10x EWMA baseline`` → halt.
  - ``distinct_agents > 3x baseline-window distinct count`` → multi-author flag.
  - ``rollback_chain_max_depth > rollback_storm_threshold`` (default 5)
    → rollback storm marker (cascade via
    ``prov:wasInvalidatedBy``-style ``derived_from`` chain).

Threshold tuning is domain-dependent: academic / curated KGs run at
~0.1 activity/sec baseline, operational / agent-driven KGs can sustain
~10 activity/sec. Calibrate ``warn_ratio`` / ``halt_ratio`` per deployment.

# KG: CONTRACT_ProvChannel_v1_2026-05-19, sa-longinus-v3.4-L3-prov-diff-2026-05-19,
#     plan-longinus-oq2-multi-channel-v3.3-2026-05-19, finding_A4S4_oq2_2026_05_19
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from pydantic import BaseModel, Field, field_validator


class ProvActivity(BaseModel):
    # KG: ATOM_Skill_longinus
    """W3C PROV-DM 2013 Activity record.

    Minimal projection: when (timestamp), who (agent), what (action verb on
    entity), and optional causal antecedent (``derived_from`` — models
    ``prov:wasDerivedFrom`` for forward chains and
    ``prov:wasInvalidatedBy`` for rollback chains; the channel treats
    both as parent-pointer edges for cycle / depth analysis).
    """

    timestamp: datetime
    agent: str = Field(min_length=1)
    action: str = Field(min_length=1)
    entity: str = Field(min_length=1)
    derived_from: Optional[str] = None


class ProvDriftReport(BaseModel):
    # KG: ATOM_Skill_longinus
    """Output of L3 PROV-based causal-flow drift comparison."""

    activity_count: int = Field(ge=0)
    baseline_ewma: float = Field(ge=0.0)
    current_rate: float = Field(ge=0.0)
    ratio: float = Field(ge=0.0)
    distinct_agents: int = Field(ge=0)
    rollback_chain_max_depth: int = Field(ge=0)
    warn: bool
    halt: bool
    multi_author_flag: bool
    severity: str
    channel: str = "L3-prov-causal-flow"

    @field_validator("severity")
    @classmethod
    def _severity_valid(cls, v: str) -> str:
        valid = {"QUIET", "NORMAL", "BURST", "STORM", "ROLLBACK_STORM"}
        if v not in valid:
            raise ValueError(f"severity must be one of {valid}")
        return v


def _ewma(values: Iterable[float], alpha: float) -> float:
    """Exponentially-weighted moving average. Initialized with first sample."""
    ewma: Optional[float] = None
    for v in values:
        ewma = v if ewma is None else alpha * v + (1.0 - alpha) * ewma
    return ewma if ewma is not None else 0.0


def _windowed_rates(activities: list[ProvActivity], window_count: int) -> list[float]:
    """Bucket activities into fixed-count windows and compute per-window rates.

    Rate = activities / span_seconds. Activities are pre-sorted by timestamp.
    A window with a single activity (zero span) is assigned rate=1.0 by
    convention (avoid div-by-zero while still signalling "burst").
    """
    rates: list[float] = []
    if window_count <= 0 or not activities:
        return rates
    for i in range(0, len(activities), window_count):
        bucket = activities[i : i + window_count]
        if len(bucket) < 2:
            rates.append(float(len(bucket)))
            continue
        span = (bucket[-1].timestamp - bucket[0].timestamp).total_seconds()
        if span <= 0.0:
            rates.append(float(len(bucket)))
        else:
            rates.append(len(bucket) / span)
    return rates


def _max_rollback_chain_depth(activities: list[ProvActivity]) -> int:
    """Compute longest ``derived_from`` chain length over entity history.

    Builds entity → parent_entity map (most recent ``derived_from`` wins).
    Cycle-safe via visited set.
    """
    parent: dict[str, str] = {}
    for a in activities:
        if a.derived_from:
            parent[a.entity] = a.derived_from

    max_depth = 0
    for entity in parent:
        depth = 0
        visited: set[str] = set()
        cur: Optional[str] = entity
        while cur is not None and cur in parent and cur not in visited:
            visited.add(cur)
            cur = parent.get(cur)
            depth += 1
        max_depth = max(max_depth, depth)
    return max_depth


def _severity_for(*, warn: bool, halt: bool, rollback_storm: bool) -> str:
    if rollback_storm:
        return "ROLLBACK_STORM"
    if halt:
        return "STORM"
    if warn:
        return "BURST"
    return "NORMAL"


_EMPTY_REPORT = ProvDriftReport(
    activity_count=0,
    baseline_ewma=0.0,
    current_rate=0.0,
    ratio=0.0,
    distinct_agents=0,
    rollback_chain_max_depth=0,
    warn=False,
    halt=False,
    multi_author_flag=False,
    severity="QUIET",
)


def _validate_drift_inputs(
    *,
    ewma_alpha: float,
    warn_ratio: float,
    halt_ratio: float,
    baseline_window_count: int,
    current_window_count: int,
) -> None:
    if not (0.0 < ewma_alpha <= 1.0):
        raise ValueError(f"ewma_alpha must be in (0, 1], got {ewma_alpha}")
    if warn_ratio <= 0.0 or halt_ratio <= 0.0:
        raise ValueError("warn_ratio and halt_ratio must be > 0")
    if warn_ratio >= halt_ratio:
        raise ValueError(f"warn_ratio ({warn_ratio}) must be < halt_ratio ({halt_ratio})")
    if baseline_window_count <= 0 or current_window_count <= 0:
        raise ValueError("window counts must be > 0")


def _split_windows(
    acts: list[ProvActivity],
    current_window_count: int,
) -> tuple[list[ProvActivity], list[ProvActivity]]:
    if len(acts) <= current_window_count:
        return [], acts
    return acts[:-current_window_count], acts[-current_window_count:]


def _current_rate_for(current_acts: list[ProvActivity]) -> float:
    if len(current_acts) < 2:
        return float(len(current_acts))
    span = (current_acts[-1].timestamp - current_acts[0].timestamp).total_seconds()
    if span <= 0.0:
        return float(len(current_acts))
    return len(current_acts) / span


def _ratio_with_cold_start(
    current_rate: float,
    baseline_ewma: float,
    halt_ratio: float,
) -> float:
    if baseline_ewma <= 0.0:
        # No usable baseline. If there is *any* current activity, treat as
        # saturating burst (ratio = halt_ratio) to avoid div-by-zero while
        # signalling cold-start anomaly.
        return halt_ratio if current_rate > 0.0 else 0.0
    return current_rate / baseline_ewma


def compute_prov_drift(
    activities: Iterable[ProvActivity],
    *,
    baseline_window_count: int = 100,
    current_window_count: int = 10,
    ewma_alpha: float = 0.3,
    warn_ratio: float = 2.0,
    halt_ratio: float = 10.0,
    multi_author_threshold_ratio: float = 3.0,
    rollback_storm_threshold: int = 5,
) -> ProvDriftReport:
    # KG: ATOM_Skill_longinus
    """Compute L3 PROV-DM causal-flow drift.

    Args:
        activities: PROV Activity records (any order; sorted internally).
        baseline_window_count: activities per baseline window (default 100).
        current_window_count: activities per current window (default 10).
        ewma_alpha: EWMA smoothing factor in (0, 1] (default 0.3).
        warn_ratio: current/baseline ratio threshold for ``warn`` (default 2.0).
        halt_ratio: current/baseline ratio threshold for ``halt`` (default 10.0).
        multi_author_threshold_ratio: distinct_agents must exceed
            ``baseline_distinct * ratio`` to set ``multi_author_flag``
            (default 3.0).
        rollback_storm_threshold: ``derived_from`` chain depth that elevates
            severity to ``ROLLBACK_STORM`` (default 5).

    Returns:
        ProvDriftReport with rate stats, EWMA baseline, distinct-agent counts,
        rollback chain depth, warn / halt / multi-author flags, and severity.

    Edge cases:
        - Empty activities → all-zero report, severity=QUIET.
        - Baseline EWMA = 0 (e.g. single-event window) and current_rate > 0 →
          ratio is set to ``halt_ratio`` (max-saturate) to avoid div-by-zero
          while preserving the "any burst from quiet" semantic.
    """
    _validate_drift_inputs(
        ewma_alpha=ewma_alpha,
        warn_ratio=warn_ratio,
        halt_ratio=halt_ratio,
        baseline_window_count=baseline_window_count,
        current_window_count=current_window_count,
    )

    acts = sorted(list(activities), key=lambda a: a.timestamp)
    if not acts:
        return _EMPTY_REPORT

    baseline_acts, current_acts = _split_windows(acts, current_window_count)
    baseline_ewma = _ewma(_windowed_rates(baseline_acts, baseline_window_count), ewma_alpha)
    current_rate = _current_rate_for(current_acts)
    ratio = _ratio_with_cold_start(current_rate, baseline_ewma, halt_ratio)

    distinct_current = len({a.agent for a in current_acts})
    distinct_baseline = len({a.agent for a in baseline_acts}) if baseline_acts else 1
    multi_author_flag = distinct_current > multi_author_threshold_ratio * distinct_baseline

    rollback_depth = _max_rollback_chain_depth(acts)
    rollback_storm = rollback_depth > rollback_storm_threshold

    warn = ratio >= warn_ratio
    halt = ratio >= halt_ratio

    return ProvDriftReport(
        activity_count=len(acts),
        baseline_ewma=baseline_ewma,
        current_rate=current_rate,
        ratio=ratio,
        distinct_agents=distinct_current,
        rollback_chain_max_depth=rollback_depth,
        warn=warn,
        halt=halt,
        multi_author_flag=multi_author_flag,
        severity=_severity_for(warn=warn, halt=halt, rollback_storm=rollback_storm),
    )
