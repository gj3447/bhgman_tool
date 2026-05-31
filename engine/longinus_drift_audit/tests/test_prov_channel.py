"""Tests for L3 PROV-based causal-flow drift channel.

# KG: CONTRACT_ProvChannel_v1_2026-05-19, sa-longinus-v3.4-L3-prov-diff-2026-05-19
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from engine.longinus_drift_audit.prov_channel import (
    ProvActivity,
    ProvDriftReport,
    _ewma,
    _max_rollback_chain_depth,
    compute_prov_drift,
)


def _activity(
    *,
    t: datetime,
    agent: str = "alice",
    action: str = "update",
    entity: str = "e1",
    derived_from: str | None = None,
) -> ProvActivity:
    return ProvActivity(
        timestamp=t,
        agent=agent,
        action=action,
        entity=entity,
        derived_from=derived_from,
    )


def _steady_stream(
    *, n: int, interval_sec: float, start: datetime, agent: str = "alice"
) -> list[ProvActivity]:
    """Generate ``n`` evenly-spaced activities, one entity per step."""
    return [
        _activity(t=start + timedelta(seconds=i * interval_sec), agent=agent, entity=f"e{i}")
        for i in range(n)
    ]


# ─────────────────────────────────────────────────────────────────
# 1. Empty input edge case
# ─────────────────────────────────────────────────────────────────


def test_empty_activities_returns_quiet():
    report = compute_prov_drift([])
    assert report.activity_count == 0
    assert report.baseline_ewma == 0.0
    assert report.current_rate == 0.0
    assert report.ratio == 0.0
    assert report.distinct_agents == 0
    assert report.rollback_chain_max_depth == 0
    assert not report.warn
    assert not report.halt
    assert not report.multi_author_flag
    assert report.severity == "QUIET"


# ─────────────────────────────────────────────────────────────────
# 2. Identity baseline (no burst): steady stream → ratio ≈ 1.0
# ─────────────────────────────────────────────────────────────────


def test_steady_stream_no_burst():
    """200 events at 1 Hz. Baseline ≈ current ≈ 1.0 rate → ratio ≈ 1.0."""
    start = datetime(2026, 1, 1, 0, 0, 0)
    acts = _steady_stream(n=200, interval_sec=1.0, start=start)
    report = compute_prov_drift(acts, baseline_window_count=50, current_window_count=10)
    # baseline windows of 50 events span 49 sec → rate ≈ 50/49 ≈ 1.02
    # current 10 events span 9 sec → rate ≈ 10/9 ≈ 1.11
    assert 0.5 < report.ratio < 2.0
    assert not report.warn
    assert not report.halt
    assert report.severity == "NORMAL"


# ─────────────────────────────────────────────────────────────────
# 3. Burst above warn (~2.5x baseline)
# ─────────────────────────────────────────────────────────────────


def test_burst_above_warn():
    """Baseline 1 Hz, current ~2.5 Hz → warn but not halt."""
    start = datetime(2026, 1, 1, 0, 0, 0)
    baseline = _steady_stream(n=190, interval_sec=1.0, start=start)
    # current 10 events at 0.4 sec interval → 9 events over 3.6 sec ≈ 2.5 Hz
    last = baseline[-1].timestamp
    current = [
        _activity(t=last + timedelta(seconds=(i + 1) * 0.4), entity=f"c{i}") for i in range(10)
    ]
    report = compute_prov_drift(
        baseline + current, baseline_window_count=50, current_window_count=10
    )
    assert report.warn
    assert not report.halt
    assert report.severity == "BURST"
    assert 2.0 <= report.ratio < 10.0


# ─────────────────────────────────────────────────────────────────
# 4. Burst above halt (~12x baseline)
# ─────────────────────────────────────────────────────────────────


def test_burst_above_halt():
    """Baseline 1 Hz, current ~12 Hz → halt."""
    start = datetime(2026, 1, 1, 0, 0, 0)
    baseline = _steady_stream(n=190, interval_sec=1.0, start=start)
    last = baseline[-1].timestamp
    # 10 events over ~0.83 sec → ≈ 12 Hz
    current = [
        _activity(t=last + timedelta(seconds=(i + 1) * (1.0 / 12.0)), entity=f"c{i}")
        for i in range(10)
    ]
    report = compute_prov_drift(
        baseline + current, baseline_window_count=50, current_window_count=10
    )
    assert report.warn
    assert report.halt
    assert report.severity in {"STORM", "ROLLBACK_STORM"}
    assert report.ratio >= 10.0


# ─────────────────────────────────────────────────────────────────
# 5. Multi-agent flag (>3 distinct agents in current window vs single
#    agent baseline)
# ─────────────────────────────────────────────────────────────────


def test_multi_author_flag():
    start = datetime(2026, 1, 1, 0, 0, 0)
    baseline = _steady_stream(n=100, interval_sec=1.0, start=start, agent="alice")
    last = baseline[-1].timestamp
    # 10 current events from 5 distinct agents (baseline=1 distinct → 5 > 3*1)
    current = [
        _activity(
            t=last + timedelta(seconds=(i + 1) * 1.0),
            agent=f"agent_{i % 5}",
            entity=f"c{i}",
        )
        for i in range(10)
    ]
    report = compute_prov_drift(
        baseline + current, baseline_window_count=50, current_window_count=10
    )
    assert report.distinct_agents == 5
    assert report.multi_author_flag


def test_no_multi_author_when_single_agent():
    start = datetime(2026, 1, 1, 0, 0, 0)
    acts = _steady_stream(n=100, interval_sec=1.0, start=start, agent="alice")
    report = compute_prov_drift(acts)
    assert report.distinct_agents == 1
    assert not report.multi_author_flag


# ─────────────────────────────────────────────────────────────────
# 6. EWMA correctness (manual computation match)
# ─────────────────────────────────────────────────────────────────


def test_ewma_manual_match():
    """Manual EWMA: alpha=0.5 over [10, 20, 40] = (((10)*0.5 + 20*0.5)*0.5 + 40*0.5)."""
    # init ewma = 10
    # step 2: 0.5*20 + 0.5*10 = 15
    # step 3: 0.5*40 + 0.5*15 = 27.5
    assert _ewma([10.0, 20.0, 40.0], alpha=0.5) == pytest.approx(27.5)


def test_ewma_single_value():
    assert _ewma([7.0], alpha=0.3) == 7.0


def test_ewma_empty():
    assert _ewma([], alpha=0.3) == 0.0


# ─────────────────────────────────────────────────────────────────
# 7. Threshold validation
# ─────────────────────────────────────────────────────────────────


def test_warn_ratio_must_be_less_than_halt_ratio():
    with pytest.raises(ValueError, match="warn_ratio"):
        compute_prov_drift([], warn_ratio=5.0, halt_ratio=2.0)


def test_warn_ratio_equal_halt_ratio_rejected():
    with pytest.raises(ValueError, match="warn_ratio"):
        compute_prov_drift([], warn_ratio=2.0, halt_ratio=2.0)


def test_negative_ratios_rejected():
    with pytest.raises(ValueError):
        compute_prov_drift([], warn_ratio=-1.0, halt_ratio=2.0)


def test_invalid_ewma_alpha_rejected():
    with pytest.raises(ValueError, match="ewma_alpha"):
        compute_prov_drift([], ewma_alpha=0.0)
    with pytest.raises(ValueError, match="ewma_alpha"):
        compute_prov_drift([], ewma_alpha=1.5)


def test_invalid_window_count_rejected():
    with pytest.raises(ValueError, match="window counts"):
        compute_prov_drift([], baseline_window_count=0)


# ─────────────────────────────────────────────────────────────────
# 8. Rollback chain detection (mock chain via derived_from links)
# ─────────────────────────────────────────────────────────────────


def test_rollback_chain_short():
    """Chain e1 ← e2 ← e3 → depth 2 (e3 → e2 → e1, e1 has no parent)."""
    start = datetime(2026, 1, 1, 0, 0, 0)
    acts = [
        _activity(t=start, entity="e1"),
        _activity(t=start + timedelta(seconds=1), entity="e2", derived_from="e1"),
        _activity(t=start + timedelta(seconds=2), entity="e3", derived_from="e2"),
    ]
    assert _max_rollback_chain_depth(acts) == 2


def test_rollback_storm_triggers_severity():
    """Chain depth 6 > default threshold 5 → ROLLBACK_STORM severity."""
    start = datetime(2026, 1, 1, 0, 0, 0)
    acts = [_activity(t=start, entity="e0")]
    for i in range(1, 8):  # chain of 8 → depth 7
        acts.append(
            _activity(
                t=start + timedelta(seconds=i),
                entity=f"e{i}",
                derived_from=f"e{i - 1}",
            )
        )
    report = compute_prov_drift(acts)
    assert report.rollback_chain_max_depth >= 6
    assert report.severity == "ROLLBACK_STORM"


def test_rollback_chain_cycle_safe():
    """Cyclic derived_from must not loop forever."""
    start = datetime(2026, 1, 1, 0, 0, 0)
    acts = [
        _activity(t=start, entity="e1", derived_from="e2"),
        _activity(t=start + timedelta(seconds=1), entity="e2", derived_from="e1"),
    ]
    # No assertion on exact depth — just that it terminates.
    depth = _max_rollback_chain_depth(acts)
    assert depth >= 1
    assert depth <= 3  # bounded by visited-set


# ─────────────────────────────────────────────────────────────────
# 9. Pydantic serialization
# ─────────────────────────────────────────────────────────────────


def test_report_serialization():
    start = datetime(2026, 1, 1, 0, 0, 0)
    acts = _steady_stream(n=20, interval_sec=1.0, start=start)
    report = compute_prov_drift(acts)
    d = report.model_dump()
    assert "activity_count" in d
    assert d["activity_count"] == 20
    assert d["channel"] == "L3-prov-causal-flow"
    assert "severity" in d


def test_activity_pydantic_validates_min_length():
    with pytest.raises(ValueError):
        ProvActivity(
            timestamp=datetime(2026, 1, 1),
            agent="",
            action="update",
            entity="e1",
        )


def test_activity_optional_derived_from():
    a = ProvActivity(
        timestamp=datetime(2026, 1, 1),
        agent="alice",
        action="update",
        entity="e1",
    )
    assert a.derived_from is None


def test_severity_validator_rejects_bogus():
    with pytest.raises(ValueError, match="severity"):
        ProvDriftReport(
            activity_count=0,
            baseline_ewma=0.0,
            current_rate=0.0,
            ratio=0.0,
            distinct_agents=0,
            rollback_chain_max_depth=0,
            warn=False,
            halt=False,
            multi_author_flag=False,
            severity="WHATEVER",
        )
