"""Tests for KG VR → instrument log backfill.

PROM 16 follow-up: verify backfill correctness without requiring a live KG.
"""

from __future__ import annotations

from pathlib import Path

from engine.legion.threshold_derivation.backfill_kg import BACKFILL_PLAN, backfill_one
from engine.legion.threshold_derivation.instrument import DispatchInstrumentLog


class TestBackfillPlan:
    def test_plan_covers_4_metrics(self) -> None:
        assert len(BACKFILL_PLAN) == 4
        commanders = {row[1] for row in BACKFILL_PLAN}
        assert commanders == {"prometheus", "naesengmoon"}

    def test_plan_marks_proxies(self) -> None:
        proxy_metrics = [row[2] for row in BACKFILL_PLAN if "proxy" in row[2]]
        assert len(proxy_metrics) == 3


class TestBackfillOne:
    def test_appends_labeled_pairs(self, tmp_path: Path) -> None:
        log = DispatchInstrumentLog(path=tmp_path / "log.jsonl")
        pairs = [
            (0.85, "APPROVED", "vr-001"),
            (0.42, "REJECTED", "vr-002"),
            (0.71, "CONDITIONAL_APPROVED", "vr-003"),
        ]
        appended, skipped = backfill_one(
            log, "confidence", "naesengmoon", "confidence_proxy", pairs
        )
        assert appended == 3
        assert skipped == 0
        loaded = log.load_pairs("naesengmoon", "confidence_proxy")
        assert (0.85, 1) in loaded
        assert (0.42, 0) in loaded
        assert (0.71, 1) in loaded

    def test_skips_ambiguous_verdicts(self, tmp_path: Path) -> None:
        log = DispatchInstrumentLog(path=tmp_path / "log.jsonl")
        pairs = [
            (0.5, "BORDERLINE", "vr-a"),
            (0.6, "PARTIAL", "vr-b"),
            (0.7, "INTENTIONAL_EDIT", "vr-c"),
            (0.8, "APPROVED", "vr-d"),
        ]
        appended, skipped = backfill_one(
            log, "confidence", "naesengmoon", "confidence_proxy", pairs
        )
        assert appended == 1
        assert skipped == 3

    def test_dispatch_id_includes_backfill_prefix(self, tmp_path: Path) -> None:
        log_path = tmp_path / "log.jsonl"
        log = DispatchInstrumentLog(path=log_path)
        pairs = [(0.85, "APPROVED", "vr-named-001")]
        backfill_one(log, "confidence", "naesengmoon", "confidence_proxy", pairs)
        content = log_path.read_text()
        assert "backfill::naesengmoon::confidence_proxy::vr-named-001" in content

    def test_empty_pairs_no_writes(self, tmp_path: Path) -> None:
        log = DispatchInstrumentLog(path=tmp_path / "log.jsonl")
        appended, skipped = backfill_one(log, "any", "prometheus", "x", [])
        assert appended == 0
        assert skipped == 0
