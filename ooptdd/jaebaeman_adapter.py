"""ooptdd-loop in_process target — binds the jaebaeman 출격(sortie) lifecycle to the
REAL engine chain (``plant_seeds`` -> ``read_ready_seeds`` -> ``drive_seeds``).

This is the system-under-test the loop calls as ``run_jaebaeman_pipeline(backend, cid)``.
It does NOT fake the trace: every event it ships is produced by genuinely running the
engine's plant (MERGE-only covenant) -> READY read-back (store join) -> germinate
(dispatcher outcomes + applied status writes) chain over an in-adapter seed store that
EXECUTES the engine's real cyphers.

Honest-count contract (verified before writing, STEP-0 baseline):
    A dry-run plant executes NO write, so the store stays empty and ``read_ready_seeds``
    joins back 0 rows — every ==N gate is therefore GENUINELY RED until the real chain
    populates the store. To EARN nonzero counts the apply wing lands the 3-seed fixture
    via the engine's own MERGE cyphers, reads the READY seeds back OUT of the store (the
    join crux — a seed that never landed cannot come back), and drives them to COLLECTED
    through ``drive_seeds`` with applied status writes. Every shipped count is RE-DERIVED
    from the store / the real read-back / the real ``LifecycleResult`` — never a
    hand-typed number and never an echo of the input list.

Longinus binding (AST-checked by ``ooptdd_loop.longinus.verify_binding``):
    Each must_emit event-name string literal lives VERBATIM, as a string constant, inside
    the body of the ADAPTER symbol that ships it (``emit_plant_phase`` /
    ``emit_ready_phase`` / ``emit_germinate_phase`` / ``run_jaebaeman_pipeline``) — and
    those are exactly the events shipped. The literals live ONLY here, NEVER inside
    ``engine/jaebaeman/`` (the engine stays key-free, I/O-free, emit-free so its pure
    unit tests and the LLM-disjoint floor are preserved). Rename a literal => UNBOUND/RED.

# KG: finding-ooptdd-bhgman-jaebaeman-adapter-20260702
# KG: 재배맨-v2-subagent-runtime-protocol
"""
from __future__ import annotations

from engine.jaebaeman.jaebaeman_models import SeedApplyResult, SeedRecord, SeedStatus
from engine.jaebaeman.kg_adapter import plant_seeds, read_ready_seeds
from engine.jaebaeman.lifecycle import LifecycleResult, SeedOutcome, drive_seeds

_KG_ANCHOR = "finding-ooptdd-bhgman-jaebaeman-adapter-20260702"
_CYCLE_ID = "jaebaeman-ooptdd"

# The 3-seed plan-tree fixture: one self-anchored root (source_id == name => no HAS_SEED
# edge) and two children anchored to it (HAS_SEED + DECOMPOSES_TO edges). Depths mirror
# the germination generations (root=0, children=1) — the depth-pinned gate checks split
# exactly along this shape.
_SEEDS = (
    SeedRecord(
        name="jbm-root-goal",
        skill="jaebaeman",
        source_id="jbm-root-goal",
        display_name="재배맨 루트 계획",
        task_type="research",
        target_domain="bhgman",
        expected_outcome="계획 트리를 씨앗으로 심는다",
        germination_method="decompose",
        depth=0,
        parent=None,
    ),
    SeedRecord(
        name="jbm-leaf-a",
        skill="jaebaeman",
        source_id="jbm-root-goal",
        display_name="재배맨 잎 A",
        task_type="research",
        target_domain="bhgman",
        expected_outcome="잎 A 수행",
        germination_method="singleton",
        depth=1,
        parent="jbm-root-goal",
    ),
    SeedRecord(
        name="jbm-leaf-b",
        skill="jaebaeman",
        source_id="jbm-root-goal",
        display_name="재배맨 잎 B",
        task_type="research",
        target_domain="bhgman",
        expected_outcome="잎 B 수행",
        germination_method="singleton",
        depth=1,
        parent="jbm-root-goal",
    ),
)


