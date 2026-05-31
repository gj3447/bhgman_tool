"""make_local_runner — 엔진의 CypherRunner를 로컬 store로 충족 (neo4j 없이).

엔진들(occam/hades/eureka)은 고정된 소수의 cypher 템플릿만 emit한다. 범용 cypher 파서
대신 *그 템플릿들의 feature*(특징 substring)로 dispatch → LocalKgStore 연산에 매핑.
whitespace에 견고(정확 문자열 매칭 아님). 미지 쿼리는 조용히 빈 결과 대신 *명시적 에러*
(UnsupportedLocalQuery) — 로컬 모드 한계를 정직하게 노출(거짓 0-drift 방지).

지원 (engine 핵심 KG 동사):
  - occam: SourceCodeNode fetch / supersede
  - hades: AbstractClass(ACCEPTED) fetch / materialize MERGE / INSTANCE_OF link
  - eureka: facet formal-context read
  - longinus/binding: SourceCodeNode merge + sha256 rebind(UNWIND)

# KG: bhgman-local-kg-backend-2026-05-28
"""

from __future__ import annotations

from collections.abc import Callable

from engine.kg_local.store import LocalKgStore

CypherRunner = Callable[[str, dict], "list[dict]"]


class UnsupportedLocalQuery(RuntimeError):
    """로컬 backend가 인식 못 한 cypher. 조용한 오답 대신 명시 실패."""


def _fetch_source_nodes(store: LocalKgStore, params: dict) -> list[dict]:
    scope = params.get("scope")

    def ok(p: dict) -> bool:
        if p.get("sha256") in (None, "") or p.get("lineCount") is None or not p.get("sourcePath"):
            return False
        if p.get("status") == "SUPERSEDED":
            return False
        return scope is None or (scope in str(p.get("sourcePath", "")))

    return [
        {
            "name": n["props"].get("name"),
            "source_path": n["props"]["sourcePath"],
            "sha256": n["props"]["sha256"],
            "line_count": n["props"]["lineCount"],
        }
        for n in store.find_nodes("SourceCodeNode", ok)
    ]


def _occam_supersede(store: LocalKgStore, params: dict) -> list[dict]:
    stale = store.find_one("name", params["stale_name"], "SourceCodeNode")
    current = store.find_one("name", params["current_name"], "SourceCodeNode")
    if stale is None or current is None or stale is current:
        return []
    stale["props"].update(
        {
            "status": "SUPERSEDED",
            "supersededBy": params["current_name"],
            "supersededReason": params.get("reason", ""),
            "occamPass": "occam",
        }
    )
    store.add_edge(stale, "SUPERSEDED_BY", current)
    return [{"superseded": params["stale_name"], "current": params["current_name"]}]


def _hades_fetch_accepted(store: LocalKgStore, params: dict) -> list[dict]:
    want = params.get("concept")

    def ok(p: dict) -> bool:
        if p.get("verdictStatus") != "ACCEPTED" or p.get("status") == "CANONICAL":
            return False
        return want is None or p.get("name") == want

    return [
        {
            "concept": n["props"]["name"],
            "verdict": n["props"].get("verdictStatus"),
            "members": list(n["props"].get("extent") or []),
        }
        for n in store.find_nodes("AbstractClass", ok)
    ]


def _hades_merge_concept(store: LocalKgStore, params: dict) -> list[dict]:
    store.merge_node(
        "AbstractClass", "name", params["concept"], {"status": "CANONICAL", "realizedBy": "hades"}
    )
    return []


def _hades_link_members(store: LocalKgStore, params: dict) -> list[dict]:
    ac = store.find_one("name", params["concept"], "AbstractClass")
    if ac is None:
        ac = store.merge_node("AbstractClass", "name", params["concept"], {})
    for m in params.get("members") or []:
        member = store.find_one("name", m) or store.merge_node("Node", "name", m, {})
        store.add_edge(member, "INSTANCE_OF", ac)
    return []


