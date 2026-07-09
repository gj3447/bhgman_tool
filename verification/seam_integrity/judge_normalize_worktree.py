"""judge J-A1 — normalize_path 워크트리 seam: 워크트리 실행이 정본과 같은 세계를 보는가.

RED(main 실측): `_REPO_MARKER="bhgman_tool/"` rfind 는 `bhgman_tool-wt-*/...` 경로에
매치되지 않아 (a) 워크트리 root 의 scan_disk_paths 가 전량 비정규화 절대경로를 만들어
KG 키와 미조인 → 정본 lineage 노드 전원 false-orphan, (b) `_in_repo("-wt-")=False` 로
move/orphan 판정 자체에서 제외된다. 라이브 KG 543노드 dry-run 실측: in-repo 274 중
270 false-orphan (정찰 wf_5e7d6ea7-d7a).

GREEN 기대: 세그먼트-앵커 정규식 + relpath 합성 scan 후 — 워크트리명 root 실행의
false-orphan 0, `_in_repo(-wt-)=True`.

측정: LocalKgStore 시드 + 실 tmp 디렉터리(워크트리명)로 run_occam — 상태 재도출.
사용: .venv/bin/python verification/seam_integrity/judge_normalize_worktree.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

N_FILES = 6


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--receipt",
        default=str(REPO / "verification" / "seam_integrity" / "normalize_worktree_receipt.json"),
    )
    args = ap.parse_args()

    from engine.kg_local.runner import make_local_runner
    from engine.kg_local.store import LocalKgStore
    from engine.occam.occam import _in_repo, normalize_path
    from engine.occam.occam_runner import run_occam

    with tempfile.TemporaryDirectory() as td:
        # 실파일을 *워크트리명* root 아래 생성 — 정본 checkout 이 아니라 worktree 시나리오.
        wt_root = Path(td) / "bhgman_tool-wt-judge"
        (wt_root / "engine").mkdir(parents=True)
        shas = {}
        for i in range(N_FILES):
            f = wt_root / "engine" / f"jnw_{i}.py"
            body = f"# live file {i}\n".encode()
            f.write_bytes(body)
            shas[f"engine/jnw_{i}.py"] = hashlib.sha256(body).hexdigest()

        # KG 에는 정본 rel-lineage 로 시드 (실 KG 의 지배적 lineage 모양).
        store = LocalKgStore()
        for rel, sha in shas.items():
            store.nodes.append(
                {
                    "labels": ["SourceCodeNode"],
                    "props": {
                        "name": rel.rsplit("/", 1)[-1],
                        "sourcePath": f"bhgman_tool/{rel}",
                        "sha256": sha,
                        "lineCount": 1,
                    },
                }
            )
        runner = make_local_runner(store, autosave=False)
        result = run_occam(runner, write_cypher=runner, apply=False, repo_root=wt_root)

        false_orphans = [
            n.source_path
            for n in result.report.orphans
            # 시드 전원이 디스크에 실존하므로 orphan 으로 잡힌 것은 전부 false.
        ]
        in_repo_wt = _in_repo(str(wt_root / "engine" / "jnw_0.py"))
        norm_wt = normalize_path(str(wt_root / "engine" / "jnw_0.py"))

    receipt = {
        "metric_name": "worktree_false_orphans",
        "metric_value": float(len(false_orphans)),
        "n_seeded": N_FILES,
        "in_repo_on_worktree_path": bool(in_repo_wt),
        "normalize_on_worktree_path": norm_wt,
        "worktree_in_repo": 1.0 if in_repo_wt else 0.0,
        "false_orphan_paths": false_orphans[:10],
        "note": (
            "시드 전원 디스크 실존 — orphan 은 전부 false-orphan. RED=6(전원, 워크트리 root 가 "
            "KG 키와 미조인), GREEN=0 + _in_repo(-wt-)=True."
        ),
    }
    out = Path(args.receipt)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
