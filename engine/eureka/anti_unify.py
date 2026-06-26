"""code backend (유레카 Phase 3) — Plotkin anti-unification / LGG.

N개 코드 조각의 *최소 일반화*(least general generalization): 같은 위치 모두 일치=고정,
불일치=fresh 변수(hole). = 추상클래스/공유함수 템플릿. (Plotkin 1970)

**경계**: 유레카는 *템플릿 PROPOSE까지만*. 실제 Extract Superclass(추상→구체 코드 써냄)
= 하데스 + materialize(engine-impl c6 "가장 위험"). 여기선 dry-run 템플릿만.
가드: hole_ratio>0.5 = over-generalization → reject (engine-spec guard "홀>50% reject").

**WIRING STATUS (2026-06-02)**: implemented + tested (tests/test_anti_unify.py) but NOT
yet wired to a CLI/pipeline entry — `pipeline.run` is the *KG-induction* path (FCA/AMIE3/
Leiden over a formal context); this is the disjoint *code-template* path (over code
fragments). It is a real capability awaiting a code-scanner front-end (`eureka --code`),
NOT dead code — do not Occam-archive. Follow-up: wire a code-fragment → anti_unify entry.

# KG: consensus-eureka-academic-grounding-2026-05-26 (C5 anti-unification),
#     eureka-canonical-2026-05-26 (PROPOSE만, auto-commit 금지), eureka-engine-spec-2026-05-26
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HOLE_PREFIX = "·"  # fresh 변수 표시 (불일치 위치)


def tokenize(line: str) -> list[str]:
    # KG: eureka-canonical-2026-05-26
    """코드 라인 → 토큰 (식별자/숫자/연산자/구두점). 공백 무시."""
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|\S", line)


@dataclass(frozen=True)
class LggTemplate:
    # KG: eureka-canonical-2026-05-26
    template: list[str]  # 고정 토큰 + ·N 변수
    holes: int
    arity: int  # 토큰 수
    hole_ratio: float
    over_general: bool  # hole_ratio > 0.5 → reject
    aligned: bool  # 모든 seq 길이 동일했나 (LGG 가능 조건)


def anti_unify(sequences: list[list[str]]) -> LggTemplate | None:
    # KG: eureka-canonical-2026-05-26
    """Plotkin LGG (token-sequence). 같은 위치 전부 일치=keep, 불일치=fresh var(·N).

    구조(길이) 다르면 None — 단순 LGG 불가, SP decompose 위임(클론 아님).
    """
    seqs = [s for s in sequences if s]
    if len(seqs) < 2:
        return None
    lengths = {len(s) for s in seqs}
    if len(lengths) != 1:
        return None  # 구조 불일치 → LGG 적용 안 됨
    arity = next(iter(lengths))
    template: list[str] = []
    holes = 0
    for i in range(arity):
        vals = {s[i] for s in seqs}
        if len(vals) == 1:
            template.append(next(iter(vals)))
        else:
            template.append(f"{HOLE_PREFIX}{holes}")
            holes += 1
    ratio = holes / arity if arity else 1.0
    return LggTemplate(
        template=template,
        holes=holes,
        arity=arity,
        hole_ratio=round(ratio, 3),
        over_general=ratio > 0.5,
        aligned=True,
    )


def propose_template(snippets: list[str], min_instances: int = 3) -> dict:
    # KG: eureka-canonical-2026-05-26
    """N 코드 조각 → LGG 템플릿 PROPOSE (dry-run, materialize 안 함).

    Rule of Three: min_instances 미만이면 propose 안 함(premature abstraction 가드).
    반환: {status, template, hole_ratio, reason}. status ∈ PROPOSED/REJECTED/INSUFFICIENT.
    """
    if len(snippets) < min_instances:
        return {
            "status": "INSUFFICIENT",
            "reason": f"{len(snippets)} < Rule of Three {min_instances}",
        }
    lgg = anti_unify([tokenize(s) for s in snippets])
    if lgg is None:
        return {
            "status": "REJECTED",
            "reason": "구조(토큰 길이) 불일치 — LGG 불가, SP decompose 위임",
        }
    if lgg.over_general:
        return {
            "status": "REJECTED",
            "reason": f"over-generalization hole_ratio={lgg.hole_ratio} > 0.5",
            "template": " ".join(lgg.template),
        }
    return {
        "status": "PROPOSED",
        "template": " ".join(lgg.template),
        "hole_ratio": lgg.hole_ratio,
        "holes": lgg.holes,
        "instances": len(snippets),
        "note": "PROPOSE only — Extract Superclass(materialize)는 하데스 소관. auto-commit 금지.",
    }


def _skeleton(tokens: list[str]) -> tuple[str, ...]:
    """Structural signature for grouping: numeric literals → '*' wildcard, identifiers and
    operators kept literal. Same skeleton ⇒ same token count ⇒ anti_unify is well-defined and
    only literal-valued positions become holes."""
    return tuple("*" if t.isdigit() else t for t in tokens)


def scan_fragments(snippets: list[str], min_instances: int = 3) -> list[dict]:
    # KG: eureka-canonical-2026-05-26
    """Producer (the missing front-end for anti_unify): group structurally-similar code
    fragments and PROPOSE an LGG template per family meeting the Rule of Three.

    PROPOSE-only / dry-run — materialize (Extract-Superclass) is 하데스 소관, this writes nothing.
    Returns only the PROPOSED families (REJECTED/INSUFFICIENT dropped), sorted by template.
    """
    groups: dict[tuple[str, ...], list[str]] = {}
    for s in snippets:
        toks = tokenize(s)
        if not toks:
            continue
        groups.setdefault(_skeleton(toks), []).append(s)
    proposals: list[dict] = []
    for members in groups.values():
        if len(members) < min_instances:
            continue
        result = propose_template(members, min_instances=min_instances)
        if result["status"] == "PROPOSED":
            proposals.append(result)
    return sorted(proposals, key=lambda p: p["template"])


__all__ = [
    "HOLE_PREFIX",
    "LggTemplate",
    "anti_unify",
    "propose_template",
    "scan_fragments",
    "tokenize",
]
