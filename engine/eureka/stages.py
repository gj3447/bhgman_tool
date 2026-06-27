"""eureka pipeline stage 2/3/6/7 구현체 — pipeline의 NotImplementedStage 주입점을 채운다.

GraphRAG 체인(Edge 2024): community → summarize → (induce) → retrieval / drift.
pipeline이 성공 stage의 dict payload를 context에 merge하므로 stage들이 순차로 산출을 잇는다.

**실 infra 검증 2026-05-27** (Neo4j 2026.02.3 Community + gds 2.27.1, MCP dogfood):
  - gds.leiden은 **UNDIRECTED projection 선행 필수** → LeidenCommunityStage가 project→stream→drop 수행.
    실 KG 86765 nodes/1.22M rels에서 community 반환 검증(FMEA/비행기맨 등 latent 군집).
  - vector retrieval = native `db.index.vector.queryNodes`(dim 768, researchfinding_embedding 검증).
    임베딩 backfill은 미populate(Lesson 0/1120) → query_embedding+index 주어질 때만 vector 채널 활성.

**정직한 의존 분리**: gds/vector 실행은 inject한 run_cypher 책임(부재 시 degrade). 순수부(cypher 빌더/
파싱/RRF/Jaccard/degrade)는 완전 TDD. 임베딩 생성(모델)은 미포함 — query_embedding 주입식.

# KG: eureka-canonical-2026-05-26, consensus-eureka-design-synthesis-2026-05-27,
#     consensus-eureka-engine-impl-2026-05-26
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from engine.eureka.protocols import StageResult

CypherRunner = Callable[[str, dict], "list[dict]"]


# ── Stage 2: Leiden community detection (gds, project→stream→drop) ──────────


def project_cypher(graph_name: str, orientation: str = "UNDIRECTED") -> tuple[str, dict]:
    # KG: eureka-canonical-2026-05-26
    """gds.graph.project (native, 전체 그래프). leiden은 UNDIRECTED 필수(실 검증). name만 $param."""
    cypher = (
        "CALL gds.graph.project($graph, '*', {R: {type: '*', orientation: $orient}}) "
        "YIELD graphName, nodeCount, relationshipCount "
        "RETURN graphName, nodeCount, relationshipCount"
    )
    return cypher, {"graph": graph_name, "orient": orientation}


def drop_cypher(graph_name: str) -> tuple[str, dict]:
    # KG: eureka-canonical-2026-05-26
    """gds.graph.drop(failIfMissing=false) — 멱등(없어도 에러 안 남). pre-drop + cleanup 겸용."""
    return (
        "CALL gds.graph.drop($graph, false) YIELD graphName RETURN graphName",
        {"graph": graph_name},
    )


def leiden_stream_cypher(graph_name: str, gamma: float) -> tuple[str, dict]:
    # KG: eureka-canonical-2026-05-26
    """gds.leiden.stream → flat (name, community) rows. randomSeed 고정 = 재현."""
    cypher = (
        "CALL gds.leiden.stream($graph, {gamma: $gamma, randomSeed: 42, maxLevels: 10}) "
        "YIELD nodeId, communityId "
        "RETURN gds.util.asNode(nodeId).name AS name, communityId AS community"
    )
    return cypher, {"graph": graph_name, "gamma": gamma}


def parse_communities(rows: list[dict]) -> dict[int, list[str]]:
    # KG: eureka-canonical-2026-05-26
    """[{name, community}] → {community_id: [names]}. None/결손 row skip."""
    out: dict[int, list[str]] = {}
    for r in rows:
        name, cid = r.get("name"), r.get("community")
        if name is None or cid is None:
            continue
        out.setdefault(int(cid), []).append(str(name))
    return out


class LeidenCommunityStage:
    # KG: eureka-canonical-2026-05-26
    """gds.leiden 군집화 — project(UNDIRECTED)→stream→drop. gds 부재 시 degrade(비치명적)."""

    def __init__(
        self, run_cypher: CypherRunner, graph_name: str = "eureka-proj", gamma: float = 1.0
    ):
        self.run_cypher = run_cypher
        self.graph_name = graph_name
        self.gamma = gamma
        self.name = "2-community"

    def _drop_quiet(self) -> None:
        try:
            self.run_cypher(*drop_cypher(self.graph_name))
        except Exception:  # noqa: BLE001 — cleanup best-effort
            pass

    def run(self, context: dict[str, Any]) -> StageResult:
        try:
            self._drop_quiet()  # 멱등: stale projection 제거 후
            self.run_cypher(*project_cypher(self.graph_name))  # UNDIRECTED project
            cypher, params = leiden_stream_cypher(self.graph_name, self.gamma)
            rows = self.run_cypher(cypher, params)
        except Exception as e:  # noqa: BLE001 — gds 부재/projection 실패 → degrade
            self._drop_quiet()
            return StageResult(self.name, False, error=f"gds.leiden unavailable: {e}")
        communities = parse_communities(rows)
        self._drop_quiet()  # 임시 projection cleanup
        return StageResult(self.name, True, payload={"communities": communities})


# ── Stage 3: per-community summarize (deterministic, LLM-free) ──────────────


def summarize_community(cid: int, members: list[str], top: int = 5) -> str:
    # KG: eureka-canonical-2026-05-26
    """결정론 digest — LLM 없이 멤버 수 + 대표 멤버. 재현 가능(정렬 고정)."""
    ms = sorted(members)
    head = ", ".join(ms[:top])
    more = f" (+{len(ms) - top} more)" if len(ms) > top else ""
    return f"community {cid}: {len(ms)} members — {head}{more}"


class SummarizeStage:
    # KG: eureka-canonical-2026-05-26
    """community→요약. context['communities'](Stage 2 산출) 소비. 결정론, 인프라 불필요."""

    name = "3-summarize"

    def run(self, context: dict[str, Any]) -> StageResult:
        communities: Mapping[int, list[str]] = context.get("communities") or {}
        summaries = {cid: summarize_community(cid, members) for cid, members in communities.items()}
        return StageResult(self.name, True, payload={"summaries": summaries})


# ── Stage 6: hybrid retrieval (lexical-community + native vector channel) ────


def _tokens(text: str) -> set[str]:
    return {t for t in text.lower().replace(",", " ").split() if len(t) > 2}


def lexical_rrf(query: str, summaries: Mapping[int, str], k: int = 60) -> list[tuple[int, float]]:
    # KG: eureka-canonical-2026-05-26
    """community-summary 토큰 overlap RRF 랭킹 (결정론)."""
    q = _tokens(query)
    scored = [(cid, len(q & _tokens(s))) for cid, s in summaries.items()]
    scored = [(cid, n) for cid, n in scored if n > 0]
    scored.sort(key=lambda x: (-x[1], x[0]))
    return [(cid, 1.0 / (k + rank)) for rank, (cid, _n) in enumerate(scored, start=1)]


def vector_query_cypher(index_name: str, k: int) -> tuple[str, dict]:
    # KG: eureka-canonical-2026-05-26
    """native vector index 검색 (db.index.vector.queryNodes, dim 768 검증). $vec는 호출자 주입."""
    cypher = (
        "CALL db.index.vector.queryNodes($index, $k, $vec) YIELD node, score "
        "RETURN node.name AS name, score"
    )
    return cypher, {"index": index_name, "k": k}


class HybridRetrievalStage:
    # KG: eureka-canonical-2026-05-26
    """2-채널 검색: lexical(community summary) + native vector(node embedding).

    채널 granularity가 다르므로(community vs node) 강제 융합 않고 **둘 다 보고**(정직).
    vector 채널은 run_cypher + vector_index + context['query_embedding'] 모두 있을 때만 활성.
    context['query'] 없으면 lexical no-op. 둘 다 없으면 pass.
    """

    def __init__(
        self,
        run_cypher: CypherRunner | None = None,
        vector_index: str | None = None,
        k: int = 10,
    ):
        self.run_cypher = run_cypher
        self.vector_index = vector_index
        self.k = k
        self.name = "6-hybrid-retrieval"

    def _vector_channel(self, query_embedding: list[float]) -> list[tuple[str, float]]:
        if self.run_cypher is None or self.vector_index is None:
            return []  # vector channel inactive without runner + index
        cypher, params = vector_query_cypher(self.vector_index, self.k)
        params["vec"] = query_embedding
        try:
            rows = self.run_cypher(cypher, params)
        except Exception:  # noqa: BLE001 — vector index 부재/미populate → 빈 채널 degrade
            return []
        return [(r["name"], float(r["score"])) for r in rows if r.get("name") is not None]

    def run(self, context: dict[str, Any]) -> StageResult:
        query = context.get("query")
        summaries = context.get("summaries") or {}
        query_embedding = context.get("query_embedding")

        lexical = lexical_rrf(query, summaries) if query else []
        vector: list[tuple[str, float]] = []
        if self.run_cypher and self.vector_index and query_embedding:
            vector = self._vector_channel(query_embedding)

        if not query and not vector:
            return StageResult(
                self.name, True, payload={"lexical": [], "vector": [], "note": "no query"}
            )
        return StageResult(self.name, True, payload={"lexical": lexical, "vector": vector})


# ── Stage 7: drift loop (deterministic partition stability) ─────────────────


def _directional_stability(a_sets: list[set[str]], b_sets: list[set[str]]) -> float:
    """mean over a_sets of each cluster's best-match Jaccard against b_sets."""
    total = 0.0
    for a in a_sets:
        best = max(
            (len(a & b) / len(a | b) if (a | b) else 0.0 for b in b_sets),
            default=0.0,
        )
        total += best
    return total / len(a_sets)


