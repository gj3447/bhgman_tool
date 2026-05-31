"""하데스 코드 실현 — 진짜 Extract-Superclass refactor (stdlib ast, no deps).

이전 `realize_code_template`은 *문자열 plan*("EXTRACT shared template …")만 냈다.
이 모듈은 실제 소스를 ast로 분석해 **진짜 코드**를 생성한다:

  1. ≥2 클래스에서 **구조적으로 동일한 공통 메서드**(LGG = least general generalization)를 찾고,
  2. 그 메서드를 담은 **실 superclass 코드**를 생성하고,
  3. 각 subclass를 (공통 메서드 제거 + base 상속) **재작성**하고,
  4. 사람이 검토할 **실 unified diff**를 만든다.

정직 공시: `ast.unparse`는 원본 포맷/주석을 보존하지 않고 canonical하게 재출력한다(libcst 미설치).
dry-run PLAN/diff 용도로는 충분하며, apply는 하데스 covenant상 명시적 writer 주입 시에만.

# KG: hades-canonical-2026-05-27 (실현=추상→구체), consensus-eureka-engine-impl-2026-05-26 (c6 materialize danger)
"""

from __future__ import annotations

import ast
import difflib
from dataclasses import dataclass

_FuncT = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class ExtractSuperclassPatch:
    base_name: str
    base_source: str  # generated superclass code (real)
    common_methods: tuple[str, ...]  # method names lifted into the base
    modified: dict[str, str]  # class_name -> rewritten source (real)
    unified_diff: str  # human-reviewable real diff


def _methods(cls: ast.ClassDef) -> dict[str, ast.AST]:
    return {n.name: n for n in cls.body if isinstance(n, _FuncT)}


def common_methods(classdefs: list[ast.ClassDef]) -> list[str]:
    """Method names present in EVERY class with a structurally identical body.

    Structural identity = equal ``ast.dump`` (line numbers excluded by default),
    so two methods match iff their parsed AST is identical regardless of source
    formatting or which class they live in. This is the LGG of the class family.
    """
    if len(classdefs) < 2:
        return []
    maps = [_methods(c) for c in classdefs]
    shared = set(maps[0])
    for m in maps[1:]:
        shared &= set(m)
    out: list[str] = []
    for name in sorted(shared):
        dumps = {ast.dump(m[name]) for m in maps}
        if len(dumps) == 1:  # identical across all classes
            out.append(name)
    return out


def _build_superclass(base_name: str, donor: ast.ClassDef, names: list[str]) -> str:
    methods = [n for n in donor.body if isinstance(n, _FuncT) and n.name in names]
    base = ast.ClassDef(
        name=base_name,
        bases=[],
        keywords=[],
        body=methods or [ast.Pass()],
        decorator_list=[],
        type_params=[],
    )
    ast.fix_missing_locations(base)
    return ast.unparse(base)


def _rewrite_subclass(cls: ast.ClassDef, base_name: str, names: list[str]) -> str:
    kept = [n for n in cls.body if not (isinstance(n, _FuncT) and n.name in names)]
    if not kept:
        kept = [ast.Pass()]
    new = ast.ClassDef(
        name=cls.name,
        bases=[*cls.bases, ast.Name(id=base_name, ctx=ast.Load())],
        keywords=cls.keywords,
        body=kept,
        decorator_list=cls.decorator_list,
        type_params=getattr(cls, "type_params", []),
    )
    ast.fix_missing_locations(new)
    return ast.unparse(new)


def _find_classdef(src: str, name: str) -> ast.ClassDef | None:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    named = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name]
    if named:
        return named[0]
    any_cls = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    return any_cls[0] if len(any_cls) == 1 else None


def extract_superclass(
    base_name: str, class_sources: dict[str, str]
) -> ExtractSuperclassPatch | None:
    """Generate a real Extract-Superclass patch, or None if nothing to lift.

    None when: a source does not parse / its class is not found, fewer than 2
    classes, or the classes share no structurally-identical method.
    """
    parsed: dict[str, ast.ClassDef] = {}
    for name, src in class_sources.items():
        cd = _find_classdef(src, name)
        if cd is None:
            return None
        parsed[name] = cd
    classdefs = list(parsed.values())
    names = common_methods(classdefs)
    if not names:
        return None
    base_source = _build_superclass(base_name, classdefs[0], names)
    modified = {n: _rewrite_subclass(cd, base_name, names) for n, cd in parsed.items()}
    diff_parts: list[str] = [f"# new superclass {base_name}\n{base_source}\n"]
    for name, src in class_sources.items():
        before = src.splitlines(keepends=True)
        after = (modified[name] + "\n").splitlines(keepends=True)
        diff_parts.append(
            "".join(
                difflib.unified_diff(
                    before, after, fromfile=f"{name} (before)", tofile=f"{name} (after)"
                )
            )
        )
    return ExtractSuperclassPatch(
        base_name=base_name,
        base_source=base_source,
        common_methods=tuple(names),
        modified=modified,
        unified_diff="".join(diff_parts),
    )


__all__ = ["ExtractSuperclassPatch", "common_methods", "extract_superclass"]
