"""Dispatch provenance 정직화 (T1-2) — 침묵 삼킴 실명화 + 약키 unsigned 정직 표기.

실측 격차 (2026-07-15):
  * legion._measure_and_dispatch — decide_dispatch 예외는 blanket except 로 무기록 증발,
    measure *팩토리* 예외는 try 밖이라 run 전체를 크래시 (양방향 오류: 은폐 vs 치명).
    dispatch_consumer 는 '침묵 패턴을 복제하지 않는다'고 명문화했지만 원본은 미수복.
  * :DispatchEvent HMAC — repo 에 공개된 dev-default 키로도 서명해 'tamper-evident' 를
    위장 (verdict_gate 는 같은 문자열을 hard-refuse 하는 비대칭). 키는 import-time frozen
    이라 장수 프로세스(bot/MCP)에서 env 변경이 반영 안 됨.

고정하는 계약: 측정 실패는 fail-soft + LegionRun.dispatch_errors 실명 기록 / 약키면
signature_status='unsigned_weak_key' 정직 표기(서명 위장 금지) / 키는 call-time 해석.

# KG: 7cmd-measurement-driven-conditional-dispatch-2026-05-30, cycle-bhgman-tier0-loop-wiring-2026-07-15
"""

from __future__ import annotations

import pytest

from engine.legion.legion import Legion
from engine.legion.legion_models import CommanderStage
from engine.legion.measurement import DISPATCH_HMAC_ENV, DispatchDecision

_STRONG_KEY = "k" * 40  # ≥32B, 비-default


def _decision(**over) -> DispatchDecision:
    base = dict(
        source_commander="occam", target_commander="naesengmoon",
        metric_name="supersession_confidence", metric_value=0.5, threshold=0.7,
        reason="test", decided_at="2026-07-15T00:00:00+00:00",
    )
    base.update(over)
    return DispatchDecision(**base)


def _stage(name: str, measure=None) -> CommanderStage:
    return CommanderStage(
        name=name, verb="검증", requires=(), provides=(f"{name}_out",),
        run=lambda ctx: {f"{name}_out": True}, measure=measure,
    )


# ── (a) 침묵 삼킴 실명화 ────────────────────────────────────────────────────


def test_measure_factory_error_is_recorded_not_fatal():
    """measure 팩토리 예외 = fail-soft(run 은 계속) + dispatch_errors 실명 기록.
    이전엔 try 밖이라 run 전체가 크래시했다."""

    def exploding_factory(ctx):
        raise RuntimeError("factory boom")

    run = Legion().register(_stage("s1", measure=exploding_factory)).run(context={})
    assert run.completed, "measure 실패가 run 을 죽이면 안 된다 (fail-soft)"
    assert any("s1" in e and "factory boom" in e for e in run.dispatch_errors), run.dispatch_errors


def test_decide_dispatch_error_is_recorded():
    """decide_dispatch 예외 = 무기록 증발 금지 — dispatch_errors 에 실명."""

    class BrokenCommander:
        def decide_dispatch(self, cycle_id=None):
            raise ValueError("decide boom")

    run = Legion().register(_stage("s2", measure=lambda ctx: BrokenCommander())).run(context={})
    assert run.completed
    assert any("s2" in e and "decide boom" in e for e in run.dispatch_errors), run.dispatch_errors


def test_provenance_write_error_is_recorded(monkeypatch):
    """:DispatchEvent write 실패 = best-effort 유지하되 실명 기록 (provenance 유실 가시화)."""
    monkeypatch.setenv(DISPATCH_HMAC_ENV, _STRONG_KEY)

    class OneShotCommander:
        def decide_dispatch(self, cycle_id=None):
            return [_decision()]

    def failing_wc(cypher, params):
        raise ConnectionError("kg down")

    ctx = {"write_cypher": failing_wc}
    run = Legion().register(_stage("s3", measure=lambda c: OneShotCommander())).run(context=ctx)
    assert run.completed
    assert len(run.dispatch_decisions) == 1, "결정 자체는 LegionRun 에 남아야 한다"
    assert any("s3" in e and "kg down" in e for e in run.dispatch_errors), run.dispatch_errors


def test_no_errors_means_empty_tuple():
    run = Legion().register(_stage("s4")).run(context={})
    assert run.completed and run.dispatch_errors == ()


# ── (b) 약키 unsigned 정직 표기 + call-time 키 해석 ─────────────────────────


def test_weak_key_event_is_honestly_unsigned(monkeypatch):
    """dev-default(공개) 키로는 서명하지 않는다 — unsigned 를 정직하게 표기.
    verdict_gate 가 hard-refuse 하는 바로 그 키로 'tamper-evident' 를 위장하지 않는다."""
    monkeypatch.delenv(DISPATCH_HMAC_ENV, raising=False)
    evt = _decision().to_kg_event(cycle_id="cyc-t")
    assert evt["signature_status"] == "unsigned_weak_key"
    assert evt["hmac_signature"] is None
    assert DispatchDecision.verify_signature(evt) is False  # None 서명 = 검증 실패 (TypeError 아님)


def test_short_custom_key_is_also_weak(monkeypatch):
    monkeypatch.setenv(DISPATCH_HMAC_ENV, "short")
    evt = _decision().to_kg_event(cycle_id="cyc-t")
    assert evt["signature_status"] == "unsigned_weak_key"


def test_strong_key_signs_and_verifies(monkeypatch):
    monkeypatch.setenv(DISPATCH_HMAC_ENV, _STRONG_KEY)
    evt = _decision().to_kg_event(cycle_id="cyc-t")
    assert evt["signature_status"] == "signed"
    assert DispatchDecision.verify_signature(evt) is True
    tampered = dict(evt, metric_value=0.99)
    assert DispatchDecision.verify_signature(tampered) is False


def test_key_is_resolved_at_call_time(monkeypatch):
    """장수 프로세스(bot/MCP)에서 env 키 교체가 재시작 없이 반영돼야 한다 — import-time
    frozen 금지."""
    monkeypatch.delenv(DISPATCH_HMAC_ENV, raising=False)
    assert _decision().to_kg_event()["signature_status"] == "unsigned_weak_key"
    monkeypatch.setenv(DISPATCH_HMAC_ENV, _STRONG_KEY)
    assert _decision().to_kg_event()["signature_status"] == "signed"


def test_weak_key_verify_rejects_forged_dev_signature(monkeypatch):
    """공개 dev 키로 손수 서명한 위조 이벤트가 verify 를 통과하면 안 된다 — 약키 체제에서
    verify 는 항상 False (서명 부재와 위조를 구분 없이 거부)."""
    import hashlib
    import hmac as hmac_mod

    monkeypatch.delenv(DISPATCH_HMAC_ENV, raising=False)
    d = _decision()
    payload = d._signed_payload("cyc-t")
    forged = d.to_kg_event(cycle_id="cyc-t")
    forged["hmac_signature"] = hmac_mod.new(
        b"bhgman-dev-secret-2026-05-30", payload.encode(), hashlib.sha256
    ).hexdigest()
    assert DispatchDecision.verify_signature(forged) is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
