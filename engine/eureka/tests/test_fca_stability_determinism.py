"""FCA concept stability — deterministic + exact for small extents (close q-eureka-nondeterminism).

``_approx_stability`` samples random subsets for extents > 8 and iterates ``list(frozenset)``,
whose order is hash-randomized across processes — so for large extents the stability (and thus
the survivor count near the 0.50 floor) is non-reproducible. That random sampler is the lone
non-determinism source in the FCA operator. The Red artifact (test-first): up to the exact
cutoff, stability is the EXACT subset fraction (order-independent, reproducible), not a 32-sample
approximation. RED until the cutoff is raised + the sampling order fixed.

# KG: eureka-canonical-2026-05-26
"""

from __future__ import annotations

from itertools import combinations

from engine.eureka.induction_operators.fca import _approx_stability, _closure


def _exact_stability(extent, context) -> float:
    ext = sorted(extent)
    _, target = _closure(frozenset(ext), context)
    total = 2 ** len(ext)
    stable = sum(
        1
        for r in range(len(ext) + 1)
        for sub in combinations(ext, r)
        if _closure(frozenset(sub), context)[1] == target
    )
    return stable / total


def _ctx(n_total: int, n_with_y: int) -> dict:
    return {f"o{i}": frozenset({"x"} | ({"y"} if i < n_with_y else set())) for i in range(n_total)}


def test_stability_is_exact_for_extent_above_old_cutoff():
    ctx = _ctx(10, 4)  # a size-10 extent (> the old 8-element sampling cutoff)
    extent, _ = _closure(frozenset({"o5"}), ctx)
    assert len(extent) == 10
    assert _approx_stability(extent, ctx) == _exact_stability(extent, ctx)


def test_stability_is_exact_for_size_eleven():
    ctx = _ctx(11, 5)
    extent, _ = _closure(frozenset({"o6"}), ctx)
    assert len(extent) == 11
    assert _approx_stability(extent, ctx) == _exact_stability(extent, ctx)


def test_stability_is_deterministic_repeated_calls():
    ctx = _ctx(11, 5)
    extent, _ = _closure(frozenset({"o6"}), ctx)
    assert _approx_stability(extent, ctx) == _approx_stability(extent, ctx)


def test_stability_order_independent_full_solid_extent():
    # all-identical attrs => every subset closes to the same intent => exact σ, order-free.
    solid = {f"s{i}": frozenset({"k"}) for i in range(10)}
    s_ext, _ = _closure(frozenset({"s0"}), solid)
    assert len(s_ext) == 10
    assert _approx_stability(s_ext, solid) == _exact_stability(s_ext, solid)


def test_small_extent_path_unchanged():
    # n <= 8 was already exact; must stay exact (regression guard).
    ctx = _ctx(6, 2)
    extent, _ = _closure(frozenset({"o3"}), ctx)
    assert _approx_stability(extent, ctx) == _exact_stability(extent, ctx)