class _SeedStore:
    """An in-memory seed table that EXECUTES the engine's real cyphers (the same DIP seam
    the engine exposes as ``CypherRunner``). It is the arrival side of the plant->read-back
    join: only what ``plant_seeds`` genuinely wrote can ever come back out. MATCH semantics
    are honoured — an edge whose endpoints never landed records nothing."""

    def __init__(self) -> None:
        self.seeds: dict[str, dict] = {}  # name -> merged row (+ status)
        self.has_seed: list[tuple[str, str]] = []  # (anchor, seed)
        self.decomposes: list[tuple[str, str]] = []  # (parent, child)

    # -- write seam (plant_seeds / drive_seeds hand the REAL cyphers here) --------------
    def write(self, cypher: str, params: dict) -> list[dict]:
        up = cypher.upper()
        # mirror the engine covenant at the seam: seeds are PLANTED, never uprooted.
        assert not any(t in up for t in ("DELETE", "DETACH", "REMOVE")), cypher
        if "MERGE (s:SubagentTaskSpec {name: $name})" in cypher:
            self.seeds[params["name"]] = {**params, "status": "READY"}
            return [{"seeded": params["name"]}]
        if "MERGE (a)-[r:HAS_SEED]->(s)" in cypher:
            if params["anchor"] in self.seeds and params["seed"] in self.seeds:
                self.has_seed.append((params["anchor"], params["seed"]))
                return [{"linked": params["seed"]}]
            return []  # MATCH found no endpoints — nothing recorded
        if "MERGE (p)-[:DECOMPOSES_TO]->(c)" in cypher:
            if params["parent"] in self.seeds and params["child"] in self.seeds:
                self.decomposes.append((params["parent"], params["child"]))
                return [{"child": params["child"]}]
            return []
        if "SET s.status = $status" in cypher:
            row = self.seeds.get(params["name"])
            if row is None:
                return []
            row["status"] = params["status"]
            return [{"updated": params["name"]}]
        raise AssertionError(f"unrecognized write cypher: {cypher[:80]}")

    # -- read seam (read_ready_seeds hands the REAL ready-seeds cypher here) ------------
    def run(self, cypher: str, params: dict) -> list[dict]:
        if "s.status = 'READY'" not in cypher:
            raise AssertionError(f"unrecognized read cypher: {cypher[:80]}")
        rows = []
        for name, r in self.seeds.items():
            if r["status"] != "READY":
                continue
            if "$cycle_id" in cypher and r.get("cycle_id") != params.get("cycle_id"):
                continue
            parent = next((p for p, c in self.decomposes if c == name), None)
            rows.append(
                {
                    "name": r["name"],
                    "skill": r["skill"],
                    "sourceId": r["sourceId"],
                    "displayName": r["displayName"],
                    "taskType": r["taskType"],
                    "targetDomain": r["targetDomain"],
                    "expectedOutcome": r["expectedOutcome"],
                    "germinationMethod": r["germinationMethod"],
                    "depth": r["depth"],
                    "parent": parent,
                }
            )
        rows.sort(key=lambda x: (x["depth"], x["name"]))
        if "$limit" in cypher:
            rows = rows[: params["limit"]]
        return rows


def _collect_dispatcher(seeds: list[SeedRecord]) -> list[SeedOutcome]:
    """Deterministic sortie: every READY seed is dispatched and COLLECTED (the real
    ``agent_dispatcher`` is LLM-backed; the trace gate needs the LLM-disjoint floor)."""
    return [
        SeedOutcome(seed_name=s.name, status=SeedStatus.COLLECTED, detail="ooptdd sortie")
        for s in seeds
    ]


def _ev(cid: str, event: str, **attrs) -> dict:
    """Shape one trace event the way the memory backend keys + counts it (cid + event)."""
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "bhgman.jaebaeman",
        "event": event,
        **attrs,
    }


