"""amie3._find_java must honor the JAVA env var its own error message advertises.

Dep-free (no real java/jar): _find_java only iterated two macOS-Homebrew paths + bare 'java'
and raised "set JAVA env var" — without ever reading os.environ['JAVA'] / JAVA_HOME. So on
Linux/CI with a non-default JDK the operator was unusable despite the documented escape hatch.

# KG: finding-amie3-find-java-ignores-env-2026-06-26
"""
from __future__ import annotations

import stat

import pytest

from engine.eureka.induction_operators.amie3 import _find_java


def _make_exec_stub(tmp_path) -> str:
    stub = tmp_path / "myjava"
    stub.write_text("#!/bin/sh\necho stub\n")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return str(stub)


def test_find_java_honors_JAVA_env(tmp_path, monkeypatch):
    stub = _make_exec_stub(tmp_path)
    monkeypatch.setenv("JAVA", stub)
    assert _find_java() == stub  # the env var wins, before the Homebrew defaults


def test_find_java_honors_JAVA_HOME(tmp_path, monkeypatch):
    jdk = tmp_path / "jdk"
    (jdk / "bin").mkdir(parents=True)
    java = jdk / "bin" / "java"
    java.write_text("#!/bin/sh\n")
    java.chmod(java.stat().st_mode | stat.S_IEXEC)
    monkeypatch.delenv("JAVA", raising=False)
    monkeypatch.setenv("JAVA_HOME", str(jdk))
    assert _find_java() == str(java)


def test_find_java_raises_when_env_unset_and_no_candidate(monkeypatch):
    monkeypatch.delenv("JAVA", raising=False)
    monkeypatch.delenv("JAVA_HOME", raising=False)
    monkeypatch.setattr(
        "engine.eureka.induction_operators.amie3._DEFAULT_JAVA_CANDIDATES",
        ("/nonexistent/java-xyz-123",),
    )
    monkeypatch.setattr("shutil.which", lambda _name: None)
    with pytest.raises(RuntimeError):
        _find_java()
