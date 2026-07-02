"""seed_germinate E1(orphan anchor) KG-seam (jbm-s8 — s2가 정직 공시로 남긴 마지막 구멍).

RED-first: s2 승격 후에도 seed_germinate 는 로컬 4불변식(dup-PK/depth/dangling/E3)만 강제했고,
E1(외부 anchor 가 KG 에 실존하나 — FK orphan)은 run_cypher seam 미배선으로 검사 불가였다
(모듈 docstring 이 "E1 은 여기서 안 본다"고 공시). 로컬 러너가 _ORPHAN_ANCHOR_CYPHER 를 이미
지원함을 실측 확인 → 이 파일이 승격을 고정한다:

  1. kg 제공 시(E1 seam): 부재 anchor 를 가리키는 spec 은 E1_ORPHAN_ANCHOR 로 BLOCKED
     (fail-closed, 계획 0).
  2. (NOVEL) 같은 spec 이 anchor 실재 store 에선 PLANNED — E1 이 *실제 KG* 를 읽어 판별한다
     (장식 상수가 아님).
  3. kg 미제공 시: 현행 로컬-4 유지 + 응답에 정직 공시(E1 미검) — infra-0 covenant 보존,
     조용한 범위 과장 금지.
  4. 5개 위반 코드 전종이 MCP 경계에서 판별 가능 (improve 축: 4 → 5).

# KG: LakatosTree_BhgmanJaebaeman_20260702/jbm_s8_germinate_e1_kg_seam
# KG: 재배맨-v2-subagent-runtime-protocol
"""

from __future__ import annotations

from engine.jaebaeman.jaebaeman_models import ViolationCode
from engine.kg_local.store import LocalKgStore
from engine.mcp_server.tools.symposium import SeedGerminateRequest, _seed_germinate_impl

_ORPHAN_SPEC = {"seeds": [{"name": "e1-seed", "anchor": "e1-anchor-node"}]}


def _call(payload: dict, store=None) -> dict:
    return _seed_germinate_impl(
        SeedGerminateRequest(spec_name="jbm-s8", payload=payload, parent_cycle_id="jbm-s8-test"),
        store=store,
    )


def _store_with_anchor() -> LocalKgStore:
    store = LocalKgStore()
    store.merge_node("Concept", "name", "e1-anchor-node", {"name": "e1-anchor-node"})
    return store


def test_orphan_anchor_blocked_at_mcp_with_kg():
    """E1 seam: KG 를 주면 부재 anchor 는 MCP 경계에서 fail-closed BLOCKED."""
    resp = _call(_ORPHAN_SPEC, store=LocalKgStore())
    assert resp["status"] == "BLOCKED", resp
    assert resp["planned_cyphers"] == []
    codes = {v["code"] for v in resp["violations"]}
    assert ViolationCode.E1_ORPHAN_ANCHOR.value in codes, codes


def test_existing_anchor_planned_with_kg():
    """NOVEL 반대쪽: 같은 spec 이 anchor 실재 store 에선 PLANNED — E1 이 실제 KG 를 읽는다."""
    resp = _call(_ORPHAN_SPEC, store=_store_with_anchor())
    assert resp["status"] == "PLANNED", resp
    assert resp["planned_cyphers"]
    assert resp["engine"]["invariants"] == "local-4+E1"


def test_no_kg_keeps_local_four_with_disclosure():
    """infra-0 보존: kg 미제공이면 현행 로컬-4 (E1 미검) + 응답에 정직 공시 — 조용한 범위
    과장(E1 을 본 척) 금지."""
    resp = _call(_ORPHAN_SPEC)
    assert resp["status"] == "PLANNED", "kg 없인 E1 을 판별할 수 없다 — 미검이 정직"
    assert "E1" in resp["engine"]["invariants"], resp["engine"]
    assert "미검" in resp["engine"]["invariants"], "미검 사실을 공시해야"


def test_all_five_violation_codes_discriminable_at_mcp():
    """improve 축: 5개 위반 코드 전종이 MCP 경계에서 BLOCKED 로 실판별 (기존 4 + E1)."""
    store = LocalKgStore()  # anchor 없음 → E1 재료
    cases = {
        ViolationCode.DUP_SEED_NAME: ({"seeds": [{"name": "d"}, {"name": "d"}]}, None),
        ViolationCode.E4_DEPTH_RANGE: ({"seeds": [{"name": "deep", "depth": 99}]}, None),
        ViolationCode.DANGLING_PARENT: ({"seeds": [{"name": "o", "parent": "nowhere"}]}, None),
        ViolationCode.E3_MULTIPLE_SEED_PER_ANCHOR: (
            {"seeds": [{"name": "a1", "anchor": "shared"}, {"name": "a2", "anchor": "shared"}]},
            None,
        ),
        ViolationCode.E1_ORPHAN_ANCHOR: (_ORPHAN_SPEC, store),
    }
    observed: set[str] = set()
    for code, (payload, st) in cases.items():
        resp = _call(payload, store=st)
        assert resp["status"] == "BLOCKED", f"{code}: {resp}"
        got = {v["code"] for v in resp["violations"]}
        assert code.value in got, f"{code.value} not in {got}"
        observed.add(code.value)
    assert len(observed) == 5
