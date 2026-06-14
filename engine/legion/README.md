# legion — 7군단장 합성 layer

7군단장(occam/eureka/hades/longinus/prometheus/naesengmoon/jaebaeman)을 하나의 실행으로 조립.

- `legion.py` — 합성 본체, `legion run` CLI. measure()+decide_dispatch()를 stage마다 호출해
  DispatchDecision을 기록 (W2-A). DispatchDecision은 HMAC 서명됨(`measurement.py` `_sign`,
  `to_kg_event().hmac_signature`) = tamper-evident dispatch provenance.
- `commanders.py` — CommanderStage 어댑터 (각 군단장 배선; prometheus만 measure factory 배선)
- `jaebaeman_substrate.py` — 재배맨을 dispatch substrate로 (load-bearing)
- `measurement.py` — 각 commander self-metric + threshold + HMAC-signed DispatchDecision.
  `threshold_derivation/` 하위 + `record_outcome` calibration은 **현재 미배선(experimental/offline)**.
- `audit_prom_cycles.py` — Stevens-scale 측정-위반 스캐너 (HMAC 아님 — H8 정정)
- `legion_models.py` — 데이터 모델 (CommanderStage.measure / LegionRun.dispatch_decisions 포함)

> 결정론 코어 = 정체성·바닥. LLM = 옵션 enrichment (`project_legion_unification_kg_engine_2026_06_01`).
> 실행: `uv run pytest` (시스템 python3는 frontmatter 못 찾음).
