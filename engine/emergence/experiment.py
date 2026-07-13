"""울프람 실험 — 창발의 계산 불가역성(computational irreducibility) 관찰.

단순 국소 규칙(Hawkes 가중 + Hebbian 공동접근 + FSM 승격)만 주고, 잠재 의미
클러스터를 *심은* 합성 traffic 을 흘려보낸다. 엔진에는 클러스터를 알려주지 않는다.
그럼에도 강한 Hebbian 엣지가 클러스터 경계를 복원하고, 인기 개념이 계층 상단(HOT)
으로 떠오른다 = 설계되지 않은 구조의 창발.

run:  uv run python -m engine.emergence.experiment
"""
# KG: engineboy-emergence-engine-fsm-design-2026-07-13

from __future__ import annotations

import random
from dataclasses import dataclass

from engine.emergence import (
    AccessEvent,
    ActivityState,
    EmergenceConfig,
    EmergenceEngine,
)
from engine.emergence import hawkes

# --- 잠재 구조 (엔진은 모름 — ground truth) ---
LATENT: dict[str, list[str]] = {
    "physics": ["quantum", "relativity", "entropy", "gauge", "field", "symmetry"],
    "cooking": ["pasta", "sauce", "garlic", "simmer", "basil", "olive"],
    "finance": ["ledger", "equity", "hedge", "yield", "arbitrage", "liquidity"],
}
POPULARITY = {"physics": 0.5, "cooking": 0.3, "finance": 0.2}
_CLUSTER_OF = {c: name for name, members in LATENT.items() for c in members}


@dataclass
class ExperimentResult:
    intra_edge_mean: float
    inter_edge_mean: float
    hot_concepts: list[str]
    n_edges: int
    n_nodes: int
    top_edges: list[tuple[str, str, float]]

    @property
    def structure_emerged(self) -> bool:
        # 클러스터-내 엣지가 클러스터-간보다 유의미하게 강함 = 구조 복원
        return self.intra_edge_mean > 3.0 * max(self.inter_edge_mean, 1e-9)


def run_experiment(seed: int = 7, n_events: int = 800) -> ExperimentResult:
    rng = random.Random(seed)
    # l1_capacity 를 희소하게 → HOT 은 경쟁 자원. 인기 클러스터가 상단 차지 (계층 창발).
    cfg = EmergenceConfig(lam=0.004, theta_warm=1.0, theta_hot=3.0, n_est=3, l1_capacity=6)
    eng = EmergenceEngine(cfg=cfg)
    names = list(POPULARITY)
    weights = [POPULARITY[n] for n in names]

    t = 0.0
    for i in range(n_events):
        cl = rng.choices(names, weights=weights, k=1)[0]
        members = rng.sample(LATENT[cl], k=rng.randint(2, 3))
        primary, co = members[0], tuple(members[1:])
        # 5% cross-cluster noise (실제 traffic 의 잡음)
        if rng.random() < 0.05:
            other = rng.choice([m for m in LATENT[rng.choice(names)]])
            co = co + (other,)
        actor = "human" if i % 2 == 0 else "ai"
        eng.ingest(AccessEvent(f"e{i}", primary, actor, t, co_keys=co))
        t += 1.0

    # 창발 관찰: Hebbian 엣지 강도 (final 시점 decay)
    intra, inter, edge_rows = [], [], []
    for ekey, e in eng.edges.items():
        _, a, b = ekey.split("::")
        w = hawkes.decayed_weight(e.w, e.t_last, t, cfg.lam)
        edge_rows.append((a, b, w))
        same = _CLUSTER_OF.get(a) == _CLUSTER_OF.get(b)
        (intra if same else inter).append(w)

    hot = sorted(x.key for x in eng.by_state(ActivityState.HOT))
    edge_rows.sort(key=lambda r: r[2], reverse=True)
    return ExperimentResult(
        intra_edge_mean=(sum(intra) / len(intra)) if intra else 0.0,
        inter_edge_mean=(sum(inter) / len(inter)) if inter else 0.0,
        hot_concepts=hot,
        n_edges=len(eng.edges),
        n_nodes=len(eng.nodes),
        top_edges=edge_rows[:8],
    )


def _recover_communities(res_engine_edges) -> None:  # pragma: no cover
    pass


def main() -> None:  # pragma: no cover
    r = run_experiment()
    print("=" * 64)
    print("울프람 실험 — 창발 관찰 (엔진은 클러스터를 모름)")
    print("=" * 64)
    print(f"노드 {r.n_nodes} · Hebbian 엣지 {r.n_edges}")
    print(f"클러스터-내 엣지 평균 강도 : {r.intra_edge_mean:7.3f}")
    print(f"클러스터-간 엣지 평균 강도 : {r.inter_edge_mean:7.3f}")
    ratio = r.intra_edge_mean / max(r.inter_edge_mean, 1e-9)
    print(f"내/간 비율                 : {ratio:7.1f}x  → 구조 복원={r.structure_emerged}")
    print(f"\n계층 상단(HOT) 창발 개념    : {r.hot_concepts}")
    print("\n최강 Hebbian 엣지 (창발한 연결):")
    for a, b, w in r.top_edges:
        ca, cb = _CLUSTER_OF.get(a, "?"), _CLUSTER_OF.get(b, "?")
        mark = "  " if ca == cb else "✗ "  # ✗ = cross-cluster 잡음
        print(f"  {mark}{a:12s} — {b:12s}  w={w:6.2f}  [{ca}/{cb}]")
    print("\n→ 아무도 클러스터를 가르쳐주지 않았다. traffic 국소규칙만으로 창발.")


if __name__ == "__main__":
    main()
