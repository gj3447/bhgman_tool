"""occam SEMANTIC dedup must apply on the local KG backend (generic {key} supersede).

semantic_dedup emits a generic-key supersede cypher (`stale.{key} = $stale_id`, key ∈
{name, findingId, id}) with params {stale_id, current_id, reason}. The local runner routes
ANY cypher containing `stale.status = 'SUPERSEDED'` to `_occam_supersede`, which only
understood the path+sha SourceCodeNode variant — it read `params['stale_path']` → KeyError.
That KeyError was swallowed by run_semantic_dedup's `except Exception` (PROPOSE-degrade), so
AbstractClass/Concept/Finding semantic dedup was a SILENT no-op on local (applied stays 0).

# KG: finding-occam-semantic-dedup-local-keyerror-silent-noop-2026-06-26
"""
from __future__ import annotations

from engine.kg_local.runner import make_local_runner
from engine.kg_local.store import LocalKgStore
from engine.occam.semantic_dedup import (
    NearDupPair,
    plan_supersession,
    run_semantic_dedup,
)


def _store_with(*names: str) -> LocalKgStore:
    store = LocalKgStore()
    for nm in names:
        store.nodes.append({"labels": ["Concept"], "props": {"name": nm}})
    return store


def test_local_runner_handles_generic_key_supersede() -> None:
    # The exact KeyError site: the generic-key supersede cypher run through the local runner.
    store = _store_with("dup_stale", "dup_current")
    run = make_local_runner(store, autosave=False)
    cypher, params = plan_supersession(
        NearDupPair(keep_id="dup_current", drop_id="dup_stale", similarity=0.99), key="name"
    )
    rows = run(cypher, params)  # was: KeyError('stale_path') inside _occam_supersede
    assert rows == [{"superseded": "dup_stale", "current": "dup_current"}]
    stale = store.find_one("name", "dup_stale")
    assert stale["props"]["status"] == "SUPERSEDED"
    assert stale["props"]["supersededBy"] == "dup_current"


def test_run_semantic_dedup_applies_on_local_backend() -> None:
    # End-to-end symptom: applied was silently 0 on local despite a confirmed near-dup.
    store = _store_with("alpha", "alpha_dup")
    run = make_local_runner(store, autosave=False)
    report = run_semantic_dedup(
        [("alpha", "same text"), ("alpha_dup", "same text")],
        embed_fn=lambda texts: [[1.0, 0.0] for _ in texts],  # identical → cosine 1.0
        threshold=0.95,
        key="name",
        write_cypher=run,
        apply=True,
    )
    assert report.applied == 1  # was 0 (KeyError swallowed → silent no-op)
