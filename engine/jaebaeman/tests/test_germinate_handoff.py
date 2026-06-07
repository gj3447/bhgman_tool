"""씨앗→발아→동작 핸드오프 TDD — READY 씨앗 read-back + germinate.

이전엔 심긴 READY :SubagentTaskSpec를 다시 읽어 dispatch하는 코드가 부재해, KG에 심긴 씨앗이
dispatch 입장에선 dead-end였다 (감사 finding-jaebaeman-seed-dispatch-handoff-unwired-2026-06-07).
이 테스트가 read_ready_seeds(read-back) + germinate_ready_seeds(handoff) 배선을 고정한다.

# KG: finding-jaebaeman-seed-dispatch-handoff-unwired-2026-06-07, 재배맨-v2-subagent-runtime-protocol
"""

from __future__ import annotations

from engine.jaebaeman.jaebaeman_models import SeedRecord, SeedStatus
from engine.jaebaeman.jaebaeman_runner import germinate_ready_seeds
from engine.jaebaeman.kg_adapter import (
    FORBIDDEN_TOKENS,
    build_decomposes_to_edge,
    plant_seeds,
    read_ready_seeds,
    ready_seeds_cypher,
)
from engine.jaebaeman.lifecycle import SeedOutcome

_READY_ROWS = [
    {
        "name": "seed-a",
        "skill": "jaebaeman",
        "sourceId": "anchor-x",
        "displayName": "do a",
        "taskType": "research",
        "targetDomain": "kg",
        "expectedOutcome": "artifact-a",
        "germinationMethod": "decompose",
        "depth": 1,
        "parent": "root-0",
    },
    {
        "name": "root-0",
        "skill": "jaebaeman",
        "sourceId": "root-0",
        "displayName": "root",
        "taskType": "research",
        "targetDomain": "",
        "expectedOutcome": "",
        "germinationMethod": "singleton",
        "depth": 0,
        "parent": None,
    },
]


class _Reader:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        return list(self.rows)


class _Writer:
    def __init__(self):
        self.calls = []

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        return [{"updated": params.get("name")}]


class _CapturingDispatcher:
    """씨앗을 받아 전부 COLLECTED 반환 + 받은 씨앗 기록 (핸드오프 도달 검증)."""

    def __init__(self):
        self.received: list[SeedRecord] | None = None

    def __call__(self, seeds):
        self.received = list(seeds)
        return [SeedOutcome(s.name, SeedStatus.COLLECTED, "ok") for s in seeds]


# ── read_ready_seeds: KG row → SeedRecord 복원 ───────────────────────────────
def test_read_ready_seeds_reconstructs_seedrecords():
    seeds = read_ready_seeds(_Reader(_READY_ROWS))
    assert [s.name for s in seeds] == ["seed-a", "root-0"]
    a = seeds[0]
    assert isinstance(a, SeedRecord)
    assert a.source_id == "anchor-x" and a.parent == "root-0"
    assert a.depth == 1 and a.germination_method == "decompose"
    assert seeds[1].parent is None  # 루트는 DECOMPOSES_TO 부모 없음


def test_read_ready_seeds_query_filters_ready_status():
    reader = _Reader([])
    read_ready_seeds(reader)
    cypher, _ = reader.calls[0]
    assert ":SubagentTaskSpec" in cypher
    assert "status = 'READY'" in cypher


def test_read_ready_seeds_is_read_only_no_destructive_tokens():
    cypher, _ = ready_seeds_cypher()
    up = cypher.upper()
    assert all(tok not in up for tok in FORBIDDEN_TOKENS)
    assert "MERGE" not in up and "SET " not in up


def test_ready_seeds_cypher_limit():
    none_c, none_p = ready_seeds_cypher()
    lim_c, lim_p = ready_seeds_cypher(5)
    assert "LIMIT" not in none_c and none_p == {}
    assert "LIMIT $limit" in lim_c and lim_p == {"limit": 5}


def test_ready_seeds_cypher_cycle_scope():
    none_c, none_p = ready_seeds_cypher()
    cyc_c, cyc_p = ready_seeds_cypher(cycle_id="run-7")
    assert "cycleId" not in none_c and none_p == {}
    assert "s.cycleId = $cycle_id" in cyc_c and cyc_p == {"cycle_id": "run-7"}


def test_germinate_scopes_by_cycle_id():
    reader = _Reader(_READY_ROWS)
    germinate_ready_seeds(_CapturingDispatcher(), reader, cycle_id="run-7")
    _, params = reader.calls[0]
    assert params.get("cycle_id") == "run-7"  # 전역 무차별 발아 방지 — cycle scope 전달


def test_read_ready_seeds_coalesce_defaults_on_sparse_row():
    seeds = read_ready_seeds(_Reader([{"name": "bare", "parent": None}]))
    s = seeds[0]
    assert s.skill == "jaebaeman" and s.source_id == "bare"
    assert s.task_type == "research" and s.germination_method == "manual"
    assert s.depth == 0


