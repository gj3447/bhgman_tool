"""오캄 KG 어댑터 — read(SourceCodeNode→NodeRecord) + write(supersede, covenant).

순수 cypher 빌더 + 주입식 CypherRunner. occam.py(순수 분류)와 분리: 여기는 IO 경계.
sibling 일관: eureka/hades와 동일한 `CypherRunner = Callable[[str,dict], list[dict]]`.

**covenant (코드로 강제)**:
  - write cypher에 DELETE/DETACH/REMOVE 토큰 부재 → build_supersede가 assert로 차단.
  - supersede = status flag + SUPERSEDED_BY 엣지. 원본 노드 보존 = reversible (archive-only).
  - dry_run 기본: write_cypher 있어도 dry_run=True면 실행 안 함.

# KG: occam-kam-canonical-2026-05-26, lesson-occam-must-query-kg-node-dedup-not-just-filesystem-2026-05-27,
#     occam-pass-kg-wide-2026-05-27
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from engine.occam.occam_models import NodeRecord, OccamReport, SupersessionCandidate

# 실전=Neo4j read/write, 테스트=fake rows. (eureka/hades와 동일 시그니처)
CypherRunner = Callable[[str, dict], "list[dict]"]

# covenant: 오캄은 archive만 — 이 토큰들이 write cypher에 있으면 위반.
FORBIDDEN_TOKENS = ("DELETE", "DETACH", "REMOVE")

# ── READ ────────────────────────────────────────────────────────────────────

# 이미 SUPERSEDED된 노드는 제외 — 아카이브된 과거를 재-아카이브하지 않는다 (dogfood 교훈 2026-05-27).
_NOT_ALREADY_ARCHIVED = "(s.status IS NULL OR s.status <> 'SUPERSEDED')"
_REQUIRED = "s.sha256 IS NOT NULL AND s.lineCount IS NOT NULL AND s.sourcePath IS NOT NULL"
_RETURN = (
    "RETURN s.name AS name, s.sourcePath AS source_path, "
    "s.sha256 AS sha256, s.lineCount AS line_count"
)

_FETCH_ALL = f"MATCH (s:SourceCodeNode) WHERE {_REQUIRED} AND {_NOT_ALREADY_ARCHIVED} {_RETURN}"
_FETCH_SCOPED = (
    f"MATCH (s:SourceCodeNode) WHERE s.sourcePath CONTAINS $scope "
    f"AND {_REQUIRED} AND {_NOT_ALREADY_ARCHIVED} {_RETURN}"
)


def fetch_cypher(scope: str | None) -> tuple[str, dict]:
    """scope(label/path 부분문자열)로 SourceCodeNode 조회 cypher. None=전체."""
    if scope:
        return _FETCH_SCOPED, {"scope": scope}
    return _FETCH_ALL, {}


def parse_node_records(rows: list[dict]) -> list[NodeRecord]:
    """KG row → NodeRecord. 필수 필드(sourcePath/sha256/lineCount) 결손 row는 방어적 skip."""
    out: list[NodeRecord] = []
    for r in rows:
        if r.get("source_path") is None or r.get("sha256") is None or r.get("line_count") is None:
            continue
        out.append(
            NodeRecord(
                name=r["name"],
                source_path=r["source_path"],
                sha256=r["sha256"],
                line_count=int(r["line_count"]),
            )
        )
    return out


def fetch_source_nodes(run_cypher: CypherRunner, scope: str | None = None) -> list[NodeRecord]:
    """KG에서 SourceCodeNode를 NodeRecord로 가져온다 (PRIMARY = cypher)."""
    cypher, params = fetch_cypher(scope)
    return parse_node_records(run_cypher(cypher, params))


# ── WRITE (covenant: archive-only) ──────────────────────────────────────────

# 식별 키 = (sourcePath, sha256) 복합키. name 단독 불가: (1) schema상 name은 required 아님
# → null이면 MATCH 실패 + 다운스트림 None crash; (2) name 단독은 unique 아님. 복합키는 두
# required 필드(sourcePath/sha256)로 모든 occam dup 모드를 disambiguate — same-path dup은
# sha256가, abs/rel·sha-이동 dup은 sourcePath가 가른다.
# # KG: challenge-occam-supersede-name-key-not-required-nullable-2026-06-02
_SUPERSEDE_CYPHER = (
    "MATCH (stale:SourceCodeNode {sourcePath: $stale_path, sha256: $stale_sha}) "
    "MATCH (current:SourceCodeNode {sourcePath: $current_path, sha256: $current_sha}) "
    "WHERE stale <> current "  # self-supersession 차단 (exact-dup 동일키 no-op)
    "SET stale.status = 'SUPERSEDED', "
    "stale.supersededBy = $current_path, "
    "stale.supersededReason = $reason, "
    "stale.supersededAt = datetime(), "
    "stale.occamPass = 'occam' "
    "MERGE (stale)-[:SUPERSEDED_BY]->(current) "  # reversible: 원본 보존 + 엣지
    "RETURN stale.sourcePath AS superseded, current.sourcePath AS current"
)


def _ident(node: NodeRecord) -> str:
    """표시용 식별자 (never None). name이 있으면 name, 없으면 sourcePath로 폴백."""
    return node.name or node.source_path


def build_supersede(candidate: SupersessionCandidate) -> tuple[str, dict]:
    """supersede write cypher + params. covenant: 파괴적 토큰 부재를 assert로 강제."""
    cypher = _SUPERSEDE_CYPHER
    up = cypher.upper()
    violations = [tok for tok in FORBIDDEN_TOKENS if tok in up]
    if violations:  # 방어 — 향후 cypher 편집 시 covenant 회귀 차단
        raise AssertionError(f"occam covenant violation: {violations} in supersede cypher")
    params = {
        "stale_path": candidate.stale.source_path,
        "stale_sha": candidate.stale.sha256,
        "current_path": candidate.current.source_path,
        "current_sha": candidate.current.sha256,
        "reason": candidate.reason,
        # 표시 전용 (CLI dry-run plan / superseded 라벨) — never None
        "stale_name": _ident(candidate.stale),
        "current_name": _ident(candidate.current),
    }
    return cypher, params


@dataclass(frozen=True)
class ApplyResult:
    """supersede 적용 결과. dry_run=True면 planned만, write 없음 (covenant)."""

    superseded: tuple[str, ...] = ()
    planned_cyphers: tuple[tuple[str, dict], ...] = ()
    dry_run: bool = True
    applied_count: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)


def apply_supersessions(
    report: OccamReport,
    write_cypher: CypherRunner | None = None,
    dry_run: bool = True,
) -> ApplyResult:
    """후보를 supersede 적용. dry_run 기본 — write_cypher 있어도 실행 안 함.

    write_cypher=None이거나 dry_run=True → planned cypher만 반환 (archive-only 안전).
    """
    plans = [build_supersede(c) for c in report.candidates]
    stale_names = tuple(_ident(c.stale) for c in report.candidates)

    if dry_run or write_cypher is None:
        note = "dry-run: planned only, no write (covenant archive-only)"
        return ApplyResult(
            superseded=stale_names,
            planned_cyphers=tuple(plans),
            dry_run=True,
            applied_count=0,
            notes=(note,),
        )

    applied: list[str] = []
    for (cypher, params), cand in zip(plans, report.candidates):
        write_cypher(cypher, params)
        applied.append(_ident(cand.stale))
    return ApplyResult(
        superseded=tuple(applied),
        planned_cyphers=tuple(plans),
        dry_run=False,
        applied_count=len(applied),
        notes=(f"applied {len(applied)} supersession(s) — reversible via status+edge",),
    )


__all__ = [
    "ApplyResult",
    "CypherRunner",
    "FORBIDDEN_TOKENS",
    "apply_supersessions",
    "build_supersede",
    "fetch_cypher",
    "fetch_source_nodes",
    "parse_node_records",
]
