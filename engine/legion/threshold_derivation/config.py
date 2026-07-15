"""TOML-based threshold configuration loader.

Academic: 12-Factor app §III config-as-code (Wiggins 2011) + W3C PROV provenance.

PROM 16 P2(b): externalize the 14 hardcoded measurement.py thresholds to
a versioned TOML file so they can be:
  - read at runtime (no code edit for tuning),
  - audited per provenance (derivation_method + cycle_id source),
  - overridden by env var BHGMAN_THRESHOLD_CONFIG.

Lookup precedence (high → low):
  1. env BHGMAN_THRESHOLD_CONFIG=path/to.toml
  2. ~/.config/bhgman/thresholds.toml (XDG)
  3. <pkg>/thresholds.toml (defaults bundled with engine.legion)
  4. measurement.py hardcoded (fallback if all above missing)

# KG: actionplan-threshold-derivation-2026-05-30 P2(b)
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


_PKG_DEFAULT = Path(__file__).parent.parent / "thresholds.toml"
_XDG_DEFAULT = Path.home() / ".config" / "bhgman" / "thresholds.toml"


@dataclass(frozen=True)
class ThresholdEntry:
    commander: str
    target_commander: str
    metric: str
    value: float
    comparator: str
    source: str
    derivation_method: str | None = None
    derived_at_cycle: str | None = None


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    env = os.environ.get("BHGMAN_THRESHOLD_CONFIG")
    if env:
        paths.append(Path(env))
    paths.append(_XDG_DEFAULT)
    paths.append(_PKG_DEFAULT)
    return paths


def load_thresholds() -> dict[tuple[str, str], ThresholdEntry]:
    """Load thresholds from highest-precedence file present.

    Returns: {(commander, metric): ThresholdEntry}.
    Returns {} if no file present.
    """
    for path in _candidate_paths():
        if not path.is_file():
            continue
        with path.open("rb") as f:
            data = tomllib.load(f)
        return _parse_toml(data, str(path))
    return {}


class ThresholdConfigError(ValueError):
    """TOML threshold 설정이 무효 — fail-closed (조용히 무시하지 않는다)."""


# DispatchThreshold.triggered 가 해석할 수 있는 comparator 전부. 화이트리스트가 없으면
# 오타("gt"/"Greater"/"greater_than")가 triggered 의 else-분기로 떨어져 게이트를 *반대로*
# 뒤집는다 — TOML 이 런타임 정본이 된 뒤(T1-3)로는 설정 오타 하나가 dispatch 를 조용히
# 반전시키는 경로다 (적대검증 2026-07-15). 파싱 시점에 거부한다.
_VALID_COMPARATORS: frozenset[str] = frozenset({"greater", "less", "equal"})


def _parse_toml(data: dict, source: str) -> dict[tuple[str, str], ThresholdEntry]:
    out: dict[tuple[str, str], ThresholdEntry] = {}
    thresholds = data.get("threshold", [])
    if isinstance(thresholds, dict):
        thresholds = [thresholds]
    for row in thresholds:
        try:
            comparator = row["comparator"]
            if comparator not in _VALID_COMPARATORS:
                raise ThresholdConfigError(
                    f"{source}: invalid comparator {comparator!r} for "
                    f"{row.get('commander')}/{row.get('metric')} — "
                    f"허용: {sorted(_VALID_COMPARATORS)}. (오타는 게이트를 반전시킨다)"
                )
            entry = ThresholdEntry(
                commander=row["commander"],
                target_commander=row["target_commander"],
                metric=row["metric"],
                value=float(row["value"]),
                comparator=comparator,
                source=source,
                derivation_method=row.get("derivation_method"),
                derived_at_cycle=row.get("derived_at_cycle"),
            )
        except (KeyError, ValueError, TypeError) as e:
            if isinstance(e, ThresholdConfigError):
                raise
            continue
        out[(entry.commander, entry.metric)] = entry
    return out
