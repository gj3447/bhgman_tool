"""씨앗 lifecycle 구동 TDD — 4-phase SOP 폐루프 (dispatch→collect→status write).

# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01, 재배맨-v2-subagent-runtime-protocol
"""

from __future__ import annotations

from engine.jaebaeman.jaebaeman_models import SeedRecord, SeedStatus
from engine.jaebaeman.lifecycle import (
    FORBIDDEN_TOKENS,
    SeedOutcome,
    agent_dispatcher,
    build_status_write,
    drive_seeds,
)


def _seed(name):
    return SeedRecord(
        name=name,
        skill="jaebaeman",
        source_id=name,
        display_name=f"do {name}",
        task_type="research",
        target_domain="",
        expected_outcome="artifact",
        germination_method="singleton",
        depth=0,
    )


class _Writer:
    def __init__(self):
        self.calls = []

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        return [{"updated": params.get("name")}]


def _all_ok(seeds):
    return [SeedOutcome(s.name, SeedStatus.COLLECTED, "ok") for s in seeds]


# ── covenant ─────────────────────────────────────────────────────────────────
def test_status_write_is_set_not_destructive():
    cypher, params = build_status_write(SeedOutcome("s0", SeedStatus.COLLECTED))
    up = cypher.upper()
    assert all(tok not in up for tok in FORBIDDEN_TOKENS)
    assert params == {"name": "s0", "status": "COLLECTED"}


# ── dry-run / apply ──────────────────────────────────────────────────────────
def test_dry_run_default_no_write():
    w = _Writer()
    res = drive_seeds([_seed("a"), _seed("b")], _all_ok, write_cypher=w)
    assert res.dry_run and res.applied_count == 0
    assert w.calls == []  # covenant: dry-run never writes
    assert res.collected == 2 and res.failed == 0


def test_apply_writes_status_transitions():
    w = _Writer()
    res = drive_seeds([_seed("a"), _seed("b")], _all_ok, write_cypher=w, apply=True)
    assert not res.dry_run and res.applied_count == 2
    assert len(w.calls) == 2
    assert {c[1]["status"] for c in w.calls} == {"COLLECTED"}


def test_failure_isolation():
    def mixed(seeds):
        return [
            SeedOutcome(s.name, SeedStatus.FAILED if s.name == "b" else SeedStatus.COLLECTED, "")
            for s in seeds
        ]

    res = drive_seeds([_seed("a"), _seed("b"), _seed("c")], mixed)
    assert res.collected == 2 and res.failed == 1  # b 실패가 a/c 막지 않음


def test_empty_seeds():
    res = drive_seeds([], _all_ok)
    assert res.outcomes == () and "DRY-RUN" in res.summary


# ── 실 dispatcher 어댑터 (fake client, 병렬 경로) ─────────────────────────────
def test_agent_dispatcher_via_fake_client():
    class _Comp:
        def __init__(self, text):
            self.text = text

    class _FakeClient:
        # **_kw absorbs the L4/L6 dispatch contract (temperature/seed/tier/tools/
        # tool_choice) that dispatch_parallel._run now forwards — same tolerant-double
        # pattern as _BoomClient below. web_search stays explicit for the budget assert.
        def complete(self, *, system, user, model, max_tokens=2048, web_search=False, **_kw):
            assert web_search is False  # 공정 예산 (web off)
            return _Comp(f"done: {user[:10]}")

    dispatch = agent_dispatcher(_FakeClient(), model="m", max_workers=2)
    outcomes = dispatch([_seed("a"), _seed("b")])
    assert len(outcomes) == 2
    assert all(o.status is SeedStatus.COLLECTED for o in outcomes)
    assert all(o.detail.startswith("done:") for o in outcomes)


def test_agent_dispatcher_isolates_client_failure():
    class _BoomClient:
        def complete(self, **_kw):
            raise RuntimeError("LLM down")

    dispatch = agent_dispatcher(_BoomClient(), model="m")
    outcomes = dispatch([_seed("a")])
    assert outcomes[0].status is SeedStatus.FAILED and "LLM down" in outcomes[0].detail
