"""부채 #1(longinus) — 독립 drift oracle: 디스크 re-hash vs KG sha256.

longinus drift 탐지의 효능 측정을 막던 순환(oracle==signal, 둘 다 longinus 산출)을
깬다: **디스크를 지금 다시 해시**한 게 독립 ground truth. KG에 longinus가 기록한
sha256과 일치하면 longinus 바인딩이 디스크와 동기(in-sync), 불일치면 longinus가
놓친 실제 drift.

efficacy = longinus binding freshness = in-sync 비율 (독립 oracle, n≈디스크 실존 노드).
높을수록 longinus가 KG↔code 동기를 잘 유지(효능). 불일치 노드는 DriftEvent로 적재.

순수(compute_sync) + IO(hash/fetch/write) 분리.

# KG: efficacy-longinus-2026-06-01, efficacy-measurement-line-2026-06-01,
#     ATOM_Skill_longinus, lesson-longinus-self-violated-sha256-covenant-recurrence-root-cause-2026-05-20
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from engine.occam.occam import normalize_path

_SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
}


def hash_file(path: Path) -> str | None:
    """파일 sha256 hex. 읽기 실패 시 None (방어적)."""
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def compute_sync(kg_nodes: list[dict], disk_hashes: dict[str, str]) -> list[dict]:
    """노드별 {name, in_sync, disk_sha, kg_sha}. 디스크에 없는 norm은 skip(occam orphan 담당).

    kg_nodes: [{name, sourcePath, sha256}]. disk_hashes: {normpath: sha256}."""
    out: list[dict] = []
    for n in kg_nodes:
        sp = n.get("sourcePath") or ""
        if "bhgman_tool/" not in sp:
            continue
        norm = normalize_path(sp)
        disk_sha = disk_hashes.get(norm)
        if disk_sha is None:
            continue  # 디스크에 없음 = drift 아닌 orphan(occam 영역)
        out.append(
            {
                "name": n["name"],
                "disk_sha": disk_sha,
                "kg_sha": n.get("sha256"),
                "in_sync": disk_sha == n.get("sha256"),
            }
        )
    return out


def sync_accuracy(rows: list[dict]) -> tuple[int, int, float]:
    """(in_sync, total, ratio). longinus binding freshness 효능."""
    total = len(rows)
    insync = sum(1 for r in rows if r["in_sync"])
    return insync, total, (insync / total if total else 0.0)


def _hash_repo(repo_root: str | Path, wanted: set[str]) -> dict[str, str]:
    """wanted(normpath 집합) 파일만 re-hash. 전체 walk보다 빠름."""
    root = Path(repo_root)
    out: dict[str, str] = {}
    for norm in wanted:
        p = root / norm
        if p.is_file():
            sha = hash_file(p)
            if sha is not None:
                out[norm] = sha
    return out


_FETCH = (
    "MATCH (s:SourceCodeNode) WHERE s.sourcePath CONTAINS 'bhgman_tool/' "
    "AND s.sha256 IS NOT NULL AND coalesce(s.disk_present, true) "
    "RETURN s.name AS name, s.sourcePath AS sourcePath, s.sha256 AS sha256"
)
_WRITE = (
    "UNWIND $rows AS r "
    "MATCH (s:SourceCodeNode {name: r.name}) "
    "SET s.disk_sha_now = r.disk_sha, s.sha_in_sync = r.in_sync, "
    "s.drift_oracle_checked_at = datetime()"
)
# 독립 drift 이벤트 적재 (불일치분만). longinus가 놓친 실제 drift의 비순환 증거.
_DRIFT_EVENT = (
    "UNWIND $drifted AS d "
    "MATCH (s:SourceCodeNode {name: d.name}) "
    "MERGE (e:DriftEvent:IndependentDriftOracle {name: 'idrift-' + d.name}) "
    "SET e.kg_sha = d.kg_sha, e.disk_sha = d.disk_sha, e.detected_at = datetime(), "
    "e.oracle = 'disk-rehash (longinus-independent)' "
    "MERGE (e)-[:DRIFT_OF]->(s)"
)


def main() -> int:  # pragma: no cover — IO 진입점
    import os  # noqa: PLC0415

    from engine.cli.runtime import make_kg_runners  # noqa: PLC0415

    runners = make_kg_runners()
    if runners is None:
        print("neo4j 미연결 (NEO4J_PASSWORD?)", file=sys.stderr)
        return 2
    run_cypher, write_cypher, close = runners
    try:
        repo_root = os.environ.get("BHGMAN_REPO_ROOT", ".")
        nodes = run_cypher(_FETCH, {})
        wanted = {
            normalize_path(n["sourcePath"])
            for n in nodes
            if "bhgman_tool/" in (n["sourcePath"] or "")
        }
        disk_hashes = _hash_repo(repo_root, wanted)
        rows = compute_sync(nodes, disk_hashes)
        write_cypher(_WRITE, {"rows": rows})
        drifted = [r for r in rows if not r["in_sync"]]
        if drifted:
            write_cypher(_DRIFT_EVENT, {"drifted": drifted})
        insync, total, ratio = sync_accuracy(rows)
        print(
            f"longinus drift oracle: in_sync={insync}/{total} ({ratio:.3f}) — "
            f"{len(drifted)} independent drift event(s) recorded"
        )
        return 0
    finally:
        close()


__all__ = ["compute_sync", "hash_file", "sync_accuracy"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
