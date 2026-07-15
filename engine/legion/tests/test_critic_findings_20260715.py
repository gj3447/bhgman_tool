"""적대검증(2026-07-15)이 Tier0+1 작업에서 확증한 결함들의 회귀 고정.

5-lens 적대검증 워크플로(wf_9f6c3ca2-64c)가 내 자신의 T0/T1 커밋에서 찾아낸 실결함들.
각 테스트는 "내가 주장했으나 사실이 아니었던 것" 또는 "내가 넣은 회귀"를 고정한다.

# KG: cycle-bhgman-tier0-loop-wiring-2026-07-15
"""

from __future__ import annotations

import inspect

import pytest

from engine.legion.measurement import DISPATCH_HMAC_ENV, DispatchDecision

_STRONG_KEY = "k" * 40


def _decision() -> DispatchDecision:
    return DispatchDecision(
        source_commander="occam", target_commander="naesengmoon",
        metric_name="supersession_confidence", metric_value=0.5, threshold=0.7,
        reason="test", decided_at="2026-07-15T00:00:00+00:00",
    )


def test_decision_id_survives_weak_key(monkeypatch):
    """내가 넣은 회귀: dispatch_id 를 hmac_signature 로 쓰면 약키 기본환경에서 None 이 된다.

    식별(id)과 무결성(signature)은 다른 관심사 — id 는 키와 무관하게 항상 존재해야 한다."""
    monkeypatch.delenv(DISPATCH_HMAC_ENV, raising=False)
    d = _decision()
    assert d.to_kg_event()["hmac_signature"] is None  # 약키 → 서명 없음 (정직)
    did = d.decision_id()
    assert did and len(did) == 64  # 그래도 식별자는 있다


def test_decision_id_is_stable_and_key_independent(monkeypatch):
    """같은 결정 → 같은 id. 키를 바꿔도 id 는 불변 (content hash)."""
    d = _decision()
    monkeypatch.delenv(DISPATCH_HMAC_ENV, raising=False)
    weak = d.decision_id("cyc-1")
    monkeypatch.setenv(DISPATCH_HMAC_ENV, _STRONG_KEY)
    strong = d.decision_id("cyc-1")
    assert weak == strong, "decision_id 가 키에 의존하면 안 된다"
    assert d.decision_id("cyc-2") != weak, "cycle 이 다르면 id 도 다르다"


def test_consumer_records_non_null_dispatch_id(monkeypatch):
    """dispatch_consumer 가 instrument log 에 실제 식별자를 남긴다 (기본 환경에서도)."""
    monkeypatch.delenv(DISPATCH_HMAC_ENV, raising=False)
    from engine.legion import dispatch_consumer

    src = inspect.getsource(dispatch_consumer)
    assert 'dispatch_id=d.decision_id(' in src, "서명이 아니라 decision_id 를 써야 한다"
    assert 'dispatch_id=d.to_kg_event(cycle_id=cycle_id)["hmac_signature"]' not in src


def test_consume_merge_persists_signature_status():
    """:DispatchEvent 를 쓰는 두 MERGE 문 모두 signature_status 를 남겨야 한다 —
    consumer 경로가 서명만 덮어쓰고 정직 라벨을 빠뜨리면 노드가 '서명 없음'인지
    '검증 안 함'인지 구분 불가."""
    from engine.legion.dispatch_consumer import _DISPATCH_CONSUME_MERGE
    from engine.legion.legion import _DISPATCH_EVENT_MERGE

    for name, stmt in (("legion", _DISPATCH_EVENT_MERGE), ("consumer", _DISPATCH_CONSUME_MERGE)):
        assert "e.signature_status=$signature_status" in stmt, f"{name} MERGE 에 누락"


def test_recording_fake_mcp_catches_bare_decorator():
    """_RecordingFakeMcp 가 bare `@mcp.tool` 도 기록해야 한다.

    괄호-호출만 처리하면 bare 형태 tool 이 조용히 장부에서 빠져 prometheus_ingest 사고가
    3-way parity GREEN 인 채로 재현된다 — introspection 이 '구조적 차단' 이라는 주장의
    구멍이었다."""
    from engine.mcp_server.server import _RecordingFakeMcp

    f = _RecordingFakeMcp()

    @f.tool
    def bare_tool() -> None: ...

    @f.tool()
    def call_tool() -> None: ...

    @f.tool(name="renamed")
    def orig_name() -> None: ...

    assert f.names == ["bare_tool", "call_tool", "renamed"], f.names


def test_status_cypher_password_not_on_argv(monkeypatch):
    """cmd_status 의 ssh fallback 도 비밀번호를 argv 에 싣지 않는다 —
    '비밀번호 argv 제거' 가 두 자매 호출부 중 하나만 고쳤던 결함."""
    from engine.cli import commands

    src = inspect.getsource(commands)
    assert "-p {shlex.quote(password)}" not in src, "cypher-shell -p 가 argv 에 남아있다"
    assert 'f"cypher-shell -u {shlex.quote(user)} -p ' not in src


def test_resolve_thresholds_warns_on_loader_failure(monkeypatch, caplog):
    """설정 로드 실패는 fail-soft 하되 실명 경고 — 침묵 fallback 은 튜닝값을
    아무도 모르게 무시한다 (T1-2 가 없앤 침묵 삼킴을 T1-3 이 재도입할 뻔했다)."""
    import logging

    import engine.legion.measurement as m
    from engine.legion.measurement import OccamMeasurement, resolve_thresholds

    def boom():
        raise OSError("toml unreadable")

    monkeypatch.setattr(m, "load_thresholds", boom)
    with caplog.at_level(logging.WARNING):
        rules = resolve_thresholds(OccamMeasurement.dispatch_thresholds, "occam")
    assert rules == OccamMeasurement.dispatch_thresholds  # fail-soft 유지
    assert any("fallback" in r.message or "fallback" in r.getMessage() for r in caplog.records), (
        "로더 실패가 무기록으로 증발했다"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
