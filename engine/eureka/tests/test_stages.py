"""eureka stage 2/3/6/7 구현체 TDD — 순수부 + degrade + GraphRAG 체인 조합.

gds.leiden/vector 인프라부는 fake run_cypher로, 결정론부(summarize/rrf/drift)는 직접 검증.

# KG: eureka-canonical-2026-05-26, consensus-eureka-design-synthesis-2026-05-27
"""

from __future__ import annotations

from pipeline import PipelineConfig, run
from stages import (
    DriftLoopStage,
    HybridRetrievalStage,
    LeidenCommunityStage,
    SummarizeStage,
    leiden_stream_cypher,
    lexical_rrf,
    parse_communities,
    partition_stability,
    summarize_community,
    wire_default_stages,
)


class _Runner:
    def __init__(self, rows=None, raise_exc=None):
        self.rows = rows or []
        self.raise_exc = raise_exc
        self.calls = []

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        if self.raise_exc:
            raise self.raise_exc
        return self.rows


# ── Stage 2: Leiden ─────────────────────────────────────────────────────────


def test_leiden_cypher_binds_graph_and_gamma():
    cypher, params = leiden_stream_cypher("g1", 2.0)
    assert "gds.leiden.stream" in cypher
    assert params == {"graph": "g1", "gamma": 2.0}


def test_parse_communities_groups_by_id_skips_null():
    rows = [
        {"name": "A", "community": 0},
        {"name": "B", "community": 0},
        {"name": "C", "community": 1},
        {"name": None, "community": 1},  # skip
    ]
    assert parse_communities(rows) == {0: ["A", "B"], 1: ["C"]}


def test_leiden_stage_degrades_when_gds_absent():
    stage = LeidenCommunityStage(_Runner(raise_exc=RuntimeError("no gds")))
    res = stage.run({})
    assert res.ok is False
    assert "gds.leiden unavailable" in res.error


def test_leiden_stage_returns_communities_on_success():
    runner = _Runner([{"name": "A", "community": 0}, {"name": "B", "community": 0}])
    res = LeidenCommunityStage(runner).run({})
    assert res.ok is True
    assert res.payload["communities"] == {0: ["A", "B"]}


# ── Stage 3: Summarize (deterministic) ────────────────────────────────────────


def test_summarize_community_deterministic():
    s1 = summarize_community(0, ["c", "a", "b"])
    s2 = summarize_community(0, ["b", "c", "a"])
    assert s1 == s2  # 정렬 고정 → 재현 가능
    assert "3 members" in s1


def test_summarize_stage_consumes_communities():
    res = SummarizeStage().run({"communities": {0: ["A", "B"], 1: ["C"]}})
    assert res.ok
    assert set(res.payload["summaries"].keys()) == {0, 1}


# ── Stage 6: lexical RRF ──────────────────────────────────────────────────────


def test_lexical_rrf_ranks_by_token_overlap():
    summaries = {0: "topology algebra group", 1: "parser lexer grammar"}
    ranked = lexical_rrf("algebra topology", summaries)
    assert ranked[0][0] == 0  # community 0 matches more query tokens


def test_hybrid_retrieval_no_query_is_pass():
    res = HybridRetrievalStage().run({"summaries": {0: "x"}})
    assert res.ok and res.payload["ranked"] == []


# ── Stage 7: drift ────────────────────────────────────────────────────────────


def test_partition_stability_identical_is_one():
    p = {0: ["A", "B"], 1: ["C"]}
    assert partition_stability(p, p) == 1.0


def test_partition_stability_empty_prev_is_baseline_one():
    assert partition_stability({}, {0: ["A"]}) == 1.0


def test_drift_stage_flags_below_tau():
    # prev 한 군집이 3조각으로 분해 → best-match Jaccard 2/4=0.5 < τ 0.75 → drift
    res = DriftLoopStage(tau=0.75).run(
        {
            "previous_communities": {0: ["A", "B", "C", "D"]},
            "communities": {0: ["A", "B"], 1: ["C"], 2: ["D"]},
        }
    )
    assert res.ok
    assert res.payload["stability"] == 0.5
    assert res.payload["drifted"] is True


# ── 조합: pipeline이 stage 산출을 체인 (context-threading) ──────────────────


def test_pipeline_chains_leiden_into_summarize():
    """Stage 2(community) payload가 context에 merge되어 Stage 3(summarize)가 소비."""
    runner = _Runner([{"name": "A", "community": 0}, {"name": "B", "community": 0}])
    stages = wire_default_stages(runner)
    cfg = PipelineConfig(
        cycle_id="chain-test",
        stage_community=stages["stage_community"],
        stage_summarize=stages["stage_summarize"],
        stage_hybrid_retrieval=stages["stage_hybrid_retrieval"],
        stage_drift_loop=stages["stage_drift_loop"],
    )
    pr = run(reference_sites=[], formal_context={}, config=cfg)
    stage_names = {s.stage: s for s in pr.stages}
    assert stage_names["2-community"].ok
    summ = stage_names["3-summarize"]
    assert summ.ok and 0 in summ.payload["summaries"]  # community 0 요약됨 (체인 성공)
