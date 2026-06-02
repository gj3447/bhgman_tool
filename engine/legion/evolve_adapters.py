"""evolve_loop 실 컴포넌트 어댑터 — toy seam을 진짜 oracle / 생성기 / 학습 환류로.

evolve_loop.py가 정의한 3 seam(Generator/ScalarOracle/CandidateCorpus)에 *실전* 구현을 꽂는다:

  · 실 oracle scalar 파서  — pytest pass-ratio / Lean cleanliness (OracleVerdict.detail 파싱, 순수).
    + factory(pytest_oracle/lean_oracle): build_command으로 후보를 실제 `pytest`/`lake build` 실행.
  · LlmGenerator           — AgentClient(dual-backend) 래퍼. best-K read-back을 프롬프트에 주입해
    다음 후보 제안. 백엔드 없으면 graceful(주입 transport로 테스트 green).
  · export_training_set    — 검증 통과 corpus → (task, verified-solution, score) JSONL.
    inference-time→learning-time 다리 (천장 돌파: 이 검증셋으로 fine-tune/RL).

순수 파서/export는 결정론·무IO. LlmGenerator/factory는 주입식(테스트=fake runner/transport).

# KG: prom16-bhgman-ci-design-2026-06-02, lesson-bhgman-collective-intelligence-design-2026-06-02,
#     naesengmoon-generate-verify-asymmetry-2026-06-01, bhgman-llm-commander-runtime-2026-05-28
"""

from __future__ import annotations

import json
import random
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from engine.agents.agent_models import HAIKU
from engine.agents.client import AgentClient
from engine.legion.evolve_loop import (
    Candidate,
    LensScalarOracle,
    ScoredCandidate,
    candidate_id,
)
from engine.naesengmoon.oracle_lens import CommandRunner, OracleLens, OracleVerdict

# ── 실 oracle scalar 파서 (OracleVerdict.detail → fitness) ────────────────────
_PYTEST_PASS = re.compile(r"(\d+)\s+passed")
_PYTEST_FAIL = re.compile(r"(\d+)\s+(?:failed|error[s]?)")
_LEAN_ERR = re.compile(r"\berror:", re.IGNORECASE)
_LEAN_SORRY = re.compile(r"\bsorry\b|declaration uses 'sorry'", re.IGNORECASE)


def pytest_pass_ratio(verdict: OracleVerdict) -> float:
    """pytest 출력 → passed/(passed+failed). 카운트 못 찾으면 PASS=1.0/FAIL=0.0 fallback."""
    passed = sum(int(m) for m in _PYTEST_PASS.findall(verdict.detail))
    failed = sum(int(m) for m in _PYTEST_FAIL.findall(verdict.detail))
    total = passed + failed
    if total == 0:
        return 1.0 if verdict.passed else 0.0
    return passed / total


def lean_cleanliness(verdict: OracleVerdict) -> float:
    """Lean 출력 → 1/(1+errors+sorry). 0 error/sorry = 1.0(clean), 많을수록 0에 수렴."""
    if verdict.passed and not _LEAN_SORRY.search(verdict.detail):
        return 1.0
    n_err = len(_LEAN_ERR.findall(verdict.detail))
    n_sorry = len(_LEAN_SORRY.findall(verdict.detail))
    return 1.0 / (1.0 + n_err + n_sorry)


def pytest_oracle(
    test_path_for: Callable[[str, Candidate], str],  # (task,cand) → 테스트 경로
    runner: CommandRunner | None = None,
) -> LensScalarOracle:
    """후보를 임시 파일로 물질화했다고 가정, `pytest -q <path>` 실행 → pass-ratio scalar."""
    base = OracleLens(name="pytest", kind="test", command=("pytest", "-q"))

    def build(task: str, cand: Candidate) -> tuple[str, ...]:
        return ("pytest", "-q", test_path_for(task, cand))

    kwargs = {"runner": runner} if runner is not None else {}
    return LensScalarOracle(lens=base, to_scalar=pytest_pass_ratio, build_command=build, **kwargs)


