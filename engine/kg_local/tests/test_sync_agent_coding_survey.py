"""agent-coding 지식 코퍼스 로컬 KG 적재 TDD (method B, GENERATED mirror).

# KG: agent-coding-survey-local-ingest-2026-06-27
"""
from __future__ import annotations

from pathlib import Path

from engine.kg_local.store import LocalKgStore
from engine.kg_local.survey_sync import apply_sot, load_sot, verify_sot

SOT = Path(__file__).resolve().parents[3] / "scripts" / "agent_coding_survey.json"


def test_sot_loads_with_nodes_and_edges():
    sot = load_sot(SOT)
    assert sot["nodes"] and sot["edges"]


def test_before_apply_everything_is_missing(tmp_path):
    store = LocalKgStore(path=tmp_path / "kg.json")
    sot = load_sot(SOT)
    missing = verify_sot(store, sot)
    assert len(missing) >= len(sot["nodes"])  # 빈 store → 최소 모든 노드 MISSING


def test_apply_then_verify_is_drift_free(tmp_path):
    store = LocalKgStore(path=tmp_path / "kg.json")
    sot = load_sot(SOT)
    stats = apply_sot(store, sot)
    store.save()
    assert stats["nodes"] == len(sot["nodes"])
    assert stats["edges_added"] == len(sot["edges"])
    assert verify_sot(store, sot) == []  # drift 0


def test_apply_is_idempotent(tmp_path):
    store = LocalKgStore(path=tmp_path / "kg.json")
    sot = load_sot(SOT)
    apply_sot(store, sot)
    n1, e1 = len(store.nodes), len(store.edges)
    again = apply_sot(store, sot)  # 두 번째 적재
    assert again["edges_added"] == 0  # 새 엣지 0 (멱등)
    assert len(store.nodes) == n1 and len(store.edges) == e1


def test_research_finding_required_fields_enforced(tmp_path):
    # known 라벨 ResearchFinding 은 findingId+oneLineSummary required — SoT 가 충족.
    store = LocalKgStore(path=tmp_path / "kg.json")
    apply_sot(store, load_sot(SOT))
    rf = store.find_one("findingId", "rf-durable-engines-deepdive-20260627", "ResearchFinding")
    assert rf is not None and rf["props"].get("oneLineSummary")


def test_new_label_and_edge_types_persist(tmp_path):
    # 신규 라벨(DurableEngine)/엣지(IMPLEMENTS, RIVALS)가 로컬 store 에 실제로 들어간다.
    store = LocalKgStore(path=tmp_path / "kg.json")
    apply_sot(store, load_sot(SOT))
    temporal = store.find_one("name", "Temporal", "DurableEngine")
    assert temporal is not None
    out = store.out_edges(temporal)
    types = {t for t, _ in out}
    assert {"IMPLEMENTS", "SITS_IN_TIER", "RIVALS", "INFORMED_BY"} <= types
