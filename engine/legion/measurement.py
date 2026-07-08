"""Measurement-driven conditional dispatch for 7 LegionCommanders.

사용자 정전 정정 2026-05-30: `user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30`
SPEC: SYMPOSIUM/THEORY/00_공통/7CMD_NEED_BASED_DISPATCH_SPEC.md
KG: 7cmd-measurement-driven-conditional-dispatch-2026-05-30 (parent: hades-canonical-2026-05-27)

7 commander 각자가 self-measurement → threshold-gated need detection → conditional invocation.
고정 USES edge retract. Hades realization pattern universalized.

v2 (2026-05-30 P1 mitigations per PROM 16 A4S4):
- Idempotent measure() with version vector (Mattern 1989)
- max_depth recursion cap (Lawvere-Tierney 1971)
- DispatchEvent HMAC-SHA256 signing (W3C PROV)
- threading.Lock critical section (Eswaran 1976 2PL)
"""
# KG: bihaenggiman-legioncommanders-2026-05-26

from __future__ import annotations

import hashlib
import hmac
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Final


# A4S4 P1: max_depth=3 (Lawvere-Tierney j-operator idempotence, Knaster-Tarski termination)
MAX_DISPATCH_DEPTH: Final[int] = 3

# A4S4 P1: DispatchEvent HMAC secret (env override; dev default for tests)
_HMAC_SECRET: Final[bytes] = os.environ.get(
    "BHGMAN_DISPATCH_HMAC_SECRET", "bhgman-dev-secret-2026-05-30"
).encode("utf-8")


