"""KG-input 접지(grounding) — LLM 군단장이 작업 *전* 하계(KG)에서 사전지식을 읽는다.

KG-first(KGFirstCheck_v1, R1-R5) 원칙의 엔진 측 실현. prometheus(Step 0 "사전 지식")와
naesengmoon(검증 전 관련 canon/lesson 접지)이 LLM 호출 *전* 이 모듈을 호출해 관련 정전·교훈·
발견을 context로 주입한다 → 접지 없는 LLM 출력(본질 왜곡, canon-kg-based-coding-essence) 차단.

read-only. write는 재배맨 SOP(부모가 KG write, MCP 비상속 GH#13605)대로 — 여기선 읽기만.

backend 2종 (occam/eureka의 CypherRunner 추상과 동일 정신):
  - LocalGroundingSource(store): ~/.bhgman/kg.json (neo4j 불필요, `--local`).
  - Neo4jGroundingSource(run_cypher): 실 neo4j.
둘 다 search(terms, limit) -> list[{labels, props}] 한 메서드만 구현(GroundingSource Protocol).

# KG: canon-kg-based-coding-essence-2026-05-28, KGFirstCheck_v1,
#     prometheus-grounding-2026-05-05, bhgman-llm-commander-runtime-2026-05-28
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

# 접지 우선 라벨 (정전 > 교훈 > 발견/검증). 앞 4개 = 정전/교훈류(가중 우대).
_GROUND_LABELS = (
    "UserPrimaryCanon",
    "CanonicalName",
    "Principle",
    "Lesson",
    "ResearchFinding",
    "ValidationResult",
)
_CANON_LABELS = _GROUND_LABELS[:4]
# 매칭·표시할 텍스트 prop (있는 것만, 순서 = 표시 우선순위).
_TEXT_PROPS = ("title", "claim", "essence", "description", "wrongAssumption", "truth", "summary")
_SNIPPET_MAX = 280


@dataclass(frozen=True)
class GroundedFact:
    name: str
    label: str
    text: str

    def render(self) -> str:
        body = self.text[:_SNIPPET_MAX] + ("…" if len(self.text) > _SNIPPET_MAX else "")
        return f"- [{self.label}] {self.name}: {body}"


@runtime_checkable
class GroundingSource(Protocol):
    def search(self, terms: list[str], limit: int) -> list[dict[str, Any]]: ...


def _terms(query: str) -> list[str]:
    """검색 토큰. 4자+ 만(흔한 짧은 단어 noise 제거), 소문자, 중복 제거. 한국어는 길이로 통과."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in query.replace("/", " ").replace("-", " ").replace(":", " ").split():
        t = raw.strip().lower()
        if len(t) >= 4 and t not in seen:
            seen.add(t)
            out.append(t)
    return out[:12]


def _props_of(node: dict) -> dict:
    """local store({'labels','props'})와 neo4j-normalized 모두에서 props 추출."""
    return node.get("props", node)


def _node_blob(props: dict) -> str:
    parts = [str(props[p]) for p in _TEXT_PROPS if props.get(p)]
    return " ".join(parts) or str(props.get("name", ""))


def _first_text(props: dict) -> str:
    for p in _TEXT_PROPS:
        if props.get(p):
            return str(props[p])
    return str(props.get("name", ""))


def _label_of(node: dict) -> str:
    labels = node.get("labels", [])
    for pref in _GROUND_LABELS:
        if pref in labels:
            return pref
    return labels[0] if labels else "Node"


def retrieve(source: GroundingSource | None, query: str, limit: int = 6) -> list[GroundedFact]:
    """source에서 query 관련 노드 → GroundedFact. source None / 토큰 없음 → []."""
    if source is None:
        return []
    terms = _terms(query)
    if not terms:
        return []
    rows = source.search(terms, limit)
    facts: list[GroundedFact] = []
    for n in rows[:limit]:
        props = _props_of(n)
        facts.append(
            GroundedFact(name=props.get("name", "?"), label=_label_of(n), text=_first_text(props))
        )
    return facts


def format_context(facts: list[GroundedFact], *, header: str = "사전 지식 (KG 정전·교훈)") -> str:
    """GroundedFact 리스트 → LLM user prompt에 prepend할 context 블록. 빈 리스트 → ''."""
    if not facts:
        return ""
    lines = "\n".join(f.render() for f in facts)
    return (
        f"## {header}\n"
        "아래는 이 작업과 관련해 하계(KG)에 이미 결정화된 정전·교훈·발견이다. "
        "중복 재발견을 피하고, 이와 충돌하거나 이를 확장하는 지점에 집중하라.\n"
        f"{lines}\n\n"
    )


def build_grounding(
    source: GroundingSource | None,
    query: str,
    *,
    limit: int = 6,
    header: str = "사전 지식 (KG 정전·교훈)",
) -> tuple[str, int]:
    """(context 블록, fact 개수). 엔진이 한 번 호출해 prompt에 주입 + 개수 보고용."""
    facts = retrieve(source, query, limit=limit)
    return format_context(facts, header=header), len(facts)


class LocalGroundingSource:
    """로컬 JSON KG(LocalKgStore) backed read-only 접지원. neo4j 불필요."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def search(self, terms: list[str], limit: int) -> list[dict[str, Any]]:
        scored: list[tuple[int, dict]] = []
        for n in self._store.nodes:
            props = n.get("props", {})
            hay = (str(props.get("name", "")) + " " + _node_blob(props)).lower()
            score = sum(1 for t in terms if t in hay)
            if score:
                bonus = 2 if any(lbl in _CANON_LABELS for lbl in n.get("labels", [])) else 0
                scored.append((score + bonus, n))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in scored[:limit]]


class Neo4jGroundingSource:
    """neo4j run_cypher backed 접지원. name/title/claim/truth CONTAINS OR 매칭, 정전/교훈 라벨 한정."""

    def __init__(self, run_cypher: Any) -> None:
        self._run = run_cypher

    def search(self, terms: list[str], limit: int) -> list[dict[str, Any]]:
        if not terms:
            return []
        clauses: list[str] = []
        params: dict[str, Any] = {"labels": list(_GROUND_LABELS), "limit": limit}
        for i, t in enumerate(terms):
            params[f"t{i}"] = t
            clauses.append(
                f"(toLower(coalesce(n.name,'')) CONTAINS $t{i} OR "
                f"toLower(coalesce(n.title,'')) CONTAINS $t{i} OR "
                f"toLower(coalesce(n.claim,'')) CONTAINS $t{i} OR "
                f"toLower(coalesce(n.truth,'')) CONTAINS $t{i})"
            )
        cypher = (
            f"MATCH (n) WHERE ({' OR '.join(clauses)}) "
            "AND any(l IN labels(n) WHERE l IN $labels) "
            "RETURN labels(n) AS labels, properties(n) AS props LIMIT $limit"
        )
        rows = self._run(cypher, params) or []
        return [{"labels": r.get("labels", []), "props": r.get("props", r)} for r in rows]


__all__ = [
    "GroundedFact",
    "GroundingSource",
    "LocalGroundingSource",
    "Neo4jGroundingSource",
    "build_grounding",
    "format_context",
    "retrieve",
]
