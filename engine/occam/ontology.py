"""오캄 온톨로지 층 — Description Logic 정합성 엔진 (순수 함수, KG/IO 없음).

verdict-user-occam-gains-ontology-hygiene-responsibility-2026-05-27: 오캄에 온톨로지 위생
책무. 그동안 손으로 친 cypher pass(occam-pass-ontology-layer-hygiene-*)를 *코드화*하고,
단순 dedup을 넘어 **형식 온톨로지 / DL 정합성**까지 검사한다.

학문 정전 grounding:
  · Baader, Calvanese, McGuinness, Nardi, Patel-Schneider (2003/2007) *The Description Logic
    Handbook* — 𝒮ℛ𝒪ℐ𝒬(D) 가 OWL 2 DL의 logical 기반.
  · W3C OWL 2 (2012) — punning, disjointness, subClassOf 의미론.
  · Gruber (1993) "A translation approach to portable ontology specifications" — ontology=명시적
    개념화. Guarino (1998) *Formal Ontology in Information Systems*.

검사 6종 (consensus c3 6각 진단의 DL 격상판):
  1. SUBSUMPTION_CYCLE  — subClassOf 는 DAG여야 (C ⊑ … ⊑ C 순환 = 사실상 동치, 모델링 오류).
  2. DANGLING_PARENT    — 존재하지 않는 상위 클래스를 subClassOf (참조 무결성 위반).
  3. DANGLING_TYPE      — 존재하지 않는 클래스를 rdf:type 으로 가리키는 instance.
  4. PUNNING            — 같은 이름이 OntologyClass ∧ OntologyInstance (OWL 2 DL는 punning 허용
                          하나 정전 진단 대상 — 라벨충돌 lesson 측).
  5. UNSATISFIABLE_CLASS — 두 disjoint 클래스의 공통 하위 = 인스턴스 가질 수 없음 (⊥).
  6. DISJOINTNESS_VIOLATION — 한 instance가 서로 disjoint한 두 클래스의 type (모델 비정합).

정합성(consistency): 1·5·6 부재 ⇒ DL-consistent. 2·3·4 는 무결성/위생 경고(정합성과 분리).
위생(hygiene): superseded/stale 온톨로지 노드는 scoring.score_node 로 σ 매겨 supersession 후보화.

covenant (occam.py와 동일): 삭제 금지·마구잡이 금지. 후보·위반 surface만, supersede 후보는
σ + twin-gate 통과분만. ambiguous는 flag.

# KG: verdict-user-occam-gains-ontology-hygiene-responsibility-2026-05-27,
#     occam-pass-ontology-layer-hygiene-2026-05-27, occam-pass-ontology-layer-hygiene-continuation-2026-05-27,
#     consensus-occam-entropy-truth-2026-05-26, occam-kam-canonical-2026-05-26
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from engine.occam.scoring import (
    EntrenchmentTier,
    NodeScoreMeta,
    ScoringConfig,
    SupersessionScore,
    Verdict,
    score_node,
)


class ViolationKind(str, Enum):
    SUBSUMPTION_CYCLE = "SUBSUMPTION_CYCLE"
    DANGLING_PARENT = "DANGLING_PARENT"
    DANGLING_TYPE = "DANGLING_TYPE"
    PUNNING = "PUNNING"
    UNSATISFIABLE_CLASS = "UNSATISFIABLE_CLASS"
    DISJOINTNESS_VIOLATION = "DISJOINTNESS_VIOLATION"


# 정합성을 깨는 위반(logical inconsistency) vs 무결성/위생 경고(integrity warning).
_INCONSISTENCY_KINDS = frozenset(
    {
        ViolationKind.SUBSUMPTION_CYCLE,
        ViolationKind.UNSATISFIABLE_CLASS,
        ViolationKind.DISJOINTNESS_VIOLATION,
    }
)


@dataclass(frozen=True)
class OntologyClassRecord:
    """온톨로지 클래스 한 개. parents=subClassOf 상위, disjoint_with=disjointWith 형제."""

    name: str
    parents: tuple[str, ...] = ()
    disjoint_with: tuple[str, ...] = ()
    status: str | None = None  # active / SUPERSEDED / null
    age_days: float = 0.0
    invocation_count: int = 0
    tier: EntrenchmentTier = EntrenchmentTier.ONTOLOGY_CLASS
    redundancy: float = 0.0  # 동일 정의 twin이 있으면 >0 (hygiene)
    has_successor: bool = False  # 대체 클래스 존재 여부 (supersede 전제)


@dataclass(frozen=True)
class OntologyInstanceRecord:
    """온톨로지 인스턴스 한 개. types=rdf:type 으로 가리키는 클래스들."""

    name: str
    types: tuple[str, ...] = ()


@dataclass(frozen=True)
class Violation:
    kind: ViolationKind
    subject: str  # 위반 주체 노드 이름
    detail: str
    witnesses: tuple[str, ...] = ()  # 위반을 증언하는 다른 노드들 (cycle 경로, disjoint 쌍 등)


@dataclass(frozen=True)
class OntologyReport:
    violations: tuple[Violation, ...] = ()
    supersession_candidates: tuple[tuple[str, SupersessionScore], ...] = ()
    flagged: tuple[tuple[str, SupersessionScore], ...] = ()  # FLAG_ONLY/VERIFY (machloket)
    scanned_classes: int = 0
    scanned_instances: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_consistent(self) -> bool:
        """DL-consistent = inconsistency 종류 위반이 0."""
        return not any(v.kind in _INCONSISTENCY_KINDS for v in self.violations)

    @property
    def violation_count(self) -> int:
        return len(self.violations)


# ── DL 검사 헬퍼 (순수) ───────────────────────────────────────────────────────

_WHITE, _GRAY, _BLACK = 0, 1, 2


def _record_cycle(
    parent: str, stack: list[str], seen: set[frozenset[str]], out: list[Violation]
) -> None:
    """back-edge 발견 시 stack의 parent..현재 구간을 1 cycle violation으로 (중복 제거)."""
    cycle = stack[stack.index(parent) :]
    key = frozenset(cycle)
    if key in seen:
        return
    seen.add(key)
    out.append(
        Violation(
            kind=ViolationKind.SUBSUMPTION_CYCLE,
            subject=parent,
            detail=f"subClassOf cycle: {' ⊑ '.join([*cycle, parent])}",
            witnesses=tuple(cycle),
        )
    )


def _find_subsumption_cycles(classes: dict[str, OntologyClassRecord]) -> list[Violation]:
    """subClassOf 그래프의 순환 탐지 (DFS, white/gray/black). 각 순환 1 violation."""
    color: dict[str, int] = dict.fromkeys(classes, _WHITE)
    violations: list[Violation] = []
    seen: set[frozenset[str]] = set()

    def dfs(node: str, stack: list[str]) -> None:
        color[node] = _GRAY
        stack.append(node)
        for parent in classes[node].parents:
            if parent not in classes:
                continue  # dangling은 별도 검사
            if color[parent] == _GRAY:
                _record_cycle(parent, stack, seen, violations)
            elif color[parent] == _WHITE:
                dfs(parent, stack)
        stack.pop()
        color[node] = _BLACK

    for name in classes:
        if color[name] == _WHITE:
            dfs(name, [])
    return violations


def _ancestors(name: str, classes: dict[str, OntologyClassRecord]) -> set[str]:
    """name의 모든 (재귀) 상위 클래스 + 자기 자신. 순환-안전 (visited)."""
    out: set[str] = set()
    stack = [name]
    while stack:
        cur = stack.pop()
        if cur in out or cur not in classes:
            continue
        out.add(cur)
        stack.extend(classes[cur].parents)
    return out


def _disjoint_pairs(classes: dict[str, OntologyClassRecord]) -> set[frozenset[str]]:
    """대칭 disjointWith 쌍 집합."""
    pairs: set[frozenset[str]] = set()
    for c in classes.values():
        for other in c.disjoint_with:
            if other != c.name:
                pairs.add(frozenset({c.name, other}))
    return pairs


def _first_disjoint_conflict(
    labels: set[str], disjoint: set[frozenset[str]], classes: dict[str, OntologyClassRecord]
) -> tuple[str, str] | None:
    """labels(클래스 집합)의 ancestor 폐포에서 disjoint 쌍이 둘 다 포함되면 그 쌍 반환."""
    closure: set[str] = set()
    for lab in labels:
        closure |= _ancestors(lab, classes)
    for pair in disjoint:
        a, b = tuple(pair) if len(pair) == 2 else (next(iter(pair)), next(iter(pair)))
        if a in closure and b in closure:
            return a, b
    return None


# ── 6 DL 검사 (각 1 헬퍼) ──────────────────────────────────────────────────────


def _check_dangling_parents(
    classes: list[OntologyClassRecord], cls_map: dict[str, OntologyClassRecord]
) -> list[Violation]:
    return [
        Violation(
            ViolationKind.DANGLING_PARENT, c.name, f"subClassOf non-existent class '{p}'", (p,)
        )
        for c in classes
        for p in c.parents
        if p not in cls_map
    ]


def _check_dangling_types(
    instances: list[OntologyInstanceRecord], cls_map: dict[str, OntologyClassRecord]
) -> list[Violation]:
    return [
        Violation(ViolationKind.DANGLING_TYPE, i.name, f"rdf:type non-existent class '{t}'", (t,))
        for i in instances
        for t in i.types
        if t not in cls_map
    ]


def _check_punning(
    cls_map: dict[str, OntologyClassRecord], inst_names: set[str]
) -> list[Violation]:
    return [
        Violation(
            ViolationKind.PUNNING,
            name,
            "name is both OntologyClass and OntologyInstance (punning / 라벨충돌)",
        )
        for name in sorted(cls_map.keys() & inst_names)
    ]


def _check_unsatisfiable(
    classes: list[OntologyClassRecord],
    disjoint: set[frozenset[str]],
    cls_map: dict[str, OntologyClassRecord],
) -> list[Violation]:
    out: list[Violation] = []
    for c in classes:
        conflict = _first_disjoint_conflict({c.name}, disjoint, cls_map)
        if conflict and not (c.name == conflict[0] and c.name == conflict[1]):
            a, b = conflict
            out.append(
                Violation(
                    ViolationKind.UNSATISFIABLE_CLASS,
                    c.name,
                    f"subclass of disjoint classes '{a}' and '{b}' ⇒ unsatisfiable (⊥)",
                    (a, b),
                )
            )
    return out


def _check_disjointness(
    instances: list[OntologyInstanceRecord],
    disjoint: set[frozenset[str]],
    cls_map: dict[str, OntologyClassRecord],
) -> list[Violation]:
    out: list[Violation] = []
    for i in instances:
        conflict = _first_disjoint_conflict(set(i.types), disjoint, cls_map)
        if conflict:
            a, b = conflict
            out.append(
                Violation(
                    ViolationKind.DISJOINTNESS_VIOLATION,
                    i.name,
                    f"instance typed to disjoint classes '{a}' and '{b}'",
                    (a, b),
                )
            )
    return out


# ── 위생 scoring ──────────────────────────────────────────────────────────────


def _is_hygiene_candidate(c: OntologyClassRecord, cfg: ScoringConfig) -> bool:
    """active·사용중·중복없음·신선 = 위생 대상 아님. SUPERSEDED도 제외(재아카이브 금지)."""
    if c.status == "SUPERSEDED":
        return False
    return not (c.redundancy <= 0.0 and c.invocation_count > 0 and c.age_days < cfg.halflife_days)


def _hygiene_scoring(
    classes: list[OntologyClassRecord], cfg: ScoringConfig
) -> tuple[list[tuple[str, SupersessionScore]], list[tuple[str, SupersessionScore]]]:
    """stale/중복 클래스 σ scoring → (supersession, flagged). KEEP/PROTECTED는 보고 안 함."""
    supersession: list[tuple[str, SupersessionScore]] = []
    flagged: list[tuple[str, SupersessionScore]] = []
    for c in classes:
        if not _is_hygiene_candidate(c, cfg):
            continue
        meta = NodeScoreMeta(
            redundancy=c.redundancy,
            age_days=c.age_days,
            invocation_count=c.invocation_count,
            tier=c.tier,
            has_successor=c.has_successor,
        )
        sc = score_node(meta, cfg)
        if sc.verdict == Verdict.SUPERSEDE:
            supersession.append((c.name, sc))
        elif sc.verdict in (Verdict.VERIFY, Verdict.FLAG_ONLY):
            flagged.append((c.name, sc))
    return supersession, flagged


# ── 메인 pass (orchestration만) ────────────────────────────────────────────────


def ontology_pass(
    classes: list[OntologyClassRecord],
    instances: list[OntologyInstanceRecord] | None = None,
    config: ScoringConfig | None = None,
) -> OntologyReport:
    """온톨로지 층 DL 정합성 + scored 위생 pass. covenant: surface만, 삭제 0.

    6 DL 검사(순환/dangling×2/punning/unsatisfiable/disjointness)는 각 _check_* 헬퍼,
    위생 scoring은 _hygiene_scoring 에 위임. 본 함수는 orchestration만."""
    instances = instances or []
    cfg = config or ScoringConfig()
    cls_map = {c.name: c for c in classes}
    inst_names = {i.name for i in instances}
    disjoint = _disjoint_pairs(cls_map)

    violations: list[Violation] = [
        *_find_subsumption_cycles(cls_map),
        *_check_dangling_parents(classes, cls_map),
        *_check_dangling_types(instances, cls_map),
        *_check_punning(cls_map, inst_names),
        *_check_unsatisfiable(classes, disjoint, cls_map),
        *_check_disjointness(instances, disjoint, cls_map),
    ]

    supersession, flagged = _hygiene_scoring(classes, cfg)

    incon = sum(1 for v in violations if v.kind in _INCONSISTENCY_KINDS)
    notes = (
        "covenant: surface-only; no delete. DL grounding=Baader DL Handbook + OWL2 DL.",
        f"consistency={'OK' if incon == 0 else f'VIOLATED({incon})'}; "
        f"{len(violations)} total violation(s).",
        f"hygiene: {len(supersession)} supersession candidate(s), {len(flagged)} flagged.",
    )

    return OntologyReport(
        violations=tuple(violations),
        supersession_candidates=tuple(supersession),
        flagged=tuple(flagged),
        scanned_classes=len(classes),
        scanned_instances=len(instances),
        notes=notes,
    )


__all__ = [
    "OntologyClassRecord",
    "OntologyInstanceRecord",
    "OntologyReport",
    "Violation",
    "ViolationKind",
    "ontology_pass",
]