def lean_oracle(
    lean_file_for: Callable[[str, Candidate], str],  # (task,cand) → Lean 모듈
    runner: CommandRunner | None = None,
) -> LensScalarOracle:
    """`lake build <module>` 실행 → cleanliness scalar (sorry=0/error=0 → 1.0)."""
    base = OracleLens(name="lean", kind="compiler", command=("lake", "build"))

    def build(task: str, cand: Candidate) -> tuple[str, ...]:
        return ("lake", "build", lean_file_for(task, cand))

    kwargs = {"runner": runner} if runner is not None else {}
    return LensScalarOracle(lens=base, to_scalar=lean_cleanliness, build_command=build, **kwargs)


# ── 실 생성기 (LLM, best-K read-back 주입) ─────────────────────────────────────
_DEFAULT_SYSTEM = (
    "You are a candidate generator in a verification-grounded improvement loop. "
    "You are shown the best verified solutions found so far. Produce ONE improved candidate. "
    "Output only the candidate artifact, no prose."
)


def default_llm_render(task: str, best: Sequence[ScoredCandidate]) -> str:
    """best-K 검증 해답을 프롬프트에 주입 = stigmergy read-back (없으면 cold start)."""
    if not best:
        return f"TASK:\n{task}\n\nNo prior verified solutions. Produce a first candidate."
    prior = "\n".join(f"  [score={sc.score:.3f}] {sc.candidate.payload}" for sc in best)
    return (
        f"TASK:\n{task}\n\nBEST VERIFIED SO FAR (improve on these):\n{prior}\n\n"
        "Produce ONE improved candidate."
    )


@dataclass
class LlmGenerator:
    """AgentClient 래퍼 Generator. 백엔드(local vLLM/Ollama 또는 anthropic) 주입식.

    누적 토큰을 self.output_tokens에 기록(equal-token A/B 회계용). render로 best-K 주입
    (default_llm_render = 일반, coding_render 등 task별 교체 가능).
    """

    client: AgentClient
    model: str = HAIKU
    system: str = _DEFAULT_SYSTEM
    max_tokens: int = 512
    output_tokens: int = 0
    render: Callable[[str, Sequence[ScoredCandidate]], str] = default_llm_render

    def propose(self, task: str, best: Sequence[ScoredCandidate], rng: random.Random) -> Candidate:
        user = self.render(task, best)
        completion = self.client.complete(
            system=self.system, user=user, model=self.model, max_tokens=self.max_tokens
        )
        self.output_tokens += completion.output_tokens
        parent = candidate_id(task, best[0].candidate.payload) if best else None
        generation = (best[0].candidate.generation + 1) if best else 0
        return Candidate(payload=completion.text.strip(), parent=parent, generation=generation)


# ── corpus → 학습셋 환류 (천장 돌파 다리) ──────────────────────────────────────
def export_training_set(
    pairs: Sequence[ScoredCandidate], task: str, min_score: float = 0.0
) -> list[dict]:
    """검증 통과 후보 → (task, verified-solution, score) 레코드. fine-tune/RL 학습셋.

    오직 passed(검증)된 것만, min_score 이상만. 이게 inference-time→learning-time 다리:
    누적 검증 corpus가 모델 자체를 향상시키는 학습 데이터가 된다.
    """
    out: list[dict] = []
    for sc in pairs:
        if sc.passed and sc.score >= min_score:
            out.append(
                {
                    "task": task,
                    "solution": sc.candidate.payload,
                    "score": sc.score,
                    "candidate_id": candidate_id(task, sc.candidate.payload),
                    "generation": sc.candidate.generation,
                }
            )
    return out


def write_training_jsonl(records: Sequence[dict], path: str | Path) -> int:
    """학습셋 레코드를 JSONL로 기록. 반환=쓴 줄 수."""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    p.write_text("\n".join(lines) + ("\n" if lines else ""))
    return len(lines)


__all__ = [
    "LlmGenerator",
    "default_llm_render",
    "export_training_set",
    "lean_cleanliness",
    "lean_oracle",
    "pytest_oracle",
    "pytest_pass_ratio",
    "write_training_jsonl",
]
