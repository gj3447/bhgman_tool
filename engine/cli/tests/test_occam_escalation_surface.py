"""cmd_occam must surface the escalation plan + deferred candidates (CLI/MCP/legion parity).

MCP and legion both go through engine.occam_engine.summarize_occam_result, which calls
build_escalation_plan(report) and reports deferred candidates + 나생문/Longinus routing. But
cmd_occam only printed the summary, planned cyphers, and disk-orphans — it never built the
escalation plan, so the σ-gate's uncertain (deferred) candidates and their verify routing were
INVISIBLE on the most-used surface. An uncertain supersession would silently vanish from the CLI.

# KG: finding-occam-cli-discards-escalation-plan-2026-06-26
"""

from __future__ import annotations

import types

from engine.cli.main import cli
from engine.occam.occam_models import (
    Confidence,
    NodeRecord,
    OccamReport,
    SupersessionCandidate,
)


def _uncertain_result():
    """A real OccamReport with one σ-gate-uncertain candidate (verdict=VERIFY → escalation),
    plus a deferred entry — the exact shape the CLI used to drop."""
    stale = NodeRecord(name="old_dup", source_path="a/x.py", sha256="aaa", line_count=10)
    current = NodeRecord(name="new_dup", source_path="b/x.py", sha256="bbb", line_count=12)
    cand = SupersessionCandidate(
        stale=stale,
        current=current,
        normalized_path="x.py",
        reason="partial overlap, not byte-identical",
        confidence=Confidence.MEDIUM,
        verdict="VERIFY",  # ≠ SUPERSEDE → uncertain → deferred + escalated
    )
    report = OccamReport(candidates=(cand,), scanned_nodes=2, groups_with_dups=1)
    apply_result = types.SimpleNamespace(
        dry_run=True, planned_cyphers=[], superseded=[], deferred=("old_dup",), notes=()
    )
    return types.SimpleNamespace(
        summary="occam: 1 group, 1 uncertain", report=report, apply_result=apply_result, scope=None
    )


def _patch(monkeypatch):
    read = types.SimpleNamespace()
    write = types.SimpleNamespace()
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: (read, write, lambda: None))
    monkeypatch.setattr("engine.occam.occam_runner.run_occam", lambda *a, **k: _uncertain_result())


def _scored_result():
    stale = NodeRecord(name="old_dup", source_path="a/x.py", sha256="aaa", line_count=10)
    current = NodeRecord(name="new_dup", source_path="b/x.py", sha256="bbb", line_count=12)
    cand = SupersessionCandidate(
        stale=stale,
        current=current,
        normalized_path="x.py",
        reason="partial overlap",
        confidence=Confidence.MEDIUM,
        score=0.42,
        verdict="VERIFY",
    )
    report = OccamReport(candidates=(cand,), scanned_nodes=2, groups_with_dups=1)
    apply_result = types.SimpleNamespace(
        dry_run=True, planned_cyphers=[], superseded=[], deferred=(), notes=()
    )
    return types.SimpleNamespace(
        summary="occam: 1 scored", report=report, apply_result=apply_result, scope=None
    )


def test_occam_cli_surfaces_candidate_sigma(monkeypatch, capsys):
    read, write = types.SimpleNamespace(), types.SimpleNamespace()
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: (read, write, lambda: None))
    monkeypatch.setattr("engine.occam.occam_runner.run_occam", lambda *a, **k: _scored_result())
    rc = cli(["occam", "--no-disk-scan"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "σ=0.42" in out  # the continuous safety value is now surfaced
    assert "VERIFY" in out


def test_occam_cli_surfaces_escalation_and_deferred(monkeypatch, capsys):
    _patch(monkeypatch)
    rc = cli(["occam", "--no-disk-scan"])
    out = capsys.readouterr().out
    assert rc == 0
    # the σ-gate deferred candidate must be visible (not silently dropped)
    assert "deferred" in out.lower()
    assert "old_dup" in out
    # the escalation routing (build_escalation_plan) must be surfaced like MCP/legion
    assert "escalate" in out.lower()
    assert "/tlb old_dup" in out  # the 나생문 verify invocation from the plan
