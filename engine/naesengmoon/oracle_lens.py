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
from typing import Any

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


# ── 연속 fitness oracle (FunSearch loop용 scalar 확장) ──────────────────────
# binary OracleLens(PASS/FAIL)의 scalar 확장. evolve_loop가 maximize할 *외부 결정론*
# metric. 점수원이 외부 도구 실행(LLM 판정 아님)이어야 equal-compute에서 DPI 상한을
# 뚫는 외부 정보원이 된다 (prom16-bhgman-ci-design-2026-06-02 §0/§3). 관례: 높을수록
# 좋음 — minimize 지표(drift·complexity)는 음수화하여 등록.
# 자격 task 4류 metric: lean-goals(닫은 goal 수) / pytest-ratio(통과율) /
# drift-recount(drift→0, 음수화) / occam-twins(무손실 제거 수).

# candidate -> fitness (높을수록 좋음). candidate 타입은 task마다 다름(코드 str / KG diff / proof).
ScoreFn = Callable[[Any], float]


@dataclass(frozen=True)
class OracleScore:
    """연속 fitness 결과. value 높을수록 좋음 (minimize 지표는 음수화하여 등록)."""

    lens: str
    kind: str
    value: float


@dataclass(frozen=True)
class ScalarOracle:
    """연속 fitness oracle. binary OracleLens 의 scalar 확장.

    FunSearch/AlphaEvolve 가 maximize 할 외부 결정론 metric. 점수원이 *외부 도구 실행*
    이어야 (LLM-judges-LLM 아님) DPI 를 뚫는다 — 그렇지 않으면 evolve_loop 가
    equal-compute ~0 의 자기참조 함정으로 붕괴한다.
    """

    name: str
    kind: str  # lean-goals | pytest-ratio | drift-recount | occam-twins
    score: ScoreFn

    def evaluate(self, candidate: Any) -> OracleScore:
        return OracleScore(self.name, self.kind, float(self.score(candidate)))


def scalar_from_lens(lens: OracleLens, runner: CommandRunner = subprocess_runner) -> ScalarOracle:
    """binary 컴파일러나생문 → {0.0, 1.0} fitness 어댑터 (gate→scalar).

    candidate 는 무시(렌즈의 command 가 고정)하므로 gate-as-fitness 용도. 연속 gradient
    가 필요한 task(pytest 통과율 등)는 전용 ScoreFn 으로 ScalarOracle 을 직접 구성.
    """

    def _score(_candidate: Any) -> float:
        return 1.0 if lens.verify(runner).passed else 0.0

    return ScalarOracle(name=lens.name, kind=lens.kind, score=_score)


__all__ = [
    "CommandRunner",
    "OracleLens",
    "OracleScore",
    "OracleVerdict",
    "ScalarOracle",
    "ScoreFn",
    "run_oracle_gate",
    "scalar_from_lens",
    "subprocess_runner",
]
