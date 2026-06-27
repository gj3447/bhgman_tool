"""write_guard — KG write cypher 정적 검증 + 안전 빌더 + 강제 runner.

세 층:
  1. validate_write(cypher) -> GuardReport : 임의 write cypher를 3대 불변식으로 lint.
  2. upsert_node / supersede_node          : 불변식을 *by construction* 만족하는 빌더.
  3. guarded_run(run, cypher, params)       : ERROR면 실행 거부(WriteGuardError) — chokepoint.

정직: validate_write는 정규식 lint이라 완벽한 파서가 아니다(거짓음성 가능). 그래서
빌더(by-construction)가 1차 방어, lint는 raw-cypher 회귀 차단용 2차 그물. DB-level
constraint(constraint_cypher)는 어떤 writer도 우회 못 하는 3차 백스톱.

# KG: occam-pass-metahumotonic-20260626 (왜 필요한지: Superseded 10%·동명 18%·god-object)
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

CypherRunner = Callable[[str, dict], "list[dict]"]

# raw CREATE가 정당한 드문 경우(스키마 부트스트랩 등) 명시적 opt-out 주석.
ALLOW_CREATE_MARKER = "// kgh:allow-create"


class Severity(str, Enum):
    ERROR = "ERROR"  # 실행 거부
    WARN = "WARN"  # 통과하되 경고(추후 ERROR 승격 후보)


@dataclass(frozen=True)
class Violation:
    code: str
    severity: Severity
    message: str
    evidence: str = ""


@dataclass(frozen=True)
class GuardReport:
    cypher: str
    violations: tuple[Violation, ...] = ()

    @property
    def errors(self) -> tuple[Violation, ...]:
        return tuple(v for v in self.violations if v.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[Violation, ...]:
        return tuple(v for v in self.violations if v.severity is Severity.WARN)

    @property
    def ok(self) -> bool:
        """ERROR가 하나도 없으면 실행 가능(WARN은 통과)."""
        return not self.errors


class WriteGuardError(RuntimeError):
    """하네스 ERROR 위반 — write 실행 거부."""

    def __init__(self, report: GuardReport) -> None:
        self.report = report
        codes = ", ".join(f"{v.code}: {v.message}" for v in report.errors)
        super().__init__(f"KG write guard refused {len(report.errors)} violation(s): {codes}")


_IDENT = re.compile(r"^[A-Za-z_]\w*$")
# 빌더가 거부할 오염 속성 키(누적/묘비 흔적). INV2/INV3을 props 단계에서 차단.
_DIRTY_KEY = re.compile(r"(_v\d+$|_old$|_stale$|^superseded)", re.IGNORECASE)


def validate_write(cypher: str, rules: "list | None" = None) -> GuardReport:
    """write cypher를 룰 레지스트리로 정적 검증. ERROR/WARN을 GuardReport로.

    rules=None이면 engine.kg_harness.rules.RULES(정전) 사용. 호출자가 직접 룰 리스트를
    주입하면 그것만 적용(테스트/특수 게이트). 새 불변식 = RULES에 Rule 추가(OCP).
    """
    from engine.kg_harness.rules import RULES  # noqa: PLC0415 — lazy(순환 회피)

    active = RULES if rules is None else rules
    violations: list[Violation] = []
    for rule in active:
        violations.extend(rule.check(cypher))
    return GuardReport(cypher=cypher, violations=tuple(violations))


# ── 안전 빌더 (by construction) ──────────────────────────────────────────────


def _require_ident(name: str, what: str) -> None:
    if not _IDENT.match(name):
        raise ValueError(f"unsafe {what} (cypher 주입 위험): {name!r}")


def _reject_dirty_props(props: dict) -> None:
    dirty = sorted(k for k in props if _DIRTY_KEY.search(k))
    if dirty:
        raise WriteGuardError(
            GuardReport(
                cypher="<upsert props>",
                violations=tuple(
                    Violation(
                        "VERSIONED_FIELD" if re.search(r"_v\d+$", k) else "STALE_FIELD",
                        Severity.ERROR,
                        f"오염 속성 키 '{k}' — update-in-place 위반.",
                        k,
                    )
                    for k in dirty
                ),
            )
        )


def upsert_node(
    label: str,
    id_key: str,
    id_val,
    props: dict | None = None,
    *,
    run: CypherRunner | None = None,
) -> tuple[str, dict]:
    """stable-id MERGE upsert (update-in-place). 오염 키는 빌드 단계에서 거부.

    `_kgh_updated_at`을 자동 stamp. run 주면 guarded_run으로 실행.
    """
    _require_ident(label, "label")
    _require_ident(id_key, "id_key")
    props = dict(props or {})
    _reject_dirty_props(props)
    cypher = (
        f"MERGE (n:{label} {{{id_key}: $id}}) "
        f"SET n += $props "
        f"SET n._kgh_updated_at = datetime() "
        f"RETURN n.{id_key} AS id"
    )
    params = {"id": id_val, "props": props}
    if run is not None:
        guarded_run(run, cypher, params)
    return cypher, params


def supersede_node(
    label: str,
    id_key: str,
    stale_id,
    current_id,
    reason: str,
    *,
    run: CypherRunner | None = None,
) -> tuple[str, dict]:
    """stale 노드를 archive — SUPERSEDED_BY 엣지 필수(by construction). delete 아님.

    occam covenant와 동형: 상태 flag + 엣지 = reversible. self-supersede 차단.
    """
    _require_ident(label, "label")
    _require_ident(id_key, "id_key")
    cypher = (
        f"MATCH (stale:{label} {{{id_key}: $stale}}) "
        f"MATCH (current:{label} {{{id_key}: $current}}) "
        f"WHERE stale <> current "
        f"SET stale:Superseded, stale.status = 'SUPERSEDED', "
        f"stale.supersededBy = $current, stale.supersededReason = $reason, "
        f"stale.supersededAt = datetime() "
        f"MERGE (stale)-[:SUPERSEDED_BY]->(current) "
        f"RETURN stale.{id_key} AS superseded"
    )
    params = {"stale": stale_id, "current": current_id, "reason": reason}
    # 자가검증: 빌더 출력이 스스로 불변식을 통과해야 한다(회귀 방지).
    report = validate_write(cypher)
    if not report.ok:  # pragma: no cover — 빌더 버그 방어
        raise WriteGuardError(report)
    if run is not None:
        guarded_run(run, cypher, params)
    return cypher, params


def constraint_cypher(label: str, id_key: str | tuple[str, ...]) -> str:
    """stable-id 제약 — DB-level 백스톱(어떤 writer도 우회 불가). MCP/bolt로 1회 설치.

    str이면 단일키, tuple이면 복합키. 둘 다 IS UNIQUE — 복합 UNIQUE는 키 일부가 null인
    노드를 면제하고 *완전한* 노드만 유일성 강제(NODE KEY와 달리 non-null 요구 안 함).
    (예: ReferenceSite는 (sourceId,name) 복합 — sourceId 단독은 컬렉션 grouping이라 유니크
    아니고, null 키 노드 800+개 존재 → NODE KEY 불가, 복합 UNIQUE가 정답.)
    """
    _require_ident(label, "label")
    keys = (id_key,) if isinstance(id_key, str) else tuple(id_key)
    for k in keys:
        _require_ident(k, "id_key")
    name = f"kgh_{label}_{'_'.join(keys)}_unique"
    props = ", ".join(f"n.{k}" for k in keys)
    target = props if len(keys) == 1 else f"({props})"
    return f"CREATE CONSTRAINT {name} IF NOT EXISTS FOR (n:{label}) REQUIRE {target} IS UNIQUE"


def guarded_run(run_cypher: CypherRunner, cypher: str, params: dict | None = None) -> "list[dict]":
    """chokepoint: 검증 통과 시에만 실행. ERROR면 WriteGuardError(실행 0)."""
    report = validate_write(cypher)
    if not report.ok:
        raise WriteGuardError(report)
    return run_cypher(cypher, params or {})


__all__ = [
    "ALLOW_CREATE_MARKER",
    "CypherRunner",
    "GuardReport",
    "Severity",
    "Violation",
    "WriteGuardError",
    "constraint_cypher",
    "guarded_run",
    "supersede_node",
    "upsert_node",
    "validate_write",
]
