"""bhgman-tool MCP server: assembles tools into a FastMCP instance.

KG: span-mcp-server-skeleton-fastmcp-2026-05-13 (:AtomicSpan)

Design:
- One FastMCP instance per server.
- Each tool registered via `@mcp.tool()` decorator from `tools/*` modules.
- stdio transport (default for `mcp.run()`).
- All tools must be deterministic, time-bounded, and structured (no eval/exec).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _registrars() -> list[Any]:
    """SSOT: 모든 tool register 함수의 단일 목록.

    build_server()(실 FastMCP)와 list_registered_tool_names()(recording fake) 가 같은
    목록을 소비 — 새 tools 모듈이 둘 중 한쪽에만 붙는 drift 를 구조적으로 차단 (T1-4).
    """
    from .tools.apt import register as register_apt
    # eureka_induce — 창조(FCA induction, PROPOSE-only, EARNED counts) 단독 노출 (실체감사 유레카 갭):
    # KG: LakatosTree_Bhgman6CommanderOoptdd_20260624/eureka_mcp_earned_counts
    from .tools.eureka import register as register_eureka
    # hades_realize — 실현(materialize) behind the verdict-provenance gate (OQ1, 2026-06-20):
    # KG: adr-legion-runtime-shape-review-2026-06-20
    from .tools.hades import register as register_hades
    from .tools.harness import register as register_harness
    # 7-commander legion (비행기맨#4) — full roster + closed loop (2026-06-18):
    # KG: adr-seven-commander-legion-architecture-2026-05-27
    from .tools.legion import register as register_legion
    from .tools.longinus import register as register_longinus
    from .tools.occam import register as register_occam
    from .tools.prometheus import register as register_prometheus  # Legion step 6 (획득)
    # SYMPOSIUM-absorbed tools (Wave 7 P2-A, 2026-05-14):
    # KG: rs-mcp-symposium-absorb-2026-05-14
    from .tools.symposium import register as register_symposium
    from .tools.taliban import register as register_taliban
    from .tools.tpa import register as register_tpa

    return [
        register_longinus,
        register_harness,
        register_apt,
        register_taliban,
        register_tpa,
        register_prometheus,
        register_occam,
        register_eureka,
        register_symposium,
        register_legion,
        register_hades,
    ]


def build_server() -> Any:
    """Construct and configure the FastMCP server.

    Returns a `fastmcp.FastMCP` instance ready to `.run()`.
    Raises ImportError if `fastmcp` is not installed (handled by __main__).
    """
    from fastmcp import FastMCP

    mcp: Any = FastMCP("bhgman-tool")

    # Register tools (each module attaches its @mcp.tool() functions to `mcp`)
    for register in _registrars():
        register(mcp)

    # Per-call security enforcement (bhg-f-mcp-security-boot-only): a FastMCP middleware
    # runs enforce_call on EVERY tool invocation, scanning the live arguments for
    # prompt-injection. AUDIT mode (default) logs and never blocks; ENFORCE mode
    # (BHGMAN_SECURITY_ENFORCE=1) raises SecurityViolation on a HIGH detection → the call
    # is denied. Fail-open: any wiring error is swallowed so a bug never breaks a real call.
    try:
        from fastmcp.server.middleware import Middleware

        from .security import SecurityViolation, enforce_call

        class _SecurityMiddleware(Middleware):  # type: ignore[misc]
            async def on_call_tool(self, context: Any, call_next: Any) -> Any:
                try:
                    msg = getattr(context, "message", None)
                    name = getattr(msg, "name", "") or ""
                    args = getattr(msg, "arguments", None) or {}
                    if name:
                        enforce_call(name, args)  # raises SecurityViolation on DENY
                except SecurityViolation:
                    raise  # ENFORCE + HIGH → deny the call
                except Exception:  # fail-open: any other error must not break a real call
                    pass
                return await call_next(context)

        mcp.add_middleware(_SecurityMiddleware())
    except Exception:  # pragma: no cover — middleware wiring must never break server build
        logger.debug("MCP security middleware not wired (non-fatal)", exc_info=True)

    # Boot-time trifecta profiler (static toolset composition; complements the per-call
    # middleware above): log the toolset's lethal-trifecta profile once.
    try:
        from .security import audit_toolset, current_mode

        report = audit_toolset(list_registered_tool_names())
        if report.has_trifecta:
            logger.warning("MCP security: %s", report.summary)
        else:
            logger.info("MCP security: %s (mode=%s)", report.summary, current_mode().value)
    except Exception:  # pragma: no cover - audit must never break server build
        logger.debug("MCP security audit skipped (non-fatal)", exc_info=True)

    return mcp


class _RecordingFakeMcp:
    """`@mcp.tool()` 등록을 이름만 기록하는 fake — fastmcp 없이도 실등록면을 열거한다."""

    def __init__(self) -> None:
        self.names: list[str] = []

    def tool(self, *args: Any, **kwargs: Any) -> Any:
        explicit = kwargs.get("name")

        def _decorator(fn: Any) -> Any:
            self.names.append(explicit or fn.__name__)
            return fn

        return _decorator


def list_registered_tool_names() -> list[str]:
    """Enumerate the tools that build_server() registers — by actually running the registrars.

    Superseded 2026-07-15 (T1-4): the previous hand-maintained list here drifted from the
    live surface (`prometheus_ingest` was @mcp.tool()-registered but absent from this list,
    security.TOOL_CAPABILITIES, AND the registry catalog — so it sailed through the boot
    trifecta audit with zero capabilities). Introspection over the same `_registrars()` SSOT
    makes that drift class structurally impossible; the legacy list is preserved in git
    history (@59654e1). KG: cycle-bhgman-tier0-loop-wiring-2026-07-15.
    """
    fake = _RecordingFakeMcp()
    for register in _registrars():
        register(fake)
    return fake.names
