"""하데스(Hades) 코어 — 실현한다(추상→구체↓). 유레카(구체→추상↑)의 dual. 7번째 군단장 동사.

유레카가 PROPOSE한 *승인된* 추상을 구체 KG 구조/코드로 실현(materialize). TDD GREEN.
형식: Galois γ(concretization) / anamorphism·unfold / refinement calculus / TDD GREEN.

**Formal status (2026-05-28 promoted)**: INDEXED_PAIR (Place, Realize-Action).
  - component_place = 場 / scaffold (비행기맨#4 결정화 — 3계층 IDE-host / runtime / managed cloud)
  - component_realize_action = 하계의 신 — 실현 동사 (추상→구체, 유레카 dual)
  - relationship = USES (same entity, two aspects, NOT alias merge)
  - hades=하네스 R1↔R2 flip-flop 은 indexed-pair structure 명시로 해소
  - eureka 와의 dual: dual-hades-eureka-formal-galois-2026-05-28 (FORMAL_GALOIS_DUAL)
  - Naesengmoon promoted via vr-7commander-coverage-completeness-2026-05-28

**경계**: 재배맨=출격(누가/분배), 하데스=실현(실제 써냄). 하네스=바닥/場(수동), 하데스=場에 써내림(능동).
**위험**: materialize = engine-impl c6 "가장 위험"(우연 결합 영구화/분산장애/비가역). 그래서:
  - dry_run 기본 (PLANNED만, auto-apply 금지)
  - **ACCEPTED 후보만** 실현 (PROVISIONAL/REJECTED 거부) — fidelity/judgment gate 통과분만
  - **reversibility-first**: 모든 plan에 undo (covenant)
  - code: ≤max_sites 점진 rollout (분산장애 차단)

# KG: hades-canonical-2026-05-27 (INDEXED_PAIR formal status, 2026-05-28),
#     eureka-canonical-2026-05-26 (dual),
#     dual-hades-eureka-formal-galois-2026-05-28,
#     consensus-eureka-engine-impl-2026-05-26 (c6 materialize danger),
#     vp-hades-harness-indexed-pair-formalization-2026-05-28 (RATIFIED_DELEGATED)
"""

from __future__ import annotations

from collections.abc import Callable

from engine.hades.extract_superclass import extract_superclass, extract_superclass_cst
from engine.hades.hades_models import MaterializationPlan, RealizeStatus, RealizeVerdict

CypherRunner = Callable[[str, dict], "list[dict]"]
CodeWriter = Callable[[str, dict[str, str]], None]
"""apply 시 caller가 주입: (base_source, {class_name: new_source}) → 디스크 write."""


def realize_kg_abstraction(
    concept_name: str,
    verdict_status: str,
    member_names: list[str],
    *,
    dry_run: bool = True,
    apply_cypher: CypherRunner | None = None,
) -> RealizeVerdict:
    """KG 추상 실현: concept를 CANONICAL로 승격 + 멤버 INSTANCE_OF. dry_run 기본.

    가드: verdict_status='ACCEPTED'만 (PROVISIONAL/REJECTED 거부). undo=supersede(reversible).
    """
    if verdict_status != "ACCEPTED":
        return RealizeVerdict(
            concept_name,
            RealizeStatus.REFUSED,
            None,
            f"verdict={verdict_status} — ACCEPTED만 실현 (PROVISIONAL/REJECTED는 gate 미통과). 유레카 PROPOSE→fidelity/judgment→ACCEPTED 후 하데스.",
        )
    if not member_names:
        return RealizeVerdict(
            concept_name, RealizeStatus.REFUSED, None, "empty extent — 실현 대상 없음"
        )

    # 파라미터화 cypher (injection 차단 + concept_name에 따옴표 들어가도 안전).
    # op1은 새 쿼리라 op0의 (a) 바인딩이 안 넘어옴 → AbstractClass를 *재-MATCH* 해야 함
    # (옛 bare `(a)`는 익명 신규 노드를 MERGE하던 버그).
    ops = (
        "MERGE (a:AbstractClass {name:$concept}) SET a.status='CANONICAL', a.realizedBy='hades'",
        "UNWIND $members AS m "
        "MATCH (a:AbstractClass {name:$concept}) "
        # exclude AbstractClass: a member node is an INSTANCE_OF the abstraction, never
        # itself an abstract class — bare (o {name:m}) bound arbitrary same-named nodes,
        # including other AbstractClasses (W3-I).
        "MATCH (o {name:m}) WHERE NOT o:AbstractClass "
        "MERGE (o)-[:INSTANCE_OF]->(a)",
    )
    undo = (
        "MATCH (a:AbstractClass {name:$concept}) SET a.status='SUPERSEDED'",
        "MATCH (o)-[r:INSTANCE_OF]->(a:AbstractClass {name:$concept}) DELETE r",
    )
    plan = MaterializationPlan(concept_name, "kg", ops, undo, reversible=True)

    applied = False
    if not dry_run and apply_cypher is not None:
        apply_cypher(ops[0], {"concept": concept_name})
        apply_cypher(ops[1], {"concept": concept_name, "members": list(member_names)})
        applied = True
    status = RealizeStatus.APPLIED if applied else RealizeStatus.PLANNED
    return RealizeVerdict(
        concept_name, status, plan, "kg materialize (CANONICAL + INSTANCE_OF)", applied
    )


