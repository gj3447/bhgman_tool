"""rules — write-guard 검증 룰 plug-in 레지스트리 (OCP: 새 불변식 = 새 Rule 등록).

각 Rule은 `check(cypher) -> list[Violation]` 하나만 구현. `validate_write`는 RULES를
순회만 한다 — 규칙 추가/교체에 validate_write 본문 수정 불필요(open for extension).

정규식 lint의 false-negative를 좁히는 #2 룰 포함:
  ApocCreateRule : apoc.create.node/nodes/addLabels = MERGE 우회 동적 생성/라벨.
  BulkLoadRule   : LOAD CSV = 벌크 경로(Python 빌더 우회) → 사후 audit 환기.
(apoc.merge.node는 키 기반 MERGE 등가라 정당 → 미플래그.)

# KG: occam-pass-metahumotonic-20260626
"""

from __future__ import annotations

import re

from engine.kg_harness.write_guard import (
    ALLOW_CREATE_MARKER,
    ALLOW_DESTRUCTIVE_MARKER,
    Severity,
    Violation,
)


class Rule:
    """검증 룰 base. code = 위반코드, check()가 위반 0개 이상 반환."""

    code = "RULE"

    def check(self, cypher: str) -> list[Violation]:  # pragma: no cover - 추상
        raise NotImplementedError


# ── INV0: anti-destruction (archive-only covenant 의 chokepoint 승격) ─────────


class DestructiveWriteRule(Rule):
    """파괴 연산 = ERROR. 공유 KG covenant 는 archive-only(supersede+SUPERSEDED_BY) —
    guarded 경로에 정당한 delete/drop/remove 는 없다 (2026-07-08 감사 confirmed-high:
    DETACH DELETE 등이 chokepoint 를 ALLOWED 로 통과하던 delete-blind 봉합).

    occam/jaebaeman 의 raise-covenant 는 자기 고정 템플릿만 지킨다 — 이 룰이 raw-cypher
    전체를 커버한다. 문자열 리터럴 *내부* 토큰(apoc.periodic.iterate 의 내부 쿼리 등)도
    의도적으로 매치한다(거부 우선). 드문 정당 사례(로컬 픽스처 청소)는 마커로 opt-out."""

    code = "DESTRUCTIVE_WRITE"
    _res = (
        re.compile(r"\b(?:DETACH\s+)?DELETE\b", re.IGNORECASE),
        re.compile(r"\bDROP\s+(?:CONSTRAINT|INDEX|DATABASE)\b", re.IGNORECASE),
        re.compile(r"\bREMOVE\b", re.IGNORECASE),
        re.compile(
            r"\bapoc\.(?:nodes\.delete|refactor\.(?:mergeNodes|deleteAndReconnect)"
            r"|periodic\.commit)\b",
            re.IGNORECASE,
        ),
    )

    def check(self, cypher: str) -> list[Violation]:
        if ALLOW_DESTRUCTIVE_MARKER in cypher:
            return []
        return [
            Violation(
                self.code,
                Severity.ERROR,
                f"파괴 연산 '{m.group(0)}' — archive-only covenant: 삭제/드랍/제거는 복구 "
                "불가(묘비도 계보도 안 남음). supersede_node 로 archive 하라. "
                f"정당하면 '{ALLOW_DESTRUCTIVE_MARKER}' 주석으로 opt-out.",
                m.group(0),
            )
            for rx in self._res
            if (m := rx.search(cypher))
        ]


# ── INV1: anti-dup (생성 경로) ────────────────────────────────────────────────


class NakedCreateRule(Rule):
    code = "NAKED_CREATE"
    # 라벨 붙은 노드 CREATE. CONSTRAINT/INDEX·관계전용 CREATE(라벨 없음)는 매치 안 됨.
    _re = re.compile(r"\bCREATE\s*\(\s*\w*\s*:\s*\w+", re.IGNORECASE)

    def check(self, cypher: str) -> list[Violation]:
        if ALLOW_CREATE_MARKER in cypher:
            return []
        m = self._re.search(cypher)
        if not m:
            return []
        return [
            Violation(
                self.code,
                Severity.ERROR,
                "라벨 노드를 CREATE — stable-id MERGE 사용(중복 ingest 방지). "
                f"정당하면 '{ALLOW_CREATE_MARKER}' 주석으로 opt-out.",
                m.group(0),
            )
        ]


class ApocCreateRule(Rule):
    """#2: apoc.create.node/nodes/addLabels — 정규식 NakedCreate를 우회하는 동적 생성/라벨."""

    code = "APOC_CREATE"
    _re = re.compile(r"\bapoc\.create\.(node|nodes|addLabels)\b", re.IGNORECASE)

    def check(self, cypher: str) -> list[Violation]:
        if ALLOW_CREATE_MARKER in cypher:
            return []
        m = self._re.search(cypher)
        if not m:
            return []
        fn = m.group(1)
        return [
            Violation(
                self.code,
                Severity.ERROR,
                f"apoc.create.{fn} — stable-id MERGE / apoc.merge.node 우회(동적 노드/라벨 생성). "
                "dup·god-object 위험. 키 기반 apoc.merge.node를 쓰라.",
                m.group(0),
            )
        ]


