"""부채 — eureka(발견·창조) 독립 oracle: planted-concept recovery vs naive baseline.

eureka 동사 = "발견·창조"(반복 패턴 → 추상 추출, FCA colimit). production reuse 효능은
실 KG에 측정 재료가 *없다*: `:AbstractCategory`(eureka 산출 라벨) 0개 + 범용 :Concept은
eureka provenance 미태깅이라 기여 분리 불가 + reuse 시계열 미수집. 따라서 *downstream
reuse 효능*은 UNMEASURABLE이 정직값(날조 금지).

대신 *extraction 정확성*은 비순환으로 잰다(naesengmoon mutation_oracle 패턴): 잠재
개념을 **심고**(ground truth = 내가 author, eureka 무관) eureka의 FCA가 그걸 복원하나.
핵심 — 개념을 *순환 attribute 쌍*으로 정의(각 단일 속성은 2개 개념에 걸침)해서 단일-속성
naive grouping으론 분리 불가, FCA closure(conjunction)만 복원 가능 = FCA의 진짜 강점.

측정: recovery_recall(FCA) vs recovery_recall(naive 단일속성) + lift. lift>0이면 eureka가
naive가 못 잡는 conjunctive 잠재구조를 추출 = extraction 효능. 결정론(구성·closure 둘 다).

정직 라벨: 이건 **extraction 정확성**(잠재구조 복원)이지 *reuse 효능*(추출한 추상이 실제
재사용되어 가치 생산)이 아니다. 후자는 eureka가 실 KG에 써서 fan-in 시계열이 쌓여야 측정
가능 = OPEN. hades(realization)·prometheus(verifiability)와 같은 "측정 가능한 층은 잼,
cognitive/downstream 층은 정직히 OPEN" 패턴.

순수(build_planted_context/recovery_recall) + IO(induce_fca 드라이브) 분리.

# KG: efficacy-eureka-2026-06-01, efficacy-measurement-line-2026-06-01,
#     eureka-canonical-2026-05-26, project_eureka_bottomup_builder_2026_05_27
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from engine.eureka.induction_operators.fca import induce_fca

_DECOY = "common_decoy_attr"  # 모든 객체 공유 = naive baseline의 함정


def build_planted_context(
    k: int = 6, objects_per: int = 4
) -> tuple[dict[str, frozenset[str]], list[frozenset[str]]]:
    """K개 개념을 *순환 attribute 쌍*으로 심는다 → (formal context, planted 객체그룹).

    개념 i = attribute {a_i, a_{(i+1)%K}} 둘 다 가진 객체들. 각 a_j는 개념 j와 j-1에
    걸쳐(단일속성으론 식별 불가) — conjunction closure만 개념 i를 분리한다.
    """
    context: dict[str, frozenset[str]] = {}
    planted: list[frozenset[str]] = []
    for i in range(k):
        a1, a2 = f"a_{i}", f"a_{(i + 1) % k}"
        objs = {f"o_{i}_{j}" for j in range(objects_per)}
        for o in objs:
            context[o] = frozenset({a1, a2, _DECOY})
        planted.append(frozenset(objs))
    return context, planted


def recovery_recall(
    extents: list[frozenset[str]], planted: list[frozenset[str]], thresh: float = 0.8
) -> float:
    """planted 그룹 중 어떤 extent와 Jaccard ≥ thresh로 매칭되는 비율 (순수)."""
    if not planted:
        return 0.0
    hits = 0
    for g in planted:
        best = max((_jaccard(g, e) for e in extents), default=0.0)
        if best >= thresh:
            hits += 1
    return hits / len(planted)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def naive_extents(context: dict[str, frozenset[str]]) -> list[frozenset[str]]:
    """naive baseline: 각 단일 attribute별로 그 속성을 가진 객체 집합 (closure 없음)."""
    attrs = {a for attrs in context.values() for a in attrs}
    return [frozenset(o for o, oa in context.items() if a in oa) for a in sorted(attrs)]


@dataclass(frozen=True)
class ReuseBreadth:
    """실 KG에서 eureka 추상의 즉시적 reuse breadth (synchronic cover)."""

    n_objects: int
    n_concepts: int
    extents: tuple[int, ...]  # 각 induced 추상이 cover하는 KG 노드 수 (내림차순)
    nodes_covered: int

    @property
    def avg_extent(self) -> float:
        return sum(self.extents) / len(self.extents) if self.extents else 0.0

    @property
    def median_extent(self) -> int:
        return self.extents[len(self.extents) // 2] if self.extents else 0

    @property
    def coverage(self) -> float:
        return self.nodes_covered / self.n_objects if self.n_objects else 0.0

    def summary(self) -> str:
        return (
            f"eureka KG reuse-breadth: {self.n_concepts} 추상 induced over {self.n_objects} "
            f"facet-graph 노드 · extents={list(self.extents)} · avg={self.avg_extent:.1f} "
            f"median={self.median_extent} · coverage={self.nodes_covered}/{self.n_objects} "
            f"({self.coverage:.2f})"
        )


def reuse_breadth(extents: list[int], n_objects: int, nodes_covered: int) -> ReuseBreadth:
    """induced 추상 extent 리스트 → reuse breadth (순수). extent = 한 추상이 묶은 노드 수."""
    ordered = tuple(sorted(extents, reverse=True))
    return ReuseBreadth(
        n_objects=n_objects,
        n_concepts=len(ordered),
        extents=ordered,
        nodes_covered=nodes_covered,
    )


def _kg_reuse() -> ReuseBreadth | None:  # pragma: no cover — IO
    """실 KG에서 eureka 돌려 reuse breadth 측정. neo4j 없으면 None."""
    from engine.cli.runtime import make_kg_runners  # noqa: PLC0415
    from engine.eureka.formal_context_builder import build_formal_context  # noqa: PLC0415

    runners = make_kg_runners()
    if runners is None:
        return None
    run_cypher, _w, close = runners
    try:
        ctx, meta = build_formal_context(run_cypher)
        res = induce_fca(ctx, min_extent=2, min_stability=0.0)
        extents = [len(c.extent) for c in res.concepts]
        covered = len(set().union(*[c.extent for c in res.concepts])) if res.concepts else 0
        return reuse_breadth(extents, int(meta["objects"]), covered)
    finally:
        close()


def main() -> int:  # pragma: no cover — 진입점
    context, planted = build_planted_context()
    result = induce_fca(context, min_extent=2, min_stability=0.0)
    fca_ext = [c.extent for c in result.concepts]
    fca_recall = recovery_recall(fca_ext, planted)
    naive_recall = recovery_recall(naive_extents(context), planted)
    lift = fca_recall - naive_recall
    print(
        f"eureka recovery oracle (planted K={len(planted)} cyclic-pair concepts): "
        f"FCA recall={fca_recall:.3f} vs naive single-attr={naive_recall:.3f} "
        f"(lift={lift:+.3f}; FCA concepts induced={len(fca_ext)})"
    )
    print(
        "  읽기: lift>0 = eureka가 단일속성으론 못 잡는 conjunctive 잠재구조를 추출(extraction 효능)."
    )
    # 2층: 실 KG reuse breadth (synchronic cover) — neo4j 있으면.
    rb = _kg_reuse()
    if rb is None:
        print("  [KG reuse] neo4j 미연결 — synchronic reuse-breadth 생략.", file=sys.stderr)
    else:
        print("  ── 실 KG reuse-breadth (synchronic, 비순환: 노드·facet은 eureka 무관) ──")
        print(f"  {rb.summary()}")
        print(
            "  읽기: 각 추상이 13~수십 노드를 묶음 = 즉시적 reuse breadth(추상 하나가 N개 기존노드 cover). "
            "단 min_extent=2가 singleton pruning이라 'extent≥2'는 tautology — 의미는 extent *분포·coverage*."
        )
    print(
        "  주의: (1)planted=extraction capability (2)KG breadth=*synchronic* cover(지금 N노드 묶음)이지 "
        "*diachronic fan-in*(미래 재사용 시계열) 아님 — 후자는 :AbstractCategory write+시간 필요 = OPEN. "
        "facet-graph 319노드 narrow slice."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
