"""judge J-C — 비유일키 3시나리오: 시스템이 애매성 앞에서 fail-close 하는가.

세 시나리오 (전부 실 Neo4j 에서 재현 가능한 모양 — LocalKgStore 러너의 충실도 수리
C-0 이 전제라, main 에서는 로컬 러너의 first-match 마스킹 *자체*가 baseline 의 일부다):

  C1 복합키 쌍둥이: (sourcePath, sha256) 동일 stale 쌍둥이 2 + 상이 current —
     유일성 가드 없으면 다중매치 아카이브(실서버) / 임의 1개 아카이브(로컬 마스킹).
  C2 keep==drop 무생존: 동명 동률 노드 2 → plan_supersession(keep==drop) →
     자기-supersede → (실서버 의미론) 양쪽 SUPERSEDED, 생존자 0.
  C3 harness 사이클: kg_harness.supersede_node 로 X→Y, Y→X 교차 write —
     H3 가드 부재면 SUPERSEDED_BY 사이클, 생존자 0.

metric = safe_refusals(0~3): 각 시나리오에서 시스템이 안전하게 거부/무변이로 처리한 수.
RED=0 (전부 unsafe), GREEN=3.

사용: .venv/bin/python verification/seam_integrity/judge_nonunique_key.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def _sc_nodes(store):
    return [n for n in store.nodes if "SourceCodeNode" in n["labels"]]


def _superseded(store, label="SourceCodeNode"):
    return [
        n["props"]
        for n in store.nodes
        if label in n["labels"] and n["props"].get("status") == "SUPERSEDED"
    ]


def scenario_c1_composite_twins() -> dict:
    """(path,sha) 동일 쌍둥이 다중매치 — 안전 = 아카이브 0 + 거부 기록."""
    from engine.kg_local.runner import make_local_runner
    from engine.kg_local.store import LocalKgStore
    from engine.occam.kg_adapter import apply_supersessions
    from engine.occam.occam import occam_pass
    from engine.occam.occam_models import NodeRecord

    store = LocalKgStore()
    # stale 쌍둥이 2 (동일 path+sha — UNCONSTRAINABLE 라벨이라 실서버에 실재 가능)
    for _ in range(2):
        store.nodes.append(
            {
                "labels": ["SourceCodeNode"],
                "props": {
                    "name": "jc1_stale",
                    "sourcePath": "/Users/old/bhgman_tool/pkg/jc1.py",
                    "sha256": "d" * 64,
                    "lineCount": 3,
                },
            }
        )
    store.nodes.append(
        {
            "labels": ["SourceCodeNode"],
            "props": {
                "name": "jc1_cur",
                "sourcePath": "bhgman_tool/pkg/jc1.py",
                "sha256": "d" * 64,
                "lineCount": 3,
            },
        }
    )
    runner = make_local_runner(store, autosave=False)
    # occam_pass 로 후보 구성(같은 정규화 그룹) 후 same-sha 확신 경로 apply
    nodes = [
        NodeRecord(
            name=p.get("name"),
            source_path=p["sourcePath"],
            sha256=p["sha256"],
            line_count=p["lineCount"],
        )
        for p in (n["props"] for n in _sc_nodes(store))
    ]
    report = occam_pass(nodes)
    ar = apply_supersessions(report, write_cypher=runner, dry_run=False)
    archived = _superseded(store)
    # 안전 = (다중매치 애매성 앞에서) 아무 노드도 아카이브하지 않고 거부를 기록
    refused_note = any("refus" in n.lower() or "no match" in n.lower() for n in ar.notes)
    safe = 1 if (len(archived) == 0 and refused_note) else 0
    return {
        "safe": safe,
        "archived": len(archived),
        "applied_count": ar.applied_count,
        "notes": list(ar.notes)[:4],
    }


def scenario_c2_keep_eq_drop() -> dict:
    """keep==drop 무생존 — 안전 = *명시 거부*(ValueError fail-closed)만 인정.

    main 의 LocalKgStore 러너는 first-match 마스킹으로 이 write 를 no-op 처럼 보이게
    하지만(실 Neo4j 의미론은 대칭 2행 매치 → 양쪽 SUPERSEDED, 생존자 0), 마스킹된 무변이는
    safe 가 아니다 — 결함이 로컬에서 안 보일 뿐."""
    from engine.occam.semantic_dedup import NearDupPair, plan_supersession

    try:
        plan_supersession(
            NearDupPair(keep_id="jc2_dup", drop_id="jc2_dup", similarity=0.99),
            key="name",
            label="Concept",
        )
    except ValueError:
        return {"safe": 1, "mode": "raised (fail-closed)"}
    return {"safe": 0, "mode": "plan issued for keep==drop (실서버 의미론=무생존)"}


def scenario_c3_harness_cycle() -> dict:
    """kg_harness.supersede_node 교차 write — 안전 = 두 번째 write 무효(생존자 ≥1)."""
    from engine.kg_harness.write_guard import supersede_node
    from engine.kg_local.runner import make_local_runner
    from engine.kg_local.store import LocalKgStore

    store = LocalKgStore()
    for nm in ("jc3_x", "jc3_y"):
        store.nodes.append({"labels": ["Lesson"], "props": {"name": nm, "status": None}})
    runner = make_local_runner(store, autosave=False)

    try:
        for stale, cur in (("jc3_x", "jc3_y"), ("jc3_y", "jc3_x")):
            cypher, params = supersede_node(
                "Lesson", "name", stale, cur, "judge cycle probe", run=None
            )
            runner(cypher, params)
    except ValueError as e:
        # write_guard 의 의도된 fail-closed 거부만 safe.
        return {"safe": 1, "survivors": -1, "mode": f"guard raised: {e!r}"}
    except KeyError as e:
        # 로컬 러너가 kg_harness 파라미터를 라우팅 못 함 = 인프라 공백(마스킹) — safe 아님:
        # 실 Neo4j 의미론은 두 write 를 실행해 사이클을 만든다(생존자 0).
        return {"safe": 0, "survivors": -1, "mode": f"local routing gap (masked): {e!r}"}
    survivors = [
        n["props"]
        for n in store.nodes
        if "Lesson" in n["labels"] and n["props"].get("status") != "SUPERSEDED"
    ]
    return {
        "safe": 1 if len(survivors) >= 1 else 0,
        "survivors": len(survivors),
        "mode": "executed",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--receipt",
        default=str(REPO / "verification" / "seam_integrity" / "nonunique_key_receipt.json"),
    )
    args = ap.parse_args()

    c1 = scenario_c1_composite_twins()
    c2 = scenario_c2_keep_eq_drop()
    c3 = scenario_c3_harness_cycle()
    safe_refusals = c1["safe"] + c2["safe"] + c3["safe"]
    zero_survivor = (1 if c2.get("survivors") == 0 else 0) + (1 if c3.get("survivors") == 0 else 0)

    receipt = {
        "metric_name": "nonunique_safe_refusals",
        "metric_value": float(safe_refusals),
        "zero_survivor_scenarios": float(zero_survivor),
        "c1_composite_twins": c1,
        "c2_keep_eq_drop": c2,
        "c3_harness_cycle": c3,
        "note": "RED=0(전 시나리오 unsafe — 로컬 마스킹 포함), GREEN=3 + zero_survivor 0.",
    }
    out = Path(args.receipt)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
