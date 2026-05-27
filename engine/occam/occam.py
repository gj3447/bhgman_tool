"""오캄 코어 — KG node-dedup (PRIMARY). 순수 함수, KG/IO 없음.

대체된 낡은 노드만 선별 → SupersessionCandidate. **delete 함수 부재 (covenant)**.
abs-path lineage(`/Users/.../bhgman_tool/...`)와 rel-path lineage(`bhgman_tool/...`)를
normalize_path로 통합해 naive GROUP BY가 가렸던 중복을 드러냄.

# KG: lesson-occam-must-query-kg-node-dedup-not-just-filesystem-2026-05-27,
#     occam-pass-bhgman_tool-2026-05-27 (이 알고리즘이 손으로 한 그 pass의 코드화)
"""

from __future__ import annotations

from collections import defaultdict

from occam_models import Confidence, NodeRecord, OccamReport, SupersessionCandidate

_REPO_MARKER = "bhgman_tool/"


def normalize_path(path: str) -> str:
    """abs/rel lineage 통합: repo marker 이후만 남김. marker 없으면 원본."""
    idx = path.rfind(_REPO_MARKER)
    if idx == -1:
        return path
    return path[idx + len(_REPO_MARKER) :]


def _pick_current(group: list[NodeRecord], disk_sha: str | None) -> tuple[NodeRecord, Confidence]:
    """현재 lineage 노드 선정. disk sha 일치 = HIGH, 없으면 max line_count = MEDIUM."""
    if disk_sha:
        for node in group:
            if node.sha256 == disk_sha:
                return node, Confidence.HIGH
    return max(group, key=lambda n: n.line_count), Confidence.MEDIUM


def _reason(stale: NodeRecord, current: NodeRecord) -> str:
    if stale.sha256 == current.sha256:
        return "exact duplicate node (identical sha) — redundant"
    return f"superseded: {stale.line_count}L → current {current.line_count}L (old lineage)"


def occam_pass(nodes: list[NodeRecord], disk_truth: dict[str, str] | None = None) -> OccamReport:
    """하계 node-dedup pass. covenant: supersede 후보만 반환, 삭제 없음."""
    disk_truth = disk_truth or {}
    groups: dict[str, list[NodeRecord]] = defaultdict(list)
    for node in nodes:
        groups[normalize_path(node.source_path)].append(node)

    candidates: list[SupersessionCandidate] = []
    dup_groups = 0
    for norm, group in groups.items():
        if len(group) < 2:
            continue
        dup_groups += 1
        current, conf = _pick_current(group, disk_truth.get(norm))
        for node in group:
            if node is current:
                continue
            candidates.append(
                SupersessionCandidate(
                    stale=node,
                    current=current,
                    normalized_path=norm,
                    reason=_reason(node, current),
                    confidence=conf,
                )
            )

    notes = (
        "covenant: archive-only; no delete. PRIMARY=KG node-dedup.",
        f"{dup_groups} path(s) with duplicate nodes across abs/rel lineages.",
    )
    return OccamReport(
        candidates=tuple(candidates),
        scanned_nodes=len(nodes),
        groups_with_dups=dup_groups,
        notes=notes,
    )
