"""Measurement-driven conditional dispatch for 7 LegionCommanders.

사용자 정전 정정 2026-05-30: `user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30`
SPEC: SYMPOSIUM/THEORY/00_공통/7CMD_NEED_BASED_DISPATCH_SPEC.md
KG: 7cmd-measurement-driven-conditional-dispatch-2026-05-30 (parent: hades-canonical-2026-05-27)

7 commander 각자가 self-measurement → threshold-gated need detection → conditional invocation.
고정 USES edge 측 retract.  Hades realization pattern 측 universalized.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Final


@dataclass(frozen=True)
class DispatchDecision:
    """Single dispatch decision record."""

    source_commander: str
    target_commander: str
    metric_name: str
    metric_value: float
    threshold: float
    reason: str
    decided_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_kg_event(self, cycle_id: str | None = None) -> dict:
        """Return :DispatchEvent node properties."""
        return {
            "source_commander": self.source_commander,
            "target_commander": self.target_commander,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "reason": self.reason,
            "decided_at": self.decided_at,
            "cycle_id": cycle_id,
        }


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


class CommanderBase(ABC):
    """Abstract base for all 7 LegionCommanders.

    Each concrete subclass MUST implement:
      - measure(): return dict[str, float] of self-measurements
      - dispatch_thresholds: tuple of DispatchThreshold rules

    decide_dispatch() orchestrates measure() → threshold check → DispatchDecision list.
    """

    name: str = ""
    dispatch_thresholds: tuple[DispatchThreshold, ...] = ()

    @abstractmethod
    def measure(self) -> dict[str, float]:
        """Self-measurement returning named metrics.

        Must be deterministic given current state. Used for need detection.
        """
        raise NotImplementedError

    def decide_dispatch(self, cycle_id: str | None = None) -> list[DispatchDecision]:
        """Run measurement and produce dispatch decisions for threshold-triggered metrics."""
        metrics = self.measure()
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
                    )
                )
        return decisions


# ─────────────────────────────────────────────────────────────
# 7 concrete commander measurement classes (skeleton — engines plug actual logic)
# ─────────────────────────────────────────────────────────────


class PrometheusMeasurement(CommanderBase):
    name = "prometheus"
    dispatch_thresholds = (
        DispatchThreshold(
            "prometheus",
            "naesengmoon",
            "research_finding_count",
            16,
            "greater",
            "N>16 findings → verification gate per PROM 16 STAB consensus",
        ),
        DispatchThreshold(
            "prometheus",
            "prometheus",
            "external_grounding_ratio",
            0.3,
            "less",
            "<0.3 external grounding → self-recurse research",
        ),
    )

    def __init__(self, finding_count: int = 0, external_grounding_ratio: float = 1.0) -> None:
        self.finding_count = finding_count
        self.external_grounding_ratio = external_grounding_ratio

    def measure(self) -> dict[str, float]:
        return {
            "research_finding_count": float(self.finding_count),
            "external_grounding_ratio": self.external_grounding_ratio,
        }


class EurekaMeasurement(CommanderBase):
    name = "eureka"
    dispatch_thresholds = (
        DispatchThreshold(
            "eureka",
            "longinus",
            "binding_density",
            0.5,
            "less",
            "<0.5 binding density → bind need before colimit",
        ),
        DispatchThreshold(
            "eureka",
            "prometheus",
            "novelty_score",
            0.4,
            "less",
            "<0.4 novelty → external research needed",
        ),
    )

    def __init__(
        self,
        binding_density: float = 1.0,
        novelty_score: float = 1.0,
        colimit_termination_depth: int = 0,
    ) -> None:
        self.binding_density = binding_density
        self.novelty_score = novelty_score
        self.colimit_termination_depth = colimit_termination_depth

    def measure(self) -> dict[str, float]:
        return {
            "binding_density": self.binding_density,
            "novelty_score": self.novelty_score,
            "colimit_termination_depth": float(self.colimit_termination_depth),
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
            ">5 drift instances → cleanup need",
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
        self.sha256_drift_count = sha256_drift_count
        self.reference_orphan_count = reference_orphan_count
        self.kg_node_unbound_count = kg_node_unbound_count

    def measure(self) -> dict[str, float]:
        return {
            "sha256_drift_count": float(self.sha256_drift_count),
            "reference_orphan_count": float(self.reference_orphan_count),
            "kg_node_unbound_count": float(self.kg_node_unbound_count),
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
    )

    def __init__(
        self,
        supersession_confidence: float = 1.0,
        dead_node_count: int = 0,
        twin_status_score: float = 1.0,
    ) -> None:
        self.supersession_confidence = supersession_confidence
        self.dead_node_count = dead_node_count
        self.twin_status_score = twin_status_score

    def measure(self) -> dict[str, float]:
        return {
            "supersession_confidence": self.supersession_confidence,
            "dead_node_count": float(self.dead_node_count),
            "twin_status_score": self.twin_status_score,
        }


class NaesengmoonMeasurement(CommanderBase):
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
            "<0.7 RTI/FVR pass → self multi-lens recurse",
        ),
    )

    def __init__(
        self,
        claim_confidence_distribution: tuple[float, ...] = (),
        lens_agreement_ratio: float = 1.0,
        RTI_FVR_pass_rate: float = 1.0,
    ) -> None:
        self.claim_confidence_distribution = claim_confidence_distribution
        self.lens_disagreement_ratio = 1.0 - lens_agreement_ratio
        self.RTI_FVR_pass_rate = RTI_FVR_pass_rate

    def measure(self) -> dict[str, float]:
        return {
            "claim_confidence_mean": (
                sum(self.claim_confidence_distribution) / len(self.claim_confidence_distribution)
                if self.claim_confidence_distribution
                else 1.0
            ),
            "lens_disagreement_ratio": self.lens_disagreement_ratio,
            "RTI_FVR_pass_rate": self.RTI_FVR_pass_rate,
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
        self.subagent_collect_drift = subagent_collect_drift
        self.seed_freshness_score = seed_freshness_score
        self.dispatch_intent_completeness = dispatch_intent_completeness

    def measure(self) -> dict[str, float]:
        return {
            "subagent_collect_drift": self.subagent_collect_drift,
            "seed_freshness_score": self.seed_freshness_score,
            "dispatch_intent_completeness": self.dispatch_intent_completeness,
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
        self.spec_ambiguity_score = spec_ambiguity_score
        self.TDD_GREEN_failure_count = TDD_GREEN_failure_count
        self.binding_completeness = binding_completeness

    def measure(self) -> dict[str, float]:
        return {
            "spec_ambiguity_score": self.spec_ambiguity_score,
            "TDD_GREEN_failure_count": float(self.TDD_GREEN_failure_count),
            "binding_completeness": self.binding_completeness,
        }


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
