"""정방향 legion-run ctx 준비의 3진입점 패리티 (T0-3).

RED-first: 이전엔 (a) 재배맨 substrate 가 Legion.run 의 `gate` 파라미터를 삼켜 정방향
3진입점(CLI/bot/MCP)이 ADR 이 명시한 per-stage 나생문 oracle gate 를 영영 못 썼고,
(b) CLI cmd_legion 은 cycle_id 를 스탬프하지 않아 :DispatchEvent.cycle_id 가 null 이었다.
이 파일은 substrate 의 gate 관통 + 공유 헬퍼 prepare_forward_ctx 의 계약을 고정한다.

# KG: adr-seven-commander-legion-architecture-2026-05-27, adr-legion-runtime-shape-review-2026-06-20
"""

from __future__ import annotations

import engine.legion.jaebaeman_substrate as jsub
from engine.legion.legion_models import LegionRun
from engine.legion.verdict_gate import VERDICT_SECRET_ENV, prepare_forward_ctx


class _FakeLegion:
    """build_default_legion() 대역 — 받은 gate 를 포착 (stage 체인 없이 관통만 검증)."""

    def __init__(self, sink: dict) -> None:
        self._sink = sink

    def run(self, context: dict | None = None, gate=None) -> LegionRun:
        self._sink["gate"] = gate
        self._sink["ctx_cycle_id"] = (context or {}).get("cycle_id")
        return LegionRun(completed=True)


def test_substrate_forwards_gate_to_legion_run(monkeypatch):
    """T0-3a: run_legion_via_jaebaeman 은 gate 를 Legion.run 으로 관통시켜야 한다."""
    sink: dict = {}
    monkeypatch.setattr(jsub, "build_default_legion", lambda: _FakeLegion(sink))

    def sentinel_gate(ctx):
        return True, "ok"

    jsub.run_legion_via_jaebaeman({"cycle_id": "cyc-x"}, gate=sentinel_gate)
    assert sink["gate"] is sentinel_gate  # 삼키지 않고 그대로 전달


def test_substrate_gate_defaults_to_none(monkeypatch):
    """gate 미지정이면 None — 기존 무-게이트 동작 불변."""
    sink: dict = {}
    monkeypatch.setattr(jsub, "build_default_legion", lambda: _FakeLegion(sink))
    jsub.run_legion_via_jaebaeman({"cycle_id": "cyc-y"})
    assert sink["gate"] is None


def test_prepare_forward_ctx_stamps_cycle_id_without_store():
    """T0-3b: store 없어도 cycle_id 는 항상 스탬프 → :DispatchEvent.cycle_id non-null."""
    ctx: dict = {}
    prepare_forward_ctx(ctx)
    assert ctx["cycle_id"] and ctx["cycle_id"].startswith("cyc-")
    assert "verdict_gate" not in ctx  # store 부재 → legacy (fail-open 아님)


def test_prepare_forward_ctx_preserves_existing_cycle_id():
    """이미 cycle_id 가 있으면 보존 (MCP 가 서버-mint 한 id 를 헬퍼가 덮어쓰지 않음)."""
    ctx: dict = {"cycle_id": "cyc-preexisting"}
    prepare_forward_ctx(ctx, cycle_id="cyc-ignored")
    assert ctx["cycle_id"] == "cyc-preexisting"


def test_prepare_forward_ctx_injects_gate_with_store_and_strong_key(monkeypatch):
    """store + 강키면 verdict_gate + artifact_id 주입 (MCP 경로 동작 보존)."""
    from engine.kg_local.store import LocalKgStore

    monkeypatch.setenv(VERDICT_SECRET_ENV, "k" * 40)  # ≥32B 비-default = 강키
    ctx: dict = {}
    prepare_forward_ctx(ctx, store=LocalKgStore())
    assert "verdict_gate" in ctx
    assert ctx["artifact_id"] == ctx["cycle_id"]


def test_prepare_forward_ctx_weak_key_stays_legacy(monkeypatch):
    """약/무키면 verdict_gate 미주입(legacy) — 단 cycle_id 는 여전히 스탬프. fail-open 아님."""
    from engine.kg_local.store import LocalKgStore

    monkeypatch.delenv(VERDICT_SECRET_ENV, raising=False)
    ctx: dict = {}
    prepare_forward_ctx(ctx, store=LocalKgStore())
    assert "verdict_gate" not in ctx
    assert ctx["cycle_id"]  # 게이트는 못 걸어도 provenance id 는 남는다
