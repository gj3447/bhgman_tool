# TA World Reference

> TPA v1.1 TA Phase 상세 (terminal). Mirror sibling: `apt-sa/references/sa_world.md` (forward direction — anchor bootstrap).
> TPA의 *마지막* phase. 복원된 design을 우리 KG의 `:SemanticAnchor`에 안착시키고 5-drift를 측정한다.

---

## 1. Phase Identity

**TA = TargetAnchor** — TPA 사이클의 종착점. 추출된 Contract + Pattern 집합을 우리 KG의 SemanticAnchor 라우팅에 결정화하고, 5종 drift로 *recovery faithfulness*를 정량화한다.

| 질문 | 답 |
|------|----|
| pre-gate | SP VR APPROVED via Hook |
| post-gate | Final Naesengmoon 9-lens VR + 5-drift 측정 + Lesson Feedback Loop fires |
| 결정 | 2-A 신규 anchor / 2-B 기존 reuse / 2-C 분기(branch) |
| 종료 조건 | coverage_ratio ≥ 0.8 OR anchor.status='SUSPENDED' |

---

## 2. SemanticAnchor 라우팅 결정 트리

```
                  SP Result + 추출된 Contract/Pattern
                              │
                  기존 SemanticAnchor 검색
                  (cosine similarity on Contract names + Pattern set)
                              │
                  ┌───────────┼───────────┐
              overlap < 0.4   0.4 ~ 0.85   > 0.85
                  │             │             │
              2-A NEW       2-C BRANCH     2-B REUSE
                  │             │             │
              새 SemanticAnchor  기존 SA 분기  기존 SA 흡수
              생성             + SUPERSEDES   (속성 갱신)
                              edge
```

`overlap` 계산:
```cypher
MATCH (existing:SemanticAnchor {status: 'active'})
MATCH (sp:TPA_SP_Result {name: $sp_name})-[:RECOVERS_CONTRACT]->(c)
WITH existing, sp, count(DISTINCT c) AS sp_count
OPTIONAL MATCH (existing)-[:HAS_CONTRACT]->(ec)
WITH existing, sp, sp_count, count(DISTINCT ec) AS existing_count,
     [(existing)-[:HAS_CONTRACT]->(ec2) WHERE ec2.name IN [(sp)-[:RECOVERS_CONTRACT]->(c2) | c2.name] | ec2] AS shared
WITH existing, size(shared) * 2.0 / (sp_count + existing_count) AS overlap_score
RETURN existing.name, overlap_score ORDER BY overlap_score DESC LIMIT 5
```

---

## 3. 5-Drift 측정 (Recovery Faithfulness)

| Drift kind | 의미 | 검출 query |
|------------|------|-----------|
| **Missing** | KG 노드가 더 이상 코드에 없는 파일/심볼 참조 | `MATCH (n) WHERE n.sourcePath IS NOT NULL AND NOT exists_on_disk(n.sourcePath) RETURN n` |
| **Orphan** | 코드 심볼이 매칭 KG Contract 없음 | TCW manifest - 모든 Contract.sourcePath 차집합 |
| **SigMismatch** | 코드 시그니처가 복원 Contract 와 다름 | parser_signature != contract.protocol |
| **PatternDiv** | 패턴이 시간에 따라 변화 (예: State → Strategy 마이그레이션) | 동일 sym 의 INSTANCE_OF 패턴이 이전 vs 현재 다름 |
| **LabelRot** | KG 라벨/관계가 현 컨벤션 drift | label_audit ≠ canonical_label_set |

```cypher
MERGE (drift:DriftReport:AbstractNode {name: 'DR_' + $target_id + '_' + $date})
SET drift.missing = $missing_n,
    drift.orphan = $orphan_n,
    drift.sigmismatch = $sig_n,
    drift.patterndiv = $patt_n,
    drift.labelrot = $label_n,
    drift.total_recovered = $total,
    drift.coverage_ratio = (1.0 * ($total - ($missing_n + $orphan_n + $sig_n + $patt_n + $label_n)) / $total),
    drift.measured_at = datetime()
MERGE (exec:TPA_Execution)-[:HAS_DRIFT_REPORT]->(drift)
```

---

## 4. Coverage Threshold Enforcement

`tpa_drift_coverage_ratio_min` (default 0.8) — `MethodologyConfig_default_v26` slot.

