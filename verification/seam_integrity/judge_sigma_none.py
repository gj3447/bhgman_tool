"""judge J-B1 — σ-None 관용: verdict 미계산 후보가 확신-supersede 로 통과하는가.

RED(main 실측): is_confident_supersede 의 ①절이 `verdict is not None and != SUPERSEDE`
— None(σ 미배선/미계산)이면 거부절을 *우회*해 HIGH 또는 same-sha 만으로 auto-apply.
생산원: name=None 노드는 _build_score_meta 가 건너뛰어(occam_runner.py:128-130) score
미부착 → verdict=None 후보가 게이트 직행.

GREEN 기대: 술어가 verdict=="SUPERSEDE" 필수(None=확신 아님→escalate) + score_meta 가
(source_path, sha256) 복합키로 name=None 노드에도 σ 부착 → 프로덕션에서 verdict-None
write 0, name=None same-sha 케이스는 σ(redundancy=1.0)로 SUPERSEDE verdict 를 *정직하게*
받아 여전히 적용(하위호환), partition(applied+deferred+refused=candidates) 불변.

사용: .venv/bin/python verification/seam_integrity/judge_sigma_none.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--receipt",
        default=str(REPO / "verification" / "seam_integrity" / "sigma_none_receipt.json"),
    )
    args = ap.parse_args()

    from engine.kg_local.runner import make_local_runner
    from engine.kg_local.store import LocalKgStore
    from engine.occam.escalation import is_confident_supersede
    from engine.occam.occam_models import Confidence, NodeRecord, SupersessionCandidate
    from engine.occam.occam_runner import run_occam

    # ── 축 1: 술어 직접 — verdict=None + HIGH + sha 상이 (σ 없이 확신 판정?) ──────
    stale = NodeRecord(name="jsn_s", source_path="bhgman_tool/a.py", sha256="a" * 64, line_count=5)
    cur = NodeRecord(name="jsn_c", source_path="bhgman_tool/a.py", sha256="b" * 64, line_count=9)
    cand_none_high = SupersessionCandidate(
        stale=stale,
        current=cur,
        normalized_path="a.py",
        reason="probe",
        confidence=Confidence.HIGH,
        score=None,
        verdict=None,
    )
    predicate_confident_on_none = 1.0 if is_confident_supersede(cand_none_high) else 0.0

    # ── 축 2: 파이프라인 — name=None same-sha 2노드 apply 실측 ──────────────────
    store = LocalKgStore()
    for prefix in ("/Users/old/bhgman_tool/", "bhgman_tool/"):
        store.nodes.append(
            {
                "labels": ["SourceCodeNode"],
                "props": {
                    # name 부재 (실 KG 에 존재하는 모양 — fetch 는 name 미필터)
                    "sourcePath": f"{prefix}pkg/jsn.py",
                    "sha256": "c" * 64,
                    "lineCount": 3,
                },
            }
        )
    runner = make_local_runner(store, autosave=False)
    result = run_occam(runner, write_cypher=runner, apply=True)
    report, ar = result.report, result.apply_result

    applied_with_verdict_none = sum(
        1
        for c in report.candidates
        if c.verdict is None and any(c.stale.source_path == s for s in ar.superseded)
    )
    nameless_applied = ar.applied_count  # 하위호환 축: same-sha 무명 노드는 여전히 정리돼야
    partition_ok = ar.applied_count + len(ar.deferred) + sum(
        1 for n in ar.notes if "REFUSE" in n.upper()
    ) >= len(report.candidates)

    receipt = {
        "metric_name": "sigma_none_confident",
        "metric_value": predicate_confident_on_none + float(applied_with_verdict_none),
        "predicate_confident_on_none": predicate_confident_on_none,
        "applied_with_verdict_none": applied_with_verdict_none,
        "nameless_samesha_applied": nameless_applied,
        "partition_holds": bool(partition_ok),
        "candidates": [
            {"verdict": c.verdict, "sigma": c.score, "conf": c.confidence.value}
            for c in report.candidates
        ],
        "note": (
            "RED: 술어가 None 을 확신 취급(=1) + verdict-None 적용 발생(≥1) → 합계 ≥2. "
            "GREEN: 둘 다 0 — 단 무명 same-sha 는 복합키 σ로 SUPERSEDE verdict 를 받아 "
            "nameless_samesha_applied=1 유지(하위호환·정직화 동시)."
        ),
    }
    out = Path(args.receipt)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
