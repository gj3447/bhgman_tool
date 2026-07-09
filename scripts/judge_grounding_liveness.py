#!/usr/bin/env python3
"""judge — grounding 측정 생사 실측 (LakatosTree_BhgmanSeamIntegrity_20260708/grounding_measurement_liveness).

metric: grounding_dead_signal_count
  = (빈 획득 legion run 2회 중 external_grounding_ratio self-recurse 오발화 수)   ← 구조적 0.0 축
  + (미측정 기본 상태에서 measure() 가 ratio 값을 위장 노출하면 1)               ← dead 1.0 축
  + (실 findings 비접지 시 발화하지 않으면 1)                                    ← 판별력 counter 축
세 축 합산이라 "메트릭 통째 삭제" 치팅(판별력 상실)도 벌점이다. 목표 0.

verdict 는 손입력이 아니라 live import 한 production legion 루프/측정 클래스 실행에서
도출된다. 영수증: verification/grounding_liveness_receipt.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine.kg_local.runner import make_local_runner  # noqa: E402
from engine.kg_local.store import LocalKgStore  # noqa: E402
from engine.legion.commanders import build_default_legion  # noqa: E402
from engine.legion.measurement import PrometheusMeasurement  # noqa: E402

METRIC = "external_grounding_ratio"


def main() -> None:
    # 축 1: 살아있는 legion 경로, 빈 KG·fetcher 부재(MCP infra-0 과 동형 ctx) 2회 —
    # 획득 0건인데 접지 self-recurse 가 발화하면 그 수만큼 벌점(구조적 0.0 오발화).
    fires_on_empty = 0
    for i in range(2):
        rc = make_local_runner(LocalKgStore(), autosave=False)
        run = build_default_legion().run({"run_cypher": rc, "cycle_id": f"judge-empty-{i}"})
        fires_on_empty += sum(1 for d in run.dispatch_decisions if d.metric_name == METRIC)

    # 축 2: 미측정 기본 상태 — measure() 가 ratio 를 노출하면(어떤 상수든) 위장 벌점.
    default_exposed = PrometheusMeasurement().measure().get(METRIC)
    dead_default = 1 if default_exposed is not None else 0

    # 축 3(counter): 실 findings 전부 비접지 → self-recurse 는 *발화해야* 한다.
    m = PrometheusMeasurement()
    m.update_grounding(["", "not a url"])
    alive = any(d.metric_name == METRIC for d in m.decide_dispatch(cycle_id="judge-alive"))
    not_alive_penalty = 0 if alive else 1

    value = fires_on_empty + dead_default + not_alive_penalty
    receipt = {
        "tree": "LakatosTree_BhgmanSeamIntegrity_20260708",
        "node": "grounding_measurement_liveness",
        "metric": "grounding_dead_signal_count",
        "value": value,
        "fires_on_empty_acquisition": fires_on_empty,
        "default_exposed_ratio": default_exposed,
        "dead_default": dead_default,
        "discrimination_alive": alive,
        "not_alive_penalty": not_alive_penalty,
    }
    out = REPO / "verification" / "grounding_liveness_receipt.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
