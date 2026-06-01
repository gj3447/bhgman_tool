"""Benchmark — 재배맨 계획→씨앗 결정화 성능 (Longinus bench_parallel.py 거울).

합성 b-ary 트리 코퍼스(branching b × depth d → N nodes). 각 단계 비용 측정:
  plan_build(eager μ) / to_seeds(flatten) / plant_dryrun(cypher build) / plant_null(writer call)
  + eager μ vs lazy ν take(k) break-even (Longinus parallel break-even의 거울).

정직 가설: plan_build CPU는 µs급 노이즈, plant(KG IO)가 지배 — 벤치가 측정으로 확정한다.
Goodhart 가드: 단일 점수 금지, raw 숫자 JSON (Longinus가 raw exit code 찍듯).

사용:
    python -m engine.jaebaeman.bench.bench_plan --shapes 2x3,4x3,4x5,8x4 --runs 5
    python -m engine.jaebaeman.bench.bench_plan --local      # LocalKgStore 실제 write 비용

# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01 (D 벤치 + C2 break-even),
#     longinus-parallel-bench-2026-05-18 (구조 출처)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from engine.jaebaeman.jaebaeman_models import Goal  # noqa: E402
from engine.jaebaeman.kg_adapter import plant_seeds  # noqa: E402
from engine.jaebaeman.planner import (  # noqa: E402
    plan,
    plan_lazy,
    static_decompose,
    take_n,
    to_seeds,
)


def _node_count(branching: int, depth: int) -> int:
    if branching == 1:
        return depth + 1
    return (branching ** (depth + 1) - 1) // (branching - 1)


def _build_decompose_tree(branching: int, depth: int) -> dict:
    """b-ary 합성 분해 dict (timed 구간 밖에서 1회 build)."""
    tree: dict[str, list[Goal]] = {}

    def expand(name: str, d: int) -> None:
        if d >= depth:
            return
        children = [Goal(name=f"{name}.{i}", objective=f"obj {name}.{i}") for i in range(branching)]
        tree[name] = children
        for c in children:
            expand(c.name, d + 1)

    expand("g", 0)
    return tree


class _NullWriter:
    """write 호출 횟수만 세는 no-op (KG IO 제외, 순수 cypher 호출 오버헤드 측정)."""

    def __init__(self) -> None:
        self.n = 0

    def __call__(self, _cypher: str, _params: dict) -> list:
        self.n += 1
        return []


def _best(fn, runs: int) -> float:
    """best-of-runs perf_counter (cold-start 노이즈 제거, Longinus와 동일)."""
    return min(_time(fn) for _ in range(runs))


def _time(fn) -> float:
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


def bench_shape(branching: int, depth: int, runs: int) -> dict:
    n = _node_count(branching, depth)
    dec_tree = _build_decompose_tree(branching, depth)
    dec = static_decompose(dec_tree)
    g = Goal(name="g", objective="root")

    plan(g, dec, max_depth=depth)  # warm-up

    plan_s = _best(lambda: plan(g, dec, max_depth=depth), runs)
    tree = plan(g, dec, max_depth=depth)
    seeds = to_seeds(tree, "jaebaeman")
    to_seeds_s = _best(lambda: to_seeds(tree, "jaebaeman"), runs)
    plant_dry_s = _best(lambda: plant_seeds(seeds, dry_run=True), runs)
    plant_null_s = _best(
        lambda: plant_seeds(seeds, write_cypher=_NullWriter(), dry_run=False), runs
    )

    # eager vs lazy break-even: prefix k = 10% of nodes.
    # eager는 prefix만 원해도 트리 전체 build 필요 → 항상 full cost.
    k = max(1, n // 10)
    eager_prefix_s = _best(lambda: _eager_prefix(g, dec, depth, k), runs)
    lazy_prefix_s = _best(lambda: take_n(plan_lazy(g, dec, max_depth=depth), k), runs)

    return {
        "shape": f"{branching}x{depth}",
        "node_count": n,
        "plan_build_s": round(plan_s, 6),
        "to_seeds_s": round(to_seeds_s, 6),
        "plant_dryrun_s": round(plant_dry_s, 6),
        "plant_null_s": round(plant_null_s, 6),
        "prefix_k": k,
        "eager_prefix_s": round(eager_prefix_s, 6),
        "lazy_prefix_s": round(lazy_prefix_s, 6),
        "lazy_speedup_at_k": (
            round(eager_prefix_s / lazy_prefix_s, 2) if lazy_prefix_s > 0 else None
        ),
        "runs_per_config": runs,
    }


def _eager_prefix(g, dec, depth, k):
    from engine.jaebaeman.planner import walk  # noqa: PLC0415

    tree = plan(g, dec, max_depth=depth)
    return [n for n, _ in walk(tree)][:k]


def bench_local(branching: int, depth: int, runs: int) -> dict:
    """LocalKgStore(JSON 파일) 실제 write 비용 — plant_null(no-op) 대비 진짜 IO 오버헤드."""
    import tempfile  # noqa: PLC0415

    from engine.kg_local.runner import make_local_runner  # noqa: PLC0415
    from engine.kg_local.store import LocalKgStore  # noqa: PLC0415

    dec = static_decompose(_build_decompose_tree(branching, depth))
    g = Goal(name="g", objective="root")
    seeds = to_seeds(plan(g, dec, max_depth=depth), "jaebaeman")

    def run_once() -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=True) as tf:
            store = LocalKgStore(path=tf.name)
            writer = make_local_runner(store, autosave=False)
            plant_seeds(seeds, write_cypher=writer, dry_run=False)
            store.save()

    run_once()  # warm-up
    return {
        "shape": f"{branching}x{depth}",
        "node_count": _node_count(branching, depth),
        "local_kg_plant_s": round(_best(run_once, runs), 6),
        "runs_per_config": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="bench_plan")
    parser.add_argument(
        "--shapes",
        default="2x3,4x3,4x5,8x4",
        help="Comma-separated branching x depth (default: 2x3,4x3,4x5,8x4).",
    )
    parser.add_argument("--runs", type=int, default=5, help="Best-of runs per config.")
    parser.add_argument(
        "--local", action="store_true", help="Also bench LocalKgStore real-write cost."
    )
    args = parser.parse_args()

    shapes = []
    for tok in args.shapes.split(","):
        b, d = tok.strip().split("x")
        shapes.append((int(b), int(d)))

    out: dict = {"synthetic": [bench_shape(b, d, args.runs) for b, d in shapes]}
    if args.local:
        out["local_kg"] = [bench_local(b, d, args.runs) for b, d in shapes]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
