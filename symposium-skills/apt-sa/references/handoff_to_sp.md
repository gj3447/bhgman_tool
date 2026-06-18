# SA → SP Handoff Checklist (Phase-Specific)

> SA 완료 후 SP 진입 *직전* 검증. 모든 항목 PASS만 핸드오프 가능. 일반적 압축 규약은 [_common/phase_transition_compaction.md](../../_common/phase_transition_compaction.md).

---

## 8 항목 체크리스트

| # | 체크 항목 | 검증 방법 |
|---|----------|----------|
| 1 | SemanticAnchor가 KG에 존재 | `MATCH (sa:SemanticAnchor {name: $sa}) RETURN sa` |
| 2 | SA status = 'active' | `sa.status = 'active'` 확인 |
| 3 | Root Span이 SA에 연결됨 | `MATCH (sa)-[:HAS_ROOT]->(root) RETURN root` |
| 4 | Progressive Disclosure L1 로드됨 | apt-progress.md에 L1 Span 목록 기재 확인 |
| 5 | Context Budget 할당됨 | `sa.context_budget_total IS NOT NULL` |
| 6 | apt-progress.md 생성됨 | 파일 존재 확인 |
| 7 | 기존 앵커 중복 없음 | KG 탐색으로 유사 앵커 부재 확인 |
| 8 | Git commit 완료 | `apt-progress.md` 커밋됨 |

### v27 A15 추가 항목

| # | 체크 항목 | 검증 방법 |
|---|----------|----------|
| 9 | Work Kind 분류 기록됨 | `sa.created_via_work_kind IS NOT NULL` (V-SA5) |
| 10 | Phase Activation Matrix mode 결정됨 | `sa.phase_activation_mode IN ['FULL','SHORT_CIRCUIT','SKIP_TO_ST_DRIFT']` |
| 11 | (MAINTENANCE인 경우) SP 우회 마커 | `sa.bypass_sp_to_st_drift = true` — 다음 phase가 SP 진입 *안* 함을 명시 |

---

## 검증 cypher (10 항목 일괄)

```cypher
// SA → SP handoff readiness gate
MATCH (sa:SemanticAnchor {name: $sa_name})
OPTIONAL MATCH (sa)-[:HAS_ROOT]->(root)
WITH sa, root,
     CASE WHEN sa IS NULL                                            THEN false ELSE true END AS c1_exists,
     CASE WHEN sa.status = 'active'                                  THEN true ELSE false END AS c2_active,
     CASE WHEN root IS NOT NULL                                       THEN true ELSE false END AS c3_root,
     CASE WHEN sa.context_budget_total IS NOT NULL                   THEN true ELSE false END AS c5_budget,
     CASE WHEN sa.created_via_work_kind IS NOT NULL                  THEN true ELSE false END AS c9_workkind,
     CASE WHEN sa.phase_activation_mode IN
              ['FULL','SHORT_CIRCUIT','SKIP_TO_ST_DRIFT']             THEN true ELSE false END AS c10_mode
RETURN sa.name AS anchor,
       c1_exists, c2_active, c3_root, c5_budget, c9_workkind, c10_mode,
       (c1_exists AND c2_active AND c3_root AND c5_budget AND c9_workkind AND c10_mode) AS handoff_ready
```

`handoff_ready = false` → SP 진입 차단. 어떤 컬럼이 false인지 확인 후 SA로 복귀하여 누락 채움.

---

## Phase Transition Compaction (SA → SP 적용)

[_common/phase_transition_compaction.md](../../_common/phase_transition_compaction.md) 의 SA → SP 표:

| 보존 | 제거 |
|---|---|
| 앵커 이름, 설명, domain, status | KG 탐색 과정 (Step 1 cypher 결과) |
| L1 Span 목록 (name + description) | 후보 앵커 비교 표 |
| Context Budget 할당 결과 | A15 work_kind 분류 추론 과정 |
| 라우팅 결정 (NEW/EXTEND/MAINTENANCE + Matrix mode) | 폐기된 앵커 라우팅 후보 |

압축 결과 = PhaseHandoff_SA_to_SP Kafka 이벤트 payload 입력.

```json
{
  "event_type": "PhaseHandoff_SA_to_SP",
  "agent": "agent_sa_01",
  "payload": {
    "anchor": "SA_xxx",
    "work_kind": "NEW",
    "phase_activation_matrix_a15": "FULL",
    "l1_spans_count": 4,
    "context_budget_total": 100000,
    "next_phase": "apt-sp",
    "compacted_at": "2026-05-11T14:00:00Z"
  }
}
```

이벤트 형식 자세히는 [_common/kafka_event_convention.md](../../_common/kafka_event_convention.md).

---

## MAINTENANCE 특수 처리

work_kind=MAINTENANCE이면 **SP 자체 건너뛰고 ST drift detection 모드 직행**. 핸드오프 대상이 apt-sp가 아닌 apt-st.

체크리스트 항목 1, 2, 3, 9, 10, 11만 검증. 다음:
- skip: 4 (L1 Span 목록 — drift 모드는 기존 트리 재사용), 7 (앵커 중복 — MAINTENANCE는 본질적으로 기존 앵커 재사용)
- handoff event: `PhaseHandoff_SA_to_ST_DRIFT` (특수 변형)

```json
{
  "event_type": "PhaseHandoff_SA_to_ST_DRIFT",
  "payload": {
    "anchor": "SA_xxx",
    "work_kind": "MAINTENANCE",
    "phase_activation_matrix_a15": "SKIP_TO_ST_DRIFT",
    "bypass_sp_reason": "maintenance — no decomposition needed, drift check only"
  }
}
```

---

## anti-pattern

### E-SA-Handoff-1: silent handoff
**Context:** SA → SP 전환 시 PhaseHandoff_SA_to_SP Kafka 이벤트 미발행.
**Lesson:** 다음 phase가 작업 시작 시점 추적 불가. PROV 깨짐.
**Guard:** 핸드오프 cypher가 동시에 Kafka producer call (`emit_phase_handoff()`).

### E-SA-Handoff-2: handoff_ready=false 무시
**Context:** 핸드오프 readiness gate에서 c5_budget=false인데도 SP 진입.
**Lesson:** SA의 모든 약속 (Context Budget, Root Span, Work Kind) 이 충족되어야 SP가 cold-start 가능.
**Guard:** SP SKILL.md 시작 시 SA handoff gate cypher 재실행, 한 컬럼이라도 false면 즉시 SA로 복귀.

### E-SA-Handoff-3: MAINTENANCE인데 SP 진입
**Context:** A15 분류는 MAINTENANCE인데 apt-sp 호출됨.
**Lesson:** A15 SHORT_CIRCUIT_BYPASS 무시 = magic number 적용 실패.
**Guard:** SP SKILL.md 시작 시 `sa.phase_activation_mode = 'SKIP_TO_ST_DRIFT'` 체크. 해당 시 즉시 apt-st drift mode로 위임.

# KG: APT_SA_handoff_canonical
