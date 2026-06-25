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
  - prometheus: gap-scan(OpenQuestion/VerdictPending) read + :ResearchFinding ingest write
  - jaebaeman: 분해 anchor 자식 read + SubagentTaskSpec 씨앗 MERGE + HAS_SEED/DECOMPOSES_TO 엣지

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

    matched = store.find_nodes("SourceCodeNode", ok)
    # inbound 참조 수: neo4j `count(x)` (OPTIONAL MATCH (x)-[]->(s))의 local mirror.
    inbound: dict[int, int] = {}
    for e in store.edges:
        inbound[e["dst"]] = inbound.get(e["dst"], 0) + 1
    idx_of = {id(n): i for i, n in enumerate(store.nodes)}
    return [
        {
            "name": n["props"].get("name"),
            "source_path": n["props"]["sourcePath"],
            "sha256": n["props"]["sha256"],
            "line_count": n["props"]["lineCount"],
            "last_validated": n["props"].get("lastValidated"),
            "created_at": n["props"].get("createdAt"),
            "invocation_count": n["props"].get("invocation_count"),  # oracle_backfill usage (--local parity)
            "inbound_edges": inbound.get(idx_of.get(id(n), -1), 0),
        }
        for n in matched
    ]


# semantic_dedup._KEY_ALLOWLIST mirror — the generic-key supersede matches an *unlabeled*
# node on any of these identity props (stale.{key} = $stale_id).
_GENERIC_IDENTITY_KEYS = ("name", "findingId", "id")


def _occam_supersede_generic(store: LocalKgStore, params: dict) -> list[dict]:
    # semantic_dedup._SUPERSEDE_TMPL 변종: `MATCH (stale) WHERE stale.{key} = $stale_id`
    # (key ∈ {name,findingId,id}, label 무관). params = {stale_id, current_id, reason}.
    # 과거엔 _occam_supersede가 params['stale_path']를 읽어 KeyError → 로컬서 의미론 dedup이
    # silent no-op였다 (applied=0). label-agnostic identity 매칭으로 그 seam을 닫는다.
    def _by(ident: str) -> dict | None:
        for n in store.nodes:
            props = n.get("props", {})
            if any(props.get(k) == ident for k in _GENERIC_IDENTITY_KEYS):
                return n
        return None

    stale = _by(params["stale_id"])
    current = _by(params["current_id"])
    if stale is None or current is None or stale is current:
        return []
    stale["props"].update(
        {
            "status": "SUPERSEDED",
            "supersededBy": params["current_id"],
            "supersededReason": params.get("reason", ""),
            "occamPass": "occam-semantic",
        }
    )
    store.add_edge(stale, "SUPERSEDED_BY", current)
    return [{"superseded": params["stale_id"], "current": params["current_id"]}]


def _occam_supersede(store: LocalKgStore, params: dict) -> list[dict]:
    # 두 supersede 변종 처리 (둘 다 cypher에 `stale.status = 'SUPERSEDED'` 포함 → 같은 라우트):
    #  · generic-key (semantic_dedup, key∈{name,findingId,id}): params에 stale_id → 위 핸들러.
    #  · path+sha (SourceCodeNode, adapter._SUPERSEDE_CYPHER): params에 stale_path/stale_sha.
    if "stale_path" not in params:
        return _occam_supersede_generic(store, params)
    # 복합키 (sourcePath, sha256) 매칭 — name은 schema상 nullable이라 키로 못 씀.
    # (adapter._SUPERSEDE_CYPHER와 동일 식별 계약)
    def _by(path: str, sha: str) -> dict | None:
        return next(
            iter(
                store.find_nodes(
                    "SourceCodeNode",
                    lambda p: p.get("sourcePath") == path and p.get("sha256") == sha,
                )
            ),
            None,
        )

    stale = _by(params["stale_path"], params["stale_sha"])
    current = _by(params["current_path"], params["current_sha"])
    if stale is None or current is None or stale is current:
        return []
    stale["props"].update(
        {
            "status": "SUPERSEDED",
            "supersededBy": params["current_path"],
            "supersededReason": params.get("reason", ""),
            "occamPass": "occam",
        }
    )
    store.add_edge(stale, "SUPERSEDED_BY", current)
    return [{"superseded": params["stale_path"], "current": params["current_path"]}]


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


