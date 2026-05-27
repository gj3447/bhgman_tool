"""formal_context_builder TDD — 3 pre-filter + 순수 assembly + 추출 cypher.

# KG: eureka-formal-context-smoketest-2026-05-27, consensus-eureka-design-synthesis-2026-05-27
"""

from __future__ import annotations

from formal_context_builder import (
    DEFAULT_BULK_LABELS,
    FormalContextConfig,
    assemble_context,
    build_extraction_cypher,
    build_formal_context,
)


def test_assemble_groups_attributes_by_object():
    rows = [
        {
            "object": "RoslynDocs",
            "attributes": ["ALIGNS_WITH_AXIS:Execution and Runtime", "USES_ABSTRACT_DOMAIN:VM"],
        },
        {
            "object": "ConsulDocs",
            "attributes": [
                "ALIGNS_WITH_AXIS:Systems and Coordination",
                "USES_ABSTRACT_DOMAIN:Kernel",
            ],
        },
    ]
    ctx = assemble_context(rows)
    assert set(ctx.keys()) == {"RoslynDocs", "ConsulDocs"}
    assert "ALIGNS_WITH_AXIS:Execution and Runtime" in ctx["RoslynDocs"]
    assert isinstance(ctx["RoslynDocs"], frozenset)


def test_assemble_skips_null_object_and_empty_attrs():
    rows = [{"object": None, "attributes": ["x"]}, {"object": "A", "attributes": []}]
    assert assemble_context(rows) == {}


def test_extraction_cypher_carries_3_prefilters():
    q, params = build_extraction_cypher(FormalContextConfig())
    # ① bulk-exclude  ② hub-cap  ③ independent facets
    assert "bulk_labels" in q and "NONE(l IN labels(o)" in q
    assert "facet_deg <= $hub_cap" in q
    assert params["facet_rels"] == ["ALIGNS_WITH_AXIS", "USES_ABSTRACT_DOMAIN"]
    assert "KG_AI" in params["bulk_labels"]
    assert params["hub_cap"] == 4
    assert params["min_facets"] == 2


def test_default_bulk_labels_cover_known_noise():
    assert {"KG_AI", "Comment", "OCCAM_SLICED", "ARCHIVED"} <= DEFAULT_BULK_LABELS


def test_build_formal_context_with_fake_runner():
    def fake_runner(query, params):
        assert params["hub_cap"] == 4  # config wired into params
        return [
            {
                "object": "Roslyn",
                "attributes": ["ALIGNS_WITH_AXIS:Exec", "USES_ABSTRACT_DOMAIN:VM"],
            },
            {
                "object": "Consul",
                "attributes": ["ALIGNS_WITH_AXIS:Sys", "USES_ABSTRACT_DOMAIN:Kernel"],
            },
            {
                "object": "Cockroach",
                "attributes": ["ALIGNS_WITH_AXIS:State", "USES_ABSTRACT_DOMAIN:Coordination"],
            },
        ]

    ctx, meta = build_formal_context(fake_runner)
    assert meta["objects"] == 3
    assert meta["avg_intent"] == 2.0
    assert meta["hub_cap"] == 4
    assert "KG_AI" in meta["bulk_excluded"]


def test_custom_config_overrides_facets():
    cfg = FormalContextConfig(
        facet_rels=("IN_CATEGORY",), hub_degree_cap=2, min_facets_per_object=1
    )
    q, params = build_extraction_cypher(cfg)
    assert params["facet_rels"] == ["IN_CATEGORY"]
    assert params["hub_cap"] == 2
    assert params["min_facets"] == 1
