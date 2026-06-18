# prometheus — Error Handling

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## 1. KG Pre-fetch Failure (G1)

```
IF Neo4j unreachable:
  1. server-status skill 호출 (외부 진단)
  2. NEO4J_URL_OVERRIDE env 시도 (alternate endpoint)
  3. 여전히 fail → BLOCK + Lesson `lesson-prom-kg-unreachable`
  4. APT_GATE_ALLOW_NEO4J_DOWN=1 dev mode override 가능 (production 금지)
```

## 2. Axis Matrix Generation Fail (G2)

```
IF axis count < N OR sub_axis 분해 불가:
  1. topic 자체 reformulate 요청 (사용자 verdict)
  2. 또는 N 감소 (large → medium)
  3. axis 후보 web 탐색 (ResearchProvider 우선 호출)
  4. 여전히 fail → ABORT cycle + Lesson
```

## 3. Subagent Dispatch Truncation (G4 → G5)

```
IF intent_N > actual_N (GH#29181):
  1. 누락된 axis/sub_axis 식별
  2. 보충 dispatch (idempotent — 같은 seed_bundle 재사용)
  3. 재차 self-check
  4. 3 attempts 후에도 실패 → partial collection 인정 + sigma_oracle escalate
  5. PR_DispatchTruncation Lesson 자동 생성
```

## 4. Lakatos DEGENERATING Verdict (G6)

```
IF lakatos_verdict = DEGENERATING:
  1. 모든 finding 보관 (KG 결정화는 진행)
  2. 가설 자체 reformulate 후보 surface
  3. sigma_oracle: (a) 가설 폐기 (b) 추가 evidence dispatch (c) accept as-is
  4. Lesson `lesson-prom-degenerating-rescue` 생성
```

## 5. Filesystem Dispersion Drift (G6.5)

```
IF KG↔fs sha256 mismatch:
  1. file 측 마지막 수정 timestamp 확인
  2. KG 측 마지막 갱신 timestamp 확인
  3. newer 가 source-of-truth (default)
  4. 충돌 (둘 다 수정) → BX PutPut → sigma_oracle
  5. 자동 머지 회피 (위험)
```

## 6. UNWIND Batch Write ROLLBACK (G7)

```
IF Cypher syntax error OR cardinality mismatch:
  1. Transaction ROLLBACK 자동
  2. 실패 sub-batch 식별 (binary search)
  3. 재시도 (max 3 attempts)
  4. 영구 실패 → Lesson + sigma_oracle escalate
  5. KG state 는 롤백 전 상태 유지 (no partial commit)
```

## 7. Hot-Fix Latency-Critical Override (v6.1 exception)

```
IF cycle_purpose = 'hot-fix' AND latency_critical = true:
  1. KG-skip allowed (G1 + G6.5 skip)
  2. immediate action 수행
  3. POST-HOC 의무:
     a. Lesson `lesson-prom-hot-fix-skip-<cycle>` 생성
     b. Skipped invariants 재검증 plan
     c. Next cycle G1 에서 추가 audit
  4. justification missing → PR_KGSkipWithoutJustification (Lesson)
```

## 8. Common Failure Modes

| 증상 | 원인 | 처방 |
|------|------|------|
| 모든 axis 의 finding 가 동일 | dedup_hash 미생성 (PR_DedupSkipped) | G5 hash field 검증 강화 |
| critic verdict 항상 PROGRESSIVE | Lakatos test 미작동 | G6 4-criterion 강제 |
| dispersion drift 누적 | G6.5 skip 반복 | sha256 daemon 활성화 |
| Lesson resolved=false 누적 | ActionPlan 미연결 | TR10 mirror — 자동 ActionPlan 생성 |
| N=4 가 default 로 박힘 (PR_NUndersampling) | size_class 결정 누락 | MethodologyConfig.prometheus_N_default_* slot 사용 |

# KG: ATOM_Skill_prometheus, fw-prometheus-references-apt-parity-2026-05-06
