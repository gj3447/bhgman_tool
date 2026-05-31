"""AMIE3 Horn rule → FormalConcept 어댑터 + induce_via_amie3 orchestration.

amie3.py(Java subprocess)는 typed triples → PCA-confident Horn rules.
eureka pipeline은 FormalConcept(extent/intent/stability) 기반이라 어댑터로 통일:
  - context(object→attrs) → triples(s,p,o)
  - Horn rule(body⇒head) → FormalConcept: body+head atom = intent, intent 만족 객체 = extent,
    stability ← pca_confidence proxy.

**보수적** (eureka covenant — 헛 "유레카!" 차단):
  - min_pca_confidence 미만 rule 버림 (저신뢰 = apophenia 후보).
  - extent < min_extent 버림 (Rule of Three).
  - 변환 후도 PROPOSE까지만 — oracle/fidelity/나생문 gate가 후속 검증. 어댑터는 변환만.

# KG: eureka-canonical-2026-05-26, consensus-eureka-academic-grounding-2026-05-26 (AMIE3 C5),
#     consensus-eureka-engine-impl-2026-05-26
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from engine.eureka.induction_operators.amie3 import Amie3Result, HornRule, induce_amie3
from engine.eureka.induction_operators.fca import FcaResult, FormalConcept


def formal_context_to_triples(
    context: Mapping[str, frozenset[str]],
) -> list[tuple[str, str, str]]:
    """object→attrs를 typed triple(s,p,o)로. attr 'P:V'→(obj,P,V), 'plain'→(obj,HAS_ATTR,plain)."""
    triples: list[tuple[str, str, str]] = []
    for obj, attrs in context.items():
        for a in attrs:
            if ":" in a:
                pred, val = a.split(":", 1)
                triples.append((obj, pred.strip(), val.strip()))
            else:
                triples.append((obj, "HAS_ATTR", a))
    return triples


def _atom_to_attr(atom: str) -> str | None:
    """AMIE atom '?x PRED VALUE' → context attr 'PRED:VALUE'. var-only/malformed → None."""
    parts = atom.split()
    if len(parts) < 3:
        return None
    pred = parts[1]
    value = " ".join(parts[2:])
    if pred == "HAS_ATTR":
        return value
    return f"{pred}:{value}"


def _rule_intent(rule: HornRule) -> frozenset[str]:
    """rule의 body+head atom들을 context attr 집합(intent)으로 복원. 다중 atom은 콤마 분리."""
    atoms: list[str] = []
    for clause in (rule.body, rule.head):
        for raw in clause.split("  "):  # AMIE는 atom 사이 공백 다수; 보수적 분할
            raw = raw.strip()
            if raw:
                atoms.append(raw)
    attrs = {a for atom in atoms if (a := _atom_to_attr(atom)) is not None}
    return frozenset(attrs)


def horn_rules_to_concepts(
    rules: Iterable[HornRule],
    context: Mapping[str, frozenset[str]],
    min_pca_confidence: float = 0.5,
    min_extent: int = 2,
) -> FcaResult:
    """high-PCA Horn rule → FormalConcept. intent=body+head attrs, extent=intent 만족 객체."""
    seen: set[tuple[frozenset[str], frozenset[str]]] = set()
    survivors: list[FormalConcept] = []
    pruned = 0
    for rule in rules:
        if rule.pca_confidence < min_pca_confidence:
            pruned += 1
            continue
        intent = _rule_intent(rule)
        if not intent:
            pruned += 1
            continue
        extent = frozenset(o for o, attrs in context.items() if intent <= attrs)
        if len(extent) < min_extent:
            pruned += 1
            continue
        key = (extent, intent)
        if key in seen:
            continue
        seen.add(key)
        survivors.append(FormalConcept(extent=extent, intent=intent, stability=rule.pca_confidence))
    survivors.sort(key=lambda c: (-c.stability, -len(c.extent)))
    return FcaResult(concepts=tuple(survivors), pruned=pruned, fallback_reason=None)


def induce_via_amie3(
    context: Mapping[str, frozenset[str]],
    amie3_fn: Callable[..., Amie3Result] = induce_amie3,
    min_pca_confidence: float = 0.5,
    min_extent: int = 2,
    **amie3_kwargs: Any,
) -> FcaResult:
    """context → triples → AMIE3(Java, 주입식) → Horn rules → FormalConcept(FcaResult).

    amie3_fn 기본=induce_amie3(Java subprocess). 테스트는 fake 주입(Java 불필요).
    """
    triples = formal_context_to_triples(context)
    result = amie3_fn(triples, **amie3_kwargs)
    return horn_rules_to_concepts(
        result.rules, context, min_pca_confidence=min_pca_confidence, min_extent=min_extent
    )


__all__ = [
    "formal_context_to_triples",
    "horn_rules_to_concepts",
    "induce_via_amie3",
]