def _dispatch_event_merge(store: LocalKgStore, params: dict) -> list[dict]:
    """legion W2-A — MERGE a :DispatchEvent (runtime measurement-driven dispatch decision)."""
    key = (
        f"dispatch-{params.get('source_commander')}-{params.get('target_commander')}-"
        f"{params.get('metric_name')}-{params.get('epoch')}"
    )
    store.merge_node("DispatchEvent", "name", key, {k: v for k, v in params.items()})
    return [{"src": params.get("source_commander")}]


def _eureka_persist_abstractclass(store: LocalKgStore, params: dict) -> list[dict]:
    """eureka stage_6 persist (W1-I) — MERGE an AbstractClass with the verdictStatus hades
    fetches on. Distinct from _hades_merge_concept (which marks status=CANONICAL on realize)."""
    store.merge_node(
        "AbstractClass",
        "name",
        params["name"],
        {
            "verdictStatus": params.get("verdictStatus"),
            "status": params.get("status"),
            "summary": params.get("summary"),
            "inductionMethod": params.get("inductionMethod"),
            "cycleId": params.get("cycleId"),
            "extent": list(params.get("extent") or []),
            "intent": list(params.get("intent") or []),
            "stabilityScore": params.get("stabilityScore"),
        },
    )
    return [{"name": params["name"]}]


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


