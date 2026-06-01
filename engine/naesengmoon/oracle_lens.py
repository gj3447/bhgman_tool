"""나생문 oracle 렌즈 (정본 primitive) — 결정론 실행 critic (컴파일러나생문 family).

LLM 판단이 아니라 *실제 도구 실행* 결과로 검증(verify). TDD의 테스트가 바로 이것:
RED = OracleVerdict.passed=False, GREEN = passed=True. 나생문=GAN의 D, 코드=G.
**HARD GATE**: FAIL이면 토론 없이 즉시 reject. 컴파일 안 되면 의미검증 무의미하므로 선(先) gate.
**경계**: checkable(문법·빌드·타입·테스트·수치)만. semantic 의도는 판단 렌즈(LLM) 몫.

정본 위치 = 나생문 패키지 (occam/eureka 가 공유 import). occam/oracle_lens.py 와
eureka/oracle_lens.py 에 중복돼 있던 primitive 를 여기로 추출
(wqi-extract-shared-naesengmoon-oracle-primitive-2026-05-27, 오캄 dedup 2026-06-01).

# KG: naesengmoon-wired-ensemble-upgrade-2026-05-27 (oracle lens-class),
#     naesengmoon-compiler-family-2026-05-27, naesengmoon-tdd-connection-2026-05-27,
#     naesengmoon-cerberus-variant-pre-emit-gate-2026-05-20 (test-first = pre-emit timing),
#     naesengmoon-generate-verify-asymmetry-2026-06-01 (빠꾸=싸다, oracle floor)
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


__all__ = [
    "CommandRunner",
    "OracleLens",
    "OracleVerdict",
    "run_oracle_gate",
    "subprocess_runner",
]
