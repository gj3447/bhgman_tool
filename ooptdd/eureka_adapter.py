"""ooptdd-loop in_process target — binds the eureka 창조(abstraction synthesis) lifecycle to
the REAL FCA induction engine (``engine.eureka.run_from_kg``).

Honest-count contract (verified, STEP-0 baseline):
    ``run_from_kg`` over an EMPTY CypherRunner builds an empty formal context => ``induce_fca``
    yields ZERO concepts => concepts=0, survivors=0, persisted=0. CRUCIALLY the pipeline's
    ``stages_ok`` is STILL 5 on that empty run (stage_1-extract etc. report ok=True over zero
    concepts) — so a gate bound to ``stages_ok`` would FAKE-GREEN on a garbage KG. We NEVER bind
    ``stages_ok``. Every count is RE-DERIVED from the real ``PipelineRun`` stage payloads:
    concepts from "4-induce", survivors from "4.5-quality-gate", persisted (per-row, real
    verdictStatus) from the real ``stage_6_persist`` via the injected persist_cypher. To EARN
    nonzero we seed the real 8-object math/compiler cluster (two 4-member latent groups, each
    sharing a closed 2-facet intent) and persist them as VERDICT_PENDING. Semantic ACCEPTED now
    requires a content-bound creative validation receipt and is covered by the CLI seam tests.

Longinus binding (AST-checked by ``ooptdd_loop.longinus.verify_binding``):
    Each must_emit literal lives VERBATIM in its ADAPTER symbol (``emit_induction_phase`` /
    ``emit_persist_phase`` / ``run_eureka_pipeline``) — NEVER inside ``engine/eureka/`` (the
    engine records into a pure ``PipelineRun`` and has no ship machinery). Rename => UNBOUND/RED.

# KG: finding-ooptdd-bhgman-eureka-adapter-20260625
# KG: eureka-canonical-2026-05-26
"""

from __future__ import annotations

from engine.eureka.pipeline import PipelineConfig, run_from_kg

_KG_ANCHOR = "finding-ooptdd-bhgman-eureka-adapter-20260625"

# The real 8-object cluster (eureka-formal-context-smoketest): math 4 + compiler 4, each group
# sharing a closed 2-facet intent => two non-trivial FCA concepts. A wrong/empty runner yields
# zero concepts (the honest RED baseline).
_MATH = [
    "ALIGNS_WITH_AXIS:Structural Mathematics",
    "USES_ABSTRACT_DOMAIN:Algebraic and Topological Structure",
]
_COMP = [
    "ALIGNS_WITH_AXIS:Machine and Resource",
    "USES_ABSTRACT_DOMAIN:Intermediate Representation and Lowering",
]
_CLUSTER = [
    {"object": "Topology", "attributes": _MATH},
    {"object": "Group Theory", "attributes": _MATH},
    {"object": "Abstract Algebra", "attributes": _MATH},
    {"object": "Spectral Sequences", "attributes": _MATH},
    {"object": "Operators", "attributes": _COMP},
    {"object": "Writing the Grammar", "attributes": _COMP},
    {"object": "Using Parsers", "attributes": _COMP},
    {"object": "Basic Syntax", "attributes": _COMP},
]


def _cluster_runner(_query, _params):
    """run_cypher seam returning the seeded 8-object cluster rows (boundary I/O injection)."""
    return list(_CLUSTER)


def _ev(cid: str, event: str, **attrs) -> dict:
    """Shape one trace event the way the memory backend keys + counts it (cid + event)."""
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "bhgman.eureka",
        "event": event,
        **attrs,
    }


def _stage_count(pr, name_startswith: str, key: str) -> int:
    """Re-derive a count from the real PipelineRun stage payload (never from stages_ok)."""
    for s in pr.stages:
        if s.stage.startswith(name_startswith) and isinstance(s.payload, dict):
            return int(s.payload.get(key, 0) or 0)
    return 0


def emit_induction_phase(backend, cid: str, pr) -> tuple[int, int]:
    """Ship one 'eureka_concepts_induced' per induced AbstractClass and one
    'eureka_quality_survivor' per concept clearing the FCA_STABILITY_MIN floor. Counts
    RE-DERIVED from the real PipelineRun stages — NEVER from stages_ok. Both literals live here."""
    n_induced = _stage_count(pr, "4-induce", "abstract_classes")
    n_survived = _stage_count(pr, "4.5-quality-gate", "survived")
    for i in range(n_induced):
        backend.ship([_ev(cid, "eureka_concepts_induced", idx=i)])
    for i in range(n_survived):
        backend.ship([_ev(cid, "eureka_quality_survivor", idx=i)])
    return n_induced, n_survived


def emit_persist_phase(backend, cid: str, captured: list[dict]) -> int:
    """Ship one 'eureka_abstraction_persisted' per row the REAL stage_6_persist wrote, carrying
    the real verdictStatus. Count = real persisted rows. The
    literal lives here."""
    for params in captured:
        backend.ship(
            [
                _ev(
                    cid,
                    "eureka_abstraction_persisted",
                    name=params.get("name"),
                    verdictStatus=params.get("verdictStatus"),
                )
            ]
        )
    return len(captured)


def run_eureka_pipeline(backend, cid: str, *, run_cypher=None) -> dict:
    """Loop entry (called as ``run_eureka_pipeline(backend, cid)``). Runs the REAL
    ``run_from_kg`` (FCA induce -> quality gate -> naesengmoon -> persist) over the seeded
    cluster, persisting VERDICT_PENDING, and ships the lifecycle under ``cid``. The
    'eureka_cycle_started' and 'eureka_cycle_complete' literals live verbatim in THIS symbol.

    ``run_cypher`` defaults to the 8-object cluster so the loop's 2-arg call drives the green
    path; the twin test overrides it with an empty runner for the drop-the-seed RED proof."""
    run_cypher = _cluster_runner if run_cypher is None else run_cypher
    captured: list[dict] = []

    def persist_cypher(_cypher, params):
        captured.append(dict(params))  # the boundary write seam — real stage_6_persist drives it
        return []

    cfg = PipelineConfig(
        cycle_id="eureka-ooptdd", persist_cypher=persist_cypher, persist_accept=False
    )
    pr = run_from_kg(run_cypher, cfg)

    backend.ship([_ev(cid, "eureka_cycle_started", phase="induce")])
    n_induced, n_survived = emit_induction_phase(backend, cid, pr)
    n_persisted = emit_persist_phase(backend, cid, captured)
    backend.ship(
        [
            _ev(
                cid,
                "eureka_cycle_complete",
                induced=n_induced,
                survived=n_survived,
                persisted=n_persisted,
            )
        ]
    )
    return {"induced": n_induced, "survived": n_survived, "persisted": n_persisted}


__all__ = ["emit_induction_phase", "emit_persist_phase", "run_eureka_pipeline"]
