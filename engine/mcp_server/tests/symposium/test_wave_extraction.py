"""Validates Kahn topological-sort wave_index extraction.

Reference: GAP-1 (2026-05-13 session) — wave_index = position in Kahn topo sort.
Each AtomicSpan ships in a wave; wave_n+1 can dispatch only after wave_n completes.

Pure-algorithm tests (no KG dependency).

KG: rs-test-wave-extraction-kahn-2026-05-14
Provenance: SYMPOSIUM/tests/test_wave_extraction.py (absorbed Wave 7 P2-A)
"""

from __future__ import annotations

import pytest


def kahn_waves(nodes: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Returns [[wave_0], [wave_1], ...] using Kahn's algorithm.

    Edge (a, b) means: a must complete before b. Cycles raise ValueError.
    Within a wave the order is sorted for determinism.
    """
    indeg: dict[str, int] = {n: 0 for n in nodes}
    children: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b in edges:
        if a not in indeg or b not in indeg:
            raise ValueError(f"edge references unknown node: ({a}, {b})")
        indeg[b] += 1
        children[a].append(b)

    waves: list[list[str]] = []
    frontier = sorted(n for n, d in indeg.items() if d == 0)
    visited = 0
    while frontier:
        waves.append(frontier)
        next_frontier: list[str] = []
        for n in frontier:
            visited += 1
            for child in children[n]:
                indeg[child] -= 1
                if indeg[child] == 0:
                    next_frontier.append(child)
        frontier = sorted(next_frontier)

    if visited != len(nodes):
        raise ValueError(f"cycle detected: visited {visited}/{len(nodes)}")
    return waves


def assign_wave_index(nodes: list[str], edges: list[tuple[str, str]]) -> dict[str, int]:
    """Return {node: wave_index} mapping."""
    waves = kahn_waves(nodes, edges)
    return {n: i for i, wave in enumerate(waves) for n in wave}


class TestKahnWaves:
    def test_empty_graph(self):
        assert kahn_waves([], []) == []

    def test_singleton(self):
        assert kahn_waves(["a"], []) == [["a"]]

    def test_two_parallel_roots(self):
        # No edges → both ship in wave 0
        assert kahn_waves(["a", "b"], []) == [["a", "b"]]

    def test_linear_chain(self):
        nodes = ["a", "b", "c"]
        edges = [("a", "b"), ("b", "c")]
        assert kahn_waves(nodes, edges) == [["a"], ["b"], ["c"]]

    def test_diamond(self):
        # a → b, a → c, b → d, c → d
        nodes = ["a", "b", "c", "d"]
        edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")]
        assert kahn_waves(nodes, edges) == [["a"], ["b", "c"], ["d"]]

    def test_cycle_detected(self):
        with pytest.raises(ValueError, match="cycle detected"):
            kahn_waves(["a", "b"], [("a", "b"), ("b", "a")])

    def test_unknown_edge_rejected(self):
        with pytest.raises(ValueError, match="unknown node"):
            kahn_waves(["a"], [("a", "ghost")])


class TestWaveIndexAssignment:
    def test_indexing_starts_at_zero(self):
        idx = assign_wave_index(["a", "b"], [("a", "b")])
        assert idx == {"a": 0, "b": 1}

    def test_parallel_siblings_share_wave(self):
        # 1 root, 3 leaves in parallel → wave 0 = {root}, wave 1 = {l1, l2, l3}
        idx = assign_wave_index(
            ["root", "l1", "l2", "l3"],
            [("root", "l1"), ("root", "l2"), ("root", "l3")],
        )
        assert idx["root"] == 0
        assert idx["l1"] == idx["l2"] == idx["l3"] == 1

    def test_dispatch_invariant(self):
        """The dispatch rule: wave_index[child] > wave_index[parent] for every edge."""
        nodes = ["a", "b", "c", "d", "e"]
        edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "e")]
        idx = assign_wave_index(nodes, edges)
        for parent, child in edges:
            assert (
                idx[child] > idx[parent]
            ), f"dispatch invariant violated: {parent}@{idx[parent]} → {child}@{idx[child]}"


class TestAptIntegration:
    """Wave extraction applied to a realistic APT SP→ST decomposition."""

    def test_sp_to_st_to_scw_chain(self):
        # SA emits 1 root span; SP decomposes into 2 sub-spans; ST crystallizes contracts;
        # SCW ships 4 atomic spans. Total 8 nodes, dispatch in 4 waves.
        nodes = ["SA", "SP1", "SP2", "ST1a", "ST1b", "ST2a", "ST2b", "REVIEW"]
        edges = [
            ("SA", "SP1"),
            ("SA", "SP2"),
            ("SP1", "ST1a"),
            ("SP1", "ST1b"),
            ("SP2", "ST2a"),
            ("SP2", "ST2b"),
            ("ST1a", "REVIEW"),
            ("ST1b", "REVIEW"),
            ("ST2a", "REVIEW"),
            ("ST2b", "REVIEW"),
        ]
        waves = kahn_waves(nodes, edges)
        assert waves[0] == ["SA"]
        assert sorted(waves[1]) == ["SP1", "SP2"]
        assert sorted(waves[2]) == ["ST1a", "ST1b", "ST2a", "ST2b"]
        assert waves[3] == ["REVIEW"]
        assert len(waves) == 4
