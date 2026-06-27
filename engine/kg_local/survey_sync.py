"""agent-coding 지식 코퍼스 → 로컬 KG GENERATED mirror (method B: cypher 디스패치 우회).

라이브 neo4j 적재는 `agent-coding-kg-load.cypher`(idempotent MERGE). 로컬 KG 는 runner.py
``_ROUTES`` substring 화이트리스트가 신규 라벨 MERGE 를 막으므로(UnsupportedLocalQuery),
:class:`~engine.kg_local.store.LocalKgStore` 의 ``merge_node``/``add_edge`` 를 **직접** 호출한다.

SoT = JSON 파일(``scripts/agent_coding_survey.json``). 손-큐레이션 미러=drift factory
(2026-06-18 교훈) → JSON 을 단일 SoT 로 두고 ``--verify``(MISSING/DRIFT)/``--apply`` 분리.
unknown 라벨은 schema.validate_node 가 자유 통과(신규 라벨 보호 0, 의도된 것), ResearchFinding
같은 known 라벨은 required(findingId/oneLineSummary) 강제.

# KG: agent-coding-survey-local-ingest-2026-06-27
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine.kg_local.store import LocalKgStore


def load_sot(path: str | Path) -> dict:
    """SoT JSON 로드. {nodes:[{label,key,value,props}], edges:[{src,type,dst}]}."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _k(label: str, value: Any) -> tuple[str, str]:
    return (label, str(value))


def apply_sot(store: LocalKgStore, sot: dict) -> dict:
    """SoT 노드/엣지를 store 에 멱등 적재. 반환 {nodes, edges_added}."""
    index: dict[tuple[str, str], dict] = {}
    for n in sot["nodes"]:
        node = store.merge_node(n["label"], n.get("key", "name"), n["value"], n.get("props", {}))
        index[_k(n["label"], n["value"])] = node
    edges_added = 0
    for e in sot["edges"]:
        src = index.get(_k(e["src"]["label"], e["src"]["value"]))
        dst = index.get(_k(e["dst"]["label"], e["dst"]["value"]))
        if src is None or dst is None:
            raise ValueError(f"edge endpoint not declared as a SoT node: {e}")
        before = len(store.edges)
        store.add_edge(src, e["type"], dst)
        edges_added += len(store.edges) - before
    return {"nodes": len(sot["nodes"]), "edges_added": edges_added}


def verify_sot(store: LocalKgStore, sot: dict) -> list[str]:
    """SoT 에 있으나 store 에 없는 노드/엣지 = MISSING(drift). 변이 없음. 빈 리스트=clean."""
    missing: list[str] = []
    found: dict[tuple[str, str], dict | None] = {}
    for n in sot["nodes"]:
        node = store.find_one(n.get("key", "name"), n["value"], n["label"])
        found[_k(n["label"], n["value"])] = node
        if node is None:
            missing.append(f"NODE {n['label']}:{n['value']}")
    for e in sot["edges"]:
        src = found.get(_k(e["src"]["label"], e["src"]["value"]))
        dst = found.get(_k(e["dst"]["label"], e["dst"]["value"]))
        if src is None or dst is None:
            missing.append(f"EDGE {e['type']} (endpoint missing)")
            continue
        if not any(t == e["type"] and d is dst for t, d in store.out_edges(src)):
            missing.append(f"EDGE {e['src']['value']}-{e['type']}->{e['dst']['value']}")
    return missing


__all__ = ["apply_sot", "load_sot", "verify_sot"]
