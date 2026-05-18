# MetaReview Protocol — 4 단계 (Phase-Specific)

> apt-meta-review의 실제 실행 절차. SCW 완료 후 또는 사용자 의심 발화 시 진입. *self-application 금지* (max_depth=1, delta=0).

---

## 4 단계

```
1. Lesson 생성 (의심 → 명시화)
2. SKILL.md 패치 (lesson → 코드)
3. MATERIALIZES 갱신 (Contract/Span 상태 sync)
4. Naesengmoon Gate (외부 검증)
```

---

## 단계 1: Lesson 생성

[_common/error_pattern_template.md](../../_common/error_pattern_template.md) 의 Context/Lesson/Guard 3절 양식 강제.

```cypher
MERGE (l:Lesson {name:'lesson-'+$short_name+'-'+$date})
SET l.status = 'open',
    l.severity = $severity,                      -- P1-P4
    l.wrongAssumption = $assumed,                -- 무엇을 잘못 가정했나
    l.truth = $actual,                           -- 실제로 무엇이었나
    l.context = $context,                        -- 발견 시나리오
    l.guard = $guard,                            -- 재발 방지 메커니즘
    l.discoveryType = $discovery_type,           -- 6 PH6 discovery types
    l.category = $category,                      -- 10 PH6 categories
    l.target_skill = $skill_name,                -- 어느 SKILL.md 영향
    l.auto_resolve = false,                      -- 절대 auto_resolve 금지
    l.created_at = datetime(),
    l.created_by = $agent
WITH l
MATCH (cycle:AptCycle {name:$cycle_id})
MERGE (l)-[:DISCOVERED_IN]->(cycle)
```

**원칙**: Lesson은 *항상 resolved=false*로 시작. auto_resolve = SET resolved=true 시도 → silent acceptance = AP4 Silent Patch.

---

## 단계 2: SKILL.md 패치

[v26 A6 Resolve-Only](../SKILL.md) 원칙:

- prose hardcoding 금지
- magic number 본문 박지 말고 KG slot resolve (`{{cfg.X}}`)
- LensSet 갱신은 KG `:LensSet` 노드 추가/수정, SKILL.md 본문 lens 개수 직접 인용 금지

패치 cypher 의례:

```cypher
// 1. 패치 대상 slot 존재 확인
MATCH (slot:MethodologySlot) WHERE slot.name = $slot_name
RETURN slot.name, slot.currentConcrete

// 2. SKILL.md 파일 패치 (filesystem write)
// → 실제 edit은 git 위에서 (자동 push로 dgx 자동 sync)

// 3. SkillVersion bump
MERGE (sv:SkillVersion {name:'sv-'+$skill+'-v'+$new_version+'-'+$date})
SET sv.skill = $skill,
    sv.version = $new_version,
    sv.changes = $changelog,
    sv.released_at = datetime()
WITH sv
MATCH (l:Lesson {name:$lesson_name})
MERGE (sv)-[:RESOLVES]->(l)
```

---

## 단계 3: MATERIALIZES 갱신

```cypher
// SKILL.md 패치 후 영향받는 Contract / Span 상태 sync
MATCH (l:Lesson {name:$lesson_name})
OPTIONAL MATCH (l)-[:DISCOVERED_IN]->(:AptCycle)<-[:EXECUTED_IN]-(ct:AptContract)
WITH l, collect(ct) AS affected_contracts
FOREACH (ct IN affected_contracts |
  SET ct.materialization_status = 'requires_resync',
      ct.resync_reason = l.name,
      ct.resync_triggered_at = datetime()
)
RETURN l.name, size(affected_contracts) AS contracts_to_resync
```

영향 Contract들이 `materialization_status='requires_resync'` 로 표시 → 다음 사이클에서 SCW가 인지하고 재구현.

---

## 단계 4: Naesengmoon Gate

self-review 금지. **외부 Naesengmoon이 검증**:

```cypher
// Naesengmoon dispatch (subagent)
MERGE (taskspec:SubagentTaskSpec {name:'TS_metareview_taliban_gate_'+$lesson_name})
SET taskspec.target = $lesson_name,
    taskspec.lens_set = 'constitutional',
    taskspec.executor = 'subagent-taliban',
    taskspec.dispatched_at = datetime()
```

Naesengmoon 결과:
- `APPROVED`: Lesson 정당 + SKILL.md 패치 적절 → Lesson status='resolved'
- `REJECTED`: 다시 단계 1로 (lesson refinement)
- `NEEDS_REVIEW`: 인간 위임

---

## Self-application Forbidden

apt-meta-review가 자기 자신을 review하려 하면 무한 루프:

```cypher
// 차단 cypher (MetaReview 진입 직전 검증)
MATCH (current_cycle:AptCycle {name:$cycle_id, phase:'MetaReview'})
OPTIONAL MATCH (current_cycle)-[:PARENT]->(parent_cycle:AptCycle {phase:'MetaReview'})
WITH current_cycle, parent_cycle
WHERE parent_cycle IS NOT NULL
RETURN 'E_MR_SelfApplication' AS error,
       current_cycle.name AS attempted,
       parent_cycle.name AS already_in_metareview
// 결과 있으면 즉시 차단
```

`max_depth=1, delta=0` invariant. 위반 시 cycle abort.

---

## anti-pattern

### E-MR-1: Lesson auto_resolve
**Context:** Lesson 생성 후 즉시 `SET resolved=true`.
**Lesson:** silent acceptance = AP4. 외부 검증 (Naesengmoon) 없이 자기 해결.
**Guard:** Lesson 생성 cypher가 `auto_resolve=false` 명시. Naesengmoon APPROVED만 status='resolved' 허용.

### E-MR-2: Self-application
**Context:** MetaReview가 자기 자신을 review 호출.
**Lesson:** 무한 루프. max_depth=1 violation.
**Guard:** E_MR_SelfApplication 차단 cypher.

### E-MR-3: SkillVersion bump 없음
**Context:** SKILL.md 패치만, SkillVersion 노드 생성 안 함.
**Lesson:** 진화 history 추적 불가. git commit만으로 KG와 sync 안 됨.
**Guard:** 단계 2 의례에 SkillVersion mandatory.

# KG: APT_MR_Protocol_canonical, lesson-apt-skill-drift-audit-2026-04-17
