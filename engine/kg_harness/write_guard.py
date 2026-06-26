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


# ── 정규식 (lint) ────────────────────────────────────────────────────────────
# 라벨 붙은 노드를 CREATE — MERGE(stable-id) 였어야 함. CONSTRAINT/INDEX·관계전용
# CREATE((a)-[:R]->(b), 라벨 없음)는 매치 안 됨(콜론 요구).
_NAKED_CREATE = re.compile(r"\bCREATE\s*\(\s*\w*\s*:\s*\w+", re.IGNORECASE)
# 라벨만으로 MERGE (식별 키 맵 없음) → 라벨당 1노드로 합쳐지는 함정. WARN.
_MERGE_NO_KEY = re.compile(r"\bMERGE\s*\(\s*\w*\s*:\s*\w+\s*\)")
# 버전드 필드 누적: 속성 키가 `_v<숫자>`. dot-access 또는 map-key 문맥만(문자열 리터럴 FP 회피).
_VERSIONED_DOT = re.compile(r"\.([A-Za-z_]\w*_v\d+)\b")
_VERSIONED_MAP = re.compile(r"[\{,]\s*([A-Za-z_]\w*_v\d+)\s*:")
# stale 접미사(_old/_stale) — 보통 누적 신호. WARN.
_STALE_DOT = re.compile(r"\.([A-Za-z_]\w*(?:_old|_stale))\b")
_STALE_MAP = re.compile(r"[\{,]\s*([A-Za-z_]\w*(?:_old|_stale))\s*:")
# supersede 의도 탐지(라벨/상태/속성). SUPERSEDED_BY(엣지)와는 구별됨.
_SUPERSEDE_LABEL = re.compile(r":Superseded\b")
_SUPERSEDE_STATUS = re.compile(r"""status\s*[:=]\s*['"]SUPERSEDED['"]""", re.IGNORECASE)
_SUPERSEDE_PROP = re.compile(r"\bsuperseded(?:By|At|Reason)\b", re.IGNORECASE)

_IDENT = re.compile(r"^[A-Za-z_]\w*$")
# 빌더가 거부할 오염 속성 키(누적/묘비 흔적). INV2/INV3을 props 단계에서 차단.
_DIRTY_KEY = re.compile(r"(_v\d+$|_old$|_stale$|^superseded)", re.IGNORECASE)


def validate_write(cypher: str) -> GuardReport:
    """write cypher를 3대 불변식으로 정적 검증. ERROR/WARN 목록을 GuardReport로."""
    v: list[Violation] = []
    has_create_optout = ALLOW_CREATE_MARKER in cypher

    # INV1 — naked CREATE of labeled node
    if not has_create_optout:
        m = _NAKED_CREATE.search(cypher)
        if m:
            v.append(
                Violation(
                    "NAKED_CREATE",
                    Severity.ERROR,
                    "라벨 노드를 CREATE — stable-id MERGE 사용(중복 ingest 방지). "
                    f"정당하면 '{ALLOW_CREATE_MARKER}' 주석으로 opt-out.",
                    m.group(0),
                )
            )
    mk = _MERGE_NO_KEY.search(cypher)
    if mk:
        v.append(
            Violation(
                "MERGE_WITHOUT_KEY",
                Severity.WARN,
                "MERGE에 식별 키 맵이 없음 — 라벨당 1노드로 잘못 합쳐질 수 있음.",
                mk.group(0),
            )
        )

    # INV2 — versioned/stale field accretion
    versioned = {m.group(1) for m in _VERSIONED_DOT.finditer(cypher)}
    versioned |= {m.group(1) for m in _VERSIONED_MAP.finditer(cypher)}
    for key in sorted(versioned):
        v.append(
            Violation(
                "VERSIONED_FIELD",
                Severity.ERROR,
                f"버전드 필드 '{key}' — update-in-place 하라(god-object 유발). "
                "이력이 필요하면 별도 :History 노드/엣지로.",
                key,
            )
        )
    stale = {m.group(1) for m in _STALE_DOT.finditer(cypher)}
    stale |= {m.group(1) for m in _STALE_MAP.finditer(cypher)}
    for key in sorted(stale):
        v.append(
            Violation("STALE_FIELD", Severity.WARN, f"stale 접미사 필드 '{key}' — 누적 신호.", key)
        )

    # INV3 — supersede tombstone must carry SUPERSEDED_BY edge
    has_intent = bool(
        _SUPERSEDE_LABEL.search(cypher)
        or _SUPERSEDE_STATUS.search(cypher)
        or _SUPERSEDE_PROP.search(cypher)
    )
    has_edge = "SUPERSEDED_BY" in cypher.upper()
    if has_intent and not has_edge:
        v.append(
            Violation(
                "ORPHAN_TOMBSTONE",
                Severity.ERROR,
                "노드를 supersede/tombstone 하면서 SUPERSEDED_BY 엣지가 없음 — "
                "교체본 추적 불가(나중에 자동청소 불가능). 대체 노드로 엣지를 걸어라.",
            )
        )

    return GuardReport(cypher=cypher, violations=tuple(v))


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
