"""rewire 스크립트 생성 TDD.

# KG: occam-pass-metahumotonic-20260626
"""

from __future__ import annotations

from engine.kg_harness.rewire import rewire_script


def test_script_creates_temp_index_first():
    s = rewire_script()
    assert "CREATE INDEX kgh_superseded_name" in s


def test_script_only_backfills_single_twin():
    s = rewire_script()
    assert "size(twins) = 1" in s  # 모호한 multi-twin 제외
    assert "apoc.periodic.iterate" in s  # 서버사이드 배치(타임아웃 회피)


def test_script_is_reversible_and_tagged():
    s = rewire_script()
    assert 'r.by = "kgh-rewire-20260626"' in s
    assert "DELETE r" in s  # 되돌리기 경로 포함


def test_script_never_deletes_nodes():
    s = rewire_script()
    assert "DETACH DELETE" not in s and "DELETE s" not in s
    assert "DELETE n" not in s  # archive-only covenant: 노드 삭제 없음
