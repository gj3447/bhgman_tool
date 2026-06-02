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


# ── HARD 셋: 헤드룸 보장 (edge-case 다수 + anti-memorization 트위스트 → 1-shot 부분실패) ──
HARD_PROBLEMS: tuple[CodingProblem, ...] = (
    CodingProblem(
        name="atoi_clamp",
        prompt="Write `atoi_clamp(s: str) -> int`: skip leading spaces, optional +/- sign, read "
        "digits until a non-digit, ignore the rest. Empty/no-digits -> 0. CLAMP result to "
        "[-1000, 1000].",
        entrypoint="atoi_clamp",
        test_source=(
            "from solution import atoi_clamp as f\n"
            "def test_plain(): assert f('42') == 42\n"
            "def test_ws_neg(): assert f('   -42') == -42\n"
            "def test_trail(): assert f('4193 with words') == 1000\n"
            "def test_leadword(): assert f('words and 987') == 0\n"
            "def test_clampneg(): assert f('-91283') == -1000\n"
            "def test_plus(): assert f('+1') == 1\n"
            "def test_empty(): assert f('') == 0\n"
            "def test_dot(): assert f('3.14') == 3\n"
            "def test_zeros(): assert f('  -000123') == -123\n"
            "def test_spacebetween(): assert f('  +0 123') == 0\n"
        ),
    ),
    CodingProblem(
        name="brackets_angle",
        prompt="Write `match_brackets(s: str) -> bool`: True iff brackets ()[]{} AND ANGLE <> are "
        "correctly matched and nested. Non-bracket chars are ignored. Empty -> True.",
        entrypoint="match_brackets",
        test_source=(
            "from solution import match_brackets as f\n"
            "def test_all(): assert f('()[]{}<>') is True\n"
            "def test_nest(): assert f('([{<>}])') is True\n"
            "def test_bad(): assert f('(]') is False\n"
            "def test_angle_bad(): assert f('<(>)') is False\n"
            "def test_empty(): assert f('') is True\n"
            "def test_angle_nest(): assert f('<<>>') is True\n"
            "def test_cross(): assert f('([)]') is False\n"
            "def test_ignore(): assert f('a(b)c<d>') is True\n"
        ),
    ),
    CodingProblem(
        name="rle_decode",
        prompt="Write `rle_decode(s: str) -> str`: inverse run-length. A letter optionally followed "
        "by a (possibly multi-digit) count; missing count means 1. 'a3b2c1'->'aaabbc', "
        "'a12'->12 a's, 'abc'->'abc'. Empty -> ''.",
        entrypoint="rle_decode",
        test_source=(
            "from solution import rle_decode as f\n"
            "def test_basic(): assert f('a3b2c1') == 'aaabbc'\n"
            "def test_multidigit(): assert f('a12') == 'a'*12\n"
            "def test_nocount(): assert f('abc') == 'abc'\n"
            "def test_empty(): assert f('') == ''\n"
            "def test_one(): assert f('x5') == 'xxxxx'\n"
            "def test_mix(): assert f('a2b') == 'aab'\n"
        ),
    ),
    CodingProblem(
        name="compare_version",
        prompt="Write `compare_version(v1: str, v2: str) -> int`: split on '.', compare each part "
        "NUMERICALLY (so '01'=='1'), missing parts count as 0. Return -1/0/1.",
        entrypoint="compare_version",
        test_source=(
            "from solution import compare_version as f\n"
            "def test_leadzero(): assert f('1.01','1.001') == 0\n"
            "def test_trail(): assert f('1.0','1.0.0') == 0\n"
            "def test_lt(): assert f('0.1','1.1') == -1\n"
            "def test_gt(): assert f('1.0.1','1') == 1\n"
            "def test_deep(): assert f('7.5.2.4','7.5.3') == -1\n"
            "def test_numeric(): assert f('1.2','1.10') == -1\n"
        ),
    ),
    CodingProblem(
        name="simplify_path",
        prompt="Write `simplify_path(p: str) -> str`: simplify a Unix absolute path. Collapse '.', "
        "'..' (parent, no-op at root), and multiple '/'. Result has no trailing '/' (except root '/').",
        entrypoint="simplify_path",
        test_source=(
            "from solution import simplify_path as f\n"
            "def test_basic(): assert f('/a/./b/../../c/') == '/c'\n"
            "def test_root_up(): assert f('/../') == '/'\n"
            "def test_doubleslash(): assert f('/home//foo/') == '/home/foo'\n"
            "def test_complex(): assert f('/a/../../b/../c//.//') == '/c'\n"
            "def test_root(): assert f('/') == '/'\n"
            "def test_dotdir(): assert f('/.../a') == '/.../a'\n"
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

    hard = os.environ.get("BHGMAN_AB_PROBLEMS", "easy") == "hard"
    problems = HARD_PROBLEMS if hard else PROBLEMS
    budget = int(os.environ.get("BHGMAN_AB_BUDGET", "8" if hard else "6"))
    trials = int(os.environ.get("BHGMAN_AB_TRIALS", "1"))  # LLM stochastic — 시도 평균
    fly_sessions = 2
    fly_budget = budget // fly_sessions

    results: list[CodingABResult] = []
    root = Path(tempfile.mkdtemp(prefix="coding_ab_"))
    for prob in problems:
        task = f"PROBLEM ({prob.name}): {prob.prompt}"
        bon_scores, fly_scores, read_backs = [], [], []
        for t in range(trials):
            oracle = CodingOracle(prob, root / f"{prob.name}_t{t}")
            bon = run_evolve(
                task,
                budget,
                mk(),
                oracle,
                InMemoryCorpus(),
                rng=random.Random(1 + t),
                feedback=False,
            )
            fly = run_sessions(
                task,
                fly_budget,
                fly_sessions,
                mk(),
                oracle,
                InMemoryCorpus(),
                base_seed=40 + t * 10,
                feedback=True,
            )
            bon_scores.append(bon.best_score)
            fly_scores.append(fly[-1].best_score)
            read_backs.append(fly[-1].read_back)
        bb = sum(bon_scores) / len(bon_scores)
        fb = sum(fly_scores) / len(fly_scores)
        results.append(
            CodingABResult(
                problem=prob.name,
                bon_best=bb,
                flywheel_best=fb,
                bon_solved=bb >= 1.0,
                flywheel_solved=fb >= 1.0,
                read_back=max(read_backs),
            )
        )
    label = "HARD" if hard else "easy"
    print(
        f"=== Coding flywheel A/B [{label}] (model={model}, {budget} calls/arm, {trials} trial) ==="
    )
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
