"""오캄 의미론 near-duplicate 탐지 — sha256-blind 자리를 임베딩 cosine으로 메움.

기존 occam(occam.py)은 sha256/exact-path로 *byte-동일* 중복만 본다. 패러프레이즈된
Lesson·다시 쓴 Finding 같은 *의미상* 중복은 못 잡는다. 이 모듈은 노드 텍스트를 임베딩해
cosine ≥ θ 쌍을 near-duplicate 후보로 surface한다.

규율 (기존 occam과 동일 covenant):
  • dry-run/PROPOSE 기본 — write_cypher + apply 시에만 supersede write.
  • archive-only — status 플래그 + SUPERSEDED_BY 엣지, 원본 보존 (DELETE/DETACH/REMOVE 금지, assert).
  • 결정론 — embed_fn 주입식(테스트=fake, 실전=sentence-transformers 768d). keep/drop 결정론 tiebreak.
  • PROPOSE만 — 클러스터 transitive 자동해소 안 함, 쌍만 surface (human/verdict gate).

스케일: 현재 O(N²) pairwise (수백 노드 OK). 대규모는 KG native vector index(kNN)로 후속.

# KG: rf-semdist-occam-2026-06-01 (이 finding이 이 엔진을 낳음),
#     occam-kam-canonical-2026-05-26, lesson-occam-must-query-kg-node-dedup-not-just-filesystem-2026-05-27
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field

EmbedFn = Callable[[list[str]], "list[list[float]]"]  # batch texts → vectors
CypherRunner = Callable[[str, dict], "list[dict]"]

# occam covenant — 파괴적 토큰 금지 (kg_adapter와 동일).
FORBIDDEN_TOKENS = ("DELETE", "DETACH", "REMOVE")
# archive-only 우회 차단(Tier-4): 토큰 없이 노드를 파괴하는 프로시저 (kg_adapter와 동일).
_DESTRUCTIVE_PROCEDURES = ("MERGENODES", "APOC.REFACTOR", "APOC.NODES.DELETE")


def _assert_archive_only(cypher: str) -> None:
    """covenant: 파괴 토큰(DELETE/DETACH/REMOVE) + 노드-파괴 프로시저(apoc.refactor.mergeNodes
    등)를 차단. archive-only supersede 만 통과."""
    up = cypher.upper()
    violations = [t for t in (*FORBIDDEN_TOKENS, *_DESTRUCTIVE_PROCEDURES) if t in up]
    if violations:
        raise AssertionError(f"occam covenant violation: {violations}")


# 키 prop allowlist (cypher 주입 차단). 노드 identity 키.
_KEY_ALLOWLIST = frozenset({"name", "findingId", "id"})

# 라벨은 cypher에 직접 보간되므로(파라미터화 불가) 엄격 검증 — 유효 Neo4j 라벨만 (주입 차단).
_LABEL_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


def _validate_label(label: str) -> None:
    """H5 covenant: supersede MATCH 를 노드 라벨로 스코핑한다. 라벨 없는 bare `name` MATCH 는
    전 KG 동명 노드를 SET 하므로 금지. 라벨은 파라미터화 불가 → allowlist-정규식으로 주입 차단."""
    if not isinstance(label, str) or not _LABEL_RE.fullmatch(label):
        raise ValueError(
            f"label must be a valid Neo4j label [A-Za-z][A-Za-z0-9_]*, got {label!r} "
            "(covenant: unlabeled bare-name MATCH would SET status on every same-named node)"
        )


def cosine(a: list[float], b: list[float]) -> float:
    # KG: occam-kam-canonical-2026-05-26
    """코사인 유사도. 영벡터/길이불일치는 0.0 (안전)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


@dataclass(frozen=True)
class NearDupPair:
    # KG: occam-kam-canonical-2026-05-26
    """의미론 near-dup 1쌍. keep=정전 유지, drop=supersede 후보 (PROPOSE)."""

    keep_id: str
    drop_id: str
    similarity: float


def _pick_keep_drop(a_id: str, b_id: str, weight: dict[str, float]) -> tuple[str, str]:
    """결정론 keep/drop: weight 큰 쪽 유지(=내용 많음/최신), 동률이면 id 작은 쪽 유지."""
    wa, wb = weight.get(a_id, 0.0), weight.get(b_id, 0.0)
    if wa != wb:
        return (a_id, b_id) if wa > wb else (b_id, a_id)
    return (a_id, b_id) if a_id <= b_id else (b_id, a_id)


