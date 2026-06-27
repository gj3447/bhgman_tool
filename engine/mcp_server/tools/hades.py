"""MCP tool — `hades_realize` (실현, gate 후). verdict-provenance fail-closed 경계.

OQ1 / ADR `adr-legion-runtime-shape-review-2026-06-20` §design-oq1-hades-verdict-gate.

`legion_run_impl`(tools/legion.py)의 LocalKgStore + make_local_runner 배선을 미러하되,
실현(비가역) 전에 verdict 를 HMAC 게이트로 **일방 검증**한다:

  - `VerdictGate.from_env()` — 약/무/공개-default 키면 `WeakVerdictKeyError` → catch →
    refused dict (fail-closed, never raise; legion/symposium fail-open 계약).
  - `expected_artifact_id` 는 caller 입력이 아니라, concept 의 ACCEPTED AbstractClass
    extent 에서 **서버 재계산**(`compute_artifact_id(concept, members)`). 로컬 backend 는
    `_FETCH_ALL`(+params concept 필터) 만 라우트 통과 — `_FETCH_ONE` 은 substring 불일치로
    `UnsupportedLocalQuery`. 따라서 fetch·realize 둘 다 `_FETCH_ALL` 경로를 쓴다.
  - `gate.verify(...)` ok=False ⇒ realize/KG-write 없음. ok=True ⇒ 그 한 row 만 실현.

infra-0 covenant: 번들 LocalKgStore 위에서 돈다(neo4j/API-key 불필요). 로컬 backend 는
realize MERGE apply 라우트가 없어(`apply_cypher=None`) `apply=True` 여도 PLANNED 유지 —
비가역 write 는 실제 neo4j(apply_cypher) 배선에서만. 잔여(프로세스 재시작 후 replay,
대칭 HMAC 천장)는 `oq-hades-verdict-asymmetric-key-2026-06-20` 참조.

# KG: adr-legion-runtime-shape-review-2026-06-20, hades-canonical-2026-05-27,
#     oq-hades-verdict-provenance-standalone-realize-2026-06-20
"""

from __future__ import annotations

from typing import Any


