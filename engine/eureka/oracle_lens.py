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
    """유레카 MATERIALIZE 전 기본 checkable 렌즈: 추상이 lint + test 통과해야.

    round-trip(추상 적용→원본 일치)·characterization test는 호출자가 target에 포함.
    """
    return (
        OracleLens("ruff", "typecheck", ("ruff", "check", target)),
        OracleLens("pytest", "test", ("pytest", "-q", target)),
    )


__all__ = [
    "CommandRunner",
    "OracleLens",
    "OracleVerdict",
    "default_eureka_lenses",
    "run_oracle_gate",
    "subprocess_runner",
]
