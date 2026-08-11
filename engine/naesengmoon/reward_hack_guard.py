"""Anti-reward-hack guard for repair-loop candidates (결정론 pre-accept gate).

The Verification Horizon (arXiv:2606.26300) measured a 28.57% "hacked resolved" rate: agents
pass the verifier not by fixing the source but by (a) tampering with the test/verifier itself,
or (b) landing the change outside source (assertion-side). Behavior monitoring cut this to
0.56%. This guard is that monitor as a deterministic, zero-LLM check: given the set of paths a
candidate patch touches, it refuses candidates that modify protected verifier/test files or
that never touch real source.

It composes with the naesengmoon oracle-lens: the oracle proves the tests pass; this guard
proves the pass was earned in source, not manufactured in the verifier. Slots before accepting
any gated-apply candidate (engine.hades.apply_extract_superclass_gated and the repair loop).

Pure-python (stdlib only).

# KG: finding-prom16-verification-is-bottleneck-2026-07-13, naesengmoon-canonical-2026-05-19,
#     hades-canonical-2026-05-27
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class RewardHackVerdict:
    # KG: naesengmoon-canonical-2026-05-19
    """clean=True ⇒ safe to accept. touched_protected lists tampered verifier/test files."""

    clean: bool
    touched_protected: tuple[str, ...]
    reasons: tuple[str, ...]
    summary: str


@lru_cache(maxsize=256)
def _glob_regex(pat: str) -> re.Pattern[str]:
    """`**`-aware glob → anchored regex (POSIX path semantics).

    PurePath.full_match 은 3.13+ 전용인데 CI matrix 는 3.11–3.13 을 돈다 — full_match
    는 이식 불가라 브랜치가 3.11/3.12 에서 collection-time AttributeError 로 죽었다
    (이 브랜치가 여태 main 에 못 들어간 이유). 직접 번역해 이식성을 확보한다:
      `**/` → 0개 이상의 path 세그먼트 (그래서 `**/conftest.py` 가 repo-root 의
              conftest.py 도 매칭 — fnmatch 의 `**` 는 놓친다), `**` → 임의 문자열,
      `*` → 세그먼트 내부, `?` → 세그먼트 내 1문자.
    """
    i, n, out = 0, len(pat), []
    while i < n:
        if pat.startswith("**/", i):
            out.append("(?:[^/]*/)*")
            i += 3
        elif pat.startswith("**", i):
            out.append(".*")
            i += 2
        elif pat[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pat[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pat[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def _matches_any(path: str, patterns: Sequence[str]) -> bool:
    # 3.11-compatible full_match 대체 (recursive `**`; `**/conftest.py` 는 repo-root
    # conftest.py 도 매칭). CI 3.11/3.12 이식성 (reward-hack-guard-py311-portable-2026-07-15).
    return any(_glob_regex(pat).match(path) is not None for pat in patterns)


def guard_patch(
    changed_paths: Iterable[str],
    *,
    protected_paths: Sequence[str],
    source_globs: Sequence[str] | None = None,
) -> RewardHackVerdict:
    # KG: naesengmoon-canonical-2026-05-19
    """Refuse a repair candidate that tampers with the verifier or fixes nothing in source.

    protected_paths: fnmatch globs for test/verifier/oracle files a genuine fix must NOT touch.
    source_globs:    fnmatch globs for real source; if given, at least one changed path must
                     match, else the "fix" lands only outside source (assertion/verifier-side).
    An empty patch is a clean no-op."""
    changed = list(changed_paths)
    touched_protected = tuple(p for p in changed if _matches_any(p, protected_paths))

    reasons: list[str] = []
    if touched_protected:
        reasons.append(
            "verifier/test tampering — candidate modifies protected file(s): "
            + ", ".join(touched_protected)
        )
    if changed and source_globs is not None:
        if not any(_matches_any(p, source_globs) for p in changed):
            reasons.append(
                "no source file changed — the 'fix' lands only outside source "
                "(assertion/verifier-side hack risk)"
            )

    clean = not reasons
    summary = (
        "clean: fix earned in source, no verifier tampering"
        if clean
        else "REWARD-HACK SUSPECTED — " + "; ".join(reasons)
    )
    return RewardHackVerdict(
        clean=clean,
        touched_protected=touched_protected,
        reasons=tuple(reasons),
        summary=summary,
    )


__all__ = ["RewardHackVerdict", "guard_patch"]
