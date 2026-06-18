# NFR Environment Variants (Phase-Specific)

> Contract의 NFR(Non-Functional Requirements)을 *환경별로 분리*하여 기록. dev/staging/prod 각각 다른 임계값.

---

## 환경 변형 패턴

Contract에 `nfr_env_{dev,staging,prod}` 필드. 각 환경의 JSON dict 저장.

### Database 접근 (3 환경)

| Field | Dev | Staging | Prod |
|-------|-----|---------|------|
| `nfr_env_dev` | `{"mock": true, "latency_p99_ms": null, "adapter": "MockDBAdapter"}` | — | — |
| `nfr_env_staging` | — | `{"mock": false, "latency_p99_ms": 100, "adapter": "PostgresAdapter"}` | — |
| `nfr_env_prod` | — | — | `{"mock": false, "latency_p99_ms": 50, "pool_size": 20}` |

### 환경 선택 (runtime)

```python
env = config.nfr.execution_env   # "dev" | "staging" | "prod"
nfr = json.loads(contract[f"nfr_env_{env}"])
adapter = MockDBAdapter() if nfr.get("mock") else PostgresAdapter(pool_size=nfr.get("pool_size", 10))
```

---

## Search Quality (Performance Drift 추적)

```yaml
Contract: CT_ECommerce_Search
nfr_accuracy: "nDCG@10 > 0.7"
nfr_env_dev:  '{"test_dataset": "fixtures/search_100.json", "nDCG_threshold": 0.6}'
nfr_env_prod: '{"test_dataset": "/data/search_10k.json", "nDCG_threshold": 0.7,
                "drift_check_interval_hours": 24}'
```

Prod에서 24h마다 nDCG 평가. 0.7 미만이면 `ContractAmended` (reason=`performance_drift`).
자세히: [amendment_scenarios.md](amendment_scenarios.md)

---

## API Gateway (Latency-Critical)

```yaml
Contract: CT_APIGateway_RouteRequest
nfr_latency_p99_ms: 50
nfr_hw: "load_balancer"
nfr_env_dev:  '{"mock": true, "latency_p99_ms": null, "mode": "local"}'
nfr_env_prod: '{"mock": false, "latency_p99_ms": 50, "lb": "nginx", "workers": 8}'
```

Dev는 latency 완화, Prod 50ms p99 강제. Deploy 전 load testing 필수.

---

## 검증 query

```cypher
-- V-ST-NFR-1: nfr_env_prod 누락 (prod 환경 가정 위반)
MATCH (ct:AptContract) WHERE ct.status IN ['Active','Fulfilled']
WHERE ct.nfr_env_prod IS NULL AND ct.nfr_latency_p99_ms IS NOT NULL
RETURN 'V_ST_NFR_NoProdVariant' AS validation, ct.name AS contract

-- V-ST-NFR-2: dev 환경 값이 prod보다 엄격 (anomaly)
MATCH (ct:AptContract)
WHERE ct.nfr_env_dev IS NOT NULL AND ct.nfr_env_prod IS NOT NULL
WITH ct,
     apoc.convert.fromJsonMap(ct.nfr_env_dev).latency_p99_ms AS dev_p99,
     apoc.convert.fromJsonMap(ct.nfr_env_prod).latency_p99_ms AS prod_p99
WHERE dev_p99 IS NOT NULL AND prod_p99 IS NOT NULL AND dev_p99 < prod_p99
RETURN 'V_ST_NFR_DevStricterThanProd' AS validation,
       ct.name, dev_p99, prod_p99
```

(주: apoc 의존 — Neo4j community edition에서는 application code parse.)

---

## anti-pattern

### E-ST-NFR-1: 단일 NFR 값만 (환경 변형 누락)
**Context:** `nfr_latency_p99_ms: 200` 만 설정, env 변형 없음. dev 환경에서도 200ms 강제.
**Lesson:** dev는 mock/in-memory라 latency 의미 없음. prod만 강제해야 함.
**Guard:** ST가 NFR 설정 시 `nfr_env_{dev,prod}` 분리 의무화. 단일 값은 fallback (env 미지정 시).

### E-ST-NFR-2: prod 변형 누락
**Context:** dev 변형만 있고 prod 변형 없음. prod 배포 시 NFR 미강제.
**Lesson:** prod 환경이 가장 중요. dev만 있으면 운영 시 사고.
**Guard:** V-ST-NFR-1 cypher가 차단.

# KG: APT_ST_NFR_EnvVariants_canonical
