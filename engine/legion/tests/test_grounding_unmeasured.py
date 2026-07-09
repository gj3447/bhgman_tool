"""빈 획득 = 미측정 (seam-integrity 20260708, RED-first).

PR#57 grounding-wire 는 vacuous 1.0 을 죽였지만 거울상을 남겼다: MCP/infra-0 경로
(fetcher 부재 → findings 구조적 0)에서 citation_urls=[] → ratio 0.0 → <0.3 self-recurse 가
*매 run* 발화 — 항상-발화 컨트롤은 불-발화 컨트롤과 같은 정보량 0 이다 (2026-07-08 감사
confirmed-high, 빈 획득 2/2 run 오발화 실측). v2: 미측정은 measure() 키 부재로 흐르고
decide_dispatch 가 스킵하며, MCP 응답은 dispatch 관측면을 노출해 오발화를 표면에서 보이게 한다.
판별력 counter(실 findings 비접지 → 발화)는 test_grounding_wire.py 가 계속 핀한다.

# KG: LakatosTree_BhgmanSeamIntegrity_20260708/grounding_measurement_liveness
"""

from __future__ import annotations

from engine.kg_local.runner import make_local_runner
from engine.kg_local.store import LocalKgStore
from engine.legion.commanders import build_default_legion
from engine.legion.measurement import PrometheusMeasurement
from engine.mcp_server.tools.legion import legion_run_impl

METRIC = "external_grounding_ratio"


def test_default_measurement_is_unmeasured():
    assert METRIC not in PrometheusMeasurement().measure()


def test_empty_acquisition_does_not_fire_self_recurse():
    rc = make_local_runner(LocalKgStore(), autosave=False)
    run = build_default_legion().run({"run_cypher": rc, "cycle_id": "unmeasured-red"})
    fired = [d for d in run.dispatch_decisions if d.metric_name == METRIC]
    assert fired == [], f"획득 0건인데 접지 self-recurse 오발화: {fired}"


def test_mcp_surface_exposes_dispatch_and_does_not_fire_on_empty():
    out = legion_run_impl(cycle_id="unmeasured-mcp")
    assert "dispatch" in out, "dispatch 관측면이 MCP 응답에 노출돼야 한다"
    assert [d for d in out["dispatch"] if d["metric"] == METRIC] == []
