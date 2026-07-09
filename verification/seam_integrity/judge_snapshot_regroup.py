"""judge J-A2 — 재그룹핑 불변(마이그레이션 게이트): 새 normalize_path 가 라이브 공유 KG 의
기존 노드 키를 하나라도 바꾸는가.

라이브 KG distinct sourcePath 스냅샷(2026-07-10, read-only 추출, fixture 고정) 전수에
구(old rfind marker)·신(세그먼트-앵커 정규식) 정규화를 나란히 적용 — 결과가 다른 경로 수
== 0 이어야 D1(R2′ 개방) 진행 가능. 델타 >0 이면 그 목록을 영수증에 남기고 착지 중단.

예외적으로 허용되는 델타: `-wt-` 경로(현 KG 0건 전제 — 실측 재확인 포함)와
비-세그먼트 접미 오매치(예: Xbhgman_tool/ — 구 rfind 의 *결함*이 만든 키; 실재하면
그 자체가 발견이라 목록으로 표면화).

사용: .venv/bin/python verification/seam_integrity/judge_snapshot_regroup.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

SNAPSHOT = REPO / "verification" / "seam_integrity" / "kg_sourcepath_snapshot_20260710.json"

_OLD_MARKER = "bhgman_tool/"


def _old_normalize(path: str) -> str:
    idx = path.rfind(_OLD_MARKER)
    if idx == -1:
        return path
    return path[idx + len(_OLD_MARKER) :]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--receipt",
        default=str(REPO / "verification" / "seam_integrity" / "snapshot_regroup_receipt.json"),
    )
    args = ap.parse_args()

    from engine.occam.occam import normalize_path as new_normalize

    paths = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    changed = []
    wt_paths = []
    for p in paths:
        if "-wt-" in p:
            wt_paths.append(p)
        old, new = _old_normalize(p), new_normalize(p)
        if old != new:
            changed.append({"path": p, "old": old, "new": new})

    receipt = {
        "metric_name": "changed_normalize_keys",
        "metric_value": float(len(changed)),
        "snapshot_size": len(paths),
        "wt_paths_in_live_kg": len(wt_paths),
        "changed": changed[:50],
        "note": (
            "0 = 기존 라이브 KG 노드의 그룹핑 키가 신 정규화로 불변 — 마이그레이션 위험 없음. "
            ">0 이면 목록 검토 전 D1 진행 금지."
        ),
    }
    out = Path(args.receipt)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {k: receipt[k] for k in ("metric_value", "snapshot_size", "wt_paths_in_live_kg")}
        )
    )
    if changed:
        print(json.dumps(changed[:10], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