def partition_stability(prev: Mapping[int, list[str]], curr: Mapping[int, list[str]]) -> float:
    # KG: eureka-canonical-2026-05-26
    """symmetric best-match Jaccard 평균 — 1.0=동일 partition, 낮을수록 drift. 빈 prev=1.0(baseline).

    SYMMETRIC (both directions): the prev→curr-only average was blind to a cluster present only
    in curr (a brand-new latent community) — every prev cluster still matched perfectly so it
    reported 1.0 for clearly non-identical partitions and DriftLoopStage never fired. Averaging
    dir(prev→curr) with dir(curr→prev) makes a new/merged/split community on either side drop it.
    """
    if not prev:
        return 1.0
    prev_sets = [set(v) for v in prev.values()]
    curr_sets = [set(v) for v in curr.values()]
    if not curr_sets:
        return 0.0
    return (
        _directional_stability(prev_sets, curr_sets) + _directional_stability(curr_sets, prev_sets)
    ) / 2


class DriftLoopStage:
    # KG: eureka-canonical-2026-05-26
    """partition 안정도. context['previous_communities'] 대비 Jaccard < τ면 re-induction 신호."""

    def __init__(self, tau: float = 0.75):
        self.tau = tau
        self.name = "7-drift-loop"

    def run(self, context: dict[str, Any]) -> StageResult:
        prev = context.get("previous_communities") or {}
        curr = context.get("communities") or {}
        stability = partition_stability(prev, curr)
        return StageResult(
            self.name,
            True,
            payload={"stability": stability, "drifted": stability < self.tau, "tau": self.tau},
        )


def wire_default_stages(
    run_cypher: CypherRunner, gamma: float = 1.0, vector_index: str | None = None
) -> dict[str, Any]:
    # KG: eureka-canonical-2026-05-26
    """4개 stage 구현체를 PipelineConfig 주입용 dict로. CLI/호출자가 config에 펼쳐 넣는다."""
    return {
        "stage_community": LeidenCommunityStage(run_cypher, gamma=gamma),
        "stage_summarize": SummarizeStage(),
        "stage_hybrid_retrieval": HybridRetrievalStage(
            run_cypher=run_cypher, vector_index=vector_index
        ),
        "stage_drift_loop": DriftLoopStage(),
    }


__all__ = [
    "DriftLoopStage",
    "HybridRetrievalStage",
    "LeidenCommunityStage",
    "SummarizeStage",
    "drop_cypher",
    "leiden_stream_cypher",
    "lexical_rrf",
    "parse_communities",
    "partition_stability",
    "project_cypher",
    "summarize_community",
    "vector_query_cypher",
    "wire_default_stages",
]
