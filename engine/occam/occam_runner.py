"""오캄 end-to-end runner — fetch(KG) → occam_pass(순수 분류) → apply(supersede).

orchestration만. read/write IO = kg_adapter, 분류 로직 = occam.py. dry-run 기본.

KG-only 모드는 disk_truth 부재 → PICK_CURRENT가 max line_count 휴리스틱(MEDIUM confidence).
disk sha 확정(HIGH)이 필요하면 호출자가 disk_truth를 occam_pass에 직접 주입 (CLI 향후 enhancement).

# KG: occam-kam-canonical-2026-05-26, occam-pass-kg-wide-2026-05-27,
#     lesson-occam-must-query-kg-node-dedup-not-just-filesystem-2026-05-27
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from engine.occam.kg_adapter import (
    ApplyResult,
    CypherRunner,
    apply_supersessions,
    fetch_source_nodes,
)
from engine.occam.escalation import is_confident_supersede
from engine.occam.occam import normalize_path, occam_pass
from engine.occam.occam_models import NodeRecord, OccamReport
from engine.occam.scoring import NodeScoreMeta

# 디스크 스캔 시 건너뛸 디렉터리 (vendored/cache/vcs — 소스 lineage 아님).
_SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".complexipy_cache",
    ".hypothesis",
    "node_modules",
    "dist",
    "vendor",
}


def scan_disk_paths(repo_root: str | Path) -> frozenset[str]:
    # KG: occam-kam-canonical-2026-05-26
    """repo_root 하위 실존 파일의 normalize_path 집합. occam_pass(disk_paths=)에 주입.

    normalize_path와 동일 정규화 → KG 노드 경로(abs/rel 둘 다)와 join 가능.
    **followlinks=True**: bhgman_tool/skills/*는 SYMPOSIUM/SKILLS로의 심볼릭 링크라(정전화됨)
    안 따라가면 살아있는 파일이 false-orphan으로 잡힌다. depth 가드로 심링크 cycle 폭주만 차단.

    realpath 기반 dedup은 **안 한다** — `skills/x → symposium-skills/x` 처럼 동일 실디렉터리에
    여러 symbolic alias가 ROOT 하위에 공존하는 경우(정전 패턴) realpath dedup이 alias 한 쪽을
    통째로 skip → KG가 그 symbolic path를 저장했으면 false-orphan으로 잡힌다 (self-dogfood
    2026-05-28: skills/* 83 file false-orphan). symbolic path는 그대로 walk, cycle은 depth 가드.
    """
    root = Path(repo_root)
    paths: set[str] = set()
    root_str = str(root)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        # depth 가드: 심링크 cycle(A→B→A→...) 무한 폭주만 차단. 실 repo는 깊이 10 미만.
        if dirpath[len(root_str) :].count(os.sep) > 50:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            # 확장자 무관 전부 포함: disk_paths는 "디스크 실존 경로" 집합.
            # 과대포함은 occam을 더 보수적으로만 만든다(false-orphan 차단 > true-orphan 누락 위험).
            paths.add(normalize_path(str(Path(dirpath) / fn)))
    return frozenset(paths)


def _compute_disk_truth(repo_root: str | Path, nodes: list) -> dict[str, str]:
    """{normalize_path(source) → on-disk sha256} for node files that resolve on disk.

    Enables the HIGH-confidence disk-sha arbiter in _pick_current, which was DEAD in
    production: run_occam advertised disk-aware mode via repo_root but never built
    disk_truth, so the line-count heuristic (MEDIUM) was the sole arbiter (W3-B). Purely
    additive — files that don't resolve are skipped (MEDIUM fallback, unchanged behavior)."""
    root = Path(repo_root)
    out: dict[str, str] = {}
    for n in nodes:
        sp = getattr(n, "source_path", None)
        if not sp:
            continue
        for cand in ((Path(sp) if Path(sp).is_absolute() else root / sp), Path(sp)):
            if cand.is_file():
                try:
                    out[normalize_path(sp)] = hashlib.sha256(cand.read_bytes()).hexdigest()
                except OSError:
                    pass
                break
    return out


def _parse_iso(ts: str) -> datetime | None:
    """관대한 ISO 파서 — 'Z' suffix / neo4j datetime / tz-naive 허용. 못 읽으면 None."""
    try:
        dt = datetime.fromisoformat(ts.strip().replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _age_days(node: NodeRecord, now: datetime) -> float:
    """last_validated(없으면 created_at) 이후 경과 일수. 타임스탬프 부재/파싱불가 → 0 (staleness 없음)."""
    ts = node.last_validated or node.created_at
    if not ts:
        return 0.0
    parsed = _parse_iso(ts)
    if parsed is None:
        return 0.0
    return max((now - parsed).total_seconds() / 86400.0, 0.0)


def _build_score_meta(nodes: list[NodeRecord]) -> dict[str, NodeScoreMeta]:
    """fetch한 NodeRecord → name별 NodeScoreMeta (occam_pass가 σ/verdict 부착에 사용).

    redundancy는 _score_candidates가 권위로 override. invocation_count=None: occam은 usage
    로그가 없으므로 deadness 기여 0 (사용기록 부재를 'dead'로 saturate하지 않음 — 그래야 부분중복
    MEDIUM 후보가 σ=1.0 SUPERSEDE로 잘못 떠 escalation을 건너뛰는 일이 없다). age는 recency
    타임스탬프에서, inbound_edges는 KG 참조 수에서."""
    now = datetime.now(timezone.utc)
    meta: dict[str, NodeScoreMeta] = {}
    for n in nodes:
        if n.name is None:  # _score_candidates는 stale.name으로 키잉 — 무명 노드는 unscored
            continue
        meta[n.name] = NodeScoreMeta(
            redundancy=0.0,  # _score_candidates override
            age_days=_age_days(n, now),
            invocation_count=None,  # usage 로그 부재 → deadness 0 (no false-dead)
            inbound_edges=n.inbound_edges or 0,
        )
    return meta


@dataclass(frozen=True)
class OccamRunResult:
    # KG: occam-kam-canonical-2026-05-26
    report: OccamReport
    apply_result: ApplyResult
    scope: str | None = None

    @property
    def summary(self) -> str:
        r, a = self.report, self.apply_result
        mode = "DRY-RUN (no write)" if a.dry_run else f"APPLIED {a.applied_count}"
        scope = self.scope or "ALL"
        orphan = f" disk_orphans={r.orphan_count}" if r.orphan_count else ""
        return (
            f"occam[{scope}]: scanned={r.scanned_nodes} dup_groups={r.groups_with_dups} "
            f"superseded_candidates={r.superseded_count}{orphan} → {mode}"
        )


def run_occam(
    run_cypher: CypherRunner,
    write_cypher: CypherRunner | None = None,
    scope: str | None = None,
    apply: bool = False,
    disk_truth: dict[str, str] | None = None,
    repo_root: str | Path | None = None,
) -> OccamRunResult:
    # KG: occam-kam-canonical-2026-05-26
    """KG SourceCodeNode dedup pass. apply=False(기본) → dry-run, supersede write 없음.

    repo_root 주면 디스크를 스캔해 disk_paths 도출 → sha-이동/disk-orphan(mode-2/3) 탐지 활성.
    None이면 same-path 중복(mode-1)만.
    """
    nodes = fetch_source_nodes(run_cypher, scope)
    disk_paths = scan_disk_paths(repo_root) if repo_root is not None else None
    if disk_truth is None and repo_root is not None:
        disk_truth = _compute_disk_truth(repo_root, nodes)
    # σ 깨우기: score_meta 주입 → occam_pass가 후보마다 연속 σ + verdict 부착 (이전엔 dead).
    report = occam_pass(
        nodes,
        disk_truth=disk_truth,
        disk_paths=disk_paths,
        score_meta=_build_score_meta(nodes),
    )
    # σ-gate: 확신 SUPERSEDE만 auto-apply, 불확실(VERIFY/KEEP/MEDIUM·비동일)은 deferred → escalation.
    apply_result = apply_supersessions(
        report,
        write_cypher=write_cypher,
        dry_run=not apply,
        should_apply=is_confident_supersede,
    )
    return OccamRunResult(report=report, apply_result=apply_result, scope=scope)


__all__ = ["OccamRunResult", "run_occam", "scan_disk_paths"]
