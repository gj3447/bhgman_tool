"""하데스 end-to-end runner — fetch ACCEPTED 추상 → realize_kg_abstraction. dry-run 기본.

orchestration만. 실현 로직 = hades.py(realize_kg_abstraction). 여기는 KG fetch + 순회.
occam_runner와 대칭(fetch → core → apply). materialize는 c6 "가장 위험"이라 dry-run 기본 +
apply_cypher 없으면 절대 write 안 함 (실현 불가 시 PLANNED 유지).

# KG: hades-canonical-2026-05-27, eureka-canonical-2026-05-26 (dual),
#     consensus-eureka-engine-impl-2026-05-26 (c6 materialize danger)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from engine.hades.hades import realize_kg_abstraction
from engine.hades.hades_models import RealizeStatus, RealizeVerdict

CypherRunner = Callable[[str, dict], "list[dict]"]

# verdictStatus='ACCEPTED'(유레카 PROPOSE→fidelity/judgment 통과)만 실현 대상.
# 이미 CANONICAL(실현됨)은 제외 — 재실현 방지. members = a.extent 프로퍼티(없으면 []).
_FETCH_ALL = (
    "MATCH (a:AbstractClass) "
    "WHERE a.verdictStatus = 'ACCEPTED' AND (a.status IS NULL OR a.status <> 'CANONICAL') "
    "RETURN a.name AS concept, a.verdictStatus AS verdict, coalesce(a.extent, []) AS members"
)
_FETCH_ONE = (
    "MATCH (a:AbstractClass {name: $concept}) "
    "WHERE a.verdictStatus = 'ACCEPTED' AND (a.status IS NULL OR a.status <> 'CANONICAL') "
    "RETURN a.name AS concept, a.verdictStatus AS verdict, coalesce(a.extent, []) AS members"
)


def fetch_accepted_cypher(concept: str | None) -> tuple[str, dict]:
    """실현 대상(ACCEPTED, 미실현) 추상 조회 cypher. concept 주면 한 개만."""
    if concept:
        return _FETCH_ONE, {"concept": concept}
    return _FETCH_ALL, {}


@dataclass(frozen=True)
class HadesRunResult:
    verdicts: tuple[RealizeVerdict, ...] = ()
    dry_run: bool = True
    applied_count: int = 0

    @property
    def summary(self) -> str:
        planned = sum(1 for v in self.verdicts if v.status is RealizeStatus.PLANNED)
        refused = sum(1 for v in self.verdicts if v.status is RealizeStatus.REFUSED)
        mode = "DRY-RUN" if self.dry_run else f"APPLIED {self.applied_count}"
        return (
            f"hades: candidates={len(self.verdicts)} planned={planned} refused={refused} → {mode}"
        )


def run_hades(
    run_cypher: CypherRunner,
    apply_cypher: CypherRunner | None = None,
    concept: str | None = None,
    apply: bool = False,
) -> HadesRunResult:
    """ACCEPTED 추상을 KG에 실현. apply=False(기본) → PLANNED만, write 없음.

    apply=True여도 apply_cypher 없으면 write 불가 → PLANNED 유지 (c6 위험 차단).
    """
    cypher, params = fetch_accepted_cypher(concept)
    rows = run_cypher(cypher, params)

    do_write = apply and apply_cypher is not None
    verdicts: list[RealizeVerdict] = []
    for row in rows:
        v = realize_kg_abstraction(
            row["concept"],
            row.get("verdict", ""),
            list(row.get("members") or []),
            dry_run=not do_write,
            apply_cypher=apply_cypher,
        )
        verdicts.append(v)

    applied_count = sum(1 for v in verdicts if v.status is RealizeStatus.APPLIED)
    return HadesRunResult(
        verdicts=tuple(verdicts),
        dry_run=not do_write,
        applied_count=applied_count,
    )


__all__ = ["CypherRunner", "HadesRunResult", "fetch_accepted_cypher", "run_hades"]
