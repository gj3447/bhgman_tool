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
from pathlib import Path

from engine.embedding.neo4j_vector import (
    VectorIndexSpec,
    backfill_embeddings,
    ensure_vector_index,
    knn_pairs,
)
from engine.longinus_drift_audit.repo_registry import RepoRegistry, default_registry

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


def content_spec(dimensions: int) -> VectorIndexSpec:
    """소스 *내용* 임베딩 인덱스 (prop=codeEmb, path 아님). A1 정밀화."""
    return VectorIndexSpec(
        index_name="sourcecodenode_content_emb",
        label="SourceCodeNode",
        embedding_prop="codeEmb",
        text_prop="repo_relpath",
        dimensions=dimensions,
    )


@dataclass(frozen=True)
class ContentBackfillReport:
    resolved: int
    written: int
    unresolved: int

    @property
    def summary(self) -> str:
        mode = f"WROTE {self.written}" if self.written else "PROPOSE"
        return (
            f"occam[content-emb]: resolved={self.resolved} unresolved={self.unresolved} → {mode}"
        )


def content_backfill(
    run_cypher: CypherRunner,
    embed_fn: EmbedFn,
    *,
    registry: RepoRegistry | None = None,
    limit: int = 2000,
    max_chars: int = 8000,
    apply: bool = False,
) -> ContentBackfillReport:
    """repo_id+repo_relpath 로 디스크 소스 *내용* 을 읽어 codeEmb 로 임베딩.

    A1 정밀화: sourcePath 문자열보다 강한 코드-클론 신호(이동+경편집 코드도 잡음). 디스크
    해석 불가 노드는 skip(유령 임베딩 날조 금지). content 는 max_chars 로 bound(임베딩 비용).
    apply=False(기본): resolve 만, write 없음. `db.create.setNodeVectorProperty` 로 additive write.
    """
    reg = registry or default_registry()
    spec = content_spec(len(embed_fn(["probe"])[0]))
    ensure_vector_index(run_cypher, spec)
    rows = run_cypher(
        "MATCH (n:SourceCodeNode) WHERE n.repo_id IS NOT NULL AND n.repo_relpath IS NOT NULL "
        "AND n.codeEmb IS NULL AND NOT n:ARCHIVED "
        "RETURN n.name AS id, n.repo_id AS repo_id, n.repo_relpath AS relpath LIMIT $limit",
        {"limit": limit},
    )
    ids: list[str] = []
    texts: list[str] = []
    unresolved = 0
    for r in rows:
        try:
            p = reg.locate(r["repo_id"], r["relpath"])
            content = Path(p).read_text(errors="ignore")[:max_chars]
        except Exception:
            unresolved += 1
            continue
        if not content.strip():
            unresolved += 1
            continue
        ids.append(r["id"])
        texts.append(content)
    written = 0
    if ids and apply:
        vectors = embed_fn(texts)
        for node_id, vec in zip(ids, vectors):
            run_cypher(
                "MATCH (n:SourceCodeNode {name:$id}) "
                "CALL db.create.setNodeVectorProperty(n, 'codeEmb', $vec) RETURN 1",
                {"id": node_id, "vec": vec},
            )
            written += 1
    return ContentBackfillReport(resolved=len(ids), written=written, unresolved=unresolved)


__all__ = [
    "ContentBackfillReport",
    "SemanticDedupProof",
    "content_backfill",
    "content_spec",
    "run_semantic_backfill",
    "sourcecode_spec",
]
