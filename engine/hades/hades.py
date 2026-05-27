"""하데스(Hades) 코어 — 실현한다(추상→구체↓). 유레카(구체→추상↑)의 dual. 7번째 군단장 동사.

유레카가 PROPOSE한 *승인된* 추상을 구체 KG 구조/코드로 실현(materialize). TDD GREEN.
형식: Galois γ(concretization) / anamorphism·unfold / refinement calculus / TDD GREEN.

**경계**: 재배맨=출격(누가/분배), 하데스=실현(실제 써냄). 하네스=바닥/場(수동), 하데스=場에 써내림(능동).
**위험**: materialize = engine-impl c6 "가장 위험"(우연 결합 영구화/분산장애/비가역). 그래서:
  - dry_run 기본 (PLANNED만, auto-apply 금지)
  - **ACCEPTED 후보만** 실현 (PROVISIONAL/REJECTED 거부) — fidelity/judgment gate 통과분만
  - **reversibility-first**: 모든 plan에 undo (covenant)
  - code: ≤max_sites 점진 rollout (분산장애 차단)

# KG: hades-canonical-2026-05-27, eureka-canonical-2026-05-26 (dual),
#     consensus-eureka-engine-impl-2026-05-26 (c6 materialize danger)
"""

from __future__ import annotations

from collections.abc import Callable

from hades_models import MaterializationPlan, RealizeStatus, RealizeVerdict

CypherRunner = Callable[[str, dict], "list[dict]"]


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

    ops = (
        f"MERGE (a:AbstractClass {{name:'{concept_name}'}}) SET a.status='CANONICAL', a.realizedBy='hades'",
        f"UNWIND $members AS m MATCH (o {{name:m}}) MERGE (o)-[:INSTANCE_OF]->(a)  // {len(member_names)} members",
    )
    undo = (
        f"MATCH (a:AbstractClass {{name:'{concept_name}'}}) SET a.status='SUPERSEDED'  // reversible",
        f"MATCH (o)-[r:INSTANCE_OF]->(a {{name:'{concept_name}'}}) DELETE r  // undo edges",
    )
    plan = MaterializationPlan(concept_name, "kg", ops, undo, reversible=True)

    applied = False
    if not dry_run and apply_cypher is not None:
        apply_cypher(ops[0], {})
        apply_cypher(ops[1], {"members": list(member_names)})
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


__all__ = ["CypherRunner", "realize_code_template", "realize_kg_abstraction"]
