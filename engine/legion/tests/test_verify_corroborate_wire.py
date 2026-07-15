"""나생문 kg-corroborate 자동화 경로 배선 (q-naesengmoon-single-authority 봉인 — RED artifact).

kg-corroborate(별도-소스 정전 대조 oracle)는 정확히 이 frontier 질문을 닫으려고 만들어졌지만
CLI verify() 에서만 도달 가능했고, 자동화 경로(_run_verify legion 경로)엔 미배선이었다. 게다가
LLM client 부재 시 legion verify 는 upstream-completeness critic 1개(n_eff=1.0)로 퇴화했다
(7-commander substance audit 나생문 갭).

이 파일이 배선을 고정한다:
  1. ctx 에 grounding(GroundingSource) 제공 시 kg_corroboration_oracle 이 ORACLE leg 로 합류 —
     oracle 은 Kish n_eff 에 독립 가산이라 offline n_eff 가 1.0 → 2.0.
  2. (NOVEL) 정전(CanonicalName 등) 노드와 정반대 극성의 고겹침 claim 은 ensemble 거부(veto),
     정합 claim 은 통과 — 별도-소스 판별이 실제 KG canon 을 읽는다.
  3. grounding 부재 시 현행 유지 + oracle_legs 공시 (vacuous critic 조작 금지).
  4. MCP legion_run 응답이 final_verdict(ensemble/n_eff/oracle_legs)를 노출하고, MCP 경로가
     LocalGroundingSource(store) 주입으로 infra-0 에서 n_eff ≥ 2.

# KG: LakatosTree_Bhgman6CommanderOoptdd_20260624/naesengmoon_corroborate_wire
# KG: q-naesengmoon-single-authority
"""

from __future__ import annotations

from engine.agents.grounding import LocalGroundingSource
from engine.kg_local.runner import make_local_runner
from engine.kg_local.store import LocalKgStore
from engine.legion.commanders import _run_verify
from engine.mcp_server.tools.legion import legion_run_impl

_OK_UPSTREAM = {
    "acquired": {"mode": "kg-deterministic"},
    "bindings": {"mode": "ok"},
    "abstractions": {"mode": "fca"},
    "hygiene": {"mode": "ok"},
}


def _store_with_canon(truth: str) -> LocalKgStore:
    store = LocalKgStore()
    store.merge_node(
        "CanonicalName",
        "name",
        "canon-fact",
        {"name": "canon-fact", "claim": truth},
    )
    return store


def _verify_ctx(store: LocalKgStore, claim: str) -> dict:
    return {
        "run_cypher": make_local_runner(store, autosave=False),
        "cycle_id": "ncw-test",
        "grounding": LocalGroundingSource(store),
        "claim": claim,
        **_OK_UPSTREAM,
    }


def test_offline_verify_gains_corroborate_leg():
    """배선 1: grounding 제공 시 kg-corroborate 가 ORACLE leg 로 합류 → offline n_eff 2.0."""
    store = _store_with_canon("the legion substrate is deterministic")
    out = _run_verify(_verify_ctx(store, "the legion substrate is deterministic"))["verdict"]
    assert "kg-corroborate" in out["oracle_legs"], out
    assert out["n_eff"] >= 2.0, f"oracle 은 독립 가산 — n_eff 1.0 퇴화 해소; got {out['n_eff']}"
    assert out["ensemble"] == "PASS"


def test_contradicted_claim_is_vetoed():
    """NOVEL 축: 정전 노드와 정반대 극성(고겹침) claim → 별도-소스 veto (ensemble 비-PASS)."""
    store = _store_with_canon("the retrospective mapping is not dispatch")
    out = _run_verify(_verify_ctx(store, "the retrospective mapping is dispatch"))["verdict"]
    assert out["ensemble"] != "PASS", f"정전 모순 claim 은 veto 되어야; got {out}"


def test_no_grounding_keeps_current_with_disclosure():
    """grounding 부재 시 현행(upstream-completeness 1 leg) 유지 + 공시 — 조용한 leg 조작 금지."""
    store = LocalKgStore()
    ctx = {
        "run_cypher": make_local_runner(store, autosave=False),
        "cycle_id": "ncw-nog",
        **_OK_UPSTREAM,
    }
    out = _run_verify(ctx)["verdict"]
    assert out["oracle_legs"] == ["upstream-completeness"], out
    assert out["n_eff"] == 1.0


def test_mcp_legion_run_surfaces_verdict_and_corroborate_leg():
    """배선 4: MCP legion_run 이 LocalGroundingSource 를 주입하고 응답에 final_verdict 노출.

    2026-07-15 정정 (적대검증): 이 테스트는 **빈 store**(정전 완전 침묵)에 `n_eff >= 2.0`
    을 단언하며 정확히 vacuous inflation 을 고정하고 있었다 — canon 이 아무 말도 없는데
    kg-corroborate 의 *기권* 이 완전한 독립표로 계수돼 n_eff 를 1.0→2.0 으로 올린 것이다.
    그건 레포 자신의 "vacuous critic 금지" 위반이자 clean-PASS floor(T0-1)가 MCP 경로에서
    영영 물지 못한 원인이었다. 정직한 단언: leg 는 합류하되(공시), 침묵 정전에 대해서는
    기권이므로 n_eff 는 1.0 이다. 진짜 2.0 은 canon 이 실재할 때만 (아래 테스트)."""
    resp = legion_run_impl(cycle_id="ncw-mcp", store=LocalKgStore())
    v = resp["verdict"]
    assert "kg-corroborate" in v["oracle_legs"], v  # leg 는 합류 (공시)
    assert v["n_eff"] == 1.0, f"침묵 정전에 대한 기권은 표가 아니다: {v}"


def test_mcp_path_reaches_two_legs_when_canon_actually_speaks():
    """canon 이 실재하면 kg-corroborate 가 *진짜* corroboration 표를 내고 n_eff 가 2.0.

    '기권은 표 아님' 정정이 leg 자체를 죽인 게 아님을 고정한다 — 정보가 있을 때만 계수."""
    store = _store_with_canon("legion closed loop completed for ncw-real")
    resp = legion_run_impl(cycle_id="ncw-real", store=store)
    v = resp["verdict"]
    assert "kg-corroborate" in v["oracle_legs"], v
    assert v["n_eff"] >= 2.0, f"실재 canon 과 고겹침이면 진짜 표: {v}"
