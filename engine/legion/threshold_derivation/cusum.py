"""CUSUM dual-window drift detection.

Academic: Page E.S. 1954 "Continuous Inspection Schemes" Biometrika 41:100-115.
  S_n = max(0, S_{n-1} + (X_n - (μ_0 + δ/2)))
  Alarm when S_n > h.

PROM 16 P2(c): dual-window deploy — diagnostic only.
- CUSUM-L (long, α=0.005, h≈4.77): detects ≥1% monthly creep over 6-month horizon.
- CUSUM-S (short, α=0.02, h≈3.97): detects ≥5% jump in 1-2 weeks.

# KG: actionplan-threshold-derivation-2026-05-30 P2(c)
# KG: mitigation-derive-cusum-dual-window-drift-2026-05-30
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DriftSignal(Enum):
    NO_DRIFT = "no_drift"
    WARNING = "warning"
    DETECTED = "detected"


@dataclass
class CusumChart:
    """Mutable one-sided CUSUM with threshold h and reference shift k.

    target: μ_0 (expected mean under null).
    delta: minimum shift to detect (k = delta/2).
    h: alarm threshold.
    """

    target: float
    delta: float
    h: float
    s_n: float = 0.0
    n_observed: int = 0
    last_alarm_index: int | None = None

    def reset(self) -> None:
        self.s_n = 0.0
        self.last_alarm_index = None

    def observe(self, x: float) -> DriftSignal:
        """Feed one observation; return current drift status."""
        self.n_observed += 1
        k = self.delta / 2.0
        self.s_n = max(0.0, self.s_n + (x - (self.target + k)))
        if self.s_n > self.h:
            self.last_alarm_index = self.n_observed
            return DriftSignal.DETECTED
        if self.s_n > self.h * 0.5:
            return DriftSignal.WARNING
        return DriftSignal.NO_DRIFT


@dataclass
class DualWindowCUSUM:
    """CUSUM-L (long horizon) + CUSUM-S (short horizon) parallel charts.

    Conservative dispatch: DETECTED if either chart alarms; WARNING if only S
    crosses half-threshold (S is more sensitive). L alarms tend to mean
    structural drift; S alarms tend to mean abrupt jump.
    """

    long_chart: CusumChart
    short_chart: CusumChart
    alarm_history: list[tuple[int, str, DriftSignal]] = field(default_factory=list)

    @classmethod
    def standard_config(cls, target: float = 0.7) -> "DualWindowCUSUM":
        """Page 1954 + Hawkins-Olwell 1998 standard parameters for α=0.005/0.02."""
        return cls(
            long_chart=CusumChart(target=target, delta=0.01, h=4.77),
            short_chart=CusumChart(target=target, delta=0.05, h=3.97),
        )

    def observe(self, x: float) -> dict[str, DriftSignal]:
        sl = self.long_chart.observe(x)
        ss = self.short_chart.observe(x)
        if sl == DriftSignal.DETECTED:
            self.alarm_history.append((self.long_chart.n_observed, "long", sl))
        if ss == DriftSignal.DETECTED:
            self.alarm_history.append((self.short_chart.n_observed, "short", ss))
        return {"long": sl, "short": ss}

    def status(self) -> DriftSignal:
        """Combined verdict: DETECTED > WARNING > NO_DRIFT."""
        sl_state = self._chart_state(self.long_chart)
        ss_state = self._chart_state(self.short_chart)
        for signal in (DriftSignal.DETECTED, DriftSignal.WARNING):
            if sl_state == signal or ss_state == signal:
                return signal
        return DriftSignal.NO_DRIFT

    @staticmethod
    def _chart_state(chart: CusumChart) -> DriftSignal:
        if chart.s_n > chart.h:
            return DriftSignal.DETECTED
        if chart.s_n > chart.h * 0.5:
            return DriftSignal.WARNING
        return DriftSignal.NO_DRIFT
