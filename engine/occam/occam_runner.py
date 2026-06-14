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
from pathlib import Path

from engine.occam.kg_adapter import (
    ApplyResult,
    CypherRunner,
    apply_supersessions,
    fetch_source_nodes,
)
from engine.occam.occam import normalize_path, occam_pass
from engine.occam.occam_models import OccamReport

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


@dataclass(frozen=True)
class OccamRunResult:
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
    """KG SourceCodeNode dedup pass. apply=False(기본) → dry-run, supersede write 없음.

    repo_root 주면 디스크를 스캔해 disk_paths 도출 → sha-이동/disk-orphan(mode-2/3) 탐지 활성.
    None이면 same-path 중복(mode-1)만.
    """
    nodes = fetch_source_nodes(run_cypher, scope)
    disk_paths = scan_disk_paths(repo_root) if repo_root is not None else None
    if disk_truth is None and repo_root is not None:
        disk_truth = _compute_disk_truth(repo_root, nodes)
    report = occam_pass(nodes, disk_truth=disk_truth, disk_paths=disk_paths)
    apply_result = apply_supersessions(report, write_cypher=write_cypher, dry_run=not apply)
    return OccamRunResult(report=report, apply_result=apply_result, scope=scope)


__all__ = ["OccamRunResult", "run_occam", "scan_disk_paths"]
