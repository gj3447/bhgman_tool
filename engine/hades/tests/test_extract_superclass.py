"""Real Extract-Superclass engine (stdlib ast) — genuine code generation."""

from __future__ import annotations

import ast

from engine.hades.extract_superclass import common_methods, extract_superclass
from engine.hades.hades import realize_code_extract_superclass
from engine.hades.hades_models import RealizeStatus

_A = "class Dog:\n    def speak(self):\n        return 'woof'\n    def legs(self):\n        return 4\n"
_B = "class Cat:\n    def speak(self):\n        return 'woof'\n    def name(self):\n        return 'c'\n"
# speak() is byte-for-byte structurally identical in both; legs/name are unique.


def test_common_methods_lgg():
    a = ast.parse(_A).body[0]
    b = ast.parse(_B).body[0]
    assert common_methods([a, b]) == ["speak"]


def test_single_class_has_no_common():
    a = ast.parse(_A).body[0]
    assert common_methods([a]) == []


def test_divergent_body_not_common():
    a = ast.parse("class A:\n    def f(self):\n        return 1\n").body[0]
    b = ast.parse("class B:\n    def f(self):\n        return 2\n").body[0]
    assert common_methods([a, b]) == []  # same name, different body → not lifted


def test_extract_generates_real_superclass_and_diff():
    patch = extract_superclass("Animal", {"Dog": _A, "Cat": _B})
    assert patch is not None
    assert patch.common_methods == ("speak",)
    # generated superclass is real, parseable code containing the lifted method
    base = ast.parse(patch.base_source).body[0]
    assert base.name == "Animal"
    assert "speak" in {n.name for n in base.body if isinstance(n, ast.FunctionDef)}
    # subclasses now inherit Animal and no longer define speak
    dog = ast.parse(patch.modified["Dog"]).body[0]
    assert "Animal" in {b.id for b in dog.bases}
    assert "speak" not in {n.name for n in dog.body if isinstance(n, ast.FunctionDef)}
    assert "legs" in {n.name for n in dog.body if isinstance(n, ast.FunctionDef)}  # unique kept
    assert "--- Dog (before)" in patch.unified_diff


def test_extract_none_when_no_common():
    assert (
        extract_superclass(
            "X",
            {
                "A": "class A:\n    def f(self): return 1\n",
                "B": "class B:\n    def g(self): return 2\n",
            },
        )
        is None
    )


def test_hades_realize_planned_by_default():
    v = realize_code_extract_superclass("Animal", {"Dog": _A, "Cat": _B})
    assert v.status is RealizeStatus.PLANNED and v.applied is False
    assert v.plan is not None and v.plan.reversible and v.plan.undo


def test_hades_refuses_non_accepted():
    v = realize_code_extract_superclass("A", {"Dog": _A, "Cat": _B}, verdict_status="REJECTED")
    assert v.status is RealizeStatus.REFUSED


def test_hades_refuses_over_max_sites():
    srcs = {
        f"C{i}": f"class C{i}:\n    def speak(self):\n        return 'woof'\n" for i in range(6)
    }
    v = realize_code_extract_superclass("A", srcs, max_sites=5)
    assert v.status is RealizeStatus.REFUSED


def test_hades_apply_writes_via_injected_writer():
    captured = {}

    def writer(base_src, modified):
        captured["base"] = base_src
        captured["modified"] = modified

    v = realize_code_extract_superclass(
        "Animal", {"Dog": _A, "Cat": _B}, dry_run=False, writer=writer
    )
    assert v.status is RealizeStatus.APPLIED and v.applied is True
    assert "class Animal" in captured["base"]
    assert set(captured["modified"]) == {"Dog", "Cat"}


# ── libcst format-preserving backend ([hades-cst] optional extra) ────────────
import pytest  # noqa: E402

cst_mod = pytest.importorskip("libcst")  # skip whole section if libcst absent

from engine.hades.extract_superclass import extract_superclass_cst  # noqa: E402

_WithComments = (
    "class Dog:\n    # important: keep this comment\n    def speak(self):\n        return 'woof'\n    def legs(self):\n        return 4\n",
    "class Cat:\n    # important: keep this comment\n    def speak(self):\n        return 'woof'\n    def meow(self):\n        return 'm'\n",
)


def test_cst_preserves_comments_unlike_ast():
    srcs = {"Dog": _WithComments[0], "Cat": _WithComments[1]}
    cst_patch = extract_superclass_cst("Animal", srcs)
    assert cst_patch is not None and cst_patch.common_methods == ("speak",)
    # the lifted method's comment survives in the generated superclass
    assert "# important: keep this comment" in cst_patch.base_source
    # ast backend canonicalizes it away — the contrast that justifies libcst
    from engine.hades.extract_superclass import extract_superclass

    assert "# important: keep this comment" not in extract_superclass("Animal", srcs).base_source


def test_cst_rewrite_inherits_and_drops_lifted():
    cst_patch = extract_superclass_cst("Animal", {"Dog": _WithComments[0], "Cat": _WithComments[1]})
    dog = cst_patch.modified["Dog"]
    assert "Dog(Animal)" in dog
    assert "def speak" not in dog and "def legs" in dog


def test_cst_none_when_no_common():
    assert (
        extract_superclass_cst(
            "X",
            {
                "A": "class A:\n    def f(self): return 1\n",
                "B": "class B:\n    def g(self): return 2\n",
            },
        )
        is None
    )


def test_hades_realize_preserve_format_routes_to_cst():
    from engine.hades.hades import realize_code_extract_superclass

    captured = {}
    v = realize_code_extract_superclass(
        "Animal",
        {"Dog": _WithComments[0], "Cat": _WithComments[1]},
        dry_run=False,
        writer=lambda base, mod: captured.update(base=base),
        preserve_format=True,
    )
    assert v.applied is True
    assert "# important: keep this comment" in captured["base"]


def test_find_classdef_no_single_class_fallback():
    """W3-J: requesting an absent name must return None, not the file's only (wrong) class."""
    from engine.hades.extract_superclass import _find_classdef

    src = "class Dog:\n    def bark(self): ...\n"
    assert _find_classdef(src, "Dog").name == "Dog"
    assert _find_classdef(src, "Cat") is None
