"""오캄 의미론 near-dup 엔진 검증 — fake 임베딩(무모델)으로 결정론 확인.

증명: cosine 정확성, threshold 경계, keep/drop 결정론, PROPOSE 기본, apply write,
covenant(파괴 토큰 0), idempotent.

# KG: rf-semdist-occam-2026-06-01
"""

from __future__ import annotations

import math

import pytest

from engine.occam.semantic_dedup import (
    FORBIDDEN_TOKENS,
    NearDupPair,
    cosine,
    find_near_duplicates,
    plan_supersession,
    run_semantic_dedup,
)


def test_cosine_identical_and_orthogonal():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine([1.0, 2.0], [2.0, 4.0]) == pytest.approx(1.0)  # 평행 = 1


def test_cosine_safe_on_zero_and_mismatch():
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert cosine([1.0], [1.0, 2.0]) == 0.0
    assert cosine([], [1.0]) == 0.0


def test_find_near_duplicates_threshold():
    items = [
        ("a", [1.0, 0.0, 0.0]),
        ("b", [0.99, 0.14, 0.0]),  # cosine(a,b) ≈ 0.99
        ("c", [0.0, 0.0, 1.0]),  # orthogonal
    ]
    pairs = find_near_duplicates(items, threshold=0.95)
    assert len(pairs) == 1
    assert {pairs[0].keep_id, pairs[0].drop_id} == {"a", "b"}
    # 높은 threshold → 0 쌍
    assert find_near_duplicates(items, threshold=0.999) == []


def test_keep_drop_deterministic_tiebreak_and_weight():
    items = [("zeta", [1.0, 0.0]), ("alpha", [1.0, 0.0])]
    # 동률 weight → id 작은 쪽(alpha) keep
    p = find_near_duplicates(items, threshold=0.9)[0]
    assert p.keep_id == "alpha" and p.drop_id == "zeta"
    # weight 큰 쪽(zeta) keep
    p2 = find_near_duplicates(items, threshold=0.9, weight={"zeta": 10.0})[0]
    assert p2.keep_id == "zeta" and p2.drop_id == "alpha"


def test_plan_supersession_covenant_no_destructive_tokens():
    pair = NearDupPair(keep_id="canon", drop_id="stale", similarity=0.97)
    cypher, params = plan_supersession(pair, key="name", label="Lesson")
    up = cypher.upper()
    assert not any(tok in up for tok in FORBIDDEN_TOKENS)  # archive-only
    assert "SUPERSEDED" in up and "SUPERSEDED_BY" in up
    assert params["stale_id"] == "stale" and params["current_id"] == "canon"


def test_plan_supersession_rejects_bad_key():
    with pytest.raises(ValueError, match="key must be one of"):
        plan_supersession(NearDupPair("a", "b", 0.99), key="; DROP", label="Lesson")


def test_plan_supersession_scopes_match_to_label():
    """H5 (Tier-1 write-safety): the covenant forbids matching by bare `name` — an
    unlabeled `MATCH (stale) WHERE stale.name=$id` SETs status on EVERY node of ANY type
    in the KG that shares that name. The supersede MATCH must be scoped to the node label
    so it can only touch the intended type."""
    pair = NearDupPair(keep_id="canon", drop_id="stale", similarity=0.97)
    cypher, _ = plan_supersession(pair, key="name", label="Lesson")
    # both stale and current MATCH must carry the label — never a bare (stale)/(current)
    assert "(stale:Lesson" in cypher and "(current:Lesson" in cypher
    assert "MATCH (stale) " not in cypher and "MATCH (current) " not in cypher


def test_plan_supersession_rejects_injection_in_label():
    with pytest.raises(ValueError, match="label"):
        plan_supersession(
            NearDupPair("a", "b", 0.99), key="name", label="Lesson) DETACH DELETE n //"
        )


def test_plan_supersession_guards_already_archived():
    """H3: even the semantic supersede must not re-archive / point at an already-SUPERSEDED
    node — guard both sides on status."""
    cypher, _ = plan_supersession(NearDupPair("a", "b", 0.99), key="name", label="Lesson")
    up = cypher.upper()
    assert "STALE.STATUS" in up and "CURRENT.STATUS" in up
    assert up.count("<> 'SUPERSEDED'") >= 2


def test_semantic_covenant_rejects_apoc_destructive_procedure():
    """Tier-4: semantic supersede covenant 도 DELETE/DETACH/REMOVE 토큰 없이 노드를 파괴하는
    프로시저(apoc.refactor.mergeNodes)를 차단해야."""
    from engine.occam.semantic_dedup import _assert_archive_only

    with pytest.raises(AssertionError, match="covenant"):
        _assert_archive_only("CALL apoc.refactor.mergeNodes([a,b]) YIELD node RETURN node")


def test_semantic_covenant_passes_real_template():
    """판별 반대쪽: 실제 라벨-스코핑 supersede 템플릿은 통과."""
    from engine.occam.semantic_dedup import _SUPERSEDE_TMPL, _assert_archive_only

    _assert_archive_only(_SUPERSEDE_TMPL.format(key="name", label="Lesson"))  # no raise


