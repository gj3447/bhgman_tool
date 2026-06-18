"""eureka 임베딩 backfill — KG 노드 텍스트 → embedding → SET (native vector index 채움).

stages.HybridRetrievalStage vector 채널의 **데이터 의존** 해소: vector index는 있으나
임베딩 미populate(Lesson 0/1120). 노드 텍스트를 임베딩해 SET하면 vector retrieval이 작동.

embed_fn 주입식 (테스트=fake, 실전=sentence-transformers 768d). idempotent:
embedding 있는 노드는 fetch에서 제외(WHERE embedding IS NULL) → 재실행 안전, 점진 진행.
dry_run 기본 (write 없이 후보 수만 보고).

# KG: eureka-canonical-2026-05-26, consensus-eureka-design-synthesis-2026-05-27
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

CypherRunner = Callable[[str, dict], "list[dict]"]
EmbedFn = Callable[[list[str]], "list[list[float]]"]  # batch texts → vectors

# 라벨별 embeddable 텍스트 필드. keys = 허용 라벨 allowlist (cypher 라벨 주입 차단).
TEXT_FIELDS: dict[str, list[str]] = {
    "Lesson": ["name", "description", "wrongAssumption", "truth", "problem", "solution"],
    "AptContract": ["name", "description"],
    "ResearchFinding": ["name", "description", "finding", "claim"],
}


def node_text(name: str, vals: list) -> str:
    # KG: eureka-canonical-2026-05-26
    """노드 name + 텍스트 필드 값들을 임베딩용 단일 텍스트로. 빈/None 필드 skip."""
    parts = [str(v) for v in vals if v]
    return " ".join(parts) if parts else str(name)


def fetch_unembedded_cypher(label: str) -> str:
    # KG: eureka-canonical-2026-05-26
    """embedding 없는 노드 + 텍스트 필드 조회. label allowlist 검증(주입 차단), 필드는 $fields 동적 접근."""
    if label not in TEXT_FIELDS:
        raise ValueError(f"label not in allowlist: {label} (allowed: {sorted(TEXT_FIELDS)})")
    return (
        f"MATCH (n:{label}) WHERE n.embedding IS NULL AND n.name IS NOT NULL "
        "RETURN n.name AS name, [f IN $fields | n[f]] AS vals LIMIT $limit"
    )


def set_embeddings_cypher(label: str) -> str:
    # KG: eureka-canonical-2026-05-26
    """배치 SET n.embedding. label allowlist 검증, name+emb는 $rows param."""
    if label not in TEXT_FIELDS:
        raise ValueError(f"label not in allowlist: {label}")
    return (
        "UNWIND $rows AS row "
        f"MATCH (n:{label} {{name: row.name}}) SET n.embedding = row.emb "
        "RETURN count(n) AS set_count"
    )


@dataclass(frozen=True)
class BackfillReport:
    # KG: eureka-canonical-2026-05-26
    label: str
    embedded: int = 0
    batches: int = 0
    dry_run: bool = True
    note: str = ""


def _fetch_batch(run_cypher: CypherRunner, label: str, fields: list[str], limit: int) -> list[dict]:
    return run_cypher(fetch_unembedded_cypher(label), {"fields": fields, "limit": limit})


def backfill(
    run_cypher: CypherRunner,
    write_cypher: CypherRunner | None,
    embed_fn: EmbedFn,
    label: str,
    batch_size: int = 64,
    max_nodes: int | None = None,
    dry_run: bool = True,
) -> BackfillReport:
    # KG: eureka-canonical-2026-05-26
    """label 노드의 빈 embedding을 채운다. dry_run=True면 첫 배치 후보 수만 보고(write 없음).

    apply 시 fetch(empty)→embed→SET 루프 (SET 후 더는 NULL 아니라 다음 배치 진행, 멱등).
    """
    fields = TEXT_FIELDS[label]  # raises KeyError if invalid → 명시 검증은 cypher 빌더가

    if dry_run or write_cypher is None:
        rows = _fetch_batch(run_cypher, label, fields, batch_size)
        return BackfillReport(
            label=label,
            embedded=0,
            batches=0,
            dry_run=True,
            note=f"dry-run: {len(rows)} node(s) in first batch lack embedding (no write)",
        )

    total = 0
    batches = 0
    while True:
        rows = _fetch_batch(run_cypher, label, fields, batch_size)
        if not rows:
            break
        texts = [node_text(r["name"], r.get("vals") or []) for r in rows]
        vectors = embed_fn(texts)
        payload = [{"name": r["name"], "emb": v} for r, v in zip(rows, vectors)]
        write_cypher(set_embeddings_cypher(label), {"rows": payload})
        total += len(payload)
        batches += 1
        if max_nodes is not None and total >= max_nodes:
            break
    return BackfillReport(
        label=label,
        embedded=total,
        batches=batches,
        dry_run=False,
        note=f"embedded {total} {label} node(s) over {batches} batch(es)",
    )


def _st_embed_fn(model_name: str) -> EmbedFn:
    """sentence-transformers 768d embedder. KG 한/영 혼합 → multilingual mpnet 기본."""
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415 (heavy optional dep)

    model = SentenceTransformer(model_name)

    def embed(texts: list[str]) -> list[list[float]]:
        return model.encode(texts, normalize_embeddings=True).tolist()

    return embed


def _neo4j_runners():
    """(run_cypher, write_cypher, close) from NEO4J_* env. 실 backfill용."""
    import os  # noqa: PLC0415
    from neo4j import GraphDatabase  # noqa: PLC0415

    drv = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )

    def run(cy: str, pa: dict) -> list[dict]:
        with drv.session() as s:
            return [dict(r) for r in s.run(cy, **pa)]

    return run, run, drv.close


def main() -> None:
    # KG: eureka-canonical-2026-05-26
    import argparse  # noqa: PLC0415

    ap = argparse.ArgumentParser(
        description="eureka 임베딩 backfill (768d native vector index 채움)"
    )
    ap.add_argument("--label", default="Lesson", choices=sorted(TEXT_FIELDS))
    ap.add_argument("--apply", action="store_true", help="실제 SET (생략=dry-run)")
    ap.add_argument("--limit", type=int, default=None, help="max nodes (생략=전체)")
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--model", default="paraphrase-multilingual-mpnet-base-v2")
    args = ap.parse_args()

    run_cypher, write_cypher, close = _neo4j_runners()
    embed_fn = _st_embed_fn(args.model) if args.apply else (lambda ts: [[0.0] for _ in ts])
    try:
        report = backfill(
            run_cypher,
            write_cypher if args.apply else None,
            embed_fn,
            args.label,
            batch_size=args.batch,
            max_nodes=args.limit,
            dry_run=not args.apply,
        )
    finally:
        close()
    print(f"[backfill] {report.label}: {report.note}")


if __name__ == "__main__":
    main()


__all__ = [
    "BackfillReport",
    "EmbedFn",
    "TEXT_FIELDS",
    "backfill",
    "fetch_unembedded_cypher",
    "node_text",
    "set_embeddings_cypher",
]
