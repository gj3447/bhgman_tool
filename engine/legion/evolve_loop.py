"""evolve_loop — verification-grounded composition의 production 닫힌 루프 (검증 지식 플라이휠).

PROM 3종(ma-intel/eci-existence/bhgman-ci-design) + evolve_loop_*_experiment 측정 결론의
production 배선: **전체 시스템이 단일 에이전트를 이기려면 = 검증된 지식이 복리로 불어나는 닫힌
루프.** (fan-out 더 키우기가 아니라.)

    generate(생성기) → score(결정론 oracle, 새 정보 주입) → record(oracle-gated, 검증분만 누적)
    → read_best(다음 라운드/세션이 누적 위에서 시작) → 반복.

세 seam(Protocol)으로 실 컴포넌트 교체 가능 (DIP):
  · Generator       — eureka / LLM / toy. best-K read-back을 받아 다음 후보 제안.
  · ScalarOracle    — 나생문 OracleLens(Lean/pytest/cypher) → scalar fitness 어댑터. *DPI 탈출구*
                      (모델이 안 가진 ground-truth 정보를 매 평가마다 주입).
  · CandidateCorpus — 검증 통과분만 영속. InMemory(테스트) / LocalKg(cross-session 복리 기억).

플라이휠 win 조건(단일 에이전트 대비): 세션 N은 예산 B + 세션 1..N-1의 누적 검증 corpus를
가진다. corpus 없는 같은-예산 단일 에이전트보다, 세션이 쌓일수록 best가 단조 상승 = *영속 우위*.
(experiment가 단일 세션 내 loop>BoN을 증명 → 여기선 세션 가로지르는 복리를 배선.)

순수 코어 + 주입식 seam. equal-eval 예산 정확 회계(score 1회 = 1 eval). neo4j 불요(LocalKg JSON).

# KG: prom16-bhgman-ci-design-2026-06-02, lesson-bhgman-collective-intelligence-design-2026-06-02,
#     adr-seven-commander-legion-architecture-2026-05-27 (§4 닫힌 루프),
#     naesengmoon-generate-verify-asymmetry-2026-06-01 (oracle floor = 검증이 생성보다 쌈),
#     efficacy-longinus-2026-06-01 (실험 양식)
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol, runtime_checkable

from engine.kg_local.store import LocalKgStore
from engine.naesengmoon.oracle_lens import (
    CommandRunner,
    OracleLens,
    OracleVerdict,
    subprocess_runner,
)


# ── value objects ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Candidate:
    """생성기가 제안한 후보 artifact (코드/증명/플랜/genome-as-str ...)."""

    payload: str
    parent: str | None = None  # 부모 candidateId (플라이휠 계보)
    generation: int = 0


@dataclass(frozen=True)
class ScoredCandidate:
    """oracle 채점 결과. passed=True(검증 통과)만 corpus에 누적된다(oracle-gated)."""

    candidate: Candidate
    score: float
    passed: bool
    detail: str = ""


def candidate_id(task: str, payload: str) -> str:
    """결정론 후보 id — 멱등 누적(같은 (task,payload) = 같은 노드)."""
    return "cand-" + hashlib.sha256(f"{task}::{payload}".encode()).hexdigest()[:16]


# ── seams (DIP) ──────────────────────────────────────────────────────────────
@runtime_checkable
class Generator(Protocol):
    """후보 생성기. best=누적 검증 best-K read-back(stigmergy). 빈 best=cold start."""

    def propose(
        self, task: str, best: Sequence[ScoredCandidate], rng: random.Random
    ) -> Candidate: ...


@runtime_checkable
class ScalarOracle(Protocol):
    """결정론 scalar 검증기. passed=hard gate(검증), score=fitness(steering 신호)."""

    def score(self, task: str, candidate: Candidate) -> ScoredCandidate: ...


@runtime_checkable
class CandidateCorpus(Protocol):
    """검증 지식 기억. record는 passed만 받음(oracle-gated). read_best=복리 read-back."""

    def read_best(self, task: str, k: int) -> tuple[ScoredCandidate, ...]: ...

    def record(self, task: str, scored: ScoredCandidate) -> None: ...


# ── oracle 어댑터 (step 1: boolean OracleLens → scalar) ───────────────────────
def passed_scalar(verdict: OracleVerdict) -> float:
    """기본 scalar: PASS=1.0 / FAIL=0.0. (Lean=goal수, pytest=pass-ratio 등은 주입 교체.)"""
    return 1.0 if verdict.passed else 0.0


@dataclass(frozen=True)
class LensScalarOracle:
    """나생문 OracleLens(boolean) → ScalarOracle 어댑터. *production step-1*.

    to_scalar: OracleVerdict → float (Lean 닫은 goal 수 / pytest pass-ratio / -drift-distance).
    build_command: (task,candidate) → argv. None이면 lens.command 고정 사용.
    """

    lens: OracleLens
    to_scalar: Callable[[OracleVerdict], float] = passed_scalar
    build_command: Callable[[str, Candidate], tuple[str, ...]] | None = None
    runner: CommandRunner = subprocess_runner

    def score(self, task: str, candidate: Candidate) -> ScoredCandidate:
        lens = self.lens
        if self.build_command is not None:
            lens = replace(self.lens, command=self.build_command(task, candidate))
        verdict = lens.verify(self.runner)
        return ScoredCandidate(
            candidate=candidate,
            score=self.to_scalar(verdict),
            passed=verdict.passed,
            detail=verdict.detail,
        )


@dataclass(frozen=True)
class FnScalarOracle:
    """함수형 scalar oracle (테스트/결정론 task용). passed = score >= pass_min."""

    score_fn: Callable[[str, Candidate], float]
    pass_min: float = 0.0

    def score(self, task: str, candidate: Candidate) -> ScoredCandidate:
        s = self.score_fn(task, candidate)
        return ScoredCandidate(candidate=candidate, score=s, passed=s >= self.pass_min)


# ── corpus 구현 (step 3) ──────────────────────────────────────────────────────
def _top_k(scored: Sequence[ScoredCandidate], k: int) -> tuple[ScoredCandidate, ...]:
    return tuple(sorted(scored, key=lambda sc: sc.score, reverse=True)[:k])


class InMemoryCorpus:
    """세션 내/테스트용 corpus. passed만 누적, read_best=top-k. 영속 없음."""

    def __init__(self) -> None:
        self._by_task: dict[str, list[ScoredCandidate]] = {}

    def read_best(self, task: str, k: int) -> tuple[ScoredCandidate, ...]:
        return _top_k(self._by_task.get(task, []), k)

    def record(self, task: str, scored: ScoredCandidate) -> None:
        if scored.passed:  # oracle-gated: 검증 통과분만 (쓰레기 누적 차단)
            self._by_task.setdefault(task, []).append(scored)


class LocalKgCorpus:
    """LocalKgStore(JSON) 영속 corpus = cross-session 복리 기억. neo4j 불요.

    record(passed): :EvolveCandidate MERGE(candidateId) + save. read_best: task 필터 top-k.
    새 LocalKgStore(path) 재로드 시 이전 세션 검증분이 그대로 read_back = 플라이휠의 핵심.
    """

    LABEL = "EvolveCandidate"

    def __init__(self, store: LocalKgStore) -> None:
        self.store = store

    def read_best(self, task: str, k: int) -> tuple[ScoredCandidate, ...]:
        nodes = self.store.find_nodes(self.LABEL, where=lambda p: p.get("task") == task)
        scored = [self._node_to_scored(n["props"]) for n in nodes]
        return _top_k(scored, k)

    def record(self, task: str, scored: ScoredCandidate) -> None:
        if not scored.passed:
            return
        cid = candidate_id(task, scored.candidate.payload)
        self.store.merge_node(
            self.LABEL,
            "candidateId",
            cid,
            {
                "task": task,
                "payload": scored.candidate.payload,
                "score": scored.score,
                "passed": True,
                "generation": scored.candidate.generation,
                "parent": scored.candidate.parent or "",
            },
        )
        self.store.save()

    @staticmethod
    def _node_to_scored(props: dict) -> ScoredCandidate:
        cand = Candidate(
            payload=props["payload"],
            parent=props.get("parent") or None,
            generation=int(props.get("generation", 0)),
        )
        return ScoredCandidate(cand, float(props["score"]), True, "")


# ── 닫힌 루프 orchestrator (step 2) ───────────────────────────────────────────
@dataclass(frozen=True)
class EvolveRun:
    """플라이휠 1세션 결과. read_back>0 = cross-session 복리 작동 증거."""

    task: str
    best: ScoredCandidate | None
    evals: int  # oracle 평가 횟수 (= equal-compute 회계 단위)
    recorded: int  # 본 세션 검증 통과해 corpus에 누적된 수
    read_back: int  # 시작 시 corpus에서 읽어온 best-K 수 (이전 세션 자산)
    trace: tuple[float, ...] = field(default_factory=tuple)  # 라운드별 best-so-far

    @property
    def best_score(self) -> float:
        return self.best.score if self.best is not None else float("-inf")

    @property
    def summary(self) -> str:
        return (
            f"[{self.task}] best={self.best_score:.3f} evals={self.evals} "
            f"recorded={self.recorded} read_back={self.read_back}"
        )


def run_evolve(
    task: str,
    budget: int,
    generator: Generator,
    oracle: ScalarOracle,
    corpus: CandidateCorpus,
    rng: random.Random,
    k: int = 4,
    feedback: bool = True,
    solve_threshold: float | None = None,
    explore_prob: float = 0.0,
) -> EvolveRun:
    """검증 지식 플라이휠 1세션. 최대 budget oracle-eval (equal-compute).

    feedback=True: 누적 best-K(이번 세션 + 이전 세션)에서 steer. False: blind(ablation, BoN).
    solve_threshold: best.score가 이 값 이상이면 즉시 중단(oracle-solve early-exit) — 포화 task서
      낭비 compute + best-K anchoring harm 제거 (rle_decode Δ-0.33 측정 결함 fix). None=무중단.
    explore_prob: 각 시도가 이 확률로 feedback 무시 blind 제안(ε-exploration) — best-K만 먹여
      부분해에 갇히는 mode-lock 방지(blind 탐색 유지). 0.0=순수 feedback(기존). >0만 rng 소비.
    """
    seeded = list(corpus.read_best(task, k))  # cross-session 자산 (이전 세션 검증분)
    accumulated: list[ScoredCandidate] = list(seeded)
    best: ScoredCandidate | None = seeded[0] if seeded else None
    trace: list[float] = []
    recorded = 0
    used = 0
    for _ in range(budget):
        explore = explore_prob > 0.0 and rng.random() < explore_prob
        context = _top_k(accumulated, k) if (feedback and not explore) else ()
        cand = generator.propose(task, context, rng)
        scored = oracle.score(task, cand)
        used += 1
        if scored.passed:
            corpus.record(task, scored)  # oracle-gated 영속 누적
            accumulated.append(scored)
            recorded += 1
        if best is None or scored.score > best.score:
            best = scored
        trace.append(best.score if best is not None else float("-inf"))
        if solve_threshold is not None and best is not None and best.score >= solve_threshold:
            break  # oracle-solve early-exit
    return EvolveRun(
        task=task,
        best=best,
        evals=used,
        recorded=recorded,
        read_back=len(seeded),
        trace=tuple(trace),
    )


def run_sessions(
    task: str,
    budget: int,
    n_sessions: int,
    generator: Generator,
    oracle: ScalarOracle,
    corpus: CandidateCorpus,
    base_seed: int = 0,
    k: int = 4,
    feedback: bool = True,
) -> tuple[EvolveRun, ...]:
    """같은 corpus를 가로질러 n_sessions 회 실행 = 플라이휠. best 단조 상승해야(복리)."""
    runs: list[EvolveRun] = []
    for s in range(n_sessions):
        runs.append(
            run_evolve(
                task,
                budget,
                generator,
                oracle,
                corpus,
                rng=random.Random(base_seed + s + 1),
                k=k,
                feedback=feedback,
            )
        )
    return tuple(runs)


__all__ = [
    "Candidate",
    "CandidateCorpus",
    "EvolveRun",
    "FnScalarOracle",
    "Generator",
    "InMemoryCorpus",
    "LensScalarOracle",
    "LocalKgCorpus",
    "ScalarOracle",
    "ScoredCandidate",
    "candidate_id",
    "passed_scalar",
    "run_evolve",
    "run_sessions",
]
