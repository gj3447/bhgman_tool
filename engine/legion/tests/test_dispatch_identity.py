"""출격(dispatch) 정체성의 정직 강등 oracle (jbm-s4, gap G5 of audit wf_376c327b-8f3).

RED-first: the retrospective limit of the legion-path 재배맨 substrate ("the Dispatcher
is a lambda mapping ALREADY-finished stage outcomes — no seed is actually dispatched
there") lived ONLY in a docstring — no ADR record, no machine oracle. That leaves both
silent failure modes open: a silent *promotion* (someone wires a real dispatcher and
the identity claim changes without an ADR) and silent *theater* (the docstring drifts
from behavior). This file pins the demotion in both directions:

  * test_adr_pins_retrospective_demotion — the ADR addendum with clause markers
    G5-C1..C4 exists and each carries its load-bearing phrase (the RED artifact:
    written before the addendum).
  * test_legion_path_status_writes_are_terminal_only — behavioral pin of G5-C2:
    lifecycle status writes carry ONLY terminal statuses (no in-flight DISPATCHED).
  * test_mapping_happens_after_legion_completed — behavioral pin of G5-C1: the seed
    mapping (drive_seeds) runs strictly AFTER every stage executed (sequence probe —
    retrospective by measurement, not by docstring).
  * test_degrade_still_terminal_only — the demotion holds on the halt path too
    (a degraded run maps FAILED, never a stuck in-flight status).

Promotion to dispatcher-driven execution requires replacing the ADR section AND this
oracle — 무음 승격 불가.

# KG: LakatosTree_BhgmanJaebaeman_20260702/jbm_s4_dispatch_identity_honest
# KG: adr-legion-runtime-shape-review-2026-06-20
# KG: 재배맨-v2-subagent-runtime-protocol
"""

from __future__ import annotations

from pathlib import Path

from engine.kg_local.runner import make_local_runner
from engine.kg_local.store import LocalKgStore
from engine.legion import jaebaeman_substrate
from engine.legion.jaebaeman_substrate import run_legion_via_jaebaeman
from engine.legion.legion import Legion
from engine.legion.legion_models import CommanderStage

ADR_PATH = (
    Path(__file__).resolve().parents[3] / "ADRs" / "legion-runtime-shape-review-2026-06-20.md"
)

# Clause markers + the load-bearing phrase each clause must carry (checked within the
# marker's own region, so a phrase elsewhere in the ADR cannot vacuously satisfy it).
REQUIRED_CLAUSES: dict[str, list[str]] = {
    "G5-C1": ["retrospective", "legion.run"],
    "G5-C2": ["DISPATCHED"],
    "G5-C3": ["germinate"],
    "G5-C4": ["oracle"],
}


def check_adr_clauses(text: str) -> dict[str, bool]:
    """clause id → (marker present AND its phrases live inside that marker's region).

    Region = from the marker to the next clause marker (or end of text) — shared by
    the judge script, so test and judge cannot drift on what counts as pinned.
    """
    out: dict[str, bool] = {}
    ids = list(REQUIRED_CLAUSES)
    for cid in ids:
        start = text.find(cid)
        if start < 0:
            out[cid] = False
            continue
        nexts = [p for p in (text.find(c, start + len(cid)) for c in ids) if p > start]
        region = text[start : min(nexts)] if nexts else text[start:]
        out[cid] = all(ph in region for ph in REQUIRED_CLAUSES[cid])
    return out


def test_adr_pins_retrospective_demotion():
    """Doc oracle: the ADR must carry the G5 demotion clauses — the limit is a recorded
    architecture decision, not a docstring aside."""
    text = ADR_PATH.read_text(encoding="utf-8")
    clauses = check_adr_clauses(text)
    missing = [cid for cid, ok in clauses.items() if not ok]
    assert not missing, f"ADR must pin the G5 demotion clauses; missing/incomplete: {missing}"


def _run_substrate(cycle_id: str) -> dict:
    store = LocalKgStore()
    run_cypher = make_local_runner(store, autosave=False)
    ctx = {"run_cypher": run_cypher, "cycle_id": cycle_id}
    return run_legion_via_jaebaeman(ctx, run_id=cycle_id, write_cypher=run_cypher, apply=False)


def test_legion_path_status_writes_are_terminal_only():
    """G5-C2 behavioral pin: the legion path plans ONLY terminal transitions — a seed is
    never left (or even planned) in an in-flight DISPATCHED state there."""
    result = _run_substrate("jbm-s4-terminal")
    writes = result["lifecycle"].planned_status_writes
    assert writes, "lifecycle must plan terminal status writes"
    statuses = {params["status"] for _cypher, params in writes}
    assert statuses <= {"COLLECTED", "FAILED"}, (
        f"no in-flight DISPATCHED may appear on the legion path: {statuses}"
    )


def test_mapping_happens_after_legion_completed(monkeypatch):
    """G5-C1 behavioral pin: the seed mapping runs strictly AFTER every stage executed —
    retrospective by measured sequence, not by docstring claim."""
    events: list[str] = []
    real_build = jaebaeman_substrate.build_default_legion
    real_drive = jaebaeman_substrate.drive_seeds

    def probed_build() -> Legion:
        legion = Legion()
        for s in real_build()._stages:  # noqa: SLF001 — probe wraps the real stages 1:1

            def make_run(stage: CommanderStage):
                def run(ctx: dict) -> dict:
                    events.append(f"stage:{stage.name}")
                    return stage.run(ctx)

                return run

            legion.register(
                CommanderStage(
                    name=s.name,
                    verb=s.verb,
                    requires=s.requires,
                    provides=s.provides,
                    run=make_run(s),
                    measure=s.measure,
                )
            )
        return legion

    def probed_drive(*args, **kwargs):
        events.append("drive_seeds")
        return real_drive(*args, **kwargs)

    monkeypatch.setattr(jaebaeman_substrate, "build_default_legion", probed_build)
    monkeypatch.setattr(jaebaeman_substrate, "drive_seeds", probed_drive)

    _run_substrate("jbm-s4-order")

    assert "drive_seeds" in events
    stage_events = [e for e in events if e.startswith("stage:")]
    assert len(stage_events) == 6
    assert events.index("drive_seeds") > max(events.index(e) for e in stage_events), (
        f"mapping must run AFTER all stages: {events}"
    )


def test_degrade_still_terminal_only(monkeypatch):
    """The demotion holds on the halt path: a degraded run maps FAILED (post-hoc halt
    cascade), never a stuck in-flight status."""
    real_build = jaebaeman_substrate.build_default_legion

    def degraded_build() -> Legion:
        stages = list(real_build()._stages)  # noqa: SLF001
        last = stages[-1]
        legion = Legion()
        for s in stages[:-1]:
            legion.register(s)
        legion.register(
            CommanderStage(
                name=last.name,
                verb=last.verb,
                requires=last.requires,
                provides=last.provides,
                run=lambda _ctx: {},
                measure=None,
            )
        )
        return legion

    monkeypatch.setattr(jaebaeman_substrate, "build_default_legion", degraded_build)
    result = _run_substrate("jbm-s4-degraded")

    writes = result["lifecycle"].planned_status_writes
    statuses = {params["status"] for _cypher, params in writes}
    assert "FAILED" in statuses, "the halt cascade must surface as terminal FAILED"
    assert statuses <= {"COLLECTED", "FAILED"}, f"halt path too: terminal-only, got {statuses}"
