"""eureka pipeline stage 2/3/6/7 구현체 — pipeline의 NotImplementedStage 주입점을 채운다.

GraphRAG 체인(Edge 2024): community → summarize → (induce) → retrieval / drift.
pipeline이 성공 stage의 dict payload를 context에 merge하므로 stage들이 순차로 산출을 잇는다.

**정직한 의존 분리** (feedback_empirical_falsifier_before_grand_frame):
  - Stage 2 (Leiden): gds.leiden은 dgx Neo4j 인프라 의존 → cypher 빌더/파싱/degrade는 테스트,
    실 gds 실행은 inject한 run_cypher 책임(부재 시 ok=False degrade, 비치명적).
  - Stage 3 (Summarize): 결정론 digest(LLM 불필요) — 완전 테스트.
  - Stage 6 (HybridRetrieval): **lexical** RRF(토큰 overlap) — 결정론. vector index는 미포함(별도 인프라).
  - Stage 7 (DriftLoop): 결정론 partition 안정도(best-match Jaccard) vs τ — 완전 테스트.

# KG: eureka-canonical-2026-05-26, consensus-eureka-design-synthesis-2026-05-27,
#     consensus-eureka-engine-impl-2026-05-26
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from protocols import StageResult

CypherRunner = Callable[[str, dict], "list[dict]"]


# ── Stage 2: Leiden community detection (gds, dgx-infra-gated) ──────────────


def leiden_stream_cypher(graph_name: str, gamma: float) -> tuple[str, dict]:
    """gds.leiden.stream cypher (pure). 그래프 projection은 호출자/인프라 precondition."""
    cypher = (
        "CALL gds.leiden.stream($graph, {gamma: $gamma, randomSeed: 42}) "
        "YIELD nodeId, communityId "
        "RETURN gds.util.asNode(nodeId).name AS name, communityId AS community"
    )
    return cypher, {"graph": graph_name, "gamma": gamma}


def parse_communities(rows: list[dict]) -> dict[int, list[str]]:
    """[{name, community}] → {community_id: [names]}. None/결손 row skip."""
    out: dict[int, list[str]] = {}
    for r in rows:
        name, cid = r.get("name"), r.get("community")
        if name is None or cid is None:
            continue
        out.setdefault(int(cid), []).append(str(name))
    return out


class LeidenCommunityStage:
    """gds.leiden 군집화. gds 미가용(인프라 부재) 시 ok=False degrade (비치명적)."""

    def __init__(
        self, run_cypher: CypherRunner, graph_name: str = "eureka-proj", gamma: float = 1.0
    ):
        self.run_cypher = run_cypher
        self.graph_name = graph_name
        self.gamma = gamma
        self.name = "2-community"

    def run(self, context: dict[str, Any]) -> StageResult:
        cypher, params = leiden_stream_cypher(self.graph_name, self.gamma)
        try:
            rows = self.run_cypher(cypher, params)
        except Exception as e:  # noqa: BLE001 — gds 부재/projection 미존재 → degrade
            return StageResult(self.name, False, error=f"gds.leiden unavailable: {e}")
        communities = parse_communities(rows)
        return StageResult(self.name, True, payload={"communities": communities})


# ── Stage 3: per-community summarize (deterministic, LLM-free) ──────────────


def summarize_community(cid: int, members: list[str], top: int = 5) -> str:
    """결정론 digest — LLM 없이 멤버 수 + 대표 멤버. 재현 가능(정렬 고정)."""
    ms = sorted(members)
    head = ", ".join(ms[:top])
    more = f" (+{len(ms) - top} more)" if len(ms) > top else ""
    return f"community {cid}: {len(ms)} members — {head}{more}"


class SummarizeStage:
    """community→요약. context['communities'](Stage 2 산출) 소비. 결정론, 인프라 불필요."""

    name = "3-summarize"

    def run(self, context: dict[str, Any]) -> StageResult:
        communities: Mapping[int, list[str]] = context.get("communities") or {}
        summaries = {cid: summarize_community(cid, members) for cid, members in communities.items()}
        return StageResult(self.name, True, payload={"summaries": summaries})


# ── Stage 6: hybrid retrieval (lexical RRF — deterministic) ─────────────────


def _tokens(text: str) -> set[str]:
    return {t for t in text.lower().replace(",", " ").split() if len(t) > 2}


def lexical_rrf(query: str, summaries: Mapping[int, str], k: int = 60) -> list[tuple[int, float]]:
    """토큰 overlap RRF 랭킹 (결정론). vector index 미포함 — 별도 인프라 필요."""
    q = _tokens(query)
    scored = [(cid, len(q & _tokens(s))) for cid, s in summaries.items()]
    scored = [(cid, n) for cid, n in scored if n > 0]
    scored.sort(key=lambda x: (-x[1], x[0]))
    return [(cid, 1.0 / (k + rank)) for rank, (cid, _n) in enumerate(scored, start=1)]


class HybridRetrievalStage:
    """community-summary lexical retrieval. context['query'] 없으면 no-op pass."""

    name = "6-hybrid-retrieval"

    def run(self, context: dict[str, Any]) -> StageResult:
        query = context.get("query")
        summaries = context.get("summaries") or {}
        if not query:
            return StageResult(self.name, True, payload={"ranked": [], "note": "no query — pass"})
        ranked = lexical_rrf(query, summaries)
        return StageResult(self.name, True, payload={"ranked": ranked})


# ── Stage 7: drift loop (deterministic partition stability) ─────────────────


def partition_stability(prev: Mapping[int, list[str]], curr: Mapping[int, list[str]]) -> float:
    """best-match Jaccard 평균 — 1.0=동일 partition, 낮을수록 drift. 빈 prev=1.0(baseline)."""
    if not prev:
        return 1.0
    prev_sets = [set(v) for v in prev.values()]
    curr_sets = [set(v) for v in curr.values()]
    if not curr_sets:
        return 0.0
    total = 0.0
    for ps in prev_sets:
        best = max(
            (len(ps & cs) / len(ps | cs) if (ps | cs) else 0.0 for cs in curr_sets),
            default=0.0,
        )
        total += best
    return total / len(prev_sets)


class DriftLoopStage:
    """partition 안정도 측정. context['previous_communities'] 대비 Jaccard < τ면 re-induction 신호."""

    def __init__(self, tau: float = 0.75):
        self.tau = tau
        self.name = "7-drift-loop"

    def run(self, context: dict[str, Any]) -> StageResult:
        prev = context.get("previous_communities") or {}
        curr = context.get("communities") or {}
        stability = partition_stability(prev, curr)
        drifted = stability < self.tau
        return StageResult(
            self.name,
            True,
            payload={"stability": stability, "drifted": drifted, "tau": self.tau},
        )


def wire_default_stages(run_cypher: CypherRunner, gamma: float = 1.0) -> dict[str, Any]:
    """4개 stage 구현체를 PipelineConfig 주입용 dict로. CLI/호출자가 config에 펼쳐 넣는다."""
    return {
        "stage_community": LeidenCommunityStage(run_cypher, gamma=gamma),
        "stage_summarize": SummarizeStage(),
        "stage_hybrid_retrieval": HybridRetrievalStage(),
        "stage_drift_loop": DriftLoopStage(),
    }


__all__ = [
    "DriftLoopStage",
    "HybridRetrievalStage",
    "LeidenCommunityStage",
    "SummarizeStage",
    "leiden_stream_cypher",
    "lexical_rrf",
    "parse_communities",
    "partition_stability",
    "summarize_community",
    "wire_default_stages",
]
