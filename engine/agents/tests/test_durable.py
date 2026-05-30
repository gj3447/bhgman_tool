"""durable.py 테스트 — AX durable execution 흡수 hard core 4 invariant 검증.

# KG: pattern-ax-durable-execution-2026-05-30, vp-bhgman-durable-dispatch-layer-2026-05-30
"""

from __future__ import annotations

import pytest

from dispatch import SubagentResult, SubagentSpec
from durable import CycleInFlight, DurableDispatcher, EventLog


# --- fake client: dispatch_parallel이 client.complete(system,user,model,...)을 호출 ---
class _Comp:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeClient:
    """user 프롬프트에 'FAIL'이 들어있으면 예외(→ dispatch_parallel이 ok=False로 격리)."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete(self, *, system, user, model, max_tokens=2048, web_search=False, **kw):
        self.calls.append(user)
        if "FAIL" in user:
            raise RuntimeError("boom")
        return _Comp(f"done:{user}")


def _spec(name: str, fail: bool = False) -> SubagentSpec:
    return SubagentSpec(name=name, system="s", user=f"{name}{'-FAIL' if fail else ''}")


@pytest.fixture
def log(tmp_path):
    el = EventLog(str(tmp_path / "events.db"))
    yield el
    el.close()


# === invariant 1+2: append-only event log + monotonic seq ===
def test_cycle_event_seq_monotonic_per_cycle(log):
    assert log.append_cycle_event("c1", "A") == 1
    assert log.append_cycle_event("c1", "B") == 2
    assert log.append_cycle_event("c1", "C") == 3
    assert log.append_cycle_event("c2", "A") == 1  # 다른 cycle은 독립 seq
    seqs = [e["seq"] for e in log.cycle_events("c1")]
    assert seqs == [1, 2, 3]


def test_event_signature_roundtrip_and_tamper(log):
    log.append_cycle_event("c1", "START", {"total": 3})
    ev = log.cycle_events("c1")[0]
    assert EventLog.verify_cycle_event(ev, "c1") is True
    ev["payload"]["total"] = 999  # 변조
    assert EventLog.verify_cycle_event(ev, "c1") is False


# === invariant 3: replay — completed_specs는 최신 행, ok=True만 ===
def test_record_spec_append_only_latest_wins(log):
    log.record_spec("c1", SubagentResult("B", False, "", "err1"))  # 실패 먼저
    assert "B" not in log.completed_specs("c1")  # 실패는 미완료
    log.record_spec("c1", SubagentResult("B", True, "ok-text"))  # 재시도 성공(새 행)
    done = log.completed_specs("c1")
    assert "B" in done and done["B"].text == "ok-text"


# === invariant 4: single-writer 게이트 ===
def test_single_writer_gate_rejects_reentrant(log):
    d = DurableDispatcher(log, db_key="t")
    gate = d._gate_for("c1")
    gate.acquire()  # 외부에서 점유 = 'in flight' 시뮬
    try:
        with pytest.raises(CycleInFlight):
            d.run("c1", [_spec("A")], FakeClient())
    finally:
        gate.release()


# === durable dispatch 기본 ===
def test_durable_dispatch_basic_order_and_persist(log):
    d = DurableDispatcher(log, db_key="t")
    client = FakeClient()
    specs = [_spec("A"), _spec("B"), _spec("C")]
    res = d.run("c1", specs, client)
    assert [r.name for r in res] == ["A", "B", "C"]  # 순서 보존
    assert all(r.ok for r in res)
    assert len(client.calls) == 3
    kinds = [e["kind"] for e in log.cycle_events("c1")]
    assert kinds[0] == "CYCLE_STARTED" and kinds[-1] == "CYCLE_COMPLETED"


# === resume: 완료분 skip, 미완료만 재출격 ===
def test_resume_skips_completed(log):
    d = DurableDispatcher(log, db_key="t")
    # A는 이미 완료된 것으로 사전 기록
    log.record_spec("c1", SubagentResult("A", True, "pre-A"))
    client = FakeClient()
    res = d.run("c1", [_spec("A"), _spec("B")], client)
    assert [r.name for r in res] == ["A", "B"]
    assert res[0].text == "pre-A"  # A는 replay(재출격 안 함)
    assert client.calls == ["B"]  # B만 출격
    assert [e["kind"] for e in log.cycle_events("c1")][0] == "CYCLE_RESUMED"


# === crash-resume: 실패 spec만 재출격 ===
def test_crash_resume_redispatches_only_failed(log):
    d = DurableDispatcher(log, db_key="t")
    # 1차: B 실패
    specs = [_spec("A"), _spec("B", fail=True)]
    res1 = d.run("c1", specs, FakeClient())
    assert res1[0].ok and not res1[1].ok

    # 2차(resume): B를 성공하도록 — 같은 cycle_id로 재호출, A는 replay, B만 재출격
    client2 = FakeClient()
    res2 = d.run("c1", [_spec("A"), _spec("B")], client2)  # 이번 B는 FAIL 없음
    assert [r.name for r in res2] == ["A", "B"]
    assert all(r.ok for r in res2)
    assert client2.calls == ["B"]  # A는 replay, B만 재출격


def test_idempotent_full_replay_no_redispatch(log):
    d = DurableDispatcher(log, db_key="t")
    specs = [_spec("A"), _spec("B")]
    d.run("c1", specs, FakeClient())
    client2 = FakeClient()
    res = d.run("c1", specs, client2)  # 전부 완료 → 재출격 0
    assert all(r.ok for r in res)
    assert client2.calls == []
