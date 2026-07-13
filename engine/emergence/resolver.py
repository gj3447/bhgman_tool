"""RESOLVE 단계 — traffic 이벤트를 기존 element 에 착지시키거나 신규 창발.

τ_sim 이상 근접한 기존 element 있으면 그 key 반환(dedup), 없으면 입력 key 반환
(= 유레카 CREATE 신호). namespace 별로 격리 → ③ Visibility 불변식 물리 구현
(shared 버킷과 tenant 버킷 분리 → 공유 query 가 private 에 절대 착지 못 함).

- IdentityResolver     : phase1 기본. exact-key.
- InMemoryVectorResolver: 코사인 nearest (embed in event). 테스트/실험용.
- Neo4jVectorResolver  : production. embedding.knn (native HNSW) 위임.
"""
# KG: engineboy-emergence-engine-fsm-design-2026-07-13, rf-engineboy-caching-C2-2026-07-13

from __future__ import annotations

import math
from typing import Optional, Protocol, Sequence, runtime_checkable

Vector = Sequence[float]


@runtime_checkable
class VectorResolver(Protocol):
    def resolve(self, key: str, embed: Optional[Vector], namespace: str) -> str: ...
    def add(self, key: str, embed: Optional[Vector], namespace: str) -> None: ...


class IdentityResolver:
    """exact-key. embed 무시. (phase1 기본)"""

    def resolve(self, key: str, embed: Optional[Vector], namespace: str) -> str:
        return key

    def add(self, key: str, embed: Optional[Vector], namespace: str) -> None:
        return None


def _cosine(a: Vector, b: Vector) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class InMemoryVectorResolver:
    """namespace 별 코사인 nearest. brute-force (테스트/실험 규모).

    tau_sim 이상이면 기존 key 재사용, 아니면 신규(입력 key). namespace 격리로
    shared query 는 shared 버킷만 검색 → private 착지 불가 (③ 불변식).
    """

    def __init__(self, tau_sim: float = 0.86) -> None:
        self.tau_sim = tau_sim
        self._buckets: dict[str, list[tuple[str, tuple[float, ...]]]] = {}

    def resolve(self, key: str, embed: Optional[Vector], namespace: str) -> str:
        if embed is None:
            return key
        best_key, best_score = key, -1.0
        for k, v in self._buckets.get(namespace, ()):  # noqa: B007
            s = _cosine(embed, v)
            if s > best_score:
                best_key, best_score = k, s
        return best_key if best_score >= self.tau_sim else key

    def add(self, key: str, embed: Optional[Vector], namespace: str) -> None:
        if embed is None:
            return
        bucket = self._buckets.setdefault(namespace, [])
        if any(k == key for k, _ in bucket):
            return
        bucket.append((key, tuple(float(x) for x in embed)))

    def bucket_keys(self, namespace: str) -> list[str]:
        return [k for k, _ in self._buckets.get(namespace, ())]


class Neo4jVectorResolver:
    """production RESOLVE — native HNSW (embedding.knn) 위임.

    namespace 는 별도 label/prop 로 파티션 (private tenant 는 shared index 밖).
    embedding populate 가 선행조건 (OD-5). 미populate 시 knn 은 빈 결과 → 항상 신규.
    """

    def __init__(self, run_cypher, spec, tau_sim: float = 0.86, k: int = 5) -> None:
        self._run = run_cypher
        self._spec = spec
        self.tau_sim = tau_sim
        self.k = k

    def resolve(self, key: str, embed: Optional[Vector], namespace: str) -> str:
        if embed is None or namespace != "shared":
            # 공유 index 만 조회 → private(tenant) 는 착지 대상서 제외 (③ 불변식)
            return key
        from engine.embedding.neo4j_vector import knn

        hits = knn(
            self._run, self._spec, list(embed),
            k=self.k, key_prop="name", min_score=self.tau_sim,
        )
        return hits[0].node_id if hits else key

    def add(self, key: str, embed: Optional[Vector], namespace: str) -> None:
        # production 에선 node MERGE + embedding SET 이 별도 populate 경로(하데스).
        return None
