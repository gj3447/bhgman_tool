"""Poisson random recalibration cadence.

Academic: Krasikova 2013 (mechanism design, timing-strategy robustness).
Fixed quarterly cadence is gameable; Poisson interarrival times remove the
predictable refresh window.

PROM 16 P3(d): random next-audit-time in [30d, 90d] with mean 60d.

# KG: actionplan-threshold-derivation-2026-05-30 P3(d)
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta


DEFAULT_MEAN_DAYS = 60.0
DEFAULT_MIN_DAYS = 30.0
DEFAULT_MAX_DAYS = 90.0


def _seed_from_env(default: float | None = None) -> float | None:
    """Read deterministic seed from env BHGMAN_CALIBRATION_SEED.

    For reproducibility in tests. None → cryptographic random from os.urandom.
    """
    val = os.environ.get("BHGMAN_CALIBRATION_SEED")
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _uniform_random() -> float:
    """Cryptographic uniform random in (0, 1).

    Avoids `random.random()` (PRNG state can be leaked / replayed).
    """
    seed = _seed_from_env()
    if seed is not None:
        return _deterministic_mix(seed)
    raw = int.from_bytes(os.urandom(8), "big")
    return (raw + 1) / (2**64 + 1)


def _deterministic_mix(seed: float) -> float:
    """Mix seed deterministically to (0,1) for reproducible tests."""
    x = math.fmod(seed * math.pi + 1.0, 1.0)
    if x <= 0.0:
        x = 0.0001
    if x >= 1.0:
        x = 0.9999
    return x


@dataclass(frozen=True)
class CalibrationScheduleEntry:
    """One scheduled audit time."""

    next_audit_at: datetime
    interval_days: float
    mean_days: float
    method: str = "poisson_exponential_interarrival_krasikova_2013"


def sample_next_audit(
    now: datetime | None = None,
    mean_days: float = DEFAULT_MEAN_DAYS,
    min_days: float = DEFAULT_MIN_DAYS,
    max_days: float = DEFAULT_MAX_DAYS,
) -> CalibrationScheduleEntry:
    """Sample next audit time via exponential interarrival (Poisson process).

    Clamps to [min_days, max_days] to avoid pathological schedules.
    """
    if now is None:
        now = datetime.now()
    u = _uniform_random()
    raw = -mean_days * math.log(u)
    interval = max(min_days, min(max_days, raw))
    return CalibrationScheduleEntry(
        next_audit_at=now + timedelta(days=interval),
        interval_days=interval,
        mean_days=mean_days,
    )