def find_near_duplicates(
    items: list[tuple[str, list[float]]],
    *,
    threshold: float = 0.95,
    weight: dict[str, float] | None = None,
) -> list[NearDupPair]:
    # KG: occam-kam-canonical-2026-05-26
    """(id, vector) 목록 → cosine ≥ threshold 쌍. i<j pairwise, 결정론 정렬."""
    w = weight or {}
    pairs: list[NearDupPair] = []
    n = len(items)
    for i in range(n):
        ai, av = items[i]
        for j in range(i + 1, n):
            bj, bv = items[j]
            sim = cosine(av, bv)
            if sim >= threshold:
                keep, drop = _pick_keep_drop(ai, bj, w)
                pairs.append(NearDupPair(keep_id=keep, drop_id=drop, similarity=sim))
    pairs.sort(key=lambda p: (-p.similarity, p.drop_id))
    return pairs


# H5 (Tier-1): stale/current MATCH 를 {label} 로 스코핑 + 상태가드(H3). 예전 템플릿은 라벨 없는
# bare `(stale)` 였고 `WHERE ... WHERE ...` 연속이라 실 Neo4j 문법오류(로컬 러너가 가려 미검출).
# 유일성 가드 (seam-integrity 2026-07-10): {key} 는 비유일(동명 이노드 실재) — 옛 템플릿은
# 다중매치 전부 SET + 동명 쌍이면 stale/current 가 대칭 매치돼 양쪽 SUPERSEDED(생존자 0).
# collect/size=1 로 양측 정확히 1개일 때만 write, 다중매치 = 0-row fail-closed.
_SUPERSEDE_TMPL = (
    "MATCH (s:{label}) WHERE s.{key} = $stale_id "
    "AND (s.status IS NULL OR s.status <> 'SUPERSEDED') "
    "WITH collect(s) AS ss "
    "MATCH (c:{label}) WHERE c.{key} = $current_id "
    "AND (c.status IS NULL OR c.status <> 'SUPERSEDED') "
    "WITH ss, collect(c) AS cs "
    "WHERE size(ss) = 1 AND size(cs) = 1 "
    "WITH ss[0] AS stale, cs[0] AS current "
    "WHERE stale <> current "
    "SET stale.status = 'SUPERSEDED', stale.supersededBy = $current_id, "
    "stale.supersededReason = $reason, stale.supersededAt = datetime(), "
    "stale.occamPass = 'occam-semantic' "
    "MERGE (stale)-[:SUPERSEDED_BY]->(current) "
    "RETURN stale.{key} AS superseded, current.{key} AS current"
)


def plan_supersession(pair: NearDupPair, *, key: str = "name", label: str) -> tuple[str, dict]:
    # KG: occam-kam-canonical-2026-05-26
    """near-dup 쌍 → supersede write cypher + params. covenant: 파괴 토큰 부재 assert +
    라벨 스코핑(bare-name over-supersede 차단, H5) + keep==drop fail-closed."""
    if pair.keep_id == pair.drop_id:
        # seam-integrity 2026-07-10: 동명 동률 쌍의 tiebreak 가 keep==drop 을 만들 수 있고,
        # 그 write 는 실서버 의미론에서 자기-supersede 대칭 매치 = 양쪽 SUPERSEDED(생존자 0).
        # plan 단계에서 거부 — indistinguishable 쌍은 escalation(나생문)의 몫이다.
        raise ValueError(
            f"keep==drop ({pair.keep_id!r}) — 무생존 supersede 금지; "
            "indistinguishable near-dup 쌍은 escalation 으로 라우팅하라"
        )
    if key not in _KEY_ALLOWLIST:
        raise ValueError(f"key must be one of {sorted(_KEY_ALLOWLIST)}, got {key!r}")
    _validate_label(label)
    cypher = _SUPERSEDE_TMPL.format(key=key, label=label)
    _assert_archive_only(cypher)  # 파괴 토큰 + apoc 파괴 프로시저 부재 강제 (archive-only)
    params = {
        "stale_id": pair.drop_id,
        "current_id": pair.keep_id,
        "reason": f"semantic near-duplicate (cosine={pair.similarity:.4f}) of {pair.keep_id}",
    }
    return cypher, params


@dataclass(frozen=True)
class SemanticDedupReport:
    # KG: occam-kam-canonical-2026-05-26
    pairs: tuple[NearDupPair, ...]
    scanned: int
    threshold: float
    dry_run: bool
    applied: int = 0
    planned_cyphers: tuple[str, ...] = field(default_factory=tuple)
    # keep==drop(무생존 위험) 쌍 — plan 에서 제외되고 escalation(나생문) 몫으로 표면화.
    indistinguishable: tuple[str, ...] = field(default_factory=tuple)

    @property
    def summary(self) -> str:
        mode = "DRY-RUN (PROPOSE)" if self.dry_run else f"APPLIED {self.applied}"
        return (
            f"occam[semantic]: scanned={self.scanned} near_dup_pairs={len(self.pairs)} "
            f"θ={self.threshold} → {mode}"
        )


