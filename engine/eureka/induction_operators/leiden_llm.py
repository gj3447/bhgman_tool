"""Leiden-family community induction operator (offline default).

Edge et al. 2024 GraphRAG (arXiv 2404.16130): hierarchical Leiden (Traag-Waltman-vanEck
2019) → per-community LLM summary → :AbstractClass.

**실구현 (2026-05-27, NotImplementedError 제거)** — 3-way bake-off candidate를 실제 동작하게:
  - 입력: FCA/AMIE3와 동일한 formal context `{object → attribute set}` (bake-off 동일 입력 보장).
  - 그래프: object = node, edge weight = |shared attributes| (속성-유사도 그래프).
  - 커뮤니티: **resolution(γ)-parameterized greedy modularity** (Newman 2004 / Clauset-Newman-Moore
    agglomerative). Leiden과 같은 modularity-maximization family의 *오프라인·결정론* 구현 —
    외부 gds 의존 없이 테스트 가능. 대규모(>max_nodes)는 gds.leiden로 위임 권장(아래 seam).
  - 출력: community → FormalConcept(extent=멤버, intent=공유속성, stability=내부응집도) =
    FcaResult. → `_concepts_to_acs`로 AbstractClass 직결 (FCA/AMIE3 어댑터와 동일 shape).

**정직 공시 (over-claim 차단)**:
  - 이 오프라인 기본은 *Leiden 알고리즘 그 자체가 아니라* 동일 family(modularity max)의 결정론
    그리디 구현. production 규모(수천 노드↑)는 gds.leiden(γ-sweep)을 `community_fn` 주입으로 교체.
  - "LLM per-community summary"(Edge 2024)는 pipeline **stage_3 (resolve_stage_summarize)** 의
    주입 seam — 이 operator는 community 구조까지 산출, 요약은 별도 stage. PROPOSE까지만(eureka covenant).

# KG: eureka-canonical-2026-05-26, consensus-eureka-engine-impl-2026-05-26,
#     consensus-eureka-academic-grounding-2026-05-26 (Leiden-LLM C-line),
#     challenge-occam-pass-bhgman_tool-bakeoff-not-completed-2026-05-27 (이 구현이 3-way bake-off unblock)
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from engine.eureka.induction_operators.fca import FcaResult, FormalConcept

# 오프라인 그리디는 pure-python — 큰 그래프는 gds.leiden로. 정직한 상한.
MAX_NODES = 2000


def _build_similarity_graph(
    context: Mapping[str, frozenset[str]],
) -> tuple[list[str], dict[str, dict[str, int]]]:
    """object → 속성-유사도 그래프. edge weight = |공유 속성|. 결정론(sorted)."""
    objs = sorted(context)
    adj: dict[str, dict[str, int]] = {o: {} for o in objs}
    for i, oi in enumerate(objs):
        ai = context[oi]
        if not ai:
            continue
        for oj in objs[i + 1 :]:
            shared = len(ai & context[oj])
            if shared > 0:
                adj[oi][oj] = shared
                adj[oj][oi] = shared
    return objs, adj


def _initial_inter(
    objs: list[str], adj: dict[str, dict[str, int]], comm: dict[str, int]
) -> dict[tuple[int, int], float]:
    """초기 community 간 edge weight (각 undirected edge 1회). 처음엔 1 node=1 community."""
    inter: dict[tuple[int, int], float] = defaultdict(float)
    for o in objs:
        for p, w in adj[o].items():
            if o < p:
                a, b = comm[o], comm[p]
                if a != b:
                    inter[(min(a, b), max(a, b))] += w
    return inter


def _best_merge_pair(
    inter: dict[tuple[int, int], float],
    comm_deg: dict[int, float],
    resolution: float,
    two_w: float,
) -> tuple[int, int] | None:
    """ΔQ(a,b)=2(e_ab/2W − γ·a_a·a_b/(2W)²) 최대 양의 쌍. sorted 순회로 결정론 tie-break."""
    best_pair: tuple[int, int] | None = None
    best_dq = 1e-12  # 양의 gain만
    for (a, b), eab in sorted(inter.items()):
        dq = 2.0 * (eab / two_w - resolution * (comm_deg[a] * comm_deg[b]) / (two_w * two_w))
        if dq > best_dq:
            best_dq = dq
            best_pair = (a, b)
    return best_pair


def _rebuild_inter_after_merge(
    inter: dict[tuple[int, int], float],
    adj: dict[str, dict[str, int]],
    comm: dict[str, int],
    members_a: set[str],
    a: int,
    b: int,
) -> dict[tuple[int, int], float]:
    """b를 a로 병합한 뒤 inter 재계산: a/b 무관 edge 보존 + 병합 community a의 edge 재집계."""
    new_inter: dict[tuple[int, int], float] = defaultdict(float)
    for (x, y), w in inter.items():
        if x not in (a, b) and y not in (a, b):
            new_inter[(x, y)] += w
    adj_comm: dict[int, float] = defaultdict(float)
    for o in members_a:
        for p, w in adj[o].items():
            c = comm[p]
            if c != a:
                adj_comm[c] += w
    for c, w in adj_comm.items():
        new_inter[(min(a, c), max(a, c))] += w
    return new_inter


def _greedy_modularity(
    objs: list[str],
    adj: dict[str, dict[str, int]],
    resolution: float,
) -> list[frozenset[str]]:
    """Resolution-parameterized greedy modularity (Newman-CNM agglomerative). 결정론."""
    total_w = sum(w for o in objs for w in adj[o].values()) / 2.0
    if total_w == 0:  # edge 없음 → 전부 싱글톤
        return [frozenset({o}) for o in objs]

    comm: dict[str, int] = {o: i for i, o in enumerate(objs)}
    members: dict[int, set[str]] = {i: {o} for i, o in enumerate(objs)}
    comm_deg: dict[int, float] = {i: float(sum(adj[o].values())) for i, o in enumerate(objs)}
    inter = _initial_inter(objs, adj, comm)
    two_w = 2.0 * total_w

    while inter:
        pair = _best_merge_pair(inter, comm_deg, resolution, two_w)
        if pair is None:
            break
        a, b = pair  # b를 a로 병합
        members[a] |= members[b]
        comm_deg[a] += comm_deg[b]
        for o in members[b]:
            comm[o] = a
        del members[b], comm_deg[b]
        inter = _rebuild_inter_after_merge(inter, adj, comm, members[a], a, b)

    return [frozenset(s) for s in members.values()]


def _community_to_concept(
    community: frozenset[str],
    context: Mapping[str, frozenset[str]],
    adj: dict[str, dict[str, int]],
) -> FormalConcept:
    """community → FormalConcept. intent=공유속성 교집합, stability=내부 edge 응집도∈[0,1]."""
    if len(community) == 1:
        only = next(iter(community))
        return FormalConcept(extent=community, intent=context[only], stability=0.0)

    intent = frozenset.intersection(*(context[o] for o in community))
    internal = 0.0
    boundary = 0.0
    for o in community:
        for p, w in adj[o].items():
            if p in community:
                internal += w  # 양방향 카운트 → 아래서 /2
            else:
                boundary += w
    internal /= 2.0
    denom = internal + boundary
    stability = internal / denom if denom > 0 else 0.0
    return FormalConcept(extent=community, intent=intent, stability=stability)


def induce_leiden_llm(
    context: Mapping[str, frozenset[str]],
    *,
    resolution: float = 1.0,
    min_extent: int = 2,
    min_stability: float = 0.0,
    max_nodes: int = MAX_NODES,
) -> FcaResult:
    """formal context → resolution-parameterized community induction → FcaResult(FormalConcept).

    FCA/AMIE3와 동일 출력 shape → pipeline `_concepts_to_acs`로 AbstractClass 직결.
    extent < min_extent OR stability < min_stability 는 pruned. >max_nodes는 gds.leiden 위임 fallback.
    """
    if len(context) > max_nodes:
        return FcaResult(
            concepts=(),
            pruned=0,
            fallback_reason=(
                f"context size {len(context)} > max_nodes {max_nodes}; "
                "offline greedy-modularity not for this scale — inject gds.leiden (γ-sweep) community_fn"
            ),
        )

    objs, adj = _build_similarity_graph(context)
    communities = _greedy_modularity(objs, adj, resolution)
    return assemble_fca(
        communities, context, adj, min_extent=min_extent, min_stability=min_stability
    )


def assemble_fca(
    communities: list[frozenset[str]],
    context: Mapping[str, frozenset[str]],
    adj: dict[str, dict[str, int]],
    *,
    min_extent: int,
    min_stability: float,
) -> FcaResult:
    """communities → FcaResult(FormalConcept), pruning + deterministic sort.

    Shared by the CNM (induce_leiden_llm) and true-Leiden (induce_leiden_true)
    operators so both produce byte-identical output shape from the same clusters.
    """
    survivors: list[FormalConcept] = []
    pruned = 0
    for community in communities:
        concept = _community_to_concept(community, context, adj)
        if len(concept.extent) < min_extent or concept.stability < min_stability:
            pruned += 1
            continue
        survivors.append(concept)
    survivors.sort(key=lambda c: (-c.stability, -len(c.extent), tuple(sorted(c.extent))))
    return FcaResult(concepts=tuple(survivors), pruned=pruned, fallback_reason=None)


__all__ = ["MAX_NODES", "assemble_fca", "induce_leiden_llm"]
