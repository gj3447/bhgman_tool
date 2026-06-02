"""유레카 evolve loop — 검증 접지 합성(Verification-Grounded Composition).

bhgman 이 equal-compute 에서 *비영(非零)* 인지 우위를 내는 유일하게 입증가능한 길
(prom16-bhgman-ci-design-2026-06-02 §0): 결정론 외부 oracle 을 fitness 로 둔
FunSearch/AlphaEvolve 루프. legion.run 은 1-pass 라 feedback 을 못 받는다 — 이 모듈이
generate → oracle.score → program-database 누적 → best-K read-back 의 닫힌 fixpoint 다.

왜 이게 A/B 의 equal-compute ~0 을 뚫나: 기존 ~0 은 loop 가 LLM 이 LLM 을 판정(DPI 상
새 bit 0)했기 때문. 외부 결정론 oracle(Lean sorry=0 / pytest / cypher-recount /
occam disk-hash)은 매 iteration ground-truth bit 를 주입하고, program-database 누적이
그걸 단조증가 탐색 prior(stigmergy)로 바꾼다. 단 이 win 조차 "oracle 로 채널링된 탐색
compute" 이지 마법적 집단 IQ 가 아니다 — 그렇게 정직히 라벨한다 (설계 §6).

자격 task 4류 (값싼 건전 verifier 보유): Lean 증명탐색 / 테스트동반 refactor /
KG drift 수복 / occam supersession. verifier 없는 task(서사·canon·주관)는 시도 금지 —
loop 가 LLM-judges-LLM 으로 붕괴한다 (§6).

DI 규율: generate/oracle 모두 주입. 결정론 generate + 결정론 oracle 이면 전체가 결정론
= LLM 없이 단위 테스트 가능 (legion.run 의 DI 패턴 동일). 프로덕션은 LLM generator +
외부 ScalarOracle 주입. read-back(best-K)이 unguided best-of-N 과의 유일한 차이 —
`best_of_n` 이 그 control arm (engine/efficacy 4th gate, ARM1).

⚠ 정직 경계 (critic verdict 2026-06-02): 동봉 단위테스트는 *합성 landscape* 위 존재증명
(read-back primitive 가 구조적으로 동작함 + 기만적 landscape 에선 질 수도 있음을 보임)
이지, 4개 실제 oracle task 에서 equal-compute 인지 우위를 보인 것이 *아니다*. 그 주장은
engine/efficacy 4th gate(3-arm equal-TOKEN A/B)가 실제 oracle 에서 ARM2 > ARM1 AND
ARM2 > ARM3 를 통과해야 비로소 성립한다 (VERDICT.md 의 synthetic→real 강등 규율: longinus
Δ+0.227 합성 → Δ+0.050 실데이터). 그 전까지 "equal-compute ~0 을 뚫는다"는 미검증이다.

# KG: prom16-bhgman-ci-design-2026-06-02 (검증접지합성 #1 ROI),
#     lesson-bhgman-collective-intelligence-design-2026-06-02,
#     adr-seven-commander-legion-architecture-2026-05-27 (legion.run 1-pass → loop 승격),
#     eureka-canonical-2026-05-26 (생성=유레카), naesengmoon-wired-ensemble-upgrade-2026-05-27 (oracle=나생문),
#     efficacy-measurement-line-2026-06-01 (정직 측정 = 4th gate)
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from engine.naesengmoon.oracle_lens import ScalarOracle

# generate(parents, generation) -> 자식 payload 들.
#   parents = program-database best-K read-back (stigmergy prior, read-only).
#   generation = 현재 세대 인덱스(>=1). 프로덕션은 LLM, 테스트는 결정론 mutator.
GenerateFn = Callable[[Sequence[Any], int], Sequence[Any]]

_EPS = 1e-12  # float 동률 판정 tolerance (plateau / improved)


@dataclass(frozen=True)
class Candidate:
    """program-database 한 항목. parent = 부모 index(stigmergy lineage)."""

    index: int
    payload: Any
    score: float
    generation: int
    parent: int | None


class ProgramDatabase:
    """점수付 후보 누적 = FunSearch program-database (stigmergy blackboard).

    best-K read-back 으로 다음 세대 생성을 편향(단조증가 탐색 prior). tie 는 먼저 들어온
    후보(작은 index) 우선 → 결정론 보장.
    """

    def __init__(self) -> None:
        self._items: list[Candidate] = []

    def add(self, *, payload: Any, score: float, generation: int, parent: int | None) -> Candidate:
        cand = Candidate(
            index=len(self._items),
            payload=payload,
            score=float(score),
            generation=generation,
            parent=parent,
        )
        self._items.append(cand)
        return cand

    @property
    def size(self) -> int:
        return len(self._items)

    def all(self) -> tuple[Candidate, ...]:
        return tuple(self._items)

    def best_k(self, k: int) -> list[Candidate]:
        """상위 k 후보 (score 내림차순, tie 는 index 오름차순)."""
        if k <= 0:
            return []
        return sorted(self._items, key=lambda c: (-c.score, c.index))[:k]

    def best(self) -> Candidate | None:
        top = self.best_k(1)
        return top[0] if top else None

    def lineage(self, cand: Candidate) -> list[Candidate]:
        """후보 → seed 까지 parent 사슬 (stigmergy provenance, KG :Candidate 결정화용)."""
        chain = [cand]
        while chain[-1].parent is not None:
            chain.append(self._items[chain[-1].parent])
        return list(reversed(chain))


@dataclass(frozen=True)
class EvolveResult:
    """evolve / best_of_n 1회 결과. lift·evaluations 가 4th-gate A/B 비교 단위."""

    best: Candidate | None
    seed_score: float
    generations: int
    evaluations: int
    history: tuple[float, ...]  # 세대별 best-so-far (단조 비감소)
    stop_reason: str  # "converged" | "plateau" | "budget" | "empty"
    database: ProgramDatabase

    @property
    def improved(self) -> bool:
        return self.best is not None and self.best.score > self.seed_score + _EPS

    @property
    def lift(self) -> float:
        return (self.best.score - self.seed_score) if self.best is not None else 0.0


def _best_score(db: ProgramDatabase) -> float:
    best = db.best()
    return best.score if best is not None else float("-inf")


def _spawn_generation(
    db: ProgramDatabase,
    generate: GenerateFn,
    oracle: ScalarOracle,
    gen: int,
    *,
    k_parents: int,
    evaluations: int,
    max_evaluations: int | None,
) -> int:
    """한 세대 생성·평가 → db 누적, 갱신된 누적 evaluation 수 반환 (nesting 축소용 추출).

    parent_index 는 best-K[0] 단일 부모로 기록 — lineage 충실도는 k_parents==1 기준
    (k>1 crossover 의 다중 부모 귀속은 미지원, 의도된 단순화).
    """
    parents = db.best_k(k_parents)
    parent_index = parents[0].index if parents else None
    for child in generate([c.payload for c in parents], gen):
        if max_evaluations is not None and evaluations >= max_evaluations:
            break
        ev = oracle.evaluate(child)
        db.add(payload=child, score=ev.value, generation=gen, parent=parent_index)
        evaluations += 1
    return evaluations


def _stagnation(
    stagnant: int, prev_best: float, new_best: float, patience: int
) -> tuple[int, bool]:
    """무개선 카운트 갱신 → (new_stagnant, plateaued)."""
    if new_best > prev_best + _EPS:
        return 0, False
    stagnant += 1
    return stagnant, stagnant >= patience


def evolve(
    seed: Any,
    generate: GenerateFn,
    oracle: ScalarOracle,
    *,
    max_generations: int = 10,
    max_evaluations: int | None = None,
    k_parents: int = 2,
    patience: int = 3,
    target: float | None = None,
) -> EvolveResult:
    """검증접지 합성 fixpoint loop.

    seed 를 gen 0 으로 평가 → 매 세대 best-K read-back 으로 generate → 외부 oracle 로 채점
    → program-database 누적. plateau(patience 세대 무개선) / budget(max_generations 또는
    max_evaluations) / target 도달 시 종료.

    Args:
        seed: 초기 후보 payload (gen 0).
        generate: (parents, generation) -> 자식 payload 들. parents = best-K read-back.
        oracle: 외부 결정론 fitness (높을수록 좋음). LLM 판정 금지 (DPI 함정).
        max_generations: 최대 세대 (>=0; 0 이면 seed 만 평가).
        max_evaluations: 누적 oracle 호출 상한 (None=무제한). equal-compute A/B 통제 손잡이.
        k_parents: read-back 부모 수 (<=0 이면 unguided = best_of_n 에 수렴).
        patience: 무개선 허용 세대 수 (초과 시 plateau 종료).
        target: best score 가 이 값 이상이면 즉시 converged 종료 (None=비활성).

    Returns:
        EvolveResult — best 후보 + 단조 history + 종료 사유 + 전체 database.
    """
    db = ProgramDatabase()
    ev = oracle.evaluate(seed)
    db.add(payload=seed, score=ev.value, generation=0, parent=None)
    seed_score = ev.value
    evaluations = 1
    history = [seed_score]
    stagnant = 0
    generations_run = 0
    stop_reason = "budget"

    for gen in range(1, max(0, max_generations) + 1):
        if target is not None and _best_score(db) >= target:
            stop_reason = "converged"
            break
        if max_evaluations is not None and evaluations >= max_evaluations:
            stop_reason = "budget"
            break

        prev_best = _best_score(db)
        evaluations = _spawn_generation(
            db,
            generate,
            oracle,
            gen,
            k_parents=k_parents,
            evaluations=evaluations,
            max_evaluations=max_evaluations,
        )
        generations_run = gen
        history.append(_best_score(db))

        stagnant, plateaued = _stagnation(stagnant, prev_best, _best_score(db), patience)
        if plateaued:
            stop_reason = "plateau"
            break

    if target is not None and _best_score(db) >= target:
        stop_reason = "converged"

    return EvolveResult(
        best=db.best(),
        seed_score=seed_score,
        generations=generations_run,
        evaluations=evaluations,
        history=tuple(history),
        stop_reason=stop_reason,
        database=db,
    )


def best_of_n(
    generate: GenerateFn,
    oracle: ScalarOracle,
    *,
    n: int,
) -> EvolveResult:
    """ARM1 control — read-back 없는 *faithful* best-of-N (engine/efficacy 4th gate baseline).

    n 회 **독립 추출**: generate((), i) 를 i=0..n-1 로 호출해 매번 첫 제안 1개만 취한다
    (generation 인덱스 i 가 seed 역할 → 독립). parents 를 항상 빈 tuple 로 줘 stigmergy
    prior 를 차단하므로, equal-evaluation 에서 evolve 와의 유일한 차이는 read-back 유무다.

    (이전 구현은 generate((),0) 1회 호출 후 slice 라 generator 가 한 번에 >=n 개를 뱉을
    때만 equal-evals 가 성립하는 rig 였다 — 독립 추출로 교정. critic verdict 2026-06-02.)

    evolve.best.score 가 같은 evaluations 에서 이 값을 strictly 넘어야 "read-back 구조가
    real" — 그래도 그건 *합성 landscape* 위 존재증명이지 실제 oracle task 의 equal-compute
    인지 우위 주장이 아니다 (모듈 docstring 주의).
    """
    db = ProgramDatabase()
    evaluations = 0
    for i in range(max(0, n)):
        proposals = list(generate((), i))
        if not proposals:
            continue
        child = proposals[0]  # 1 independent draw per call (seed=i)
        ev = oracle.evaluate(child)
        db.add(payload=child, score=ev.value, generation=0, parent=None)
        evaluations += 1
    best = db.best()
    if best is None:
        return EvolveResult(
            best=None,
            seed_score=float("-inf"),
            generations=0,
            evaluations=0,
            history=(),
            stop_reason="empty",
            database=db,
        )
    return EvolveResult(
        best=best,
        seed_score=db.all()[0].score,  # 첫 독립 추출 점수 = lift 기준선
        generations=0,
        evaluations=evaluations,
        history=(best.score,),
        stop_reason="budget",
        database=db,
    )


__all__ = [
    "Candidate",
    "EvolveResult",
    "GenerateFn",
    "ProgramDatabase",
    "best_of_n",
    "evolve",
]