# ── 파이프라인 (fake embed_fn) ───────────────────────────────────────────────
def _fake_embed(texts: list[str]) -> list[list[float]]:
    """결정론 fake: 같은 텍스트→같은 벡터, 'dup' 포함 텍스트끼리 거의 동일."""
    out = []
    for t in texts:
        if "koide" in t.lower():
            out.append([1.0, 0.0, 0.05])
        elif "eureka" in t.lower():
            out.append([0.0, 1.0, 0.0])
        else:
            # 텍스트 해시 기반 고정 벡터
            h = sum(ord(c) for c in t)
            out.append([math.sin(h), math.cos(h), 0.3])
    return out


def test_run_semantic_dedup_propose_default():
    items = [
        ("f1", "The Koide formula relates lepton masses"),
        ("f2", "Koide relation precision lepton mass"),  # near-dup of f1
        ("f3", "Eureka induces abstractions"),
    ]
    report = run_semantic_dedup(
        items, embed_fn=_fake_embed, threshold=0.95, label="ResearchFinding"
    )
    assert report.scanned == 3
    assert len(report.pairs) == 1
    assert {report.pairs[0].keep_id, report.pairs[0].drop_id} == {"f1", "f2"}
    assert report.dry_run is True  # PROPOSE 기본
    assert report.applied == 0
    assert len(report.planned_cyphers) == 1


def test_run_semantic_dedup_apply_writes():
    captured = []

    def write(cypher, params):
        captured.append((params["stale_id"], params["current_id"]))
        return [{"superseded": params["stale_id"], "current": params["current_id"]}]

    items = [("f1", "Koide a"), ("f2", "Koide b")]
    report = run_semantic_dedup(
        items,
        embed_fn=_fake_embed,
        threshold=0.9,
        key="findingId",
        label="ResearchFinding",
        write_cypher=write,
        apply=True,
    )
    assert report.dry_run is False
    assert report.applied == 1
    assert captured == [("f2", "f1")]  # f1 keep(작은 id), f2 drop


def test_run_semantic_dedup_no_match_not_counted_applied():
    """W3-C: a nullable/non-unique key that matches no node returns 0 rows — must NOT be
    counted as applied (was always incremented, masking a silent no-op write)."""

    def write(_cypher, _params):
        return []  # cypher ran but matched nothing (e.g. key=name was null)

    items = [("f1", "Koide a"), ("f2", "Koide b")]
    report = run_semantic_dedup(
        items,
        embed_fn=_fake_embed,
        threshold=0.9,
        key="name",
        label="Lesson",
        write_cypher=write,
        apply=True,
    )
    assert report.applied == 0


def test_run_semantic_dedup_idempotent_proposal():
    items = [("f1", "Koide a"), ("f2", "Koide b")]
    r1 = run_semantic_dedup(items, embed_fn=_fake_embed, threshold=0.9, label="Lesson")
    r2 = run_semantic_dedup(items, embed_fn=_fake_embed, threshold=0.9, label="Lesson")
    assert [(p.keep_id, p.drop_id) for p in r1.pairs] == [(p.keep_id, p.drop_id) for p in r2.pairs]


def test_empty_input_safe():
    report = run_semantic_dedup([], embed_fn=_fake_embed, label="Lesson")
    assert report.scanned == 0 and report.pairs == ()


# ---- kNN path (Neo4j native vector index, scales past O(N²)) ----


def test_near_duplicates_via_index_uses_knn_and_keeps_covenant():
    """near_duplicates_via_index surfaces the same NearDupPair shape as the O(N²)
    path, but candidate discovery comes from the injected vector-index kNN."""
    from engine.occam.semantic_dedup import near_duplicates_via_index
    from engine.embedding.neo4j_vector import VectorIndexSpec

    spec = VectorIndexSpec(index_name="vec_lesson", label="Lesson", dimensions=2)

    class FakeNeo4j:
        def __call__(self, cypher, params):
            # every queryNodes probe returns the same 2 neighbours (a self-hit + b)
            if "queryNodes" in cypher:
                return [
                    {"id": "a", "score": 1.0, "text": "x"},
                    {"id": "b", "score": 0.97, "text": "y"},
                ]
            return []

    def embed(texts):
        return [[1.0, 0.0] for _ in texts]

    items = [("a", "alpha"), ("b", "beta")]
    # b has more weight → must be kept, a dropped (covenant tiebreak preserved)
    pairs = near_duplicates_via_index(
        items,
        embed_fn=embed,
        run_cypher=FakeNeo4j(),
        spec=spec,
        threshold=0.95,
        weight={"a": 0.0, "b": 1.0},
    )
    assert len(pairs) == 1
    assert pairs[0].keep_id == "b" and pairs[0].drop_id == "a"
    assert pairs[0].similarity == 0.97


def test_near_duplicates_via_index_empty():
    from engine.occam.semantic_dedup import near_duplicates_via_index
    from engine.embedding.neo4j_vector import VectorIndexSpec

    spec = VectorIndexSpec(index_name="vec_x", label="X", dimensions=2)
    out = near_duplicates_via_index(
        [], embed_fn=lambda t: [], run_cypher=lambda c, p: [], spec=spec
    )
    assert out == []