def hades_realize_impl(
    cycle_id: str = "mcp-legion",
    verdict: dict[str, Any] | None = None,
    concept: str = "",
    apply: bool = False,
    kg_path: str | None = None,
    require_signed_selection: bool = False,
) -> dict[str, Any]:
    """ACCEPTED 추상(concept)을 verdict-gate 통과 시에만 실현. dry-run 기본, never raise."""
    from engine.hades.hades_runner import fetch_accepted_cypher, run_hades  # noqa: PLC0415
    from engine.kg_local.runner import make_local_runner  # noqa: PLC0415
    from engine.kg_local.store import LocalKgStore  # noqa: PLC0415
    from engine.legion.verdict_gate import (  # noqa: PLC0415
        KgVerdictLedger,
        WeakVerdictKeyError,
        build_gate_from_env,
        compute_artifact_id,
    )

    if not isinstance(verdict, dict) or not concept:
        return {
            "ok": False,
            "realized": False,
            "reason": "verdict (dict) and concept (str) are required",
            "concept": concept,
            "cycle_id": cycle_id,
        }

    # 번들 LocalKgStore — artifact 재계산 + 영속 ledger(:RealizedVerdict) 양쪽의 backend.
    store = LocalKgStore(kg_path) if kg_path else LocalKgStore()
    run_cypher = make_local_runner(store, autosave=False)

    # 1. KEY GATE (construction-time). 약/무/공개-default 키 ⇒ fail-closed, never raise.
    #    ledger = KG-backed(:RealizedVerdict) → 프로세스 재시작 후에도 (cycle, artifact) 1회성 유지.
    try:
        gate = build_gate_from_env(ledger=KgVerdictLedger(store))
    except WeakVerdictKeyError:
        return {
            "ok": False,
            "realized": False,
            "reason": "verdict gate misconfigured (weak/absent key)",
            "concept": concept,
            "cycle_id": cycle_id,
        }

    # 2. SERVER-SIDE ARTIFACT RECOMPUTE — caller 의 artifact_id 를 신뢰하지 않음.
    #    _FETCH_ALL 만 로컬 라우트 통과(runner.py:450); 핸들러가 params["concept"] 로 필터.
    fetch_all_cypher, _ = fetch_accepted_cypher(None)  # = _FETCH_ALL (concept=None → all-form)
    try:
        rows = run_cypher(fetch_all_cypher, {"concept": concept})
    except Exception as exc:  # noqa: BLE001 - backend degraded → fail-closed dict
        return {
            "ok": False,
            "realized": False,
            "reason": f"kg backend error: {exc}",
            "degraded": True,
            "concept": concept,
            "cycle_id": cycle_id,
        }

    row = next((r for r in rows if r.get("concept") == concept), None)
    if row is None:
        return {
            "ok": False,
            "realized": False,
            "reason": "no ACCEPTED AbstractClass for concept",
            "concept": concept,
            "cycle_id": cycle_id,
        }
    members = list(row.get("members") or [])  # = a.extent
    expected_artifact_id = compute_artifact_id(concept, members)

    # 2b. OQ1b: selection-node 자기-인증 (opt-in, 두 번째 신뢰 지점). verdict verify 전에 둬서
    #     selection 실패가 verdict ledger 를 소비하지 않게 한다. 노드의 node_signature 가
    #     (name, verdictStatus, cycleId, extent) 에 대한 HMAC 과 일치해야 통과 — verdictStatus
    #     직접 위조(writable property)를 차단.
    if require_signed_selection:
        node = store.find_one("name", concept, "AbstractClass")
        sel = gate.verify_selection(node["props"] if node else None, expected_cycle_id=cycle_id)
        if not sel.ok:
            return {
                "ok": False,
                "realized": False,
                "selection_reason": sel.reason,
                "expected_artifact_id": expected_artifact_id,
                "concept": concept,
                "cycle_id": cycle_id,
            }

    # 3. VERIFY — provenance + content. ok=False ⇒ realize/write 절대 없음.
    result = gate.verify(
        verdict,
        expected_cycle_id=cycle_id,
        expected_artifact_id=expected_artifact_id,
    )
    if not result.ok:
        return {
            "ok": False,
            "realized": False,
            "gate_reason": result.reason,
            "expected_artifact_id": expected_artifact_id,
            "concept": concept,
            "cycle_id": cycle_id,
        }

    # 4. PASS ⇒ 그 한 gated concept 만 실현. run_hades(concept=...) 는 _FETCH_ONE(로컬 라우트
    #    불가)을 쓰므로, pre-fetch 한 단일 row 를 shim 으로 주입(concept=None → _FETCH_ALL 폼).
    #    apply_cypher=None → do_write=False → 항상 dry-run/PLANNED (c6 비가역 위험 차단).
    try:
        run = run_hades(lambda _cy, _pa: rows, apply_cypher=None, concept=None, apply=apply)
    except Exception as exc:  # noqa: BLE001 - realize degraded → fail-closed dict
        return {
            "ok": False,
            "realized": False,
            "gate_reason": result.reason,
            "reason": f"realize failed post-gate: {exc}",
            "degraded": True,
            "concept": concept,
            "cycle_id": cycle_id,
        }

    return {
        "ok": True,
        "realized": True,
        "gate_reason": result.reason,
        "expected_artifact_id": expected_artifact_id,
        "concept": concept,
        "cycle_id": cycle_id,
        "candidates": len(run.verdicts),
        "dry_run": bool(run.dry_run),
        "applied_count": run.applied_count,
        "summary": run.summary,
        "backend": "local-kg (infra-0; apply_cypher 미배선 → realize 는 PLANNED)",
    }


def register(mcp: Any) -> None:
    """Attach the `hades_realize` tool to the FastMCP instance."""

    @mcp.tool()
    def hades_realize(
        cycle_id: str = "mcp-legion",
        verdict: dict[str, Any] | None = None,
        concept: str = "",
        apply: bool = False,
        kg_path: str = "",
        require_signed_selection: bool = False,
    ) -> dict[str, Any]:
        """Realize an ACCEPTED abstraction (실현) ONLY behind a verified verdict.

        Fail-closed: a weak/absent HMAC key, or any forged/stale/cross-artifact/
        unsigned verdict, returns a refused dict with NO KG write. The
        expected_artifact_id is recomputed server-side from the concept's extent —
        caller-supplied artifact ids are not trusted. With require_signed_selection
        the target AbstractClass node must also carry a valid node_signature (OQ1b).
        """
        return hades_realize_impl(
            cycle_id=cycle_id,
            verdict=verdict or {},
            concept=concept,
            apply=apply,
            kg_path=kg_path or None,
            require_signed_selection=require_signed_selection,
        )


__all__ = ["register", "hades_realize_impl"]
