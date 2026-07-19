"""occam 임베딩 backfill + 시맨틱 near-dup 러너 — PROM 6 P2 (rf-occam-adv-A1).

exact (sourcePath, sha256) 키가 놓치는 near-duplicate(명명규칙 다른 같은 파일, 이동+경편집
코드)를 임베딩 cosine 으로 surface. 이미 완성된 substrate(engine.embedding.neo4j_vector +
sentence-transformers embed_fn)를 SourceCodeNode 도메인에 배선한다.

**정밀도 주의 (proof 2026-07-19)**: text_prop='sourcePath' 는 약한 신호 — line-anchor 형제
(`x.py:27` vs `x.py:28`)와 exact-key 가 이미 처리하는 same-path 변종을 conflate 한다.
그래서 (a) 기본 threshold 를 높게(0.985) 두고, (b) line-anchor 만 다른 same-base-file 쌍을
제외한다. **진짜 코드-클론 값은 소스 *내용* 임베딩(GraphCodeBERT, repo_registry 로 디스크
접근)** — 이 러너의 다음 정밀화. archive-only 규약: near-dup 은 PROPOSE 일 뿐, 자동 archive
안 함(occam σ-gate + 나생문 verify 경유).

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A1-2026-07-19,
#     occam-kam-canonical-2026-05-26, reference_neo4j_gds_vector_available
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from engine.embedding.neo4j_vector import (
    VectorIndexSpec,
    backfill_embeddings,
    ensure_vector_index,
    knn_pairs,
)

CypherRunner = Callable[[str, "dict"], "list[dict]"]
EmbedFn = Callable[[list[str]], "list[list[float]]"]

_LINE_ANCHOR = re.compile(r":\d+$")


def sourcecode_spec(dimensions: int) -> VectorIndexSpec:
    """SourceCodeNode 벡터 인덱스 스펙 (text = sourcePath). dim 은 live embedder 에서."""
    return VectorIndexSpec(
        index_name="sourcecodenode_emb",
        label="SourceCodeNode",
        embedding_prop="embedding",
        text_prop="sourcePath",
        dimensions=dimensions,
    )


def _base(path: str | None) -> str:
    """line-anchor(`:NN`) 제거한 파일 경로 — 같은 파일의 다른 라인 판별용."""
    return _LINE_ANCHOR.sub("", path or "")


@dataclass(frozen=True)
class SemanticDedupProof:
    embedded: int
    probed: int
    pairs: list[tuple[str, str, float]]  # (a_name, b_name, cosine) — line-sibling 제외됨


def run_semantic_backfill(
    run_cypher: CypherRunner,
    embed_fn: EmbedFn,
    *,
    threshold: float = 0.985,
    k: int = 6,
    limit: int = 5000,
    apply_embeddings: bool = False,
) -> SemanticDedupProof:
    """SourceCodeNode 임베딩 채우고(옵션) 시맨틱 near-dup 쌍 반환.

    apply_embeddings=False(기본): 인덱스만 보장, 백필 write 없음(count 리포트).
    반환 pairs 는 line-anchor 만 다른 same-file 쌍을 제외한 진짜 cross-node 후보.
    """
    probe = embed_fn(["dimension probe"])
    spec = sourcecode_spec(len(probe[0]))
    ensure_vector_index(run_cypher, spec)
    rep = backfill_embeddings(
        run_cypher, spec, embed_fn, key_prop="name", limit=limit, apply=apply_embeddings
    )

    rows = run_cypher(
        "MATCH (n:SourceCodeNode) WHERE n.embedding IS NOT NULL AND n.name IS NOT NULL "
        "AND NOT n:ARCHIVED RETURN n.name AS id, n.sourcePath AS text, n.sourcePath AS path "
        "LIMIT $limit",
        {"limit": limit},
    )
    path_of = {r["id"]: r.get("path") for r in rows}
    items = [(r["id"], v) for r, v in zip(rows, embed_fn([r["text"] for r in rows]))] if rows else []
    raw = knn_pairs(run_cypher, spec, items, threshold=threshold, k=k, key_prop="name")
    # line-anchor 만 다른 same-base-file 쌍 제외 (같은 파일의 다른 참조 위치 ≠ 중복)
    pairs = [
        (a, b, sc)
        for a, b, sc in raw
        if not (_base(path_of.get(a)) == _base(path_of.get(b)) and path_of.get(a) != path_of.get(b))
    ]
    return SemanticDedupProof(embedded=rep.embedded, probed=len(rows), pairs=pairs)


__all__ = ["SemanticDedupProof", "run_semantic_backfill", "sourcecode_spec"]