def _run_real_sortie(
    seeds=None, *, apply: bool = True
) -> tuple[_SeedStore, list[SeedRecord], SeedApplyResult, LifecycleResult]:
    """Drive the REAL plant -> read-back -> germinate chain over one seed store. Every
    downstream count is RE-DERIVED from these artifacts (store rows / joined read-back /
    ``LifecycleResult``)."""
    seeds = list(_SEEDS if seeds is None else seeds)
    store = _SeedStore()
    plant = plant_seeds(seeds, write_cypher=store.write, cycle_id=_CYCLE_ID, dry_run=not apply)
    readback = read_ready_seeds(store.run, cycle_id=_CYCLE_ID)
    lifecycle = drive_seeds(readback, _collect_dispatcher, write_cypher=store.write, apply=apply)
    return store, readback, plant, lifecycle


def emit_plant_phase(backend, cid: str, store: _SeedStore) -> int:
    """Ship one 'jaebaeman_seed_planted' per seed PK the real ``plant_seeds`` landed in
    the store, carrying its depth. Count RE-DERIVED from the store rows (a dry-run plant
    lands nothing => 0 events => RED). The literal 'jaebaeman_seed_planted' lives
    verbatim here — Longinus AST-checks THIS symbol."""
    for name, row in sorted(store.seeds.items()):
        backend.ship([_ev(cid, "jaebaeman_seed_planted", seed=name, depth=row["depth"])])
    return len(store.seeds)


def emit_ready_phase(backend, cid: str, readback: list[SeedRecord]) -> int:
    """Ship one 'jaebaeman_seed_ready' per SeedRecord the real ``read_ready_seeds``
    JOINED back out of the store (never the input list — a seed that never landed
    cannot come back)."""
    for s in readback:
        backend.ship([
            _ev(cid, "jaebaeman_seed_ready", seed=s.name, depth=s.depth, parent=s.parent)
        ])
    return len(readback)


def emit_germinate_phase(backend, cid: str, store: _SeedStore) -> int:
    """Ship one 'jaebaeman_seed_germinated' per seed whose APPLIED status write landed
    COLLECTED at the store (the real ``drive_seeds`` Phase-4 write, observed at the
    arrival side — a dry-run drive leaves rows READY => 0 events => RED)."""
    n = 0
    for name, row in sorted(store.seeds.items()):
        if row["status"] == SeedStatus.COLLECTED.value:
            backend.ship([_ev(cid, "jaebaeman_seed_germinated", seed=name, status=row["status"])])
            n += 1
    return n


def run_jaebaeman_pipeline(backend, cid: str, *, seeds=None, apply: bool = True) -> dict:
    """Loop entry point (called as ``run_jaebaeman_pipeline(backend, cid)``). Runs the REAL
    sortie and ships the full lifecycle under ``cid``. The 'jaebaeman_sortie_started' and
    'jaebaeman_sortie_completed' literals live verbatim in THIS symbol's body — Longinus
    AST-checks ``run_jaebaeman_pipeline`` for the completion event.

    ``seeds``/``apply`` default to the real fixture so the loop's 2-arg call drives the
    green path; the twin tests override them for the seed-drop / dry-run RED proofs.
    """
    store, readback, plant, _lifecycle = _run_real_sortie(seeds, apply=apply)

    backend.ship([_ev(cid, "jaebaeman_sortie_started", phase="plant")])
    n_planted = emit_plant_phase(backend, cid, store)
    n_ready = emit_ready_phase(backend, cid, readback)
    n_germinated = emit_germinate_phase(backend, cid, store)
    backend.ship([
        _ev(cid, "jaebaeman_sortie_completed", dry_run=plant.dry_run,
            planted=n_planted, ready=n_ready, germinated=n_germinated)
    ])
    return {
        "planted": n_planted,
        "ready": n_ready,
        "germinated": n_germinated,
        "dry_run": plant.dry_run,
    }


__all__ = [
    "emit_germinate_phase",
    "emit_plant_phase",
    "emit_ready_phase",
    "run_jaebaeman_pipeline",
]
