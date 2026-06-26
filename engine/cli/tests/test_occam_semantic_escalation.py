"""cmd_occam_semantic must escalate semantic near-dup pairs to naesengmoon.

build_escalation_plan(report, *, semantic_pairs=) routes every semantic near-dup to
naesengmoon (covenant: byte-identity 없는 의미론 중복은 단독 supersede 금지, 항상 검증). But the
ONLY caller passing semantic_pairs= was a unit test — cmd_occam_semantic printed the pairs and
auto-superseded them on --apply with NO naesengmoon gate. The verify routing was a dead seam on
the CLI (MCP/legion parity gap).

# KG: finding-occam-semantic-pairs-never-escalated-2026-06-26
"""
from __future__ import annotations

from engine.cli.main import cli
from engine.occam.semantic_dedup import NearDupPair, SemanticDedupReport


def test_occam_semantic_escalates_pairs_to_naesengmoon(monkeypatch, capsys):
    def read(cypher, params=None):
        return [{"id": "keep1", "text": "shared phrasing"}, {"id": "drop1", "text": "shared phrasing"}]

    monkeypatch.setattr(
        "engine.cli.runtime.make_kg_runners", lambda: (read, read, lambda: None)
    )
    report = SemanticDedupReport(
        pairs=(NearDupPair(keep_id="keep1", drop_id="drop1", similarity=0.92),),
        scanned=2,
        threshold=0.5,
        dry_run=True,
    )
    monkeypatch.setattr(
        "engine.occam.semantic_dedup.run_semantic_dedup", lambda *a, **k: report
    )

    rc = cli(["occam", "--semantic", "--label", "Lesson", "--threshold", "0.5"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "drop=drop1" in out  # existing pair surfacing preserved
    # the byte-identity-free near-dup must be routed to naesengmoon verify, not silently dropped
    assert "escalate" in out.lower()
    assert "naesengmoon" in out.lower()
    assert "drop1" in out
