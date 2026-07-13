"""Hades materialize sink — realise the in-memory emerged graph into Neo4j (하데스 = 실현: 추상→구체).

`resolver.Neo4jVectorResolver.add()` is a deliberate no-op; its docstring points here: "production
에선 node MERGE + embedding SET 이 별도 populate 경로(하데스)." The emergence engine accumulates
traffic-emerged nodes and Hebbian edges in memory — this sink writes them down:

  - as an `EmergenceEngine(sink=...)` callable it MERGEs each published NODE (weight / access-count /
    activity-tier / namespace), optionally SETting its embedding so the vector index the SeedFn queries
    stays populated;
  - `flush(engine)` materialises the FULL emerged graph including the Hebbian EDGES (which the per-
    publish sink hook never sees — the engine passes only nodes to `sink`).

Visibility D3: only the `shared` (upper-world) namespace is materialised by default — private/tenant
elements are never lifted into the shared, queryable index.

All I/O goes through an injected `run_cypher` (live MCP / kg_local / fake-in-test), like the rest of
engine/ — no driver import, no auto-write on import, fully offline-testable. `label` / `key_prop` /
`embedding_prop` / `rel_type` are validated as bare identifiers before interpolation (no injection
surface), matching neo4j_vector.py.

# KG: engineboy-emergence-engine-fsm-design-2026-07-13, hades-canonical-2026-05-27,
#     occam-kam-canonical-2026-05-26
"""
from __future__ import annotations

import re
from collections.abc import Callable, Sequence

from engine.emergence.engine import Transition, tier_of
from engine.emergence.protocols import Element

Vector = Sequence[float]
CypherRunner = Callable[[str, dict], "list[dict]"]
EmbedFn = Callable[[str], "Vector | None"]

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ident(kind: str, value: str) -> str:
    if not _IDENT.match(value):
        raise ValueError(f"unsafe {kind} identifier for cypher interpolation: {value!r}")
    return value


class Neo4jHadesSink:
    """`EmergenceEngine(sink=...)` callable that materialises emerged elements into Neo4j.

    Idempotent: every write is a MERGE, so replaying traffic converges. Per-event MERGE (not
    batched) — correct but chatty; batching the streaming path is a documented follow-up. Counters
    expose exactly what was written (auditable, like the rest of the naesengmoon/engine layer).
    """

    def __init__(
        self,
        run_cypher: CypherRunner,
        *,
        label: str = "EmergedElement",
        key_prop: str = "name",
        embedding_prop: str = "embedding",
        rel_type: str = "CO_ACTIVATES",
        embed_fn: EmbedFn | None = None,
        namespaces: tuple[str, ...] = ("shared",),
    ) -> None:
        self._run = run_cypher
        self.label = _ident("label", label)
        self.key_prop = _ident("key_prop", key_prop)
        self.embedding_prop = _ident("embedding_prop", embedding_prop)
        self.rel_type = _ident("rel_type", rel_type)
        self._embed = embed_fn
        self._namespaces = tuple(namespaces)
        self.nodes_written = 0
        self.edges_written = 0
        self.embeddings_set = 0
        self.skipped_private = 0

    # -- streaming sink: the engine calls this per published NODE (Transition, Element) --
    def __call__(self, tr: Transition, el: Element) -> None:
        if el.namespace not in self._namespaces:  # Visibility D3 — never lift private into shared
            self.skipped_private += 1
            return
        if el.is_edge:
            self._merge_edge(el)
        else:
            self._merge_node(el)

    # -- batch: materialise the full emerged topology (nodes + Hebbian edges) --
    def flush(self, engine) -> dict[str, int]:
        """Persist the FULL emerged graph. The per-publish hook only sees nodes; edges live in
        `engine.edges` and are written here. Call periodically or once at shutdown."""
        for el in engine.nodes.values():
            self(None, el)  # type: ignore[arg-type]  # tr is unused by __call__
        for el in engine.edges.values():
            if el.namespace in self._namespaces:
                self._merge_edge(el)
            else:
                self.skipped_private += 1
        return self.stats()

    def stats(self) -> dict[str, int]:
        return {
            "nodes_written": self.nodes_written,
            "edges_written": self.edges_written,
            "embeddings_set": self.embeddings_set,
            "skipped_private": self.skipped_private,
        }

    def _merge_node(self, el: Element) -> None:
        embed = self._embed(el.key) if self._embed is not None else None
        cypher = (
            f"MERGE (n:{self.label} {{{self.key_prop}: $key}}) "
            "SET n.w = $w, n.access_n = $n, n.tier = $tier, n.activity = $state, "
            "n.namespace = $ns, n.emerged = true"
            + (f", n.{self.embedding_prop} = $embed" if embed is not None else "")
        )
        params: dict[str, object] = {
            "key": el.key,
            "w": el.w,
            "n": el.n,
            "tier": tier_of(el.state),
            "state": el.state.name,
            "ns": el.namespace,
        }
        if embed is not None:
            params["embed"] = list(embed)
            self.embeddings_set += 1
        self._run(cypher, params)
        self.nodes_written += 1

    def _merge_edge(self, el: Element) -> None:
        if el.src is None or el.dst is None:
            return
        cypher = (
            f"MERGE (a:{self.label} {{{self.key_prop}: $src}}) "
            f"MERGE (b:{self.label} {{{self.key_prop}: $dst}}) "
            f"MERGE (a)-[r:{self.rel_type}]->(b) "
            "SET r.w = $w, r.namespace = $ns, r.emerged = true"
        )
        self._run(cypher, {"src": el.src, "dst": el.dst, "w": el.w, "ns": el.namespace})
        self.edges_written += 1


__all__ = ["Neo4jHadesSink"]