class BulkLoadRule(Rule):
    """#2: LOAD CSV / apoc.periodic.iterate — 벌크 경로는 빌더/엔진 chokepoint를 우회한다.
    (iterate 의 내부 쿼리가 파괴적이면 DestructiveWriteRule 이 ERROR 로 따로 잡는다.)"""

    code = "BULK_LOAD"
    _re = re.compile(r"\bLOAD\s+CSV\b|\bapoc\.periodic\.iterate\b", re.IGNORECASE)

    def check(self, cypher: str) -> list[Violation]:
        m = self._re.search(cypher)
        if not m:
            return []
        return [
            Violation(
                self.code,
                Severity.WARN,
                "LOAD CSV 벌크 경로 — 빌더/하네스 우회. 키 기반 MERGE 보장 + 사후 audit 필수.",
                m.group(0),
            )
        ]


class MergeWithoutKeyRule(Rule):
    code = "MERGE_WITHOUT_KEY"
    _re = re.compile(r"\bMERGE\s*\(\s*\w*\s*:\s*\w+\s*\)")

    def check(self, cypher: str) -> list[Violation]:
        m = self._re.search(cypher)
        if not m:
            return []
        return [
            Violation(
                self.code,
                Severity.WARN,
                "MERGE에 식별 키 맵이 없음 — 라벨당 1노드로 잘못 합쳐질 수 있음.",
                m.group(0),
            )
        ]


# ── INV2: anti-god-object (필드 누적) ─────────────────────────────────────────


class VersionedFieldRule(Rule):
    code = "VERSIONED_FIELD"
    _dot = re.compile(r"\.([A-Za-z_]\w*_v\d+)\b")
    _map = re.compile(r"[\{,]\s*([A-Za-z_]\w*_v\d+)\s*:")

    def check(self, cypher: str) -> list[Violation]:
        keys = {m.group(1) for m in self._dot.finditer(cypher)}
        keys |= {m.group(1) for m in self._map.finditer(cypher)}
        return [
            Violation(
                self.code,
                Severity.ERROR,
                f"버전드 필드 '{k}' — update-in-place 하라(god-object 유발). "
                "이력이 필요하면 별도 :History 노드/엣지로.",
                k,
            )
            for k in sorted(keys)
        ]


class StaleFieldRule(Rule):
    code = "STALE_FIELD"
    _dot = re.compile(r"\.([A-Za-z_]\w*(?:_old|_stale))\b")
    _map = re.compile(r"[\{,]\s*([A-Za-z_]\w*(?:_old|_stale))\s*:")

    def check(self, cypher: str) -> list[Violation]:
        keys = {m.group(1) for m in self._dot.finditer(cypher)}
        keys |= {m.group(1) for m in self._map.finditer(cypher)}
        return [
            Violation(self.code, Severity.WARN, f"stale 접미사 필드 '{k}' — 누적 신호.", k)
            for k in sorted(keys)
        ]


# ── INV3: anti-orphan (묘비) ──────────────────────────────────────────────────


class OrphanTombstoneRule(Rule):
    code = "ORPHAN_TOMBSTONE"
    _label = re.compile(r":Superseded\b")
    _status = re.compile(r"""status\s*[:=]\s*['"]SUPERSEDED['"]""", re.IGNORECASE)
    _prop = re.compile(r"\bsuperseded(?:By|At|Reason)\b", re.IGNORECASE)

    def check(self, cypher: str) -> list[Violation]:
        intent = bool(
            self._label.search(cypher) or self._status.search(cypher) or self._prop.search(cypher)
        )
        has_edge = "SUPERSEDED_BY" in cypher.upper()
        if intent and not has_edge:
            return [
                Violation(
                    self.code,
                    Severity.ERROR,
                    "노드를 supersede/tombstone 하면서 SUPERSEDED_BY 엣지가 없음 — "
                    "교체본 추적 불가(나중에 자동청소 불가능). 대체 노드로 엣지를 걸어라.",
                )
            ]
        return []


# 활성 룰 레지스트리 — 순서 = 보고 순서. 새 불변식은 여기 한 줄 추가하면 끝(OCP).
RULES: list[Rule] = [
    DestructiveWriteRule(),
    NakedCreateRule(),
    ApocCreateRule(),
    BulkLoadRule(),
    MergeWithoutKeyRule(),
    VersionedFieldRule(),
    StaleFieldRule(),
    OrphanTombstoneRule(),
]


__all__ = [
    "RULES",
    "ApocCreateRule",
    "BulkLoadRule",
    "DestructiveWriteRule",
    "MergeWithoutKeyRule",
    "NakedCreateRule",
    "OrphanTombstoneRule",
    "Rule",
    "StaleFieldRule",
    "VersionedFieldRule",
]