def run_semantic_dedup(
    items: list[tuple[str, str]],
    *,
    embed_fn: EmbedFn,
    label: str,
    threshold: float = 0.95,
    key: str = "name",
    weight: dict[str, float] | None = None,
    write_cypher: CypherRunner | None = None,
    apply: bool = False,
) -> SemanticDedupReport:
    # KG: occam-kam-canonical-2026-05-26
    """(id, text) 목록 → embed → near-dup → PROPOSE/apply. dry-run 기본 (archive-only).

    label = supersede MATCH 스코프(H5 covenant: 라벨 없는 bare-name MATCH 금지). 호출자는
    스캔한 노드 타입 라벨(예: 'ResearchFinding'/'Lesson')을 넘긴다."""
    _validate_label(label)  # dry-run 이어도 조기 검증 — planned cypher 도 스코프됨
    ids = [i for i, _ in items]
    texts = [t for _, t in items]
    vectors = embed_fn(texts) if texts else []
    pairs = find_near_duplicates(list(zip(ids, vectors)), threshold=threshold, weight=weight)

    planned: list[str] = []
    applied = 0
    indistinguishable: list[str] = []
    do_write = apply and write_cypher is not None
    for pair in pairs:
        if pair.keep_id == pair.drop_id:
            # seam-integrity 2026-07-10: 무생존 supersede 위험 — plan 제외, escalation 몫.
            indistinguishable.append(pair.keep_id)
            continue
        cypher, params = plan_supersession(pair, key=key, label=label)
        planned.append(cypher)
        if do_write:
            try:
                rows = write_cypher(cypher, params)  # type: ignore[misc]
                # count only writes that matched a node (the cypher RETURNs the superseded
                # row). A nullable/non-unique key → 0 rows → not counted (W3-C: was always
                # incremented, masking silent no-op writes — same lie W1-G fixed in kg_adapter).
                if rows:
                    applied += 1
            except Exception:  # noqa: BLE001 — 백엔드 미지원 시 PROPOSE로 degrade
                pass
    return SemanticDedupReport(
        pairs=tuple(pairs),
        scanned=len(items),
        threshold=threshold,
        dry_run=not do_write,
        applied=applied,
        planned_cyphers=tuple(planned),
        indistinguishable=tuple(indistinguishable),
    )


def near_duplicates_via_index(
    items: list[tuple[str, str]],
    *,
    embed_fn: EmbedFn,
    run_cypher: CypherRunner,
    spec,
    threshold: float = 0.95,
    k: int = 10,
    weight: dict[str, float] | None = None,
) -> list[NearDupPair]:
    # KG: occam-kam-canonical-2026-05-26
    """Near-dup pairs via the Neo4j native vector index (approx kNN) instead of the
    O(N²) in-memory pairwise scan — the documented follow-up this engine flagged.

    Each item probes the index for its k neighbours (O(N·k·log N)), so this scales to
    the full KG where ``find_near_duplicates`` does not. The keep/drop tiebreak and
    supersession covenant are unchanged — only candidate discovery is swapped.

    ``spec`` is an ``engine.embedding.VectorIndexSpec``; the index must already hold
    embeddings (run the substrate backfill first). Injected ``run_cypher`` keeps this
    backend-agnostic and unit-testable with a fake runner.
    """
    from engine.embedding.neo4j_vector import knn_pairs  # noqa: PLC0415 — substrate layer

    w = weight or {}
    ids = [i for i, _ in items]
    texts = [t for _, t in items]
    vectors = embed_fn(texts) if texts else []
    raw = knn_pairs(run_cypher, spec, list(zip(ids, vectors)), threshold=threshold, k=k)
    pairs: list[NearDupPair] = []
    for a_id, b_id, sim in raw:
        keep, drop = _pick_keep_drop(a_id, b_id, w)
        pairs.append(NearDupPair(keep_id=keep, drop_id=drop, similarity=sim))
    pairs.sort(key=lambda p: (-p.similarity, p.drop_id))
    return pairs


__all__ = [
    "EmbedFn",
    "NearDupPair",
    "SemanticDedupReport",
    "cosine",
    "find_near_duplicates",
    "near_duplicates_via_index",
    "plan_supersession",
    "run_semantic_dedup",
]
