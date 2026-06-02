# legion — 7군단장 합성 layer

7군단장(occam/eureka/hades/longinus/prometheus/naesengmoon/jaebaeman)을 하나의 실행으로 조립 + tamper-evident audit trail.

- `legion.py` — 합성 본체, `legion run` CLI
- `commanders.py` — CommanderStage 어댑터 (각 군단장 배선)
- `jaebaeman_substrate.py` — 재배맨을 dispatch substrate로 (load-bearing)
- `measurement.py` — 각 commander self-metric + threshold 측정 (need-based dispatch)
- `audit_prom_cycles.py` — HMAC tamper-evident audit
- `legion_models.py` — 데이터 모델

> 결정론 코어 = 정체성·바닥. LLM = 옵션 enrichment (`project_legion_unification_kg_engine_2026_06_01`).
> 실행: `uv run pytest` (시스템 python3는 frontmatter 못 찾음).
