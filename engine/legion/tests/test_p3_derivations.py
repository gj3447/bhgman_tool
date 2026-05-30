"""Tests for P3 derivation modules — instrument / scheduler / signed_config / audit.

PROM 16 P3(a-e) ActionPlan.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from engine.legion.threshold_derivation.calibration_audit import (
    AuditVerdict,
    LensVerdict,
    audit_threshold,
)
from engine.legion.threshold_derivation.instrument import DispatchInstrumentLog
from engine.legion.threshold_derivation.scheduler import (
    CalibrationScheduleEntry,
    sample_next_audit,
)
from engine.legion.threshold_derivation.signed_config import (
    compute_digest,
    bind_to_dispatch_payload,
    verify_digest,
)


class TestInstrumentLog:
    def test_record_and_load_roundtrip(self, tmp_path: Path) -> None:
        log = DispatchInstrumentLog(path=tmp_path / "log.jsonl")
        log.record("eureka", "binding_density", 0.42, 1)
        log.record("eureka", "binding_density", 0.71, 0)
        pairs = log.load_pairs("eureka", "binding_density")
        assert pairs == [(0.42, 1), (0.71, 0)]

    def test_filter_by_commander_metric(self, tmp_path: Path) -> None:
        log = DispatchInstrumentLog(path=tmp_path / "log.jsonl")
        log.record("eureka", "binding_density", 0.5, 1)
        log.record("occam", "supersession_confidence", 0.8, 1)
        assert log.count("eureka", "binding_density") == 1
        assert log.count("occam", "supersession_confidence") == 1
        assert log.count("hades", "spec_ambiguity") == 0

    def test_rejects_invalid_outcome(self, tmp_path: Path) -> None:
        log = DispatchInstrumentLog(path=tmp_path / "log.jsonl")
        with pytest.raises(ValueError, match="outcome must be"):
            log.record("eureka", "binding_density", 0.5, 2)


class TestScheduler:
    def test_returns_entry_in_range(self) -> None:
        os.environ["BHGMAN_CALIBRATION_SEED"] = "0.5"
        try:
            entry = sample_next_audit(now=datetime(2026, 5, 30))
        finally:
            del os.environ["BHGMAN_CALIBRATION_SEED"]
        assert isinstance(entry, CalibrationScheduleEntry)
        assert 30.0 <= entry.interval_days <= 90.0

    def test_clamps_to_max(self) -> None:
        entry = sample_next_audit(now=datetime(2026, 5, 30), mean_days=200, max_days=90)
        assert entry.interval_days <= 90.0

    def test_clamps_to_min(self) -> None:
        os.environ["BHGMAN_CALIBRATION_SEED"] = "0.99"
        try:
            entry = sample_next_audit(now=datetime(2026, 5, 30), mean_days=1)
        finally:
            del os.environ["BHGMAN_CALIBRATION_SEED"]
        assert entry.interval_days >= 30.0


class TestSignedConfig:
    def test_compute_and_verify(self, tmp_path: Path) -> None:
        p = tmp_path / "cfg.toml"
        p.write_text('[[threshold]]\ncommander = "test"\n')
        digest = compute_digest(p)
        assert digest.sha256
        assert digest.hmac_sha256
        assert verify_digest(digest) is True

    def test_verify_fails_on_mutation(self, tmp_path: Path) -> None:
        p = tmp_path / "cfg.toml"
        p.write_text("original")
        digest = compute_digest(p)
        p.write_text("tampered_content_x")
        assert verify_digest(digest) is False

    def test_verify_fails_on_missing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "ephemeral.toml"
        p.write_text("hi")
        digest = compute_digest(p)
        p.unlink()
        assert verify_digest(digest) is False

    def test_payload_binding(self, tmp_path: Path) -> None:
        p = tmp_path / "cfg.toml"
        p.write_text("hi")
        digest = compute_digest(p)
        payload = {"commander": "naesengmoon", "outcome": "DISPATCH"}
        bound = bind_to_dispatch_payload(payload, digest)
        assert bound["config_hmac"] == digest.hmac_sha256
        assert bound["commander"] == "naesengmoon"


class TestCalibrationAudit:
    def test_unanimous_pass(self) -> None:
        verdict = audit_threshold(
            threshold=0.7,
            actual_ece=0.05,
            null_ece_mean=0.10,
            null_ece_std=0.02,
            scale_valid=True,
            monotone_valid=True,
            disagreement_ratio=0.05,
        )
        assert isinstance(verdict, AuditVerdict)
        assert verdict.overall == LensVerdict.PASS
        assert len(verdict.lenses) == 3

    def test_scale_violation_blocks(self) -> None:
        verdict = audit_threshold(
            threshold=0.7,
            actual_ece=0.05,
            null_ece_mean=0.10,
            null_ece_std=0.02,
            scale_valid=False,
            monotone_valid=True,
            disagreement_ratio=0.05,
        )
        assert verdict.overall == LensVerdict.BLOCK

    def test_high_disagreement_blocks(self) -> None:
        verdict = audit_threshold(
            threshold=0.7,
            actual_ece=0.05,
            null_ece_mean=0.10,
            null_ece_std=0.02,
            scale_valid=True,
            monotone_valid=True,
            disagreement_ratio=0.25,
        )
        assert verdict.overall == LensVerdict.BLOCK

    def test_mid_disagreement_conditional(self) -> None:
        verdict = audit_threshold(
            threshold=0.7,
            actual_ece=0.05,
            null_ece_mean=0.10,
            null_ece_std=0.02,
            scale_valid=True,
            monotone_valid=True,
            disagreement_ratio=0.15,
        )
        assert verdict.overall == LensVerdict.CONDITIONAL

    def test_kg_props(self) -> None:
        verdict = audit_threshold(
            threshold=0.68,
            actual_ece=0.05,
            null_ece_mean=0.10,
            null_ece_std=0.02,
            scale_valid=True,
            monotone_valid=True,
            disagreement_ratio=0.05,
        )
        props = verdict.to_kg_props()
        assert props["threshold"] == 0.68
        assert props["overall"] == "pass"
        assert props["lens_count"] == 3
