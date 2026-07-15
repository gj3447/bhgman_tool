"""stable-id 레지스트리 + constraint 번들 TDD.

# KG: occam-pass-metahumotonic-20260626
"""

from __future__ import annotations

import re

from engine.kg_harness.registry import (
    NEEDS_DEDUP,
    STABLE_IDS,
    UNCONSTRAINABLE,
    constraint_bundle,
)
from engine.legion.legion import _DISPATCH_EVENT_MERGE


def _merge_identity_keys(merge_cypher: str, label: str) -> set[str]:
    """Extract the MERGE identity property keys from `MERGE (x:Label {k1:$k1, k2:$k2, ...})`."""
    m = re.search(rf"MERGE \(\w+:{label} \{{([^}}]*)\}}", merge_cypher)
    assert m, f"no MERGE (…:{label} {{…}}) block found"
    return set(re.findall(r"(\w+)\s*:\s*\$", m.group(1)))


def test_dispatch_event_stable_id_matches_engine_merge_identity():
    """T0-2 landmine: STABLE_IDS['DispatchEvent'] MUST equal the engine's runtime MERGE identity.
    A single-key constraint (source_commander only) would fail the 2nd DispatchEvent from any
    commander with ConstraintValidationFailed once installed — killing dispatch provenance on a
    live KG. The registry key and legion._DISPATCH_EVENT_MERGE are one identity, kept coupled."""
    engine_keys = _merge_identity_keys(_DISPATCH_EVENT_MERGE, "DispatchEvent")
    registry_key = STABLE_IDS["DispatchEvent"]
    registry_keys = {registry_key} if isinstance(registry_key, str) else set(registry_key)
    assert registry_keys == engine_keys, (
        f"registry {registry_keys} != engine MERGE identity {engine_keys} — installing the "
        f"constraint would collide on the non-identity fields"
    )


def test_dispatch_event_constraint_is_composite():
    """The generated DDL must be a composite UNIQUE over the full 5-key identity, not single-key."""
    ddl = next(c for c in constraint_bundle() if ":DispatchEvent)" in c)
    assert "(n.source_commander, n.target_commander, n.metric_name, n.epoch, n.decided_at)" in ddl


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
