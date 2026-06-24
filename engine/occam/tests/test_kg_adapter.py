"""오캄 KG 어댑터 TDD — read(SourceCodeNode→NodeRecord) + write(supersede, covenant).

covenant 핵심: write cypher에 DELETE/DETACH/REMOVE 토큰 부재 (archive-only, reversible).

# KG: occam-kam-canonical-2026-05-26, lesson-occam-must-query-kg-node-dedup-not-just-filesystem-2026-05-27
"""

from __future__ import annotations

from engine.occam.kg_adapter import (
    FORBIDDEN_TOKENS,
    apply_supersessions,
    build_supersede,
    fetch_cypher,
    fetch_source_nodes,
    parse_node_records,
)
from engine.occam.occam import occam_pass
from engine.occam.occam_models import NodeRecord


class _RecordingRunner:
    """fake CypherRunner — 호출 기록 + 미리 준 rows 반환."""

    def __init__(self, rows: list[dict] | None = None):
        self.rows = rows or []
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, cypher: str, params: dict) -> list[dict]:
        self.calls.append((cypher, params))
        return self.rows


# ── READ ──────────────────────────────────────────────────────────────────


def test_fetch_cypher_no_scope_is_unfiltered():
    cypher, params = fetch_cypher(None)
    assert "SourceCodeNode" in cypher
    assert params == {}
    assert "$scope" not in cypher


def test_fetch_cypher_scope_binds_param():
    cypher, params = fetch_cypher("engine/occam")
    assert "$scope" in cypher
    assert params == {"scope": "engine/occam"}


def test_fetch_cypher_excludes_already_superseded():
    # dogfood 교훈: 이미 아카이브된 과거를 재처리하지 않는다.
    for scope in (None, "engine/occam"):
        cypher, _ = fetch_cypher(scope)
        assert "SUPERSEDED" in cypher  # exclusion clause present


def test_parse_skips_incomplete_rows():
    rows = [
        {"name": "a", "source_path": "bhgman_tool/x.py", "sha256": "s", "line_count": 10},
        {"name": "b", "source_path": None, "sha256": "s", "line_count": 5},  # incomplete
        {"name": "c", "source_path": "bhgman_tool/y.py", "sha256": None, "line_count": 5},
    ]
    recs = parse_node_records(rows)
    assert len(recs) == 1
    assert recs[0].name == "a"
    assert recs[0].line_count == 10


def test_fetch_source_nodes_uses_runner():
    runner = _RecordingRunner(
        [{"name": "a", "source_path": "bhgman_tool/x.py", "sha256": "s", "line_count": 10}]
    )
    recs = fetch_source_nodes(runner, scope="bhgman_tool")
    assert len(recs) == 1
    assert runner.calls[0][1] == {"scope": "bhgman_tool"}


# ── WRITE (covenant) ────────────────────────────────────────────────────────


def _dup_report():
    stale = NodeRecord("old", "bhgman_tool/x.py", "o", 10)
    new = NodeRecord("new", "bhgman_tool/x.py", "n", 99)
    return occam_pass([stale, new])


def test_build_supersede_keys_by_name_and_sets_status():
    report = _dup_report()
    cypher, params = build_supersede(report.candidates[0])
    assert params["stale_name"] == "old"
    assert params["current_name"] == "new"
    assert "SUPERSEDED" in cypher
    assert "SUPERSEDED_BY" in cypher  # reversible edge


def test_build_supersede_covenant_no_destructive_token():
    report = _dup_report()
    cypher, _ = build_supersede(report.candidates[0])
    up = cypher.upper()
    for tok in FORBIDDEN_TOKENS:
        assert tok not in up, f"covenant violation: {tok} in occam supersede cypher"


def test_apply_dry_run_default_does_not_write():
    report = _dup_report()
    runner = _RecordingRunner()
    result = apply_supersessions(report, write_cypher=runner)  # dry_run defaults True
    assert result.dry_run is True
    assert result.applied_count == 0
    assert runner.calls == []  # covenant: no write in dry-run
    assert len(result.planned_cyphers) == 1


def test_apply_with_write_executes_per_candidate():
    report = _dup_report()
    runner = _RecordingRunner([{"superseded": "old", "current": "new"}])  # cypher matched a row
    result = apply_supersessions(report, write_cypher=runner, dry_run=False)
    assert result.dry_run is False
    assert result.applied_count == 1
    assert len(runner.calls) == 1
    assert "old" in result.superseded


def test_apply_should_apply_gate_defers_rejected_candidates():
    # 주입식 should_apply가 False인 후보는 write 안 하고 deferred로 분류 (σ-gate 메커니즘).
    # None이면 legacy(전부 적용) — 위 test_apply_with_write_executes_per_candidate가 그 경로.
    report = _dup_report()
    runner = _RecordingRunner([{"superseded": "old", "current": "new"}])
    result = apply_supersessions(
        report, write_cypher=runner, dry_run=False, should_apply=lambda _c: False
    )
    assert result.applied_count == 0
    assert runner.calls == []  # gate가 막아 write 안 함
    assert "old" in result.deferred


def test_apply_dry_run_reports_deferred_under_gate():
    report = _dup_report()
    runner = _RecordingRunner()
    result = apply_supersessions(
        report, write_cypher=runner, should_apply=lambda _c: False
    )  # dry_run 기본
    assert result.dry_run is True
    assert result.planned_cyphers == ()  # gate가 막은 후보는 planned에서도 제외
    assert "old" in result.deferred


def test_apply_counts_rows_not_candidates_on_no_match():
    """W1-G: a planned supersession whose cypher matches 0 rows (node absent / already
    superseded) must NOT be counted as applied — report planned vs actual honestly."""
    report = _dup_report()
    runner = _RecordingRunner(rows=[])  # cypher ran but matched nothing
    result = apply_supersessions(report, write_cypher=runner, dry_run=False)
    assert result.applied_count == 0
    assert len(runner.calls) == 1  # it DID run the cypher (not an exact-dup)
    assert any("0 rows" in n for n in result.notes)


def test_apply_refuses_exact_duplicate_without_running_cypher():
    """W1-G: identical (sourcePath, sha256) can't be distinguished by the supersede key —
    refuse + flag rather than no-op-but-claim-applied or archive both twins."""
    a = NodeRecord("urdna.py", "bhgman_tool/engine/urdna.py", "same", 190)
    b = NodeRecord("urdna.py", "bhgman_tool/engine/urdna.py", "same", 190)
    report = occam_pass([a, b])
    assert report.candidates and report.candidates[0].reason  # occam flagged an exact dup
    runner = _RecordingRunner([{"superseded": "x", "current": "y"}])
    result = apply_supersessions(report, write_cypher=runner, dry_run=False)
    assert result.applied_count == 0
    assert runner.calls == []  # refused: the ambiguous cypher never ran
    assert any("exact-duplicate" in n.lower() or "exact dup" in n.lower() for n in result.notes)


def test_apply_no_write_cypher_forces_dry_run():
    report = _dup_report()
    result = apply_supersessions(report, write_cypher=None, dry_run=False)
    assert result.dry_run is True
    assert result.applied_count == 0