def _sign(payload: str) -> str:
    """HMAC-SHA256 signature for provenance integrity."""
    return hmac.new(_HMAC_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class DispatchDecision:
    """Single dispatch decision record (frozen, signed)."""

    source_commander: str
    target_commander: str
    metric_name: str
    metric_value: float
    threshold: float
    reason: str
    decided_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    epoch: int = 0  # A4S4 P1: version vector epoch (Mattern 1989)
    depth: int = 0  # A4S4 P1: dispatch recursion depth (≤ MAX_DISPATCH_DEPTH)

    def _signed_payload(self, cycle_id: str | None) -> str:
        return "|".join(
            [
                self.source_commander,
                self.target_commander,
                self.metric_name,
                f"{self.metric_value:.6f}",
                f"{self.threshold:.6f}",
                str(self.epoch),
                str(self.depth),
                self.decided_at,
                cycle_id or "",
            ]
        )

    def to_kg_event(self, cycle_id: str | None = None) -> dict:
        """Return :DispatchEvent node properties (signed for forge resistance)."""
        return {
            "source_commander": self.source_commander,
            "target_commander": self.target_commander,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "reason": self.reason,
            "decided_at": self.decided_at,
            "epoch": self.epoch,
            "depth": self.depth,
            "cycle_id": cycle_id,
            "hmac_signature": _sign(self._signed_payload(cycle_id)),
        }

    @staticmethod
    def verify_signature(kg_event: dict) -> bool:
        """Verify HMAC signature on a deserialized :DispatchEvent."""
        payload = "|".join(
            [
                kg_event.get("source_commander", ""),
                kg_event.get("target_commander", ""),
                kg_event.get("metric_name", ""),
                f"{kg_event.get('metric_value', 0.0):.6f}",
                f"{kg_event.get('threshold', 0.0):.6f}",
                str(kg_event.get("epoch", 0)),
                str(kg_event.get("depth", 0)),
                kg_event.get("decided_at", ""),
                kg_event.get("cycle_id") or "",
            ]
        )
        expected = _sign(payload)
        actual = kg_event.get("hmac_signature", "")
        return hmac.compare_digest(expected, actual)


@dataclass(frozen=True)
class DispatchThreshold:
    """Threshold config for (source, target) commander pair on a metric."""

    source: str
    target: str
    metric: str
    threshold: float
    direction: str = "greater"  # "greater" or "less"
    rationale: str = ""

    def triggered(self, value: float) -> bool:
        if self.direction == "greater":
            return value > self.threshold
        return value < self.threshold


class MaxDispatchDepthExceeded(RuntimeError):
    """Raised when recursive dispatch exceeds MAX_DISPATCH_DEPTH."""


class CommanderBase(ABC):
    """Abstract base for all 7 LegionCommanders (v2 with mitigations)."""

    name: str = ""
    dispatch_thresholds: tuple[DispatchThreshold, ...] = ()

    def __init__(self) -> None:
        # A4S4 P1: version vector epoch + cached snapshot for idempotent measure()
        self._epoch: int = 0
        self._cached_snapshot: dict[str, float] | None = None
        self._lock: threading.RLock = threading.RLock()
        # PROM 16 P3(a) wire: optional ground-truth outcome logger (None = no instrument).
        self._instrument: object | None = None

    def set_instrument_log(self, instrument_log: object | None) -> None:
        """Inject a DispatchInstrumentLog. None disables (default)."""
        with self._lock:
            self._instrument = instrument_log

    def record_outcome(
        self,
        decision: DispatchDecision,
        outcome: int,
        cycle_id: str | None = None,
        dispatch_id: str | None = None,
    ) -> None:
        """Log ground-truth outcome for a past decision.

        Caller invokes after the dispatched commander's verdict is known.
        Silently no-ops if no instrument log was injected.
        Validates outcome ∈ {0, 1} (delegated to log).
        """
        if self._instrument is None:
            return
        record = getattr(self._instrument, "record", None)
        if record is None:
            return
        record(
            commander=decision.source_commander,
            metric=decision.metric_name,
            value=decision.metric_value,
            outcome=outcome,
            cycle_id=cycle_id,
            dispatch_id=dispatch_id,
        )

    def _bump_epoch(self) -> None:
        """Invalidate cached snapshot. Call from any mutator method in subclass."""
        with self._lock:
            self._epoch += 1
            self._cached_snapshot = None

    @abstractmethod
    def _measure_uncached(self) -> dict[str, float]:
        """Subclass: pure self-measurement, no caching."""
        raise NotImplementedError

    def measure(self) -> dict[str, float]:
        """Idempotent self-measurement returning named metrics (cached per epoch)."""
        with self._lock:
            if self._cached_snapshot is None:
                self._cached_snapshot = dict(self._measure_uncached())
            return dict(self._cached_snapshot)

    def current_epoch(self) -> int:
        with self._lock:
            return self._epoch

    def decide_dispatch(
        self, cycle_id: str | None = None, *, depth: int = 0
    ) -> list[DispatchDecision]:
        """Run measurement and produce dispatch decisions for threshold-triggered metrics.

        Raises MaxDispatchDepthExceeded if depth ≥ MAX_DISPATCH_DEPTH.
        """
        if depth >= MAX_DISPATCH_DEPTH:
            raise MaxDispatchDepthExceeded(
                f"Dispatch depth {depth} reached MAX_DISPATCH_DEPTH={MAX_DISPATCH_DEPTH} "
                f"in {self.name}.decide_dispatch (cycle={cycle_id})"
            )
        with self._lock:
            metrics = self.measure()
            epoch = self._epoch
        decisions: list[DispatchDecision] = []
        for rule in self.dispatch_thresholds:
            if rule.source != self.name:
                continue
            value = metrics.get(rule.metric)
            if value is None:
                continue
            if rule.triggered(value):
                decisions.append(
                    DispatchDecision(
                        source_commander=rule.source,
                        target_commander=rule.target,
                        metric_name=rule.metric,
                        metric_value=value,
                        threshold=rule.threshold,
                        reason=f"{rule.metric}={value:.4f} {rule.direction} {rule.threshold} ({rule.rationale})",
                        epoch=epoch,
                        depth=depth,
                    )
                )
        return decisions


# ─────────────────────────────────────────────────────────────
# 7 concrete commander measurement classes
# ─────────────────────────────────────────────────────────────


def _is_external_citation(url) -> bool:
    """True iff ``url`` is a REAL external source — an http/https URL with a host."""
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(str(url).strip())
    except (ValueError, AttributeError):
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def compute_external_grounding_ratio(citation_urls) -> float | None:
    """Fraction of citations backed by a REAL external source (http/https + host).

    The Goodhart-mitigation control ``external_grounding_ratio < 0.3 → self-recurse`` can only
    fire if this is COMPUTED from real findings: the field defaulted to 1.0 and was never
    derived, so ``1.0 < 0.3`` was always False and the control was dead. Empty / non-http /
    host-less citations are NOT external grounding.

    v2 (seam-integrity 2026-07-08): an EMPTY citation set is ``None`` (unmeasured) — there are
    no findings to ground, so neither constant is honest. The v1 choice of 0.0 was the vacuous
    1.0's mirror image: on the infra-0/MCP path (no fetcher → findings structurally empty) it
    made the self-recurse fire on EVERY run — an always-firing control carries exactly as much
    information as a never-firing one (zero). Unmeasured flows as a MISSING metric key, which
    ``decide_dispatch`` skips.
    """
    urls = list(citation_urls)
    if not urls:
        return None
    grounded = sum(1 for u in urls if _is_external_citation(u))
    return grounded / len(urls)


class PrometheusMeasurement(CommanderBase):
    name = "prometheus"
    dispatch_thresholds = (
        DispatchThreshold(
            "prometheus",
            "naesengmoon",
            "research_finding_count",
            16,
            "greater",
            "N>16 findings → verification gate. Shannon 4-bit decomposition: 16 = 2^4 = 4 axis × 4 sub-axis matrix → log2(16)=4 bits of axis-information per cell. PROM 16 STAB consensus + Shannon 1948 channel-capacity derivation (ratified PROM 16 P1(b) 2026-05-30, see lean/Measurement_Prometheus_ShannonRatify.lean).",
        ),
        DispatchThreshold(
            "prometheus",
            "prometheus",
            "external_grounding_ratio",
            0.3,
            "less",
            "<0.3 external grounding → self-recurse (Goodhart mitigation: WebFetch invocation log)",
        ),
    )

    def __init__(
        self, finding_count: int = 0, external_grounding_ratio: float | None = None
    ) -> None:
        # 기본 None = 미측정 — v1 의 기본 1.0 은 측정 없이 '완전 접지'를 위장하는 죽은 상수였다
        # (LLM 브랜치에서 영구 불-발화). 미측정은 measure() 키 부재로 흘러 dispatch 가 스킵한다.
        super().__init__()
        self._finding_count = finding_count
        self._external_grounding_ratio = external_grounding_ratio

    def update(
        self, finding_count: int | None = None, external_grounding_ratio: float | None = None
    ) -> None:
        with self._lock:
            if finding_count is not None:
                self._finding_count = finding_count
            if external_grounding_ratio is not None:
                self._external_grounding_ratio = external_grounding_ratio
        self._bump_epoch()

    def update_grounding(self, citation_urls) -> None:
        """Compute external_grounding_ratio from THIS cycle's finding citations and set it, so
        the <0.3 self-recurse control reflects REAL grounding instead of a dead constant.
        Empty citations (no findings) → None = unmeasured, and the metric key disappears.
        Pass e.g. ``[f.citation_url for f in report.findings]``."""
        ratio = compute_external_grounding_ratio(citation_urls)
        with self._lock:
            self._external_grounding_ratio = ratio
        self._bump_epoch()

    def _measure_uncached(self) -> dict[str, float]:
        metrics = {"research_finding_count": float(self._finding_count)}
        # 미측정(None) = 키 부재 — decide_dispatch 는 없는 메트릭을 스킵한다(발화 없음).
        if self._external_grounding_ratio is not None:
            metrics["external_grounding_ratio"] = self._external_grounding_ratio
        return metrics


class EurekaMeasurement(CommanderBase):
    name = "eureka"
    dispatch_thresholds = (
        DispatchThreshold(
            "eureka",
            "longinus",
            "binding_density",
            0.5,
            "less",
            "<0.5 KG-bound / detected pattern ratio → bind need (FCA Galois lattice incomplete)",
        ),
        DispatchThreshold(
            "eureka",
            "prometheus",
            "novelty_score",
            0.4,
            "less",
            "<0.4 novelty → external research need (Bayesian prior posterior threshold)",
        ),
    )

    def __init__(
        self,
        binding_density: float = 1.0,
        novelty_score: float = 1.0,
        colimit_termination_depth: int = 0,
    ) -> None:
        super().__init__()
        self._binding_density = binding_density
        self._novelty_score = novelty_score
        self._colimit_termination_depth = colimit_termination_depth

    def update(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, f"_{k}"):
                    setattr(self, f"_{k}", v)
        self._bump_epoch()

    def _measure_uncached(self) -> dict[str, float]:
        return {
            "binding_density": self._binding_density,
            "novelty_score": self._novelty_score,
            "colimit_termination_depth": float(self._colimit_termination_depth),
        }


class LonginusMeasurement(CommanderBase):
    name = "longinus"
    dispatch_thresholds = (
        DispatchThreshold(
            "longinus",
            "occam",
            "sha256_drift_count",
            5,
            "greater",
            ">5 drift instances → cleanup need (invocation-log empirical, not KG mention proxy)",
        ),
        DispatchThreshold(
            "longinus",
            "prometheus",
            "reference_orphan_count",
            10,
            "greater",
            ">10 orphan refs → research need",
        ),
    )

    def __init__(
        self,
        sha256_drift_count: int = 0,
        reference_orphan_count: int = 0,
        kg_node_unbound_count: int = 0,
    ) -> None:
        super().__init__()
        self._sha256_drift_count = sha256_drift_count
        self._reference_orphan_count = reference_orphan_count
        self._kg_node_unbound_count = kg_node_unbound_count

    def update(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, f"_{k}"):
                    setattr(self, f"_{k}", v)
        self._bump_epoch()

    def _measure_uncached(self) -> dict[str, float]:
        return {
            "sha256_drift_count": float(self._sha256_drift_count),
            "reference_orphan_count": float(self._reference_orphan_count),
            "kg_node_unbound_count": float(self._kg_node_unbound_count),
        }


class OccamMeasurement(CommanderBase):
    name = "occam"
    dispatch_thresholds = (
        DispatchThreshold(
            "occam",
            "naesengmoon",
            "supersession_confidence",
            0.7,
            "less",
            "<0.7 confidence → verify need (PROM 16 STAB feedback canon)",
        ),
        DispatchThreshold(
            "occam",
            "occam",
            "dead_node_count",
            10,
            "greater",
            ">10 dead nodes → self-supersede batch (operational threshold)",
        ),
    )

    def __init__(
        self,
        supersession_confidence: float = 1.0,
        dead_node_count: int = 0,
        twin_status_score: float = 1.0,
    ) -> None:
        super().__init__()
        self._supersession_confidence = supersession_confidence
        self._dead_node_count = dead_node_count
        self._twin_status_score = twin_status_score

    def update(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, f"_{k}"):
                    setattr(self, f"_{k}", v)
        self._bump_epoch()

    def _measure_uncached(self) -> dict[str, float]:
        return {
            "supersession_confidence": self._supersession_confidence,
            "dead_node_count": float(self._dead_node_count),
            "twin_status_score": self._twin_status_score,
        }


class NaesengmoonMeasurement(CommanderBase):
    """Naesengmoon lens_count는 ORDINAL scale (A1S3/A3S3 bug fix 2026-05-30).

    Ordinal에서는 mean/SD/Pearson r 측 invalid — count로만 사용.
    """

    name = "naesengmoon"
    dispatch_thresholds = (
        DispatchThreshold(
            "naesengmoon",
            "user_verdict_trigger",
            "lens_disagreement_ratio",
            0.4,
            "greater",
            ">0.4 disagreement across lenses → user verdict needed",
        ),
        DispatchThreshold(
            "naesengmoon",
            "naesengmoon",
            "RTI_FVR_pass_rate",
            0.7,
            "less",
            "<0.7 RTI/FVR pass → self multi-lens recurse (max_depth=3 cap)",
        ),
    )

    def __init__(
        self,
        claim_confidence_distribution: tuple[float, ...] = (),
        lens_agreement_ratio: float = 1.0,
        RTI_FVR_pass_rate: float = 1.0,
    ) -> None:
        super().__init__()
        self._claim_confidence_distribution = claim_confidence_distribution
        self._lens_disagreement_ratio = 1.0 - lens_agreement_ratio
        self._RTI_FVR_pass_rate = RTI_FVR_pass_rate

    def update(self, **kwargs) -> None:
        with self._lock:
            if "lens_agreement_ratio" in kwargs:
                self._lens_disagreement_ratio = 1.0 - kwargs.pop("lens_agreement_ratio")
            for k, v in kwargs.items():
                if hasattr(self, f"_{k}"):
                    setattr(self, f"_{k}", v)
        self._bump_epoch()

    def _measure_uncached(self) -> dict[str, float]:
        return {
            "claim_confidence_mean": (
                sum(self._claim_confidence_distribution) / len(self._claim_confidence_distribution)
                if self._claim_confidence_distribution
                else 1.0
            ),
            "lens_disagreement_ratio": self._lens_disagreement_ratio,
            "RTI_FVR_pass_rate": self._RTI_FVR_pass_rate,
        }


class JaebaemanMeasurement(CommanderBase):
    name = "jaebaeman"
    dispatch_thresholds = (
        DispatchThreshold(
            "jaebaeman",
            "naesengmoon",
            "subagent_collect_drift",
            0.2,
            "greater",
            ">0.2 self-claim drift (4 instance lesson 2026-05-24) → verify need",
        ),
        DispatchThreshold(
            "jaebaeman",
            "prometheus",
            "seed_freshness_score",
            0.3,
            "less",
            "<0.3 seed freshness → external research need",
        ),
    )

    def __init__(
        self,
        subagent_collect_drift: float = 0.0,
        seed_freshness_score: float = 1.0,
        dispatch_intent_completeness: float = 1.0,
    ) -> None:
        super().__init__()
        self._subagent_collect_drift = subagent_collect_drift
        self._seed_freshness_score = seed_freshness_score
        self._dispatch_intent_completeness = dispatch_intent_completeness

    def update(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, f"_{k}"):
                    setattr(self, f"_{k}", v)
        self._bump_epoch()

    def _measure_uncached(self) -> dict[str, float]:
        return {
            "subagent_collect_drift": self._subagent_collect_drift,
            "seed_freshness_score": self._seed_freshness_score,
            "dispatch_intent_completeness": self._dispatch_intent_completeness,
        }


class HadesMeasurement(CommanderBase):
    """Hades = Harness — abstract spec → concrete code realization."""

    name = "hades"
    dispatch_thresholds = (
        DispatchThreshold(
            "hades",
            "eureka",
            "spec_ambiguity_score",
            0.5,
            "greater",
            ">0.5 spec ambiguity → further abstraction need",
        ),
        DispatchThreshold(
            "hades",
            "prometheus",
            "TDD_GREEN_failure_count",
            3,
            "greater",
            ">3 GREEN failures → external knowledge need",
        ),
        DispatchThreshold(
            "hades",
            "longinus",
            "binding_completeness",
            0.7,
            "less",
            "<0.7 binding completeness → binding need",
        ),
    )

    def __init__(
        self,
        spec_ambiguity_score: float = 0.0,
        TDD_GREEN_failure_count: int = 0,
        binding_completeness: float = 1.0,
    ) -> None:
        super().__init__()
        self._spec_ambiguity_score = spec_ambiguity_score
        self._TDD_GREEN_failure_count = TDD_GREEN_failure_count
        self._binding_completeness = binding_completeness

    def update(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, f"_{k}"):
                    setattr(self, f"_{k}", v)
        self._bump_epoch()

    def _measure_uncached(self) -> dict[str, float]:
        return {
            "spec_ambiguity_score": self._spec_ambiguity_score,
            "TDD_GREEN_failure_count": float(self._TDD_GREEN_failure_count),
            "binding_completeness": self._binding_completeness,
        }


# ─────────────────────────────────────────────────────────────
# Stevens scale type registry (A1S3 + A3S3 + A3S4 bug fix 2026-05-30)
# ─────────────────────────────────────────────────────────────


STEVENS_SCALE: Final[dict[tuple[str, str], str]] = {
    # Prometheus
    ("prometheus", "research_finding_count"): "ratio",
    ("prometheus", "external_grounding_ratio"): "ratio",
    # Eureka — abstraction_level 측 ORDINAL (hierarchy depth, no arithmetic)
    ("eureka", "binding_density"): "ratio",
    ("eureka", "novelty_score"): "ratio",
    ("eureka", "colimit_termination_depth"): "ordinal",  # bug fix: hierarchy depth
    # Longinus
    ("longinus", "sha256_drift_count"): "ratio",
    ("longinus", "reference_orphan_count"): "ratio",
    ("longinus", "kg_node_unbound_count"): "ratio",
    # Occam — archival_reason_category NOMINAL (mode/count only)
    ("occam", "supersession_confidence"): "ratio",
    ("occam", "dead_node_count"): "ratio",
    ("occam", "twin_status_score"): "ratio",
    ("occam", "archival_reason_category"): "nominal",  # bug fix
    # Naesengmoon — lens_count ORDINAL (ranks of lenses, no mean)
    ("naesengmoon", "claim_confidence_mean"): "ratio",
    ("naesengmoon", "lens_disagreement_ratio"): "ratio",
    ("naesengmoon", "RTI_FVR_pass_rate"): "ratio",
    ("naesengmoon", "lens_count"): "ordinal",  # bug fix: rank ordering only
    # Jaebaeman
    ("jaebaeman", "subagent_collect_drift"): "ratio",
    ("jaebaeman", "seed_freshness_score"): "ratio",
    ("jaebaeman", "dispatch_intent_completeness"): "interval",
    # Hades
    ("hades", "spec_ambiguity_score"): "interval",
    ("hades", "TDD_GREEN_failure_count"): "ratio",
    ("hades", "binding_completeness"): "ratio",
}


# Stevens nesting = upward-closed: an op valid at a weaker scale stays valid at all
# stronger scales (count/mode/entropy are nominal-level stats, computable at every
# scale ≥ nominal). entropy was previously dropped from ordinal+ — a non-monotone
# omission that contradicted the Lean monotonicity proof (Measurement_MetricScale.lean
# nominal_subset_ordinal). Fixed 2026-06-01 in lockstep with Lean.
_VALID_OPS: Final[dict[str, set[str]]] = {
    "nominal": {"count", "mode", "entropy"},
    "ordinal": {"count", "mode", "entropy", "median", "percentile", "min", "max"},
    "interval": {"count", "mode", "entropy", "median", "percentile", "min", "max", "mean", "sd"},
    "ratio": {
        "count",
        "mode",
        "entropy",
        "median",
        "percentile",
        "min",
        "max",
        "mean",
        "sd",
        "ratio",
        "pct",
        "geomean",
    },
}


def valid_operation(commander: str, metric: str, op: str) -> bool:
    """Stevens 1946 scale type gate — block invalid ops (e.g. mean on ordinal)."""
    scale = STEVENS_SCALE.get((commander, metric))
    if scale is None:
        return False
    return op in _VALID_OPS[scale]


# ─────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────


COMMANDER_REGISTRY: Final[dict[str, type[CommanderBase]]] = {
    "prometheus": PrometheusMeasurement,
    "eureka": EurekaMeasurement,
    "longinus": LonginusMeasurement,
    "occam": OccamMeasurement,
    "naesengmoon": NaesengmoonMeasurement,
    "jaebaeman": JaebaemanMeasurement,
    "hades": HadesMeasurement,
}


def commander_by_name(name: str) -> type[CommanderBase]:
    if name not in COMMANDER_REGISTRY:
        raise KeyError(f"Unknown commander: {name}. Known: {list(COMMANDER_REGISTRY)}")
    return COMMANDER_REGISTRY[name]


__all__ = [
    "CommanderBase",
    "DispatchDecision",
    "DispatchThreshold",
    "MaxDispatchDepthExceeded",
    "MAX_DISPATCH_DEPTH",
    "STEVENS_SCALE",
    "valid_operation",
    "PrometheusMeasurement",
    "EurekaMeasurement",
    "LonginusMeasurement",
    "OccamMeasurement",
    "NaesengmoonMeasurement",
    "JaebaemanMeasurement",
    "HadesMeasurement",
    "COMMANDER_REGISTRY",
    "commander_by_name",
]
