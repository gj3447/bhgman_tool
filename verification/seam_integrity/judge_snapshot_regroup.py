"""judge J-A2 — 재그룹핑 불변(마이그레이션 게이트): 새 normalize_path 가 라이브 공유 KG 의
기존 노드 키를 하나라도 바꾸는가.

시점-고정 fixture(2026-07-10 라이브 KG 에서 read-only 1회 추출한 distinct sourcePath —
fetch-적격 노드 스코프: sha256/lineCount/sourcePath 전부 non-null, occam 이 만지는 정확히
그 집합) 전수에 구(old rfind marker)·신(세그먼트-앵커 정규식) 정규화를 나란히 적용 —
결과가 다른 경로 수 == 0 이어야 D1(R2′ 개방) 진행 가능. 델타 >0 이면 목록 검토 전 착지 중단.

정직 한계 (적대검증 2026-07-10): 이 judge 는 *fixture 시점*의 불변을 증명한다 — 라이브
재조회는 하지 않으며(스냅샷 이후 신규 경로는 범위 밖), fetch-부적격(필수필드 null) 노드도
범위 밖이다(occam write 경로가 그 노드를 만지지 않으므로 게이트 목적상 충분). -wt- 경로
존재 여부는 fixture 내 검사(wt_paths_in_live_kg)로 표면화.

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
