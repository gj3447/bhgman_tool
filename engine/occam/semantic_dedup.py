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
from collections.abc import Callable
from dataclasses import dataclass, field

EmbedFn = Callable[[list[str]], "list[list[float]]"]  # batch texts → vectors
CypherRunner = Callable[[str, dict], "list[dict]"]

# occam covenant — 파괴적 토큰 금지 (kg_adapter와 동일).
FORBIDDEN_TOKENS = ("DELETE", "DETACH", "REMOVE")

# 키 prop allowlist (cypher 주입 차단). 노드 identity 키.
_KEY_ALLOWLIST = frozenset({"name", "findingId", "id"})


def cosine(a: list[float], b: list[float]) -> float:
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


_SUPERSEDE_TMPL = (
    "MATCH (stale) WHERE stale.{key} = $stale_id "
    "MATCH (current) WHERE current.{key} = $current_id "
    "WHERE stale <> current "
    "SET stale.status = 'SUPERSEDED', stale.supersededBy = $current_id, "
    "stale.supersededReason = $reason, stale.supersededAt = datetime(), "
    "stale.occamPass = 'occam-semantic' "
    "MERGE (stale)-[:SUPERSEDED_BY]->(current) "
    "RETURN stale.{key} AS superseded, current.{key} AS current"
)


def plan_supersession(pair: NearDupPair, *, key: str = "name") -> tuple[str, dict]:
    """near-dup 쌍 → supersede write cypher + params. covenant: 파괴 토큰 부재 assert."""
    if key not in _KEY_ALLOWLIST:
        raise ValueError(f"key must be one of {sorted(_KEY_ALLOWLIST)}, got {key!r}")
    cypher = _SUPERSEDE_TMPL.format(key=key)
    violations = [tok for tok in FORBIDDEN_TOKENS if tok in cypher.upper()]
    if violations:
        raise AssertionError(f"occam covenant violation: {violations}")
    params = {
        "stale_id": pair.drop_id,
        "current_id": pair.keep_id,
        "reason": f"semantic near-duplicate (cosine={pair.similarity:.4f}) of {pair.keep_id}",
    }
    return cypher, params


@dataclass(frozen=True)
class SemanticDedupReport:
    pairs: tuple[NearDupPair, ...]
    scanned: int
    threshold: float
    dry_run: bool
    applied: int = 0
    planned_cyphers: tuple[str, ...] = field(default_factory=tuple)

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
    threshold: float = 0.95,
    key: str = "name",
    weight: dict[str, float] | None = None,
    write_cypher: CypherRunner | None = None,
    apply: bool = False,
) -> SemanticDedupReport:
    """(id, text) 목록 → embed → near-dup → PROPOSE/apply. dry-run 기본 (archive-only)."""
    ids = [i for i, _ in items]
    texts = [t for _, t in items]
    vectors = embed_fn(texts) if texts else []
    pairs = find_near_duplicates(list(zip(ids, vectors)), threshold=threshold, weight=weight)

    planned: list[str] = []
    applied = 0
    do_write = apply and write_cypher is not None
    for pair in pairs:
        cypher, params = plan_supersession(pair, key=key)
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
    )


__all__ = [
    "EmbedFn",
    "NearDupPair",
    "SemanticDedupReport",
    "cosine",
    "find_near_duplicates",
    "plan_supersession",
    "run_semantic_dedup",
]
