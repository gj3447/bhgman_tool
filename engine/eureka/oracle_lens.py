"""나생문 oracle 렌즈 — 유레카 결정론 hard-gate (컴파일러나생문 family).

유레카 PROPOSE→MATERIALIZE 사이의 *executable* 검증. 2 lens-class 중 oracle 렌즈:
LLM 판단(stage_5 VERDICT_PENDING)이 아니라 *실제 도구 실행*(ruff/pytest/lean)으로 verify.
**HARD GATE**: FAIL이면 토론 없이 즉시 reject. 빌드/테스트 깨지면 의미검증 무의미하므로 선(先) gate.
**경계**: checkable(문법·빌드·타입·테스트·수치)만. 추상의 *의미적 타당성*은 판단 렌즈(LLM/사람) 몫.

primitive(OracleLens/OracleVerdict/run_oracle_gate)는 정본 engine/naesengmoon/oracle_lens.py
에서 import (occam 과 공유, 오캄 dedup 2026-06-01). 본 모듈은 유레카 고유 렌즈
(default_eureka_lenses=CODE backend, kg_oracle_gate=KG backend)만 정의한다.

# KG: naesengmoon-wired-ensemble-upgrade-2026-05-27 (oracle lens-class, 유레카 wiring),
#     naesengmoon-compiler-family-2026-05-27, naesengmoon-tdd-connection-2026-05-27,
#     eureka-canonical-2026-05-26 (JUSTIFY=나생문 handoff, auto-commit 금지),
#     wqi-extract-shared-naesengmoon-oracle-primitive-2026-05-27 (dedup closure)
"""

from __future__ import annotations

from collections.abc import Sequence

from engine.naesengmoon.oracle_lens import (
    CommandRunner,
    OracleLens,
    OracleVerdict,
    run_oracle_gate,
    subprocess_runner,
)


def default_eureka_lenses(target: str = ".") -> tuple[OracleLens, ...]:
    # KG: eureka-canonical-2026-05-26
    """CODE backend 기본 checkable 렌즈: 추상이 lint + test 통과해야.

    **주의**: 이건 *코드* materialize 경로용(Extract Superclass 등). KG induction 경로엔
    kg_oracle_gate()를 써라 (cypher/concept 불변식). 둘은 다른 backend (위험도 비대칭).
    round-trip(추상 적용→원본 일치)·characterization test는 호출자가 target에 포함.
    """
    return (
        OracleLens("ruff", "typecheck", ("ruff", "check", target)),
        OracleLens("pytest", "test", ("pytest", "-q", target)),
    )


def kg_oracle_gate(
    abstract_classes: Sequence[object],
    *,
    min_extent: int = 2,
    min_stability: float = 0.5,
) -> tuple[bool, list[OracleVerdict]]:
    # KG: eureka-canonical-2026-05-26
    """KG backend 컴파일러나생문 — concept 후보의 결정론 *불변식* 검증 (HARD GATE).

    checkable only (의미 판단 X — 그건 stage_5 판단렌즈 + semantic-fidelity proxy 몫):
      1. extent recount  : |extent| ≥ min_extent  (주장한 support가 실제 성립?)
      2. schema          : intent 비어있지 않음    (empty intent = degenerate concept)
      3. acyclic         : name ∉ extent           (self-referential = cycle)
      4. recount/stability: stabilityScore ≥ min_stability (주장한 안정성 성립?)

    code backend의 compile/test 와 동형 역할 — "추상이 형식적으로 well-formed인가"만 본다.
    첫 FAIL에서 short-circuit (hard gate).
    """
    verdicts: list[OracleVerdict] = []
    for ac in abstract_classes:
        name = str(getattr(ac, "name", "?"))
        extent = list(getattr(ac, "extent", []) or [])
        intent = list(getattr(ac, "intent", []) or [])
        stability = getattr(ac, "stabilityScore", None)

        if len(extent) < min_extent:
            verdicts.append(
                OracleVerdict(
                    name, "recount", False, f"extent {len(extent)} < min_extent {min_extent}"
                )
            )
            return False, verdicts
        if not intent:
            verdicts.append(
                OracleVerdict(name, "schema", False, "empty intent (degenerate concept)")
            )
            return False, verdicts
        if name in extent:
            verdicts.append(
                OracleVerdict(name, "acyclic", False, "self-referential extent (cycle)")
            )
            return False, verdicts
        if stability is not None and stability < min_stability:
            verdicts.append(
                OracleVerdict(
                    name, "recount", False, f"stability {stability:.3f} < {min_stability}"
                )
            )
            return False, verdicts
        verdicts.append(OracleVerdict(name, "recount", True, "PASS"))
    return True, verdicts


__all__ = [
    "CommandRunner",
    "OracleLens",
    "OracleVerdict",
    "default_eureka_lenses",
    "kg_oracle_gate",
    "run_oracle_gate",
    "subprocess_runner",
]
