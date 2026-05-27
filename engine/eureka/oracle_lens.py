"""나생문 oracle 렌즈 — 유레카 결정론 hard-gate (컴파일러나생문 family).

유레카 PROPOSE→MATERIALIZE 사이의 *executable* 검증. 2 lens-class 중 oracle 렌즈:
LLM 판단(stage_5 VERDICT_PENDING)이 아니라 *실제 도구 실행*(ruff/pytest/lean)으로 verify.
**HARD GATE**: FAIL이면 토론 없이 즉시 reject. 빌드/테스트 깨지면 의미검증 무의미하므로 선(先) gate.
**경계**: checkable(문법·빌드·타입·테스트·수치)만. 추상의 *의미적 타당성*은 판단 렌즈(LLM/사람) 몫.

occam/oracle_lens.py 와 동일 primitive (OracleLens/OracleVerdict/run_oracle_gate). 2 commander
중복 = 공유 추출 후보 → engine/naesengmoon 공용 모듈 (유레카-extract, KG flag 참조).

# KG: naesengmoon-wired-ensemble-upgrade-2026-05-27 (oracle lens-class, 유레카 wiring),
#     naesengmoon-compiler-family-2026-05-27, naesengmoon-tdd-connection-2026-05-27,
#     eureka-canonical-2026-05-26 (JUSTIFY=나생문 handoff, auto-commit 금지)
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass

# runner: command argv -> (returncode, combined_output). 주입식 (테스트=fake, 실전=subprocess).
CommandRunner = Callable[[Sequence[str]], "tuple[int, str]"]


def subprocess_runner(cmd: Sequence[str]) -> tuple[int, str]:
    """기본 runner — 실제 subprocess. cwd/env는 호출자 책임."""
    proc = subprocess.run(list(cmd), capture_output=True, text=True, check=False)  # noqa: S603
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


@dataclass(frozen=True)
class OracleVerdict:
    """결정론 검증 결과. hard_gate=True면 FAIL이 전체 reject."""

    lens: str
    kind: str  # compiler | test | typecheck | recount
    passed: bool
    detail: str
    hard_gate: bool = True

    @property
    def is_red(self) -> bool:
        """TDD RED 상태 (테스트 실패 = 나생문 FAIL)."""
        return not self.passed


@dataclass(frozen=True)
class OracleLens:
    """컴파일러나생문 한 개. C=gcc/clang, Python=ruff/mypy/pytest, Lean=lake build."""

    name: str
    kind: str
    command: tuple[str, ...]

    def verify(self, runner: CommandRunner = subprocess_runner) -> OracleVerdict:
        code, out = runner(self.command)
        passed = code == 0
        detail = "PASS" if passed else f"exit={code}: {out.strip()[:300]}"
        return OracleVerdict(lens=self.name, kind=self.kind, passed=passed, detail=detail)


def run_oracle_gate(
    lenses: Sequence[OracleLens], runner: CommandRunner = subprocess_runner
) -> tuple[bool, list[OracleVerdict]]:
    """oracle 렌즈들을 순서대로 hard-gate 실행. 첫 FAIL에서 short-circuit.

    반환: (gate_passed, verdicts). gate_passed=False면 판단 렌즈(LLM) 진입 차단.
    """
    verdicts: list[OracleVerdict] = []
    for lens in lenses:
        verdict = lens.verify(runner)
        verdicts.append(verdict)
        if not verdict.passed:
            return False, verdicts  # hard gate: 첫 FAIL에서 멈춤
    return True, verdicts


def default_eureka_lenses(target: str = ".") -> tuple[OracleLens, ...]:
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
