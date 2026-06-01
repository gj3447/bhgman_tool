"""production 표면 TDD — run-record(KG) + OTel attrs + PROV-O export.

# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01, prov-o-nanopub-export-2026-05-30
"""

from __future__ import annotations

import pytest

from engine.jaebaeman.jaebaeman_models import Goal, SeedStatus
from engine.jaebaeman.jaebaeman_runner import run_jaebaeman
from engine.jaebaeman.lifecycle import SeedOutcome, drive_seeds
from engine.jaebaeman.planner import static_decompose
from engine.jaebaeman.telemetry import (
    RunRecord,
    build_run_merge,
    from_results,
    record_to_kg,
    to_otel_attributes,
    to_prov,
)


def _plan_result():
    tree = {"g": [Goal(name="a", objective="A"), Goal(name="b", objective="B")]}
    return run_jaebaeman(Goal(name="g", objective="r"), decompose=static_decompose(tree))


# ── from_results ─────────────────────────────────────────────────────────────
def test_from_results_plan_only():
    rec = from_results("run-1", _plan_result(), created_at="2026-06-01T00:00:00")
    assert rec.goal == "g" and rec.planned_seeds == 3 and rec.dispatched == 0


def test_from_results_with_lifecycle():
    pr = _plan_result()
    lc = drive_seeds(
        list(pr.seeds),
        lambda ss: [SeedOutcome(s.name, SeedStatus.COLLECTED, "ok") for s in ss],
    )
    rec = from_results("run-2", pr, lc, created_at="2026-06-01T00:00:00")
    assert rec.dispatched == 3 and rec.collected == 3 and rec.failed == 0


# ── (1) KG audit record (covenant MERGE) ─────────────────────────────────────
def test_run_merge_is_merge_not_destructive():
    cypher, params = build_run_merge(RunRecord("run-x", "g", 3, created_at="t"))
    up = cypher.upper()
    assert "MERGE (R:JAEBAEMANRUN" in up
    assert all(tok not in up for tok in ("DELETE", "DETACH", "REMOVE"))
    assert params["run_id"] == "run-x" and params["planned"] == 3


def test_record_to_kg_calls_write():
    calls = []
    record_to_kg(
        RunRecord("run-y", "g", 2, created_at="t"), lambda c, p: calls.append((c, p)) or []
    )
    assert calls and calls[0][1]["run_id"] == "run-y"


# ── (2) OTel attributes ──────────────────────────────────────────────────────
def test_otel_attributes_shape():
    attrs = to_otel_attributes(RunRecord("run-z", "g", 5, collected=4, failed=1))
    assert attrs["jaebaeman.run_id"] == "run-z"
    assert attrs["jaebaeman.collected"] == 4 and attrs["jaebaeman.failed"] == 1
    assert all(k.startswith("jaebaeman.") for k in attrs)


# ── (3) PROV-O export (graceful) ─────────────────────────────────────────────
def test_to_prov_graceful_or_turtle():
    rec = RunRecord("run-p", "ship", 3, dispatched=3, collected=3)
    out = to_prov(rec)
    if out is None:
        pytest.skip("prov extra not installed — graceful None (expected)")
    assert "jbm" in out and "ship" in out  # turtle에 namespace + goal


# ── e2e: 표면이 실제 run에 붙는가 ─────────────────────────────────────────────
def test_end_to_end_surface_attaches():
    pr = _plan_result()
    rec = from_results("run-e2e", pr, created_at="2026-06-01T00:00:00")
    # 세 표면 모두 같은 run에서 파생
    assert build_run_merge(rec)[1]["planned"] == 3
    assert to_otel_attributes(rec)["jaebaeman.planned_seeds"] == 3
