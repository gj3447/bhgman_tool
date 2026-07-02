"""eureka_induce MCP tool + legion earned-count 승격 (7군단장 실체감사 wf_376c327b-8f3, 유레카 갭).

RED-first: 유레카는 형제 중 유일하게 MCP 전용 툴이 없었고(tools/eureka.py 부재), legion 표면
(_run_induce)은 자기 ooptdd 어댑터가 empty-KG fake-green 이라고 *증명해 둔* stages_ok 지표로
보고했다(빈 KG 에서 stages_ok=5 green-향 요약). 이 파일이 봉인하는 계약:

  1. eureka_induce MCP 툴: run_from_kg 실엔진 경로를 태우고, 카운트는 stage payload
     ('4-induce'.abstract_classes / '4.5-quality-gate'.survived)에서 EARNED — 직접 재계산과
     parity (stages_ok 재포장이 아님).
  2. 빈 KG 정직 영점 (NOVEL 축): 빈 KG 에서 stages_ok 는 여전히 >0 (파이프라인은 돌았다)이지만
     earned induced==0 — 두 지표가 실제로 *다른 것* 을 측정함을 판별.
  3. legion _run_induce 가 earned counts(induced/survived)를 보고 — stages_ok 는 진단 필드로
     강등(요약의 머리는 earned).
  4. 3-file 등록(registry/security/server) 일관성.

# KG: LakatosTree_Bhgman6CommanderOoptdd_20260624/eureka_mcp_earned_counts
# KG: eureka-canonical-2026-05-26
"""

from __future__ import annotations

from pathlib import Path

from engine.kg_local.runner import make_local_runner
from engine.kg_local.store import LocalKgStore
from engine.legion.commanders import _run_induce
from engine.mcp_server.registry import _CATALOG_SEED, catalog_is_consistent_with_security
from engine.mcp_server.security import TOOL_CAPABILITIES, Capability
from engine.mcp_server.server import list_registered_tool_names
from engine.mcp_server.tools.eureka import eureka_induce_impl


def _direct_earned(store: LocalKgStore) -> tuple[int, int]:
    """독립 재계산: 같은 결정론 번들 store 에서 run_from_kg 를 직접 돌려 earned 카운트 재도출."""
    from engine.eureka import pipeline, stages

    rc = make_local_runner(store, autosave=False)
    cfg = pipeline.PipelineConfig(cycle_id="direct", **stages.wire_default_stages(rc))
    pr = pipeline.run_from_kg(rc, cfg)

    def count(prefix: str, key: str) -> int:
        for s in pr.stages:
            if s.stage.startswith(prefix) and isinstance(s.payload, dict):
                return int(s.payload.get(key, 0) or 0)
        return 0

    return count("4-induce", "abstract_classes"), count("4.5-quality-gate", "survived")


def test_eureka_induce_earned_counts_parity():
    """MCP 응답의 earned 카운트 == 독립 엔진 재계산 (stages_ok 재포장 불가 — 값이 payload 유래)."""
    resp = eureka_induce_impl(cycle_id="eureka-tool-parity", store=LocalKgStore())
    want_induced, want_survived = _direct_earned(LocalKgStore())

    assert resp["earned"]["induced"] == want_induced
    assert resp["earned"]["survived"] == want_survived
    assert resp["mode"] == "fca"
    assert "stages" in resp, "stage 진단은 동봉하되 earned 가 머리"


def test_eureka_induce_empty_kg_honest_zero(tmp_path):
    """NOVEL 축(빈-KG 판별): 빈 KG 에서 파이프라인 stages 는 돌았는데(stages_ok>0) earned 는
    정직한 0 — stages_ok 로는 볼 수 없는 영점을 earned 카운트가 드러낸다."""
    resp = eureka_induce_impl(cycle_id="eureka-tool-empty", store=LocalKgStore(tmp_path / "e.json"))

    assert resp["earned"]["induced"] == 0
    assert resp["earned"]["survived"] == 0
    assert resp["stages_ok"] > 0, "파이프라인 자체는 돌았다 — 이것이 stages_ok 의 fake-green 축"


def test_legion_induce_reports_earned_counts(tmp_path):
    """legion 표면 승격: _run_induce payload 의 머리는 earned(induced/survived) — 빈 KG 에서
    'induced=0' 이 요약에 보인다 (green-향 'N/M stages ok' 단독 보고 금지)."""
    rc = make_local_runner(LocalKgStore(tmp_path / "e.json"), autosave=False)
    out = _run_induce({"run_cypher": rc, "cycle_id": "legion-earned"})

    ab = out["abstractions"]
    assert ab["induced"] == 0
    assert ab["survived"] == 0
    assert "induced=0" in ab["summary"], ab["summary"]
    assert "stages_ok" in ab, "진단 필드로 유지(강등이지 삭제 아님)"


def test_amie3_without_vendor_jar_fails_loud():
    """(c) amie3 정직화 핀: vendor JAR 부재 시 침묵 degraded 가 아니라 다운로드 지침을 담은
    FileNotFoundError 로 fail-loud — 'bake-off' 주장이 무JAR 박스에서 무음 fake 로 서지 않는다.
    (JAR 을 실제로 내려받은 박스에서는 skip — 그 박스에선 실경로가 참이므로 핀 대상 아님.)"""
    import pytest

    from engine.eureka import pipeline, stages

    jar = Path(__file__).resolve().parents[2] / "eureka" / "vendor" / "amie3.5.1.jar"
    if jar.is_file():
        pytest.skip("vendor JAR 실재 — fail-loud 핀은 무JAR 박스 전용")
    rc = make_local_runner(LocalKgStore(), autosave=False)
    cfg = pipeline.PipelineConfig(
        cycle_id="amie3-pin", method="amie3", **stages.wire_default_stages(rc)
    )
    with pytest.raises(FileNotFoundError, match="amie3.5.1.jar"):
        pipeline.run_from_kg(rc, cfg)


def test_three_file_registration_consistent():
    """3-file 등록: registry 카탈로그(kind read) + security 능력 + server 툴 노출 전부 일치."""
    entry = next(t for t in _CATALOG_SEED if t[0] == "eureka_induce")
    assert entry[3] == "read", "PROPOSE-only 결정론 induce = read"
    assert TOOL_CAPABILITIES["eureka_induce"] == frozenset({Capability.READS_PRIVATE_DATA})
    assert catalog_is_consistent_with_security()
    assert "eureka_induce" in set(list_registered_tool_names())
