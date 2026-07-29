"""gate_check cypher_validate.sh 해석 회귀 봉인 (2026-07-29).

engine/mcp_server/pyproject.toml 이 _resolve_repo_root 의 pyproject walk-up 을
조기 종료시켜 script 가 영구 미발견(degraded) 되던 버그 — _resolve_gate_script 는
$SYMPOSIUM_ROOT/bin 우선 + ancestor walk 으로 실제 SYMPOSIUM 레이아웃을 찾는다.
"""

from __future__ import annotations

from engine.mcp_server.tools.symposium import _resolve_gate_script


def _mk_script(root):
    script = root / "bin" / "cypher_validate.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/bin/sh\nexit 0\n")
    return script


def test_env_symposium_root_wins(tmp_path, monkeypatch):
    script = _mk_script(tmp_path)
    monkeypatch.setenv("SYMPOSIUM_ROOT", str(tmp_path))
    assert _resolve_gate_script() == script


def test_ancestor_walk_finds_script_above_nested_repo(tmp_path, monkeypatch):
    monkeypatch.delenv("SYMPOSIUM_ROOT", raising=False)
    script = _mk_script(tmp_path)
    deep = tmp_path / "GIT" / "repo" / "engine" / "mcp_server" / "tools"
    deep.mkdir(parents=True)
    assert _resolve_gate_script(start=deep / "symposium.py") == script


def test_missing_script_returns_none(tmp_path, monkeypatch):
    monkeypatch.delenv("SYMPOSIUM_ROOT", raising=False)
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert _resolve_gate_script(start=deep / "x.py") is None