def _eureka_facets(store: LocalKgStore, params: dict) -> list[dict]:
    facet_rels = set(params.get("facet_rels") or [])
    bulk = set(params.get("bulk_labels") or [])
    hub_cap = params.get("hub_cap", 4)
    min_facets = params.get("min_facets", 2)
    rows: list[dict] = []
    for n in store.nodes:
        if any(lbl in bulk for lbl in n["labels"]):
            continue
        attrs, dsts = set(), set()
        for rel, dst in store.out_edges(n):
            if rel in facet_rels and dst["props"].get("name"):
                attrs.add(f"{rel}:{dst['props']['name']}")
                dsts.add(dst["props"]["name"])
        if len(dsts) <= hub_cap and len(attrs) >= min_facets:
            rows.append({"object": n["props"].get("name"), "attributes": sorted(attrs)})
    return rows


def _merge_source_node(store: LocalKgStore, params: dict) -> list[dict]:
    # 단일 바인딩 (F5/F7 류). sourcePath 키.
    sp = params.get("sourcePath") or params.get("source_path")
    if not sp:
        return []
    props = {k: v for k, v in params.items() if k not in ("scope",)}
    store.merge_node("SourceCodeNode", "sourcePath", sp, props)
    return []


def _harness_persist(store: LocalKgStore, params: dict) -> list[dict]:
    # harness 진단 persist: HarnessDiagnosis 노드 upsert (name=subject 키).
    props = {k: v for k, v in params.items() if k != "subject"}
    store.merge_node("HarnessDiagnosis", "name", params["subject"], props)
    return [{"diagnosed": params["subject"]}]


def _rebind_sha(store: LocalKgStore, params: dict) -> list[dict]:
    # Longinus UNWIND $rows: [{path, sha, lines}]
    n = 0
    for r in params.get("rows") or []:
        node = store.find_one("sourcePath", r["path"], "SourceCodeNode")
        if node is not None:
            node["props"].update(
                {"sha256": r["sha"], "sha256_baseline": r["sha"], "lineCount": r["lines"]}
            )
            n += 1
    return [{"updated": n}]


# dispatch 테이블: (cypher 매칭 predicate, handler, is_write). 위→아래 첫 매치.
# elif 체인 대신 루프 = 낮은 cognitive complexity + 라우트 추가 용이.
_ROUTES: list[tuple[Callable[[str], bool], Callable, bool]] = [
    (lambda c: "stale.status = 'SUPERSEDED'" in c, _occam_supersede, True),
    (lambda c: "MERGE (a:AbstractClass {name:$concept})" in c, _hades_merge_concept, True),
    (lambda c: "INSTANCE_OF" in c and "$members" in c, _hades_link_members, True),
    (lambda c: "UNWIND $rows" in c and "s.sha256" in c, _rebind_sha, True),
    (lambda c: "MERGE (h:HarnessDiagnosis" in c, _harness_persist, True),
    (lambda c: "MERGE (s:SourceCodeNode" in c, _merge_source_node, True),
    (lambda c: "$facet_rels" in c, _eureka_facets, False),
    (lambda c: "(a:AbstractClass)" in c and "verdictStatus" in c, _hades_fetch_accepted, False),
    (
        lambda c: "(s:SourceCodeNode)" in c and "RETURN s.name AS name" in c,
        _fetch_source_nodes,
        False,
    ),
]


def make_local_runner(store: LocalKgStore, autosave: bool = True) -> CypherRunner:
    """LocalKgStore를 엔진 CypherRunner로. write 후 autosave(atomic)."""

    def run_cypher(cypher: str, params: dict) -> list[dict]:
        for matches, handler, is_write in _ROUTES:
            if matches(cypher):
                rows = handler(store, params)
                if is_write and autosave:
                    store.save()
                return rows
        raise UnsupportedLocalQuery(
            "local KG backend가 인식 못 한 쿼리 (neo4j 전용). 첫 80자: " + cypher.strip()[:80]
        )

    return run_cypher


__all__ = ["UnsupportedLocalQuery", "make_local_runner"]
