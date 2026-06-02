"""코딩 task 플라이휠 효능 A/B — 실 LLM 생성 + 실 pytest oracle (AlphaCodium 구조).

헤드룸 있는 task의 진짜 효능 측정: LLM이 함수를 생성 → 실 pytest가 hidden 테스트로 검증
(pass-ratio = graded fitness, 비-gameable 외부 verifier) → 부분통과분이 corpus를 seed →
LLM이 best-K(이전 시도 코드+점수)를 보고 실패 케이스를 고침 → 반복.

A/B (동일 #호출):
  · BON      — feedback off (best-K 없이 매번 cold 1-shot). "예산 N 받은 단일 에이전트".
  · FLYWHEEL — feedback on + corpus 영속 (이전 검증 시도를 보고 개선). 본 시스템.

왜 헤드룸 task인가: vowel-toy는 강모델이 1-shot에 천장 → 분리 불가였다. 코딩은 1-shot이
edge case(subtractive roman, 중첩 괄호)에서 자주 실패 → best-K 피드백이 개선할 여지 = lift 측정 가능.

oracle = 실 `pytest -q` subprocess(timeout 보호, 무한루프 차단). score=pass-ratio, passed=ratio≥seed_floor
(부분 진전도 seed해 steering 가능; solved = ratio==1.0). pure 파싱/materialize는 단위테스트,
LLM 런은 main()(백엔드 필요).

# KG: prom16-bhgman-ci-design-2026-06-02, lesson-bhgman-collective-intelligence-design-2026-06-02,
#     naesengmoon-generate-verify-asymmetry-2026-06-01 (oracle=검증이 생성보다 쌈)
"""

from __future__ import annotations

import random
import re
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from engine.legion.evolve_adapters import pytest_pass_ratio
from engine.legion.evolve_loop import Candidate, ScoredCandidate
from engine.naesengmoon.oracle_lens import CommandRunner, OracleVerdict

_FENCE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class CodingProblem:
    name: str
    prompt: str  # 자연어 spec
    entrypoint: str  # solution.py가 정의해야 할 함수명
    test_source: str  # pytest 파일 (from solution import <entrypoint>)


def extract_code(payload: str) -> str:
    """LLM 출력에서 코드 추출 — markdown fence 있으면 그 안, 없으면 전체."""
    m = _FENCE.search(payload)
    return (m.group(1) if m else payload).strip()


def pytest_workdir_runner(workdir: Path, timeout: float = 8.0) -> CommandRunner:
    """workdir에서 pytest 실행하는 runner (cwd 고정 + timeout = 무한루프/안전 차단)."""

    def run(cmd: Sequence[str]) -> tuple[int, str]:
        try:
            p = subprocess.run(  # noqa: S603 — 신뢰된 pytest, 격리 workdir, timeout
                list(cmd),
                capture_output=True,
                text=True,
                cwd=str(workdir),
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return 124, "timeout (무한루프 의심) — 0 passed"
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    return run


def materialize_and_test(
    payload: str, problem: CodingProblem, workdir: Path, runner: CommandRunner
) -> float:
    """후보 코드를 solution.py로 물질화 + test 실행 → pass-ratio. 구문오류=0 (pytest collect error)."""
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "solution.py").write_text(extract_code(payload))
    (workdir / "test_sol.py").write_text(problem.test_source)
    code, out = runner(("pytest", "-q", "test_sol.py"))
    verdict = OracleVerdict(lens="pytest", kind="test", passed=(code == 0), detail=out)
    return pytest_pass_ratio(verdict)


@dataclass
class CodingOracle:
    """ScalarOracle: 실 pytest pass-ratio. passed=ratio≥seed_floor(부분 진전도 seed → steering)."""

    problem: CodingProblem
    workdir: Path
    seed_floor: float = 0.01
    runner: CommandRunner | None = None

    def score(self, task: str, candidate: Candidate) -> ScoredCandidate:
        runner = self.runner or pytest_workdir_runner(self.workdir)
        ratio = materialize_and_test(candidate.payload, self.problem, self.workdir, runner)
        return ScoredCandidate(
            candidate, ratio, ratio >= self.seed_floor, f"pass_ratio={ratio:.2f}"
        )


CODING_SYSTEM = (
    "You are a Python coding agent in a verify-and-improve loop. Output ONLY a complete, "
    "self-contained Python function (no prose, no tests, no examples). If prior attempts are "
    "shown with their test pass-ratios, FIX the failing cases — do not repeat the same code."
)


def coding_render(task: str, best: Sequence[ScoredCandidate]) -> str:
    """코딩 프롬프트 + best-K(이전 시도 코드 + pass-ratio) 주입 = 실패 케이스 steering."""
    if not best:
        return f"{task}\n\nNo prior attempts. Write the function."
    prior = "\n\n".join(
        f"# prior attempt (pass_ratio={sc.score:.2f}):\n{sc.candidate.payload}" for sc in best
    )
    return f"{task}\n\nPRIOR VERIFIED ATTEMPTS (improve, fix failures):\n{prior}\n\nWrite an improved function."


