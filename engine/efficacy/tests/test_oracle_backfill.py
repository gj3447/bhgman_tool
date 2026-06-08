"""oracle_backfill 순수부 테스트 — invocation 카운트 + 백필 플랜."""

from __future__ import annotations

import json

from engine.efficacy.oracle_backfill import build_backfill_plan, count_invocations


def _line(tool, fp):
    return json.dumps(
        {"message": {"content": [{"type": "tool_use", "name": tool, "input": {"file_path": fp}}]}}
    )


def test_counts_file_tools_for_repo_paths():
    lines = [
        _line("Read", "/Users/x/CD/bhgman_tool/engine/occam/occam.py"),
        _line("Edit", "/Users/x/CD/bhgman_tool/engine/occam/occam.py"),
        _line("Read", "bhgman_tool/engine/scoring.py"),
    ]
    counts = count_invocations(lines)
    assert counts["engine/occam/occam.py"] == 2
    assert counts["engine/scoring.py"] == 1


def test_ignores_non_file_tools_and_external_paths():
    lines = [
        _line("Bash", "/Users/x/CD/bhgman_tool/x.py"),  # Bash 무시
        _line("Read", "/Users/x/CD/SYMPOSIUM/other.md"),  # repo 밖 무시
        json.dumps({"message": {"content": [{"type": "text", "text": "no file_path"}]}}),
    ]
    assert count_invocations(lines) == {}


def test_skips_lines_without_file_path_and_corrupt():
    lines = ["not json at all", "{broken", json.dumps({"message": {}})]
    assert count_invocations(lines) == {}


def test_backfill_plan_marks_invocation_and_disk():
    nodes = [
        {"name": "a", "sourcePath": "bhgman_tool/engine/live.py"},
        {"name": "b", "sourcePath": "/Users/x/bhgman_tool/engine/gone.py"},
        {"name": "ext", "sourcePath": "/Users/x/SYMPOSIUM/x.md"},  # 외부 → 제외
    ]
    invocations = {"engine/live.py": 5}
    live = frozenset({"engine/live.py"})
    plan = build_backfill_plan(nodes, invocations, live)
    assert len(plan) == 2  # 외부 제외
    by_name = {p["name"]: p for p in plan}
    assert by_name["a"]["invocation_count"] == 5 and by_name["a"]["disk_present"] is True
    assert by_name["b"]["invocation_count"] == 0 and by_name["b"]["disk_present"] is False


def test_backfill_plan_empty_when_all_external():
    nodes = [{"name": "x", "sourcePath": "/Users/x/SYMPOSIUM/x.md"}]
    assert build_backfill_plan(nodes, {}, frozenset()) == []


# ── scoring_bridge + run_kg_efficacy ──────────────────────────────────────────

from engine.efficacy.run_kg_efficacy import rows_to_items  # noqa: E402
from engine.efficacy.scoring_bridge import sigma_from_row  # noqa: E402


def test_sigma_low_invocation_high_candidacy():
    # 미사용(inv=0) → deadness 높음 → candidacy 높음
    dead = sigma_from_row({"invocation_count": 0, "twins": 0})
    live = sigma_from_row({"invocation_count": 100, "twins": 0})
    assert dead > live
    assert 0.0 <= live < dead <= 1.0


def test_sigma_twin_raises_candidacy():
    no_twin = sigma_from_row({"invocation_count": 100, "twins": 0})
    twin = sigma_from_row({"invocation_count": 100, "twins": 1})
    assert twin >= no_twin


def test_rows_to_items_labels_stale_as_positive():
    rows = [
        {
            "name": "gone",
            "disk_present": False,
            "invocation_count": 0,
            "twins": 0,
            "provenance": "",
        },
        {
            "name": "live",
            "disk_present": True,
            "invocation_count": 50,
            "twins": 0,
            "provenance": "",
        },
    ]
    items = rows_to_items(rows)
    by = {i.item_id: i for i in items}
    assert by["gone"].is_positive is True and by["live"].is_positive is False
    assert by["gone"].signal > by["live"].signal  # stale가 더 높은 신호
