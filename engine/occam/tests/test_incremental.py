"""오캄 증분 fetch 테스트 — PROM 6 C7 (watermark: 풀스캔 O(all) → O(changed)).

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A2-2026-07-19
"""

from __future__ import annotations

from engine.occam.kg_adapter import _SUPERSEDE_CYPHER, fetch_cypher_since


def test_since_filters_on_updatedat_watermark():
    cypher, params = fetch_cypher_since(1234)
    assert "s.updatedAt > $watermark" in cypher
    assert "s.updatedAt IS NOT NULL" in cypher  # unstamped 노드는 증분에서 제외
    assert params == {"watermark": 1234}


def test_since_still_excludes_archived_and_requires_fields():
    cypher, _ = fetch_cypher_since(0)
    up = cypher.upper()
    assert "NOT S:ARCHIVED" in up  # 무덤 제외 유지
    assert "S.SHA256 IS NOT NULL" in up  # 필수필드 가드 유지


def test_since_scoped_binds_both_params():
    cypher, params = fetch_cypher_since(99, scope="engine/occam")
    assert "$scope" in cypher and "$watermark" in cypher
    assert params == {"watermark": 99, "scope": "engine/occam"}


def test_supersede_stamps_updatedat():
    # C7: 모든 write 가 updatedAt 을 stamp 해야 watermark 가 일관 (archive 이벤트 포함).
    assert "stale.updatedAt = timestamp()" in _SUPERSEDE_CYPHER