def _gap_scan(store: LocalKgStore, params: dict) -> list[dict]:
    # 프로메테우스 gap-detect: OpenQuestion / VerdictPending 노드 → id/question/kind.
    limit = params.get("limit", 50)
    rows: list[dict] = []
    for n in store.nodes:
        kind = next((lbl for lbl in n["labels"] if lbl in ("OpenQuestion", "VerdictPending")), None)
        if kind is None:
            continue
        p = n["props"]
        gid = p.get("name") or p.get("id")
        if not gid:
            continue
        rows.append(
            {
                "id": gid,
                "question": p.get("question") or p.get("description") or p.get("name") or "",
                "kind": kind,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _research_finding_merge(store: LocalKgStore, params: dict) -> list[dict]:
    # 프로메테우스 ingest: :ResearchFinding upsert (findingId 키). cypher params → 정전 props.
    store.merge_node(
        "ResearchFinding",
        "findingId",
        params["findingId"],
        {
            "findingId": params["findingId"],
            "oneLineSummary": params.get("claim", ""),
            "citation_url": params.get("citation_url", ""),
            "contentSha256": params.get("sha", ""),
            "cycleId": params.get("cycle_id", ""),
            "sourceKgBinding": params.get("gap_id", ""),
            "researchedAt": params.get("researched_at", ""),
        },
    )
    return [{"ingested": params["findingId"]}]


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


def _jaebaeman_seed_merge(store: LocalKgStore, params: dict) -> list[dict]:
    # 재배맨 씨앗 심기 — SubagentTaskSpec upsert. depth coalesce(.,0) (NOT NULL invariant).
    store.merge_node(
        "SubagentTaskSpec",
        "name",
        params["name"],
        {
            "skill": params["skill"],
            "sourceId": params.get("sourceId", params["name"]),
            "displayName": params.get("displayName", ""),
            "taskType": params.get("taskType", ""),
            "targetDomain": params.get("targetDomain", ""),
            "expectedOutcome": params.get("expectedOutcome", ""),
            "germinationMethod": params.get("germinationMethod", "singleton"),
            "depth": params.get("depth") if params.get("depth") is not None else 0,
            "cycleId": params.get("cycle_id"),  # germinate scope key (neo4j _SEED_MERGE 패리티)
            "status": "READY",
        },
    )
    return [{"seeded": params["name"]}]


def _jaebaeman_has_seed(store: LocalKgStore, params: dict) -> list[dict]:
    # anchor↔씨앗 발아 엣지. anchor 노드 없으면 만들어 둔다(임의 라벨 Node, 스키마 자유).
    seed = store.find_one("name", params["seed"], "SubagentTaskSpec")
    if seed is None:
        return []
    anchor = store.find_one("name", params["anchor"]) or store.merge_node(
        "Node", "name", params["anchor"], {}
    )
    store.add_edge(anchor, "HAS_SEED", seed)
    return [{"linked": params["seed"]}]


def _jaebaeman_decomposes_to(store: LocalKgStore, params: dict) -> list[dict]:
    # 계획 트리 엣지: parent_seed → child_seed (계획에 대한 계획).
    parent = store.find_one("name", params["parent"], "SubagentTaskSpec")
    child = store.find_one("name", params["child"], "SubagentTaskSpec")
    if parent is None or child is None:
        return []
    store.add_edge(parent, "DECOMPOSES_TO", child)
    return [{"child": params["child"]}]


def _jaebaeman_methods(store: LocalKgStore, params: dict) -> list[dict]:
    # HTN: task의 HAS_METHOD → DecomposeMethod, 각 method의 DECOMPOSES_TO → subgoals. ord 순.
    task = store.find_one("name", params.get("task"))
    if task is None:
        return []
    methods = []
    for rel, m in store.out_edges(task):
        if rel != "HAS_METHOD" or "DecomposeMethod" not in m["labels"]:
            continue
        subs = [
            {
                "name": s["props"].get("name"),
                "objective": s["props"].get("objective") or s["props"].get("name"),
            }
            for r2, s in store.out_edges(m)
            if r2 == "DECOMPOSES_TO" and s["props"].get("name")
        ]
        methods.append(
            {"method": m["props"].get("name"), "ord": m["props"].get("ord", 0), "subgoals": subs}
        )
    return sorted(methods, key=lambda x: x["ord"])


def _jaebaeman_run_record(store: LocalKgStore, params: dict) -> list[dict]:
    # production 표면: :JaebaemanRun 감사 노드 upsert (run_id 키).
    props = {k: v for k, v in params.items() if k != "run_id"}
    store.merge_node("JaebaemanRun", "name", params["run_id"], {"name": params["run_id"], **props})
    return [{"recorded": params["run_id"]}]


def _jaebaeman_status_set(store: LocalKgStore, params: dict) -> list[dict]:
    # lifecycle status 전이: SubagentTaskSpec.status SET (covenant SET-only).
    node = store.find_one("name", params["name"], "SubagentTaskSpec")
    if node is None:
        return []
    node["props"]["status"] = params["status"]
    return [{"updated": params["name"]}]


def _decomposes_parents(store: LocalKgStore) -> dict[str, str]:
    # child name → 첫 DECOMPOSES_TO 부모 name (SubagentTaskSpec만). dedupe 기준.
    parent_of: dict[str, str] = {}
    for n in store.nodes:
        if "SubagentTaskSpec" not in n["labels"]:
            continue
        for rel, dst in store.out_edges(n):
            cname = dst["props"].get("name")
            if rel == "DECOMPOSES_TO" and cname and cname not in parent_of:
                parent_of[cname] = n["props"].get("name")
    return parent_of


def _is_ready_seed(node: dict, cycle: str | None) -> bool:
    p = node["props"]
    if "SubagentTaskSpec" not in node["labels"] or p.get("status") != "READY":
        return False
    if cycle is not None and p.get("cycleId") != cycle:
        return False
    return bool(p.get("name"))


def _ready_seed_row(p: dict, parent: str | None) -> dict:
    name = p["name"]
    return {
        "name": name,
        "skill": p.get("skill") or "jaebaeman",
        "sourceId": p.get("sourceId") or name,
        "displayName": p.get("displayName") or name,
        "taskType": p.get("taskType") or "research",
        "targetDomain": p.get("targetDomain") or "",
        "expectedOutcome": p.get("expectedOutcome") or "",
        "germinationMethod": p.get("germinationMethod") or "manual",
        "depth": p.get("depth") if p.get("depth") is not None else 0,
        "parent": parent,
    }


def _jaebaeman_ready_seeds(store: LocalKgStore, params: dict) -> list[dict]:
    # READY SubagentTaskSpec read-back (씨앗→발아 입력). cycle_id 주면 그 cycle만. name당 1행(dedupe).
    cycle = params.get("cycle_id")
    parent_of = _decomposes_parents(store)
    out = [
        _ready_seed_row(n["props"], parent_of.get(n["props"]["name"]))
        for n in store.nodes
        if _is_ready_seed(n, cycle)
    ]
    out.sort(key=lambda r: (r["depth"], r["name"]))
    limit = params.get("limit")
    return out[:limit] if limit is not None else out


def _jaebaeman_orphan_anchor(store: LocalKgStore, params: dict) -> list[dict]:
    # E1 게이트: 주어진 anchor name 중 KG에 노드가 없는 것만 collect (read-only).
    anchors = params.get("anchors") or []
    present = {n["props"].get("name") for n in store.nodes}
    return [{"missing": [a for a in anchors if a not in present]}]


def _jaebaeman_children(store: LocalKgStore, params: dict) -> list[dict]:
    # 분해 anchor의 자식 read. 로컬엔 보통 Span 구조가 없으니 빈 결과(→ singleton 루트)면 정상.
    anchor = store.find_one("name", params.get("anchor"))
    if anchor is None:
        return []
    out: list[dict] = []
    for rel, dst in store.out_edges(anchor):
        if rel not in ("DECOMPOSES_TO", "HAS_CHILD", "DEPENDS_ON"):
            continue
        p = dst["props"]
        if not p.get("name"):
            continue
        out.append(
            {
                "child": p["name"],
                "objective": p.get("objective") or p["name"],
                "target_domain": p.get("targetDomain", ""),
            }
        )
    return out


# dispatch 테이블: (cypher 매칭 predicate, handler, is_write). 위→아래 첫 매치.
# elif 체인 대신 루프 = 낮은 cognitive complexity + 라우트 추가 용이.
_ROUTES: list[tuple[Callable[[str], bool], Callable, bool]] = [
    (lambda c: "stale.status = 'SUPERSEDED'" in c, _occam_supersede, True),
    (lambda c: "MERGE (a:AbstractClass {name:$concept})" in c, _hades_merge_concept, True),
    (
        lambda c: "MERGE (a:AbstractClass {name: $name})" in c and "SET a.verdictStatus" in c,
        _eureka_persist_abstractclass,
        True,
    ),
    (lambda c: "MERGE (e:DispatchEvent" in c, _dispatch_event_merge, True),
    (lambda c: "INSTANCE_OF" in c and "$members" in c, _hades_link_members, True),
    (lambda c: "UNWIND $rows" in c and "s.sha256" in c, _rebind_sha, True),
    # 재배맨 씨앗/계획-엣지 (write) + 분해 anchor 자식 (read).
    (lambda c: "MERGE (s:SubagentTaskSpec {name: $name})" in c, _jaebaeman_seed_merge, True),
    (lambda c: "[r:HAS_SEED]->(s)" in c, _jaebaeman_has_seed, True),
    (lambda c: "MERGE (p)-[:DECOMPOSES_TO]->(c)" in c, _jaebaeman_decomposes_to, True),
    (
        lambda c: "SET s.status = $status, s.lifecycleUpdatedAt" in c,
        _jaebaeman_status_set,
        True,
    ),
    # READY 씨앗 read-back (씨앗→발아 입력). SourceCodeNode read보다 먼저(둘 다 RETURN s.name).
    (
        lambda c: "(s:SubagentTaskSpec)" in c and "s.status = 'READY'" in c,
        _jaebaeman_ready_seeds,
        False,
    ),
    (lambda c: "MERGE (r:JaebaemanRun {name: $run_id})" in c, _jaebaeman_run_record, True),
    (
        lambda c: "-[:DECOMPOSES_TO|HAS_CHILD|DEPENDS_ON]->(c)" in c,
        _jaebaeman_children,
        False,
    ),
    (lambda c: "RETURN collect(a) AS missing" in c, _jaebaeman_orphan_anchor, False),
    (lambda c: "-[:HAS_METHOD]->(m:DecomposeMethod)" in c, _jaebaeman_methods, False),
    (lambda c: "MERGE (h:HarnessDiagnosis" in c, _harness_persist, True),
    (lambda c: "MERGE (s:SourceCodeNode" in c, _merge_source_node, True),
    (
        lambda c: "MERGE (f:ResearchFinding {findingId:$findingId})" in c,
        _research_finding_merge,
        True,
    ),
    (lambda c: "q:OpenQuestion OR q:VerdictPending" in c, _gap_scan, False),
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