# ── germinate_ready_seeds: 핸드오프 (read-back → dispatch → status) ───────────
def test_germinate_apply_feeds_readback_seeds_to_dispatcher():
    disp = _CapturingDispatcher()
    germinate_ready_seeds(disp, _Reader(_READY_ROWS), cycle_id="run-7", apply=True)
    # 핸드오프 도달: dispatcher가 KG에서 읽힌 씨앗을 실제로 받았다 (이전엔 dead-end였음)
    assert disp.received is not None
    assert {s.name for s in disp.received} == {"seed-a", "root-0"}


def test_germinate_dry_run_skips_dispatch_and_write():
    # apply=False면 dispatch 미실행(LLM 비용 0) + write 없음 — apply가 dispatch+write 공통 게이트
    writer = _Writer()
    disp = _CapturingDispatcher()
    res = germinate_ready_seeds(disp, _Reader(_READY_ROWS), cycle_id="run-7", write_cypher=writer)
    assert res.dry_run and res.applied_count == 0
    assert disp.received is None  # dispatcher 호출 안 됨 (LLM 0)
    assert writer.calls == []
    assert any("2" in n for n in res.notes)  # 발아 대기 2개 보고


def test_germinate_apply_writes_status_transitions():
    writer = _Writer()
    res = germinate_ready_seeds(
        _CapturingDispatcher(),
        _Reader(_READY_ROWS),
        cycle_id="run-7",
        write_cypher=writer,
        apply=True,
    )
    assert not res.dry_run and res.applied_count == 2
    written = {p["name"]: p["status"] for _, p in writer.calls}
    assert written == {"seed-a": "COLLECTED", "root-0": "COLLECTED"}


def test_germinate_empty_ready_set_is_noop():
    writer = _Writer()
    res = germinate_ready_seeds(
        _CapturingDispatcher(), _Reader([]), cycle_id="run-7", write_cypher=writer, apply=True
    )
    assert res.outcomes == () and writer.calls == []


def test_germinate_failure_isolated():
    def half_fail(seeds):
        return [
            SeedOutcome(s.name, SeedStatus.COLLECTED if i == 0 else SeedStatus.FAILED, "x")
            for i, s in enumerate(seeds)
        ]

    res = germinate_ready_seeds(half_fail, _Reader(_READY_ROWS), cycle_id="run-7", apply=True)
    assert res.collected == 1 and res.failed == 1


# ── 실제 local KG backend 라운드트립 (fake 아닌 진짜 store — blocker 회귀 가드) ──
def _local_runner(tmp_path):
    from engine.kg_local.runner import make_local_runner
    from engine.kg_local.store import LocalKgStore

    store = LocalKgStore(tmp_path / "kg.json")
    return make_local_runner(store, autosave=False)


def _rec(name, parent, depth, src=None):
    return SeedRecord(
        name=name,
        skill="jaebaeman",
        source_id=src or name,
        display_name=f"do {name}",
        task_type="research",
        target_domain="",
        expected_outcome="out",
        germination_method="decompose" if parent else "singleton",
        depth=depth,
        parent=parent,
    )


def test_local_backend_roundtrip_plant_read_germinate(tmp_path):
    run = _local_runner(tmp_path)
    seeds = [_rec("s-root", None, 0), _rec("s-leaf", "s-root", 1, src="s-root")]
    plant_seeds(seeds, write_cypher=run, cycle_id="cyc-A", dry_run=False)

    got = read_ready_seeds(run, cycle_id="cyc-A")
    assert {s.name for s in got} == {"s-root", "s-leaf"}
    leaf = next(s for s in got if s.name == "s-leaf")
    assert leaf.parent == "s-root" and leaf.depth == 1
    assert read_ready_seeds(run, cycle_id="other-cycle") == []  # cycle scope 격리

    disp = _CapturingDispatcher()
    res = germinate_ready_seeds(disp, run, cycle_id="cyc-A", write_cypher=run, apply=True)
    assert res.collected == 2
    assert {s.name for s in disp.received} == {"s-root", "s-leaf"}
    assert read_ready_seeds(run, cycle_id="cyc-A") == []  # COLLECTED → 더는 READY 아님


def test_local_read_dedupes_multi_parent_seed(tmp_path):
    run = _local_runner(tmp_path)
    plant_seeds(
        [_rec("root1", None, 0), _rec("root2", None, 0), _rec("child", "root1", 1, src="root1")],
        write_cypher=run,
        cycle_id="cyc",
        dry_run=False,
    )
    # child에 두 번째 부모(root2) DECOMPOSES_TO 추가 → DAG (다중 부모)
    run(*build_decomposes_to_edge(_rec("child", "root2", 1)))
    got = read_ready_seeds(run, cycle_id="cyc")
    assert [s.name for s in got].count("child") == 1  # 다중 부모여도 1행 (dedupe)