```cypher
MATCH (drift:DriftReport {name: $drift_name})
WITH drift, drift.coverage_ratio AS ratio
MATCH (cfg:MethodologyConfig {name: 'MethodologyConfig_default_v26'})
WITH drift, ratio, cfg.tpa_drift_coverage_ratio_min AS threshold
MATCH (sa:SemanticAnchor) WHERE (drift)<-[:HAS_DRIFT_REPORT]-(:TPA_Execution)-[:ANCHORS_TO]->(sa)
SET sa.status = CASE WHEN ratio < threshold THEN 'SUSPENDED' ELSE sa.status END,
    sa.suspension_reason = CASE WHEN ratio < threshold THEN 'TPA TA coverage_ratio ' + toString(ratio) + ' < ' + toString(threshold) ELSE sa.suspension_reason END,
    sa.suspended_at = CASE WHEN ratio < threshold THEN datetime() ELSE sa.suspended_at END
RETURN sa.name, sa.status
```

---

## 5. Override Mechanism (사용자 verdict)

`coverage_ratio < 0.8` 인데 사용자가 명시적으로 accept 하는 경우:

```cypher
CREATE (ol:TpaDecisionLog {
  id: randomUUID(),
  gate_type: 'TA_Gate',
  exec_name: $exec,
  decision: 'OVERRIDE',
  decided_by: 'human',
  decided_at: datetime(),
  override_reason: $human_reason,                     // 반드시 사람이 제공 — agent 생성 금지
  overridden_rule: 'tpa_drift_coverage_ratio_min',
  original_coverage_ratio: $actual_ratio,
  policy_threshold: 0.8
})
```

`override_reason` 누락 OR agent-generated → TR_CoverageOverride 위반.

---

## 6. 최종 Longinus 바인딩 (TR12) — Reverse Orphan Scan

ST에서 만든 ReferenceSite 외에, *코드 심볼 → KG 노드* 역방향 매핑 audit:

```cypher
// 1. 모든 CodeSymbol 가져옴
MATCH (sym:CodeSymbol {recovered_from_execution: $exec})
// 2. KG 어딘가에 매핑 노드가 있는지
OPTIONAL MATCH (n {sourcePath: sym.file + ':' + toString(sym.line)})
// 3. 매핑 없으면 ReverseOrphan
WITH sym, n
WHERE n IS NULL
MERGE (ro:ReverseOrphan:AbstractNode {name: 'RO_' + sym.name})
SET ro.code_symbol = sym.name,
    ro.sourcePath = sym.file + ':' + toString(sym.line),
    ro.detected_in_execution = $exec,
    ro.detected_at = datetime()
RETURN count(ro) AS reverse_orphan_count
```

ReverseOrphan은 *Lesson 후보* — TPA recovery 가 놓친 영역.

---

## 7. Lesson Feedback Loop 발동 (Cycle Terminal)

TA 종료 시 *모든 발견*을 :Lesson 으로 결정화하고 ActionPlan 후보 생성.

```cypher
// 모든 QualityGap → Lesson + ActionPlan 후보
MATCH (gap:QualityGap)<-[:IDENTIFIES]-(:TPA_Execution {name: $exec})
MERGE (l:Lesson:AbstractNode {name: 'lesson-tpa-' + gap.dimension + '-' + $target_id})
SET l.scope = 'tpa-cross-project',
    l.problem = gap.dimension + ': source=' + gap.source_level + ', target=' + gap.target_level,
    l.wrongAssumption = '우리 프로젝트의 ' + gap.dimension + ' 수준이 외부 ' + $target + ' 와 동등',
    l.truth = '실제 비교 결과 source_level=' + gap.source_level + ' vs target_level=' + gap.target_level,
    l.howToApply = gap.improvement_action,
    l.severity = $severity,
    l.resolved = false,
    l.created_at = datetime()
WITH l, gap
MERGE (gap)-[:TRIGGERS]->(l)
WITH l
MATCH (fl:FeedbackLoopOntology {name: 'agent-feedback-loop-canonical-2026-04-27'})
MERGE (l)-[:INSTANCE_OF_FEEDBACK_LOOP]->(fl)

// 우선순위 HIGH인 Lesson은 자동 ActionPlan 생성
MATCH (l:Lesson) WHERE l.severity = 'HIGH' AND l.resolved = false
  AND NOT EXISTS { MATCH (l)-[:TRIGGERS]->(:ActionPlan) }
MERGE (p:ActionPlan {name: 'AP-AUTO-' + l.name})
SET p.priority = 'HIGH',
    p.target_skill = 'apt-scw',
    p.improvements = [l.howToApply],
    p.auto_generated = true,
    p.created_at = datetime()
MERGE (l)-[:TRIGGERS]->(p)
```

