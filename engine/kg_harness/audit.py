"""audit — 3대 불변식 위반을 *사후* 탐지 (read-only).

write_guard는 ingest-time 예방이지만 벌크 import(Aura sync / Home-KG dump / LOAD CSV)는
Python chokepoint를 안 지난다. 이 모듈은 live KG를 직접 훑어 우회된 위반을 잡는 그물:

  DUP_ID          : 레지스트리 (label,id_key)에 같은 id 중복 → ingest dedup 실패.
  ORPHAN_TOMBSTONE: Superseded인데 SUPERSEDED_BY 출엣지 없음 → 교체본 추적 불가(0.4% 문제).
  VERSIONED_FIELD : 노드에 `_v<숫자>` 속성 키 잔존 → god-object 누적.

순수 cypher 빌더 + 주입식 run_cypher(occam sibling). cron/CI에서 주기 실행 → 재오염 조기경보.

# KG: occam-pass-metahumotonic-20260626
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from engine.kg_harness.registry import STABLE_IDS

CypherRunner = Callable[[str, "dict"], "list[dict]"]


@dataclass(frozen=True)
class AuditFinding:
    code: str  # DUP_ID | ORPHAN_TOMBSTONE | VERSIONED_FIELD | LINT:<rule>
    label: str  # 대상 라벨 / 문장 출처 ('*' = 무관)
    count: int  # 위반 노드/그룹 수
    detail: str = ""


# ── 순수 cypher 빌더 ──────────────────────────────────────────────────────────


def dup_id_cypher(label: str, id_key: str) -> tuple[str, dict]:
    """(label,id_key) 중복 id 그룹/노드 수."""
    cy = (
        f"MATCH (n:`{label}`) WHERE n.`{id_key}` IS NOT NULL "
        f"WITH n.`{id_key}` AS k, count(*) AS c WHERE c > 1 "
        f"RETURN count(*) AS dup_groups, coalesce(sum(c),0) AS dup_nodes"
    )
    return cy, {}


def orphan_tombstone_cypher() -> tuple[str, dict]:
    """Superseded인데 SUPERSEDED_BY 출엣지 없는 노드 수."""
    cy = (
        "MATCH (n:Superseded) WHERE NOT (n)-[:SUPERSEDED_BY]->() "
        "RETURN count(n) AS orphan_tombstones"
    )
    return cy, {}


def versioned_field_cypher(label: str) -> tuple[str, dict]:
    """라벨 내 `_v<숫자>` 속성 키를 가진 노드 수 (god-object 잔존)."""
    cy = (
        f"MATCH (n:`{label}`) WHERE any(k IN keys(n) WHERE k =~ '.*_v\\\\d+$') "
        f"RETURN count(n) AS versioned_nodes"
    )
    return cy, {}


# ── 실행 (주입식 runner) ──────────────────────────────────────────────────────


def audit_all(
    run_cypher: CypherRunner,
    registry: dict[str, str] | None = None,
    *,
    check_versioned: bool = True,
) -> list[AuditFinding]:
    """레지스트리 전 라벨 + 전역 orphan-tombstone 감사. 위반(count>0)만 반환."""
    reg = STABLE_IDS if registry is None else registry
    findings: list[AuditFinding] = []

    for label, id_key in sorted(reg.items()):
        cy, params = dup_id_cypher(label, id_key)
        rows = run_cypher(cy, params) or [{}]
        groups = int(rows[0].get("dup_groups", 0) or 0)
        nodes = int(rows[0].get("dup_nodes", 0) or 0)
        if groups > 0:
            findings.append(
                AuditFinding(
                    "DUP_ID", label, groups, f"{nodes} nodes in {groups} groups ({id_key})"
                )
            )
        if check_versioned:
            cy, params = versioned_field_cypher(label)
            rows = run_cypher(cy, params) or [{}]
            vnodes = int(rows[0].get("versioned_nodes", 0) or 0)
            if vnodes > 0:
                findings.append(AuditFinding("VERSIONED_FIELD", label, vnodes, "_vN keys present"))

    cy, params = orphan_tombstone_cypher()
    rows = run_cypher(cy, params) or [{}]
    orphans = int(rows[0].get("orphan_tombstones", 0) or 0)
    if orphans > 0:
        findings.append(
            AuditFinding("ORPHAN_TOMBSTONE", "*", orphans, "Superseded without SUPERSEDED_BY edge")
        )
    return findings


# ── cypher 코퍼스 lint (write-guard 룰 공유) ──────────────────────────────────


def lint_statements(
    statements: Iterable[str], *, warnings: bool = True
) -> list[AuditFinding]:
    """cypher 문장들을 write-guard 룰(동일 RULES)로 사후 lint.

    그래프-상태 audit는 '어떤 cypher가 썼는지' 못 본다 — apoc.create/LOAD CSV는 write-time
    텍스트 패턴이라 결과 상태만으론 안 잡힌다. 이 함수가 그 구멍을 메운다: chokepoint를
    우회하는 *텍스트 corpus*(벌크 import 스크립트 / .cypher 아티팩트 / 저장된 SavedQuery)를
    ingest-guard와 **동일 불변식**으로 검사. label = 'stmt[i]'.

    warnings=False면 ERROR만 보고.
    """
    from engine.kg_harness.write_guard import Severity, validate_write  # noqa: PLC0415

    findings: list[AuditFinding] = []
    for i, stmt in enumerate(statements):
        for v in validate_write(stmt).violations:
            if not warnings and v.severity is not Severity.ERROR:
                continue
            findings.append(
                AuditFinding(
                    code=f"LINT:{v.code}",
                    label=f"stmt[{i}]",
                    count=1,
                    detail=f"{v.severity.value} {v.evidence or v.message[:60]}",
                )
            )
    return findings


__all__ = [
    "AuditFinding",
    "CypherRunner",
    "audit_all",
    "dup_id_cypher",
    "lint_statements",
    "orphan_tombstone_cypher",
    "versioned_field_cypher",
]
