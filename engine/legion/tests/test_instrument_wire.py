"""Tests for measurement.py × instrument.py wire — record_outcome path.

PROM 16 P3(a) follow-up: verify CommanderBase.record_outcome correctly
appends to DispatchInstrumentLog after a real decide_dispatch decision.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.legion.measurement import (
    NaesengmoonMeasurement,
    OccamMeasurement,
    PrometheusMeasurement,
)
from engine.legion.threshold_derivation.instrument import DispatchInstrumentLog


class TestInstrumentWire:
    def test_no_instrument_is_silent_noop(self) -> None:
        cmd = PrometheusMeasurement(finding_count=20)
        decisions = cmd.decide_dispatch()
        assert decisions
        cmd.record_outcome(decisions[0], outcome=1)

    def test_record_outcome_appends_to_log(self, tmp_path: Path) -> None:
        log = DispatchInstrumentLog(path=tmp_path / "log.jsonl")
        cmd = PrometheusMeasurement(finding_count=20)
        cmd.set_instrument_log(log)
        decisions = cmd.decide_dispatch()
        assert decisions
        cmd.record_outcome(decisions[0], outcome=1, cycle_id="cyc-test-1")
        pairs = log.load_pairs("prometheus", "research_finding_count")
        assert pairs == [(20.0, 1)]

    def test_multiple_decisions_log_distinctly(self, tmp_path: Path) -> None:
        log = DispatchInstrumentLog(path=tmp_path / "log.jsonl")
        cmd_p = PrometheusMeasurement(finding_count=18)
        cmd_o = OccamMeasurement(supersession_confidence=0.5)
        cmd_p.set_instrument_log(log)
        cmd_o.set_instrument_log(log)
        d_p = cmd_p.decide_dispatch()
        d_o = cmd_o.decide_dispatch()
        assert d_p and d_o
        cmd_p.record_outcome(d_p[0], 1)
        cmd_o.record_outcome(d_o[0], 0)
        assert log.count("prometheus", "research_finding_count") == 1
        assert log.count("occam", "supersession_confidence") == 1

    def test_outcome_validation_propagates(self, tmp_path: Path) -> None:
        log = DispatchInstrumentLog(path=tmp_path / "log.jsonl")
        cmd = PrometheusMeasurement(finding_count=20)
        cmd.set_instrument_log(log)
        decisions = cmd.decide_dispatch()
        with pytest.raises(ValueError, match="outcome must be"):
            cmd.record_outcome(decisions[0], outcome=2)

    def test_naesengmoon_records_metric_value_correctly(self, tmp_path: Path) -> None:
        log = DispatchInstrumentLog(path=tmp_path / "log.jsonl")
        cmd = NaesengmoonMeasurement(RTI_FVR_pass_rate=0.5)
        cmd.set_instrument_log(log)
        decisions = cmd.decide_dispatch()
        nsm_self_dispatch = [d for d in decisions if d.metric_name == "RTI_FVR_pass_rate"]
        assert nsm_self_dispatch
        cmd.record_outcome(nsm_self_dispatch[0], outcome=1, cycle_id="cyc-nsm-2")
        pairs = log.load_pairs("naesengmoon", "RTI_FVR_pass_rate")
        assert pairs == [(0.5, 1)]

    def test_set_instrument_log_can_disable(self, tmp_path: Path) -> None:
        log = DispatchInstrumentLog(path=tmp_path / "log.jsonl")
        cmd = PrometheusMeasurement(finding_count=20)
        cmd.set_instrument_log(log)
        decisions = cmd.decide_dispatch()
        cmd.record_outcome(decisions[0], 1)
        cmd.set_instrument_log(None)
        cmd.record_outcome(decisions[0], 0)
        assert log.count("prometheus", "research_finding_count") == 1
