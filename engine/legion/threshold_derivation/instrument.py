"""Dispatch outcome instrumentation — accumulates (metric_value, outcome) pairs
for any commander so threshold derivation has data when N≥30.

PROM 16 P3(a): Eureka N=0 → 30. Same hook serves all commanders that lack
historical numeric instrumentation (Occam, Eureka, Longinus, Jaebaeman, Hades).

# KG: actionplan-threshold-derivation-2026-05-30 P3(a)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock


@dataclass(frozen=True)
class InstrumentEntry:
    """One observed (metric_value, ground_truth_outcome) pair."""

    commander: str
    metric: str
    value: float
    outcome: int
    timestamp: float
    cycle_id: str | None = None
    dispatch_id: str | None = None

    def to_jsonl(self) -> str:
        return json.dumps(
            {
                "commander": self.commander,
                "metric": self.metric,
                "value": self.value,
                "outcome": self.outcome,
                "timestamp": self.timestamp,
                "cycle_id": self.cycle_id,
                "dispatch_id": self.dispatch_id,
            }
        )


@dataclass
class DispatchInstrumentLog:
    """Append-only JSONL log of dispatch outcomes per (commander, metric).

    Thread-safe via RLock. Default path = ~/.cache/bhgman/dispatch_instrument.jsonl.
    """

    path: Path = field(
        default_factory=lambda: Path.home() / ".cache" / "bhgman" / "dispatch_instrument.jsonl"
    )
    _lock: RLock = field(default_factory=RLock, repr=False)

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        commander: str,
        metric: str,
        value: float,
        outcome: int,
        cycle_id: str | None = None,
        dispatch_id: str | None = None,
    ) -> InstrumentEntry:
        if outcome not in (0, 1):
            raise ValueError(f"outcome must be 0 or 1, got {outcome}")
        entry = InstrumentEntry(
            commander=commander,
            metric=metric,
            value=value,
            outcome=outcome,
            timestamp=time.time(),
            cycle_id=cycle_id,
            dispatch_id=dispatch_id,
        )
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(entry.to_jsonl() + "\n")
        return entry

    def load_pairs(
        self,
        commander: str,
        metric: str,
    ) -> list[tuple[float, int]]:
        """Return (value, outcome) pairs for a (commander, metric) key."""
        if not self.path.is_file():
            return []
        pairs: list[tuple[float, int]] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("commander") == commander and row.get("metric") == metric:
                    pairs.append((float(row["value"]), int(row["outcome"])))
        return pairs

    def count(self, commander: str, metric: str) -> int:
        return len(self.load_pairs(commander, metric))