---

## 8. TPA_TA_Result 결정화

```cypher
MERGE (ta:TPA_TA_Result:AbstractNode {name: 'TA_' + $target_id + '_' + $date})
SET ta.sourcePath = $target,
    ta.routing_decision = $routing,            // '2-A new' | '2-B reuse' | '2-C branch'
    ta.semantic_anchor_name = $anchor,
    ta.coverage_ratio = $ratio,
    ta.drift_missing = $missing_n,
    ta.drift_orphan = $orphan_n,
    ta.drift_sigmismatch = $sig_n,
    ta.drift_patterndiv = $patt_n,
    ta.drift_labelrot = $label_n,
    ta.reverse_orphan_count = $ro_n,
    ta.lesson_count = $lessons_n,
    ta.action_plan_count = $aps_n,
    ta.anchor_suspended = (ta.coverage_ratio < 0.8),
    ta.created_at = datetime()
MERGE (exec)-[:PHASE_OUTPUT {order:4}]->(ta)
MERGE (ta)-[:ANCHORS_TO]->(:SemanticAnchor {name: $anchor})
```

---

## 9. FulfillmentGate TA (7 checks)

1. [ ] SemanticAnchor 라우팅 결정 (`2-A` / `2-B` / `2-C`) 명시
2. [ ] 5-drift 모든 종류 측정값 존재 (5개 필드 모두 not null)
3. [ ] coverage_ratio 계산 + threshold 검사
4. [ ] coverage < 0.8 → anchor.status = 'SUSPENDED' 자동 SET (V9)
5. [ ] 모든 Contract Longinus ReferenceSite 보유 (TR12)
6. [ ] ReverseOrphan 카운트 기록 (0 이상)
7. [ ] Lesson Feedback Loop 발동 (≥ 1 :Lesson 또는 명시적 "no discovery" 기록)

---

## 10. Final Naesengmoon 9-lens

Critic 입력:
- routing_decision (2-A / 2-B / 2-C 합리성)
- 5-drift 분포 (편향된 drift kind 의심)
- coverage_ratio (threshold 근접 시 false positive 의심)
- ReverseOrphan 분포 (큰 cluster = 새 영역 발견)
- Lesson 카테고리 분포 (모두 한 종류 = recovery 다양성 부족)

```cypher
MERGE (vr:ValidationResult {name:'VR_TPA_TA_'+$target+'_'+$date, phase:'TA'})
SET vr.verdict = $verdict,
    vr.evidence = [...],                         // routing, drift_table, lesson_summary
    vr.validator = 'Naesengmoon-9lens',
    vr.provenance = 'subagent-taliban-ta',
    vr.validated_at = datetime()
MATCH (exec) MERGE (exec)-[:HAS_VALIDATION]->(vr)
SET exec.status = CASE $verdict
    WHEN 'APPROVED' THEN 'COMPLETE'
    ELSE 'BLOCKED_AT_TA'
  END
```

---

## 11. Common Failure Modes

| 증상 | 원인 | 처방 |
|------|------|------|
| `routing_decision` 모호 (overlap 0.4~0.85) | 임계값 ambiguous | sigma_oracle escalate, 2-C branch가 default safe |
| 5-drift 모든 kind = 0 | drift detector 미작동 (V10 violation) | references/error_handling.md, lesson 생성 |
| coverage_ratio < 0.5 | 큰 recovery loss | TR14 chunk 재조정, parallel.max_agents ↑ |
| ReverseOrphan 폭증 | TCW 단계 manifest 누락 | TCW phase로 회귀 (TR3 phase order 거꾸로 OK in audit mode) |
| Lesson count = 0 | 추출 단계에서 *no discovery* 안 일어남 | 의심 — escalated Naesengmoon prompt 재호출 |

---

## 12. References

- `../tpa/references/phases.md` §4
- `../tpa/references/error_handling.md` §5 (coverage threshold), §9 (Lesson stall)
- `../tpa/references/validation.md` V9 (suspension), V10 (drift kinds), V11 (binding), V12-V14 (Lesson)
- `../tpa/references/kg_logging.md` §3-4 (Lesson + ActionPlan)
- `../apt-sa/references/sa_world.md` (mirror — forward direction, anchor bootstrap)

# KG: ATOM_Skill_tpa_ta, fw-tpa-references-apt-parity-2026-05-06
