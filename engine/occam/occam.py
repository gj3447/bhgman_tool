"""오캄 코어 — KG node-dedup (PRIMARY). 순수 함수, KG/IO 없음.

대체된 낡은 노드만 선별 → SupersessionCandidate. **delete 함수 부재 (covenant)**.

3 탐지 모드 (challenge-occam-pass-bhgman_tool-* 2026-05-27 해결):
  1. **same-path 중복**: abs-path lineage(`/Users/.../bhgman_tool/...`)와 rel-path lineage
     (`bhgman_tool/...`)를 normalize_path로 통합 → naive GROUP BY가 가린 중복 노드.
  2. **sha-이동(NEW)**: 동일 sha인데 정규화경로가 다른 노드 = 파일이 이동(dir rename)됐는데
     KG 옛 경로 노드가 남은 것. disk_paths로 *어느 쪽이 살아있는지* 확정 → 디스크에 없는 쪽을
     살아있는 twin으로 supersede (content-identical = HIGH). (ged_drift_detector.py 케이스:
     longinus_l8_induction/ 삭제, longinus_drift/에 동일 sha 생존.)
  3. **disk-orphan(NEW, flag-only)**: 정규화경로가 디스크에 없고 동일-sha live twin도 없는 노드.
     auto-supersede 안 함 (machloket/Eilu va-Eilu) — report.orphans로 surface, 판단은 사용자/Longinus.

disk_paths=None이면 1번만 (기존 동작 불변).

# KG: lesson-occam-must-query-kg-node-dedup-not-just-filesystem-2026-05-27,
#     occam-pass-bhgman_tool-2026-05-27 (이 알고리즘이 손으로 한 그 pass의 코드화),
#     challenge-occam-pass-bhgman_tool-missed-own-domain-stale-nodes-2026-05-27 (sha-이동 gap fix),
#     challenge-occam-pass-bhgman_tool-kg-path-not-mirrored-2026-05-27 (이동 노드 supersede=path 정합)
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict

from engine.occam.occam_models import Confidence, NodeRecord, OccamReport, SupersessionCandidate
from engine.occam.scoring import NodeScoreMeta, ScoringConfig, score_node

_REPO_MARKER = "bhgman_tool/"


def normalize_path(path: str) -> str:
    # KG: occam-kam-canonical-2026-05-26
    """abs/rel lineage 통합: repo marker 이후만 남김. marker 없으면 원본."""
    idx = path.rfind(_REPO_MARKER)
    if idx == -1:
        return path
    return path[idx + len(_REPO_MARKER) :]


def _in_repo(path: str) -> bool:
    """path가 이 repo 소속인가 (디스크-aware 판정 대상). marker 없는 외부 노드는
    이 repo 디스크로 실존 여부를 판단할 수 없으므로 move/orphan 평가에서 제외."""
    return _REPO_MARKER in path


def _current_rank(n: NodeRecord) -> tuple:
    """disk-truth 부재 시 current 선정 다신호 키 (클수록 current).

    challenge-occam: 'line_count 큰 쪽이 현재'는 약한 추정. inbound 참조 수(live/load-bearing)
    와 recency(최근 검증/생성)를 line_count보다 우선해 보강한다. 메타 부재(None) 노드만 있으면
    inbound=0·recency='' 동률 → line_count 폴백 = 기존 동작 불변 (하위호환).
    sha256/source_path 마지막 tiebreak = 입력 순서 무관 결정론 (W3-A)."""
    return (
        n.inbound_edges or 0,
        n.recency_key,
        n.line_count,
        n.sha256 or "",
        n.source_path,
    )


def _pick_current(group: list[NodeRecord], disk_sha: str | None) -> tuple[NodeRecord, Confidence]:
    """현재 lineage 노드 선정. disk sha 일치 = HIGH, 없으면 다신호 rank = MEDIUM.

    MEDIUM 경로: inbound 참조 수 > recency > line_count 순 (line_count 단독 휴리스틱 보강)."""
    if disk_sha:
        for node in group:
            if node.sha256 == disk_sha:
                return node, Confidence.HIGH
    return max(group, key=_current_rank), Confidence.MEDIUM


def _reason(stale: NodeRecord, current: NodeRecord) -> str:
    if stale.sha256 == current.sha256:
        return "exact duplicate node (identical sha) — redundant"
    return f"superseded: {stale.line_count}L → current {current.line_count}L (old lineage)"


def _detect_sha_moves(
    nodes: list[NodeRecord],
    disk_paths: frozenset[str],
    superseded_ids: set[int],
) -> list[SupersessionCandidate]:
    """동일 sha·다른 경로 = 이동. 디스크에 없는 경로 노드를 살아있는 twin으로 supersede (HIGH)."""
    by_sha: dict[str, list[NodeRecord]] = defaultdict(list)
    for node in nodes:
        if id(node) not in superseded_ids and _in_repo(node.source_path):
            by_sha[node.sha256].append(node)

    out: list[SupersessionCandidate] = []
    for group in by_sha.values():
        norms = {normalize_path(n.source_path) for n in group}
        if len(norms) < 2:
            continue  # 단일 경로 = mode-1이 이미 처리(또는 중복 아님)
        live = [n for n in group if normalize_path(n.source_path) in disk_paths]
        orphan = [n for n in group if normalize_path(n.source_path) not in disk_paths]
        if not (live and orphan):
            continue  # 전부 live(디스크상 동일내용 사본, 보존) 또는 전부 orphan(mode-3로)
        current = min(live, key=lambda n: normalize_path(n.source_path))
        cur_norm = normalize_path(current.source_path)
        for node in orphan:
            if id(node) in superseded_ids:
                continue
            stale_norm = normalize_path(node.source_path)
            out.append(
                SupersessionCandidate(
                    stale=node,
                    current=current,
                    normalized_path=stale_norm,
                    reason=(
                        f"moved: '{stale_norm}' absent on disk; "
                        f"content-identical (sha) to live '{cur_norm}'"
                    ),
                    confidence=Confidence.HIGH,
                )
            )
            superseded_ids.add(id(node))
    return out


def _detect_disk_orphans(
    nodes: list[NodeRecord],
    disk_paths: frozenset[str],
    superseded_ids: set[int],
) -> list[NodeRecord]:
    """디스크에 경로 없고 동일-sha live twin도 없는 노드 = flag-only (machloket 보존, supersede 안 함)."""
    orphans: list[NodeRecord] = []
    for node in nodes:
        if id(node) in superseded_ids:
            continue
        if not _in_repo(node.source_path):  # 외부 노드는 이 repo 디스크로 판정 불가
            continue
        if normalize_path(node.source_path) in disk_paths:
            continue
        has_live_twin = any(
            other is not node
            and other.sha256 == node.sha256
            and normalize_path(other.source_path) in disk_paths
            for other in nodes
        )
        if not has_live_twin:
            orphans.append(node)
    return orphans


def _redundancy(stale: NodeRecord, current: NodeRecord) -> float:
    """MDL redundancy proxy ∈ [0,1]: 동일 sha=완전중복(1.0), 아니면 line_count 겹침 비율.

    Kolmogorov 직관: current가 주어졌을 때 stale의 추가 description-length가 작을수록 redundant."""
    if stale.sha256 == current.sha256:
        return 1.0
    lo, hi = sorted((max(stale.line_count, 0), max(current.line_count, 0)))
    if hi == 0:
        return 0.0
    return lo / hi


def _score_candidates(
    candidates: list[SupersessionCandidate],
    score_meta: dict[str, NodeScoreMeta],
    cfg: ScoringConfig,
) -> list[SupersessionCandidate]:
    """후보별 σ 부착. redundancy는 occam dedup이 권위(meta 값 override), 나머지는 caller meta.

    candidate는 정의상 current(후속자)가 있으므로 has_successor=True 강제."""
    out: list[SupersessionCandidate] = []
    for c in candidates:
        meta = score_meta.get(c.stale.name)
        if meta is None:
            out.append(c)
            continue
        merged = dataclasses.replace(
            meta,
            redundancy=_redundancy(c.stale, c.current),
            has_successor=True,
            disk_current=max(meta.disk_current, 1.0 if c.confidence is Confidence.HIGH else 0.0),
            blob_match=max(meta.blob_match, 1.0 if c.stale.sha256 == c.current.sha256 else 0.0),
        )
        sc = score_node(merged, cfg)
        out.append(dataclasses.replace(c, score=sc.sigma, verdict=sc.verdict.value))
    return out


def occam_pass(
    nodes: list[NodeRecord],
    disk_truth: dict[str, str] | None = None,
    disk_paths: frozenset[str] | None = None,
    score_meta: dict[str, NodeScoreMeta] | None = None,
    scoring_config: ScoringConfig | None = None,
) -> OccamReport:
    # KG: occam-kam-canonical-2026-05-26
    """하계 node-dedup pass. covenant: supersede 후보만 반환, 삭제 없음.

    disk_paths(정규화된 디스크 실존 경로 집합) 주면 sha-이동(mode-2)+disk-orphan(mode-3) 추가 탐지.
    None이면 same-path 중복(mode-1)만 — 기존 호출자 동작 불변.

    score_meta(노드이름→NodeScoreMeta) 주면 각 후보에 연속 σ + verdict 부착 (scoring.py).
    None이면 score=verdict=None (기존 호출자 동작 불변).
    """
    disk_truth = disk_truth or {}
    groups: dict[str, list[NodeRecord]] = defaultdict(list)
    for node in nodes:
        groups[normalize_path(node.source_path)].append(node)

    candidates: list[SupersessionCandidate] = []
    superseded_ids: set[int] = set()
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
            superseded_ids.add(id(node))

    orphans: list[NodeRecord] = []
    moved = 0
    if disk_paths is not None:
        move_candidates = _detect_sha_moves(nodes, disk_paths, superseded_ids)
        moved = len(move_candidates)
        candidates.extend(move_candidates)
        orphans = _detect_disk_orphans(nodes, disk_paths, superseded_ids)

    if score_meta is not None:
        candidates = _score_candidates(candidates, score_meta, scoring_config or ScoringConfig())

    notes = (
        "covenant: archive-only; no delete. PRIMARY=KG node-dedup.",
        f"{dup_groups} path(s) with duplicate nodes across abs/rel lineages.",
        (
            f"disk-aware: {moved} moved-node supersession(s), {len(orphans)} disk-orphan(s) flagged."
            if disk_paths is not None
            else "disk-unaware: same-path dedup only (pass disk_paths for move/orphan detection)."
        ),
    )
    return OccamReport(
        candidates=tuple(candidates),
        scanned_nodes=len(nodes),
        groups_with_dups=dup_groups,
        notes=notes,
        orphans=tuple(orphans),
    )
