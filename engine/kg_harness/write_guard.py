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

# 파괴 연산이 정당한 극히 드문 경우(로컬 KG 테스트 픽스처 청소 등) 명시적 opt-out 주석.
# 공유 KG covenant 는 archive-only — supersede_node 가 정답이고 이 마커는 감사 가능한 예외다.
ALLOW_DESTRUCTIVE_MARKER = "// kgh:allow-destructive"


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


# `// kgh:` 가드 지시 주석(ALLOW_* 마커)은 프로토콜의 일부 — 스트립에서 보존.
_KGH_DIRECTIVE = re.compile(r"^//\s*kgh:")


def strip_cypher_comments(cypher: str) -> str:
    """cypher 주석 제거(문자열 리터럴 인지) — lint 전처리.

    정규식 룰의 두 결함을 동시에 없앤다 (2026-07-08 감사):
      우회: `CREATE /* x */ (n:Foo)` 가 `CREATE\\s*\\(` 매치를 피함 → 스트립 후 매치.
      오탐: 주석 *텍스트* 속 단어(DELETE 등)가 룰에 걸림 → 스트립 후 소멸.
    따옴표(' " `) 안의 // 와 /* 는 주석이 아니다('http://...') — 문자열을 자르면
    그 *뒤*의 실제 위반을 놓친다. `// kgh:` 가드 지시 주석만 보존.
    """
    out: list[str] = []
    i, n = 0, len(cypher)
    quote: str | None = None
    while i < n:
        c = cypher[i]
        if quote is not None:
            out.append(c)
            if c == "\\" and quote != "`" and i + 1 < n:
                out.append(cypher[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
        elif c in "'\"`":
            quote = c
            out.append(c)
            i += 1
        elif c == "/" and cypher.startswith("//", i):
            j = cypher.find("\n", i)
            j = n if j == -1 else j
            comment = cypher[i:j]
            out.append(comment if _KGH_DIRECTIVE.match(comment) else " ")
            i = j
        elif c == "/" and cypher.startswith("/*", i):
            j = cypher.find("*/", i + 2)
            i = n if j == -1 else j + 2
            out.append(" ")
        else:
            out.append(c)
            i += 1
    return "".join(out)


def validate_write(cypher: str, rules: "list | None" = None) -> GuardReport:
    """write cypher를 룰 레지스트리로 정적 검증. ERROR/WARN을 GuardReport로.

    rules=None이면 engine.kg_harness.rules.RULES(정전) 사용. 호출자가 직접 룰 리스트를
    주입하면 그것만 적용(테스트/특수 게이트). 새 불변식 = RULES에 Rule 추가(OCP).
    룰은 주석-스트립된 텍스트를 본다(우회/오탐 동시 제거) — 보고서의 cypher 는 원문.
    """
    from engine.kg_harness.rules import RULES  # noqa: PLC0415 — lazy(순환 회피)

    active = RULES if rules is None else rules
    lint_text = strip_cypher_comments(cypher)
    violations: list[Violation] = []
    for rule in active:
        violations.extend(rule.check(lint_text))
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
    # H3 패리티 + 유일성 가드 (seam-integrity 2026-07-10): occam adapter 와 동형 —
    # (a) 양측 status 가드: 이미 아카이브된 노드 무접촉 + 교차 write(X→Y, Y→X)의 두 번째가
    #     0-row no-op 이 되어 SUPERSEDED_BY 사이클(생존자 0) 불가. 옛 cypher 는 이 가드가
    #     없어 kg_harness 경로가 occam 이 H3 로 막은 바로 그 모드를 열어뒀다.
    # (b) collect/size=1: {id_key} 는 비유일 가능 — 다중매치는 write 대신 0-row fail-closed.
    cypher = (
        f"MATCH (s:{label} {{{id_key}: $stale}}) "
        f"WHERE (s.status IS NULL OR s.status <> 'SUPERSEDED') "
        f"WITH collect(s) AS ss "
        f"MATCH (c:{label} {{{id_key}: $current}}) "
        f"WHERE (c.status IS NULL OR c.status <> 'SUPERSEDED') "
        f"WITH ss, collect(c) AS cs "
        f"WHERE size(ss) = 1 AND size(cs) = 1 "
        f"WITH ss[0] AS stale, cs[0] AS current "
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
    "ALLOW_DESTRUCTIVE_MARKER",
    "CypherRunner",
    "GuardReport",
    "Severity",
    "Violation",
    "WriteGuardError",
    "constraint_cypher",
    "guarded_run",
    "strip_cypher_comments",
    "supersede_node",
    "upsert_node",
    "validate_write",
]
