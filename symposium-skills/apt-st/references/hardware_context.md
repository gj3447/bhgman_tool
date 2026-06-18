# Hardware Context Layer (Phase-Specific)

> Contract가 의존하는 *물리적 자원*을 `:HardwareContext` 노드로 분리. mock 가능성 / criticality 명시.

---

## HardwareContext 노드 스키마

| Property | Type | Required | Description |
|----------|------|:--------:|-------------|
| `name` | string | yes | `HW_{manufacturer}_{model_short}` |
| `type` | string | yes | `camera`, `gpu`, `sensor`, `actuator`, `network` |
| `manufacturer` | string | no | `NVIDIA`, `Intel`, `AWS` |
| `model` | string | yes | `NVIDIA A100 80GB`, `Intel Xeon 8380` |
| `constraints` | string | no | Known limitations |
| `sdk_version` | string | no | Required SDK/driver version |
| `interface` | string | no | `USB3`, `GigE`, `PCIe`, `EtherCAT` |
| `created_at` | datetime | yes | Creation timestamp |

---

## 예시: NVIDIA GPU

```cypher
MERGE (hw:HardwareContext {name: 'HW_NVIDIA_A100'})
SET hw.type = 'gpu', hw.manufacturer = 'NVIDIA',
    hw.model = 'NVIDIA A100 80GB SXM',
    hw.constraints = 'CUDA 12.0+ required. TDP 400W.',
    hw.sdk_version = 'CUDA 12.0, cuDNN 8.9, TensorRT 8.6',
    hw.interface = 'PCIe Gen4 x16',
    hw.created_at = datetime()
```

## 예시: Robot Arm (UR10e)

```cypher
MERGE (hw:HardwareContext {name: 'HW_UR10e'})
SET hw.type = 'actuator', hw.manufacturer = 'Universal Robots',
    hw.model = 'UR10e',
    hw.constraints = 'Payload max 12.5kg. Reach 1300mm. RTDE 125Hz.',
    hw.sdk_version = 'ur_rtde 1.5+',
    hw.interface = 'EtherCAT',
    hw.created_at = datetime()
```

---

## REQUIRES_HARDWARE 패턴

### Mandatory (fallback 없음)

```cypher
MATCH (ct:AptContract {name: 'CT_Payment_Process'})
MATCH (hw:HardwareContext {name: 'HW_HSM_Thales'})
MERGE (ct)-[:REQUIRES_HARDWARE {criticality:'mandatory', note:'Encryption keys stored in HSM'}]->(hw)
```

### 다중 의존

```cypher
MATCH (ct:AptContract {name: 'CT_MLPipeline_Train'})
MATCH (hw_gpu:HardwareContext {name: 'HW_NVIDIA_A100'})
MATCH (hw_storage:HardwareContext {name: 'HW_NFS_Storage'})
MERGE (ct)-[:REQUIRES_HARDWARE {criticality:'mandatory', note:'GPU for training'}]->(hw_gpu)
MERGE (ct)-[:REQUIRES_HARDWARE {criticality:'mandatory', note:'NFS for dataset'}]->(hw_storage)
```

### Optional (fallback 있음)

```cypher
MATCH (ct:AptContract {name: 'CT_Search_MLRanking'})
MATCH (hw:HardwareContext {name: 'HW_NVIDIA_A100'})
MERGE (ct)-[:REQUIRES_HARDWARE {criticality:'optional', note:'GPU 10x speedup, CPU fallback'}]->(hw)
```

### Test-only

```cypher
MATCH (ct:AptContract {name: 'CT_UserProfile_Create'})
MATCH (hw:HardwareContext {name: 'HW_PostgreSQL_Cluster'})
MERGE (ct)-[:REQUIRES_HARDWARE {criticality:'test_only', note:'Unit tests use in-memory DB'}]->(hw)
```

---

## Ports-and-Adapters Mock 전략

```
+------------------------------------+
| Contract: CT_UserProfile_Create    |
|  +-------------+                   |
|  | DBPort      | <-- abstract      |
|  +------+------+                   |
|    +----+-----+                    |
|    |          |                    |
|  PostgresAdapter  InMemoryAdapter  |
|  (prod)           (dev/test)       |
+------------------------------------+
```

### Rules

1. Hardware SDK 호출은 Adapter 구현 (Port 인터페이스 따름)
2. Business logic은 Port에만 의존, Adapter 직접 의존 금지
3. Dev: MockAdapter 합성 데이터 (Port 타입 일치)
4. Prod: 실 Adapter 주입, NFR assertion 강제
5. 통합 테스트: 실 Adapter. 단위 테스트: Mock.

### Mock NOT 가능한 경우

- 하드웨어 *동작 자체가 로직*인 경우 (calibration accuracy)
- 타이밍 민감 (real-time control loops, jitter)
- → HIL (Hardware-in-the-Loop) 테스트 필수

---

## 검증 query

```cypher
-- V-ST-HW-1: mandatory HW 없는 nfr_hw 명시
MATCH (ct:AptContract) WHERE ct.nfr_hw IS NOT NULL
OPTIONAL MATCH (ct)-[:REQUIRES_HARDWARE]->(hw)
WITH ct, count(hw) AS hw_count
WHERE hw_count = 0
RETURN 'V_ST_HW_NoLink' AS validation, ct.name AS contract, ct.nfr_hw AS declared_hw

-- V-ST-HW-2: criticality 누락
MATCH (ct:AptContract)-[r:REQUIRES_HARDWARE]->(hw)
WHERE r.criticality IS NULL
RETURN 'V_ST_HW_NoCriticality' AS validation, ct.name, hw.name
```

# KG: APT_ST_HardwareContext_canonical