# ── headroom 문제 셋 (1-shot 자주 실패 + seedable) ────────────────────────────
PROBLEMS: tuple[CodingProblem, ...] = (
    CodingProblem(
        name="roman_to_int",
        prompt="Write `roman_to_int(s: str) -> int` converting a Roman numeral to an integer "
        "(handle subtractive forms IV, IX, XL, XC, CD, CM).",
        entrypoint="roman_to_int",
        test_source=(
            "from solution import roman_to_int\n"
            "def test_basic():\n    assert roman_to_int('III') == 3\n"
            "def test_sub():\n    assert roman_to_int('IV') == 4\n    assert roman_to_int('IX') == 9\n"
            "def test_mid():\n    assert roman_to_int('LVIII') == 58\n"
            "def test_big():\n    assert roman_to_int('MCMXCIV') == 1994\n"
        ),
    ),
    CodingProblem(
        name="valid_parens",
        prompt="Write `valid_parens(s: str) -> bool` returning True iff brackets ()[]{} are "
        "correctly matched and nested.",
        entrypoint="valid_parens",
        test_source=(
            "from solution import valid_parens\n"
            "def test_ok():\n    assert valid_parens('()[]{}') is True\n"
            "def test_nest():\n    assert valid_parens('([{}])') is True\n"
            "def test_bad():\n    assert valid_parens('(]') is False\n"
            "def test_open():\n    assert valid_parens('([)]') is False\n"
            "def test_empty():\n    assert valid_parens('') is True\n"
        ),
    ),
    CodingProblem(
        name="rle",
        prompt="Write `rle(s: str) -> str` run-length encoding: 'aaabbc' -> 'a3b2c1'. "
        "Single chars still get count 1.",
        entrypoint="rle",
        test_source=(
            "from solution import rle\n"
            "def test_basic():\n    assert rle('aaabbc') == 'a3b2c1'\n"
            "def test_single():\n    assert rle('abc') == 'a1b1c1'\n"
            "def test_empty():\n    assert rle('') == ''\n"
            "def test_long():\n    assert rle('aaaa') == 'a4'\n"
        ),
    ),
)


@dataclass(frozen=True)
class CodingABResult:
    problem: str
    bon_best: float
    flywheel_best: float
    bon_solved: bool  # ratio==1.0 (전부 통과)
    flywheel_solved: bool
    read_back: int

    @property
    def delta(self) -> float:
        return self.flywheel_best - self.bon_best


def main() -> int:  # pragma: no cover — 실 LLM 런 (백엔드 필요)
    import os

    from engine.agents.client import AgentClient, AgentRuntimeUnavailable
    from engine.legion.evolve_adapters import LlmGenerator
    from engine.legion.evolve_loop import InMemoryCorpus, run_evolve, run_sessions

    model = os.environ.get("BHGMAN_LLM_MODEL", "qwen2.5:7b-instruct")
    try:
        AgentClient()
    except AgentRuntimeUnavailable as e:
        print(f"백엔드 없음: {e}")
        return 1

    def mk() -> LlmGenerator:
        return LlmGenerator(
            client=AgentClient(),
            model=model,
            system=CODING_SYSTEM,
            max_tokens=400,
            render=coding_render,
        )

    results: list[CodingABResult] = []
    root = Path(tempfile.mkdtemp(prefix="coding_ab_"))
    for prob in PROBLEMS:
        task = f"PROBLEM ({prob.name}): {prob.prompt}"
        oracle = CodingOracle(prob, root / prob.name)
        bon = run_evolve(
            task, 6, mk(), oracle, InMemoryCorpus(), rng=random.Random(1), feedback=False
        )
        fly = run_sessions(task, 3, 2, mk(), oracle, InMemoryCorpus(), base_seed=40, feedback=True)
        last = fly[-1]
        results.append(
            CodingABResult(
                problem=prob.name,
                bon_best=bon.best_score,
                flywheel_best=last.best_score,
                bon_solved=bon.best_score >= 1.0,
                flywheel_solved=last.best_score >= 1.0,
                read_back=last.read_back,
            )
        )
    print(f"=== Coding flywheel A/B (model={model}, equal 6 calls/arm) ===")
    for r in results:
        print(
            f"  [{r.problem:14}] BON={r.bon_best:.2f}{'✓' if r.bon_solved else ' '} "
            f"FLYWHEEL={r.flywheel_best:.2f}{'✓' if r.flywheel_solved else ' '} "
            f"Δ={r.delta:+.2f} (read_back={r.read_back})"
        )
    solved_bon = sum(r.bon_solved for r in results)
    solved_fly = sum(r.flywheel_solved for r in results)
    mean_delta = sum(r.delta for r in results) / len(results)
    print(
        f"  TOTAL solved: BON={solved_bon}/{len(results)} FLYWHEEL={solved_fly}/{len(results)} "
        f"mean Δ={mean_delta:+.3f}"
    )
    return 0


__all__ = [
    "PROBLEMS",
    "CodingABResult",
    "CodingOracle",
    "CodingProblem",
    "coding_render",
    "extract_code",
    "materialize_and_test",
    "pytest_workdir_runner",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
