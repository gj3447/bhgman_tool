"""Hades gated apply — Extract-Superclass behind a characterization-test gate.

The covenant's deferred 'apply = characterization test 후': write the refactor,
run the supplied test command, keep iff it passes else restore the original
byte-for-byte (reversibility-first).
"""

from __future__ import annotations

import sys

import pytest

pytest.importorskip("libcst")

from engine.hades.hades_apply import (  # noqa: E402
    apply_extract_superclass_gated,
    apply_extract_superclass_to_module,
)

_SRC = (
    "import os\n\n"
    "class Dog:\n    def speak(self):\n        return 'woof'\n    def legs(self):\n        return 4\n\n"
    "class Cat:\n    def speak(self):\n        return 'woof'\n    def meow(self):\n        return 'm'\n"
)


def test_module_rewrite_inserts_base_and_preserves_behavior():
    out = apply_extract_superclass_to_module(_SRC, "AnimalBase", ["Dog", "Cat"])
    assert out is not None
    ns: dict = {}
    exec(out, ns)  # noqa: S102 - test of generated code
    assert ns["Dog"]().speak() == "woof" and ns["Cat"]().meow() == "m"
    assert ns["AnimalBase"] in ns["Dog"].__mro__  # genuinely inherits the lifted base
    assert "speak" not in ns["Dog"].__dict__  # lifted out of the subclass


def test_module_rewrite_none_when_no_common():
    src = "class A:\n    def f(self): return 1\nclass B:\n    def g(self): return 2\n"
    assert apply_extract_superclass_to_module(src, "X", ["A", "B"]) is None


def _check_cmd(tmp_path) -> list[str]:
    return [
        sys.executable,
        "-c",
        f"import sys; sys.path.insert(0,{str(tmp_path)!r}); "
        "import mod; assert mod.Dog().speak()=='woof'; assert mod.AnimalBase",
    ]


def test_gate_pass_applies(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text(_SRC, encoding="utf-8")
    res = apply_extract_superclass_gated(
        f, "AnimalBase", ["Dog", "Cat"], test_cmd=_check_cmd(tmp_path)
    )
    assert res.status == "APPLIED" and res.test_returncode == 0
    assert "class AnimalBase" in f.read_text(encoding="utf-8")  # file really changed


def test_gate_fail_reverts_byte_for_byte(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text(_SRC, encoding="utf-8")
    # a test command that always fails → gate must revert
    res = apply_extract_superclass_gated(
        f, "AnimalBase", ["Dog", "Cat"], test_cmd=[sys.executable, "-c", "import sys; sys.exit(1)"]
    )
    assert res.status == "REVERTED" and res.test_returncode == 1
    assert f.read_text(encoding="utf-8") == _SRC  # original restored exactly


def test_gate_restores_on_unspawnable_test_cmd(tmp_path):
    # covenant: a gate that cannot even RUN (test binary missing) must leave the tree exactly
    # as it was — the file was rewritten before the gate, and restore only existed on the
    # rc!=0 path, so an unspawnable command propagated FileNotFoundError after the overwrite.
    f = tmp_path / "mod.py"
    f.write_text(_SRC, encoding="utf-8")
    res = apply_extract_superclass_gated(
        f, "AnimalBase", ["Dog", "Cat"], test_cmd=["/nonexistent-binary-xyz-12345"]
    )  # must NOT raise
    assert res.status == "REVERTED"
    assert res.test_returncode is None  # the gate never produced an exit code
    assert f.read_text(encoding="utf-8") == _SRC  # original restored byte-for-byte


def test_gate_refused_when_nothing_to_lift(tmp_path):
    f = tmp_path / "mod.py"
    src = "class A:\n    def f(self): return 1\nclass B:\n    def g(self): return 2\n"
    f.write_text(src, encoding="utf-8")
    res = apply_extract_superclass_gated(f, "X", ["A", "B"], test_cmd=[sys.executable, "-c", ""])
    assert res.status == "REFUSED"
    assert f.read_text(encoding="utf-8") == src  # untouched
