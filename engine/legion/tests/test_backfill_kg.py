"""Tests for KG VR → instrument log backfill.

PROM 16 follow-up: verify backfill correctness without requiring a live KG.
"""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from engine.legion.threshold_derivation import backfill_kg
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


class TestBackfillConnectionConfig:
    def test_password_is_required_without_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
        with pytest.raises(SystemExit) as exc:
            backfill_kg.main([])
        assert exc.value.code == 2

    def test_connection_defaults_come_from_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict[str, object] = {}

        class FakeDriver:
            def close(self) -> None:
                captured["closed"] = True

        class FakeGraphDatabase:
            @staticmethod
            def driver(uri: str, auth: tuple[str, str]) -> FakeDriver:
                captured.update(uri=uri, auth=auth)
                return FakeDriver()

        monkeypatch.setenv("NEO4J_URI", "bolt://canonical.example:7687")
        monkeypatch.setenv("NEO4J_USER", "operator")
        monkeypatch.setenv("NEO4J_PASSWORD", "from-env")
        monkeypatch.setitem(
            sys.modules, "neo4j", SimpleNamespace(GraphDatabase=FakeGraphDatabase)
        )
        monkeypatch.setattr(backfill_kg, "BACKFILL_PLAN", ())

        assert backfill_kg.main(["--log-path", str(tmp_path / "log.jsonl")]) == 0
        assert captured == {
            "uri": "bolt://canonical.example:7687",
            "auth": ("operator", "from-env"),
            "closed": True,
        }


class TestBackfillOne:
    def test_appends_labeled_pairs(self, tmp_path: Path) -> None:
        log = DispatchInstrumentLog(path=tmp_path / "log.jsonl")
        pairs = [
            (0.85, "APPROVED", "vr-001"),
            (0.42, "REJECTED", "vr-002"),
            (0.71, "CONDITIONAL_APPROVED", "vr-003"),
        ]
        appended, skipped, _dup = backfill_one(
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
        appended, skipped, _dup = backfill_one(
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
        appended, ambig, dup = backfill_one(log, "any", "prometheus", "x", [])
        assert appended == 0
        assert ambig == 0
        assert dup == 0

    def test_incremental_dedup_skips_existing(self, tmp_path: Path) -> None:
        from engine.legion.threshold_derivation.backfill_kg import existing_dispatch_ids

        log = DispatchInstrumentLog(path=tmp_path / "log.jsonl")
        pairs = [(0.85, "APPROVED", "vr-A"), (0.42, "REJECTED", "vr-B")]
        backfill_one(log, "confidence", "naesengmoon", "confidence_proxy", pairs)
        seen = existing_dispatch_ids(log)
        assert len(seen) == 2
        new_pairs = [
            (0.85, "APPROVED", "vr-A"),
            (0.42, "REJECTED", "vr-B"),
            (0.71, "APPROVED", "vr-C"),
        ]
        appended, ambig, dup = backfill_one(
            log, "confidence", "naesengmoon", "confidence_proxy", new_pairs, seen_ids=seen
        )
        assert appended == 1
        assert dup == 2
        assert ambig == 0
