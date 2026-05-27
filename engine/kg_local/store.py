"""LocalKgStore — 무의존(stdlib) JSON 파일 그래프 저장소. neo4j 대체.

엔진들(occam/hades/eureka)은 외부 neo4j 없이 이 store 위에서 돈다. JSON 단일 파일
(기본 ~/.bhgman/kg.json) — 사람이 읽을 수 있고, atomic write(temp+rename)로 안전.
스케일: 노드 수천 = 작은 JSON, 전량 로드 OK (occam은 어차피 전 SourceCodeNode 스캔).

모델:
  nodes: [{labels: [...], props: {...}}]   # 인덱스 = list 위치
  edges: [{src: idx, type: REL, dst: idx}]

검증: merge_node가 schema.validate_node로 required 강제(neo4j NOT NULL constraint 미러).

# KG: bhgman-local-kg-backend-2026-05-28, t_sourcecode_required_fields_not_null
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from schema import validate_node


def default_kg_path() -> Path:
    """로컬 KG 파일 경로. BHGMAN_KG_PATH > ~/.bhgman/kg.json."""
    env = os.environ.get("BHGMAN_KG_PATH")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".bhgman" / "kg.json"


class LocalKgStore:
    """JSON 파일 기반 in-process 그래프. load → mutate → save(atomic)."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else default_kg_path()
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self._load()

    # ── persistence ──────────────────────────────────────────────────────
    def _load(self) -> None:
        if self.path.exists():
            data = json.loads(self.path.read_text() or "{}")
            self.nodes = data.get("nodes", [])
            self.edges = data.get("edges", [])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"nodes": self.nodes, "edges": self.edges}, ensure_ascii=False, indent=1
        )
        # atomic: temp + rename (부분쓰기로 KG 깨짐 방지)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(payload)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    # ── node ops ─────────────────────────────────────────────────────────
    def find_nodes(
        self, label: str | None = None, where: Callable[[dict], bool] | None = None
    ) -> list[dict]:
        out = []
        for n in self.nodes:
            if label is not None and label not in n["labels"]:
                continue
            if where is not None and not where(n["props"]):
                continue
            out.append(n)
        return out

    def find_one(self, prop: str, value: Any, label: str | None = None) -> dict | None:
        for n in self.nodes:
            if label is not None and label not in n["labels"]:
                continue
            if n["props"].get(prop) == value:
                return n
        return None

    def merge_node(self, label: str, key_prop: str, key_val: Any, props: dict) -> dict:
        """upsert by (label, key_prop=key_val). required-field 검증(schema). 위반 시 ValueError."""
        merged = {key_prop: key_val, **props}
        violation = validate_node(label, merged)
        if violation is not None:
            raise ValueError(
                f"LocalKgStore schema violation: {violation.reason} ({label} {key_val})"
            )
        node = self.find_one(key_prop, key_val, label)
        if node is None:
            node = {"labels": [label], "props": {}}
            self.nodes.append(node)
        if label not in node["labels"]:
            node["labels"].append(label)
        node["props"].update(merged)
        return node

    # ── edge ops ─────────────────────────────────────────────────────────
    def add_edge(self, src: dict, type_: str, dst: dict) -> None:
        si, di = self.nodes.index(src), self.nodes.index(dst)
        e = {"src": si, "type": type_, "dst": di}
        if e not in self.edges:
            self.edges.append(e)

    def out_edges(self, node: dict) -> list[tuple[str, dict]]:
        """(rel_type, dst_node) 리스트."""
        idx = self.nodes.index(node)
        return [(e["type"], self.nodes[e["dst"]]) for e in self.edges if e["src"] == idx]


__all__ = ["LocalKgStore", "default_kg_path"]
