"""Tests — anti-reward-hack guard for repair-loop candidates.

Agents pass verifiers by tampering (modifying the test/verifier) or by landing the "fix"
outside source (assertion-side), not in the real code. Measured 28.57% hacked-resolved
without a guard (Verification Horizon, arXiv:2606.26300). This guard is deterministic.

# KG: finding-prom16-verification-is-bottleneck-2026-07-13
"""

from __future__ import annotations

from engine.naesengmoon.reward_hack_guard import guard_patch


PROTECTED = ["**/test_*.py", "**/tests/**", "**/conftest.py"]
SOURCE = ["engine/**/*.py"]


def test_clean_source_only_fix() -> None:
    v = guard_patch(
        ["engine/foo/bar.py"], protected_paths=PROTECTED, source_globs=SOURCE
    )
    assert v.clean is True
    assert v.touched_protected == ()


def test_test_file_tampering_flagged() -> None:
    v = guard_patch(
        ["engine/foo/bar.py", "engine/foo/tests/test_bar.py"],
        protected_paths=PROTECTED,
        source_globs=SOURCE,
    )
    assert v.clean is False
    assert "engine/foo/tests/test_bar.py" in v.touched_protected
    assert any("tamper" in r.lower() for r in v.reasons)


def test_conftest_tampering_flagged() -> None:
    v = guard_patch(
        ["engine/foo/bar.py", "conftest.py"],
        protected_paths=PROTECTED,
        source_globs=SOURCE,
    )
    assert v.clean is False
    assert "conftest.py" in v.touched_protected


def test_fix_only_outside_source_flagged() -> None:
    # changes exist but none land in source → fake/assertion-side fix
    v = guard_patch(
        ["docs/notes.md"], protected_paths=PROTECTED, source_globs=SOURCE
    )
    assert v.clean is False
    assert any("no source" in r.lower() for r in v.reasons)


def test_no_changes_is_clean_noop() -> None:
    v = guard_patch([], protected_paths=PROTECTED, source_globs=SOURCE)
    assert v.clean is True
    assert v.reasons == ()


def test_source_glob_optional() -> None:
    # without source_globs, only protected-tampering is judged
    v = guard_patch(["docs/notes.md"], protected_paths=PROTECTED)
    assert v.clean is True


def test_both_violations_reported() -> None:
    v = guard_patch(
        ["tests/test_x.py"], protected_paths=PROTECTED, source_globs=SOURCE
    )
    assert v.clean is False
    # test tampering AND no source change both surface
    assert len(v.reasons) >= 2
