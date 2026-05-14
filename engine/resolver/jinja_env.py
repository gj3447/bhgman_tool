"""APT resolver — Jinja2 SandboxedEnvironment.

LangChain CVE-2025-68664 대응 — `__getattr__`/`__import__` 차단 + autoescape OFF
(markdown context, HTML 아님 — autoescape OFF가 맞음. 단, value sanitization 별도).

KG ref: rfc-apt-v26-A6-resolver-path-A-pre-prompt-hook-2026-04-30
Absorbed from SYMPOSIUM/THEORY/APT/resolver_prototype/jinja_env.py (Wave 7 P3-H).
"""

from __future__ import annotations

from jinja2 import Undefined
from jinja2.sandbox import SandboxedEnvironment


class StrictUndefined(Undefined):
    """`{{cfg.X}}` 마커가 KG에 없으면 즉시 raise (silent fallback 금지)."""

    def _fail_with_undefined_error(self, *args, **kwargs):
        raise UnresolvedMarkerError(
            f"Marker '{self._undefined_name}' not in KG MethodologyConfig. "
            f"RFC A6.1 위반 — 본문에 외부화하지 못한 magic 또는 KG seeding 누락."
        )

    __str__ = __repr__ = __getattr__ = _fail_with_undefined_error
    __getitem__ = __iter__ = __len__ = _fail_with_undefined_error


class UnresolvedMarkerError(Exception):
    pass


def build_env() -> SandboxedEnvironment:
    """SKILL.md body 렌더링 전용 SandboxedEnvironment."""
    env = SandboxedEnvironment(
        autoescape=False,  # markdown body, no HTML escape needed
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    # 추가 보안 — built-in filter 중 위험한 것 제거
    for danger in ("import", "open", "eval", "exec"):
        env.globals.pop(danger, None)
    return env