def realize_code_template(
    concept_name: str,
    lgg_template: str,
    sites: list[str],
    *,
    max_sites: int = 5,
    dry_run: bool = True,
) -> RealizeVerdict:
    """코드 추상 실현: LGG 템플릿 → Extract Superclass/shared-fn refactor. **PLANNED만(dry-run)**.

    가드: ≤max_sites 점진 rollout (분산장애 차단). 실제 apply는 characterization test gate 후 별도.
    """
    if len(sites) > max_sites:
        return RealizeVerdict(
            concept_name,
            RealizeStatus.REFUSED,
            None,
            f"{len(sites)} sites > max {max_sites} — ≤5 site 점진 rollout 초과(분산장애 위험). 배치 분할 필요.",
        )
    ops = (
        f"EXTRACT shared template '{lgg_template}' → new abstraction",
        *(f"REPLACE site {s} with call to abstraction" for s in sites),
    )
    undo = tuple(f"INLINE-BACK site {s} (restore original)" for s in sites)
    plan = MaterializationPlan(concept_name, "code", ops, undo, reversible=True)
    # 코드 materialize는 항상 dry-run PLANNED (apply=characterization test gate 후 인간/하데스 별 절차)
    return RealizeVerdict(
        concept_name,
        RealizeStatus.PLANNED,
        plan,
        f"code refactor PLAN (dry-run, {len(sites)} sites). apply 전 characterization test 필수.",
    )


def realize_code_extract_superclass(
    base_name: str,
    class_sources: dict[str, str],
    *,
    verdict_status: str = "ACCEPTED",
    max_sites: int = 5,
    dry_run: bool = True,
    writer: CodeWriter | None = None,
    preserve_format: bool = False,
) -> RealizeVerdict:
    """진짜 Extract-Superclass 실현 — ast로 실 코드 생성 (문자열 plan 아님).

    가드 (하데스 covenant): ACCEPTED 후보만 / ≤max_sites 점진 rollout / dry-run 기본 /
    reversibility-first(undo) / apply는 명시적 ``writer`` 주입 + dry_run=False 시에만.
    공통 메서드(구조 동일)가 없으면 REFUSED.

    preserve_format=True → libcst 백엔드(주석·레이아웃 보존, optional [hades-cst] dep).
    """
    if verdict_status != "ACCEPTED":
        return RealizeVerdict(
            base_name, RealizeStatus.REFUSED, None, f"verdict={verdict_status} (ACCEPTED만 실현)."
        )
    if len(class_sources) > max_sites:
        return RealizeVerdict(
            base_name,
            RealizeStatus.REFUSED,
            None,
            f"{len(class_sources)} sites > max {max_sites} — ≤{max_sites} 점진 rollout 초과.",
        )
    engine = extract_superclass_cst if preserve_format else extract_superclass
    patch = engine(base_name, class_sources)
    if patch is None:
        return RealizeVerdict(
            base_name, RealizeStatus.REFUSED, None, "추출할 구조-동일 공통 메서드 없음(lift 불가)."
        )
    ops = (
        f"CREATE class {base_name} with methods {list(patch.common_methods)}",
        *(f"REWRITE {n}: inherit {base_name}, drop lifted methods" for n in class_sources),
    )
    undo = (
        *(
            f"RESTORE {n}: re-inline {list(patch.common_methods)}, drop {base_name} base"
            for n in class_sources
        ),
        f"DELETE class {base_name}",
    )
    plan = MaterializationPlan(base_name, "code", ops, undo, reversible=True)
    applied = False
    if not dry_run and writer is not None:
        writer(patch.base_source, patch.modified)
        applied = True
    status = RealizeStatus.APPLIED if applied else RealizeStatus.PLANNED
    reason = (
        f"extract-superclass {'APPLIED' if applied else 'PLAN (dry-run)'}: "
        f"{len(patch.common_methods)} methods → {base_name}. apply 전 characterization test 필수."
    )
    return RealizeVerdict(base_name, status, plan, reason, applied=applied)


__all__ = [
    "CodeWriter",
    "CypherRunner",
    "realize_code_extract_superclass",
    "realize_code_template",
    "realize_kg_abstraction",
]
