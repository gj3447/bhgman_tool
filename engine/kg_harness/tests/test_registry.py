"""stable-id 레지스트리 + constraint 번들 TDD.

# KG: occam-pass-metahumotonic-20260626
"""

from __future__ import annotations

from engine.kg_harness.registry import (
    NEEDS_DEDUP,
    STABLE_IDS,
    UNCONSTRAINABLE,
    constraint_bundle,
)


def test_bundle_excludes_dirty_labels_by_default():
    bundle = constraint_bundle()
    joined = "\n".join(bundle)
    # 즉시 설치 가능(clean)만
    assert "kgh_Apostle_roman_unique" in joined
    assert "kgh_KnowledgeHub_name_unique" in joined
    # ReferenceSite는 50 stub dedup 후 복합키 clean → 복합 UNIQUE로 포함
    assert "kgh_ReferenceSite_sourceId_name_unique" in joined
    assert "REQUIRE (n.sourceId, n.name) IS UNIQUE" in joined
    # 아직 dedup 필요한 라벨은 제외
    # SubagentTaskSpec는 dedup 후 복합키 clean → 졸업(포함)
    assert "kgh_SubagentTaskSpec_sourceId_name_unique" in joined
    # SourceCodeNode는 archive-model상 단일키 영구충돌 → UNCONSTRAINABLE(제외)
    assert "SourceCodeNode" not in joined
    assert len(bundle) == len(STABLE_IDS) - len(NEEDS_DEDUP | UNCONSTRAINABLE)


def test_unconstrainable_excluded_even_with_no_dedup_pending():
    # archive-model 충돌(SourceCodeNode)은 dedup으로 해결 불가 → 항상 제외
    assert "SourceCodeNode" in UNCONSTRAINABLE
    assert NEEDS_DEDUP == frozenset()  # 현재 dedup 백로그 0
    assert "SourceCodeNode" not in "\n".join(constraint_bundle())


def test_composite_key_emits_composite_unique_constraint():
    from engine.kg_harness import constraint_cypher

    # 복합키 = 괄호 묶은 IS UNIQUE (null 키 노드 면제 — NODE KEY 아님)
    assert constraint_cypher("ReferenceSite", ("sourceId", "name")) == (
        "CREATE CONSTRAINT kgh_ReferenceSite_sourceId_name_unique IF NOT EXISTS "
        "FOR (n:ReferenceSite) REQUIRE (n.sourceId, n.name) IS UNIQUE"
    )
    # 단일키는 괄호 없는 IS UNIQUE
    assert constraint_cypher("Apostle", "roman") == (
        "CREATE CONSTRAINT kgh_Apostle_roman_unique IF NOT EXISTS "
        "FOR (n:Apostle) REQUIRE n.roman IS UNIQUE"
    )


def test_include_pending_emits_full_set():
    full = constraint_bundle(include_pending=True)
    assert len(full) == len(STABLE_IDS)
    assert any("ReferenceSite_sourceId" in c for c in full)


def test_every_constraint_is_valid_ddl_shape():
    for ddl in constraint_bundle(include_pending=True):
        assert ddl.startswith("CREATE CONSTRAINT kgh_")
        assert "IF NOT EXISTS" in ddl
        assert "IS UNIQUE" in ddl


def test_needs_dedup_is_subset_of_registry():
    assert NEEDS_DEDUP <= set(STABLE_IDS)


def test_apostle_roman_is_registered():
    # 이미 손으로 검증·정리한 라벨 — 레지스트리에 박혀 있어야 회귀 방지.
    assert STABLE_IDS["Apostle"] == "roman"
    assert "Apostle" not in NEEDS_DEDUP
