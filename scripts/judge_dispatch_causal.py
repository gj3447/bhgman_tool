"""judge v2 — 폐루프 자기해소의 *인과 분리*: 닫은 것이 run1 인가 janitor 인가.

적대검증(2026-07-10, wf_704b75b0-bee high): v1 judge 의 janitor_clears_own_trigger 는
run1(apply=True)의 in-run occam apply 가 백로그를 이미 닦은 뒤라 — 아무것도 안 하는
janitor 도 배터리를 통과할 수 있었다(자기해소 green 의 공로 귀속 오류). v2 는 두 날개로
인과를 분리한다:

  A(실 janitor): run1 후 janitor 몫의 백로그를 *재주입* → consume → 재발화 0 실측
  B(no-op janitor): 같은 재주입인데 유효한 hygiene 모양만 반환하는 가짜 janitor →
    백로그 잔존 → 재발화 ≥1 실측

janitor_causal_clears = 1.0 iff A가 닫고 AND B가 못 닫는다 — 양 날개가 모두 판별해야만
참 (한쪽만으론 vacuous). fired/refired 는 KG :DispatchEvent(dead_node_count) 카운트
델타로 재도출(로컬 키가 decided_at 을 포함하도록 수리된 뒤라 fire 마다 노드 신설),
consumed 는 consumed_at 보유 이벤트 재도출 — in-memory echo 아님.

사용: .venv/bin/python scripts/judge_dispatch_causal.py [--receipt PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

N = 12  # dead_node_count>10 임계 초과


def _seed(store, tag: str, n: int = N) -> None:
    for i in range(n):
        for prefix in ("/Users/old/bhgman_tool/", "bhgman_tool/"):
            store.nodes.append(
                {
                    "labels": ["SourceCodeNode"],
                    "props": {
                        "name": f"{tag}_{i}",
                        "sourcePath": f"{prefix}pkg/{tag}_{i}.py",
                        "sha256": f"{i:064x}",
                        "lineCount": 10 + i,
                    },
                }
            )


def _dead_fire_count(store) -> int:
    return sum(
        1
        for e in store.find_nodes("DispatchEvent")
        if e["props"].get("metric_name") == "dead_node_count"
    )


def _consumed_executed(store) -> int:
    return sum(
        1
        for e in store.find_nodes("DispatchEvent")
        if e["props"].get("consumed_at") and e["props"].get("consume_status") == "executed"
    )


def _wing(noop_janitor: bool) -> dict:
    """한 날개 실행: seed→run1→재주입→consume(실/가짜)→run2. 전 카운트 KG 재도출."""
    from engine.kg_local.runner import make_local_runner
    from engine.kg_local.store import LocalKgStore
    from engine.legion.commanders import build_default_legion, default_stages
    from engine.legion.dispatch_consumer import consume_dispatch
    from engine.legion.legion_models import CommanderStage

    store = LocalKgStore()
    _seed(store, "cz_a")
    runner = make_local_runner(store, autosave=False)
    ctx = {
        "run_cypher": runner,
        "write_cypher": runner,
        "apply": True,
        "cycle_id": "judge-causal",
    }
    run = build_default_legion().run(dict(ctx))
    fired_kg = _dead_fire_count(store)

    _seed(store, "cz_b")  # janitor 몫 재주입 — run1 은 이미 지나갔다

    stages = {s.name: s for s in default_stages()}
    if noop_janitor:
        stages["occam"] = CommanderStage(
            "occam",
            "정리",
            ("run_cypher",),
            ("hygiene",),
            lambda _ctx: {
                "hygiene": {"mode": "occam", "candidates": [], "superseded_candidates": 0}
            },
            measure=None,
        )
    consume_dispatch(run.dispatch_decisions, ctx, stages=stages)

    executed_kg = _consumed_executed(store)
    n_dead_before_run2 = _dead_fire_count(store)
    build_default_legion().run(dict(ctx))
    refired_kg = _dead_fire_count(store) - n_dead_before_run2

    return {"fired": fired_kg, "executed": executed_kg, "refired": refired_kg}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--receipt", default=str(REPO / "verification" / "dispatch_causal_receipt.json")
    )
    args = ap.parse_args()

    real = _wing(noop_janitor=False)
    noop = _wing(noop_janitor=True)

    real_clears = bool(real["fired"] and real["executed"] and real["refired"] == 0)
    noop_discriminates = bool(noop["fired"] and noop["executed"] and noop["refired"] >= 1)
    causal = 1.0 if (real_clears and noop_discriminates) else 0.0

    receipt = {
        "metric_name": "janitor_causal_clears",
        "metric_value": causal,
        "real_wing": real,
        "noop_wing": noop,
        "noop_janitor_refires": float(noop["refired"]),
        "note": (
            "양 날개 동시 성립만 참: 실 janitor 는 재주입 백로그를 닫고(재발화 0), "
            "no-op janitor 는 못 닫는다(재발화 ≥1) — 자기해소의 공로가 run1 이 아니라 "
            "janitor 실행에 귀속됨의 분리 증명. 전 카운트 KG 재도출."
        ),
    }
    out = Path(args.receipt)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
