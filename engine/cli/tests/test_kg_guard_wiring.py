"""make_kg_runners write-runner 하네스 wiring — enforce/warn/off 모드 + read 미감쌈.

출혈-차단 하네스를 runner 팩토리 chokepoint에 끼웠는지 고정. occam/kg_writer 등 모든
write가 이 한 곳을 통과하므로, 여기만 지키면 재오염을 구조적으로 막는다.

# KG: occam-pass-metahumotonic-20260626
"""

from __future__ import annotations

import pytest

from engine.cli.runtime import _guard_write, _make_mcp_runners
from engine.kg_harness import WriteGuardError

_DIRTY = "CREATE (n:Apostle {name:'x'})"  # naked CREATE → ERROR
_CLEAN = "MERGE (n:Apostle {roman:$r}) SET n.role=$x"


def test_enforce_is_default_and_refuses_dirty(monkeypatch):
    monkeypatch.delenv("BHGMAN_KG_GUARD", raising=False)
    seen = []
    guarded = _guard_write(lambda c, p: seen.append(c) or [])
    with pytest.raises(WriteGuardError):
        guarded(_DIRTY, {})
    assert seen == []  # 실행 0


def test_enforce_passes_clean_write(monkeypatch):
    monkeypatch.delenv("BHGMAN_KG_GUARD", raising=False)
    seen = []
    guarded = _guard_write(lambda c, p: seen.append((c, p)) or [{"ok": 1}])
    out = guarded(_CLEAN, {"r": "III", "x": "y"})
    assert out == [{"ok": 1}]
    assert len(seen) == 1


def test_warn_mode_executes_but_reports(monkeypatch, capsys):
    monkeypatch.setenv("BHGMAN_KG_GUARD", "warn")
    seen = []
    guarded = _guard_write(lambda c, p: seen.append(c) or [])
    guarded(_DIRTY, {})  # warn: 실행됨
    assert seen == [_DIRTY]
    err = capsys.readouterr().err
    assert "kg-guard" in err and "NAKED_CREATE" in err


def test_off_mode_is_passthrough(monkeypatch):
    monkeypatch.setenv("BHGMAN_KG_GUARD", "off")
    seen = []
    raw = lambda c, p: seen.append(c) or []  # noqa: E731
    guarded = _guard_write(raw)
    assert guarded is raw  # 동일 객체 = 검증 없음
    guarded(_DIRTY, {})
    assert seen == [_DIRTY]


def test_factory_guards_write_not_read(monkeypatch):
    monkeypatch.delenv("BHGMAN_KG_GUARD", raising=False)
    calls = []
    monkeypatch.setattr(
        "engine.cli.runtime._mcp_cypher_call",
        lambda url, tool, cypher, params: calls.append((tool, cypher)) or [],
    )
    run, write, _close = _make_mcp_runners("http://x")
    # read는 감싸지 않음 — dirty여도 통과(검증 대상 아님)
    run(_DIRTY, {})
    assert calls[-1][0] == "read_neo4j_cypher"
    # write는 감쌈 — dirty면 거부, runner 미호출
    before = len(calls)
    with pytest.raises(WriteGuardError):
        write(_DIRTY, {})
    assert len(calls) == before
