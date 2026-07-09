"""judge — dispatch 폐루프: 발화된 DispatchDecision이 실제로 *소비*되는가.

RED(2026-07-10 실측): 발화는 산다(occam dead_node_count>10 → occam self-dispatch ≥1)
— 그러나 소비자가 없다. `engine.legion.dispatch_consumer`는 존재하지 않고,
`consumed_at` property를 SET하는 코드가 repo에 전무하므로 KG의 어떤 :DispatchEvent도
consumed_at을 갖지 못한다 → decisions_consumed == 0. 사슬의 앞(측정→발화→provenance)과
뒤(소비→실행→outcome)를 분리 실측해 "소비만 죽었음"을 증명한다.

GREEN 기대: post-run consumer 경유 후 consumed_at 보유 :DispatchEvent ≥ 1, 그리고
apply=True 실행에서 janitor가 자기 발화 조건을 스스로 해소(재실행 시 dead_node_count
임계 미달 → 재발화 0 = janitor_clears_own_trigger 1.0).

측정치는 전부 KG 상태에서 재도출한다 — in-memory report echo 금지(fake-green 차단).

사용: .venv/bin/python scripts/judge_dispatch_consumed.py [--receipt PATH]
출력: JSON {metric_name, metric_value, fired_count, janitor_clears_own_trigger, ...}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

N_DUP_GROUPS = 12  # dead_node_count>10 임계를 넘기는 확신-dup 그룹 수


def seed_confident_dups(store, n_groups: int = N_DUP_GROUPS) -> None:
    """abs/rel lineage 쌍(정규화 후 같은 경로 + 같은 sha256=byte-동일, 원경로는 다름)
    n그룹 — occam mode-1이 그룹핑하고 is_confident_supersede가 확신 처리하는 정확한
    케이스(σ=1.0, verdict=SUPERSEDE, deferred 0) → superseded_candidates == n > 10.
    (LocalKgStore 직접 append — 동일 name 두 노드는 merge_node로 못 만든다)"""
    for i in range(n_groups):
        for prefix in ("/Users/old/bhgman_tool/", "bhgman_tool/"):
            store.nodes.append(
                {
                    "labels": ["SourceCodeNode"],
                    "props": {
                        "name": f"judge_dup_{i}",
                        "sourcePath": f"{prefix}pkg/judge_dup_{i}.py",
                        "sha256": f"{i:064x}",
                        "lineCount": 10 + i,
                    },
                }
            )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--receipt", default=str(REPO / "verification" / "dispatch_consumed_receipt.json")
    )
    args = ap.parse_args()

    from engine.kg_local.runner import make_local_runner
    from engine.kg_local.store import LocalKgStore
    from engine.legion.commanders import build_default_legion

    store = LocalKgStore()
    run_cypher = make_local_runner(store, autosave=False)
    seed_confident_dups(store)

    ctx = {
        "run_cypher": run_cypher,
        "write_cypher": run_cypher,
        "apply": True,  # janitor 실행이 확신-SUPERSEDE를 실제 write하는 경로 (LocalKG, 안전)
        "cycle_id": "judge-dispatch-consumed",
    }
    run = build_default_legion().run(dict(ctx))

    fired = [d for d in run.dispatch_decisions if d.metric_name == "dead_node_count"]

    # ── 소비 단계 (모듈 부재=RED 0, 실재=GREEN 실측) ───────────────────────────
    consumer_available = True
    consume_error = ""
    try:
        from engine.legion.dispatch_consumer import consume_dispatch
    except ImportError as e:
        consumer_available = False
        consume_error = str(e)
    else:
        consume_dispatch(run.dispatch_decisions, ctx)

    # ── 측정: 전부 KG 상태에서 재도출 ──────────────────────────────────────────
    events = store.find_nodes("DispatchEvent")

    def _props(n):
        return n.get("props", {}) if isinstance(n, dict) else {}

    consumed = [e for e in events if _props(e).get("consumed_at")]
    executed = [e for e in consumed if _props(e).get("consume_status") == "executed"]

    # janitor 효능: 소비(apply=True) 후 같은 조건이 재발화하는가 — 두 번째 run 실측.
    run2 = build_default_legion().run(dict(ctx))
    refired = [d for d in run2.dispatch_decisions if d.metric_name == "dead_node_count"]
    clears = 1.0 if (fired and executed and not refired) else 0.0

    receipt = {
        "metric_name": "dispatch_decisions_consumed",
        "metric_value": float(len(consumed)),
        "fired_count": len(fired),
        "executed_count": len(executed),
        "consumer_available": consumer_available,
        "consume_error": consume_error,
        "janitor_clears_own_trigger": clears,
        "refired_after_consume": len(refired),
        "dispatch_events_total": len(events),
        "n_dup_groups_seeded": N_DUP_GROUPS,
        "note": (
            "fired>0 & consumed==0 = 사슬 앞만 생존(소비 부재). "
            "consumed>0 & refired==0 = 폐루프가 자기 발화 조건을 해소."
        ),
    }
    out = Path(args.receipt)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
