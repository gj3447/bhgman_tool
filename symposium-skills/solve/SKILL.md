---
name: solve
kg_ref: ATOM_Skill_solve
version: "2.0.0"
channel: stable
provenance: AI_DERIVED_FROM_USER_PRIMARY  # SKILL.md = AI engineering; underlying methodology = user-primary mythology (12 apostles + 5 weapons). Per PseudepigraphaValidationGate-v1-2026-04-30.
description: >
  오답노트 체계적 해결 사이클 — 문제 발견 → KG 기록 → 병렬 리서치 → KG 구축 → 계획 수립 → 실행 → 검증의 7단계.
  /solve <문제설명> 또는 /solve lesson-XXX로 호출.
  # KG: ATOM_Skill_solve, MIC_v1.ReasoningProtocol→KGFirstCheck_v1 (R1-R5 mandatory before any framing/diagnostic, lesson-ai-skipped-kg-check-before-framing-2026-04-29)
---

## 🔗 MIC Binding (SOLID-DIP)

**USES slots**: ResearchProvider (병렬 리서치), AdversarialValidator (검증), KgCodeBinder (코드 주석), SubagentSeeder

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
WHERE s.name IN ['ResearchProvider','AdversarialValidator','KgCodeBinder','SubagentSeeder']
RETURN s.name, s.currentConcrete, s.invocation
```

# KG: MIC_v1, lesson-apt-not-truly-jaebaeman-2026-04-14

---

# /solve — 오답노트 체계적 해결 사이클

문제를 발견하면 KG에 기록하고, 병렬 리서치로 해결책을 찾아 KG에 구축한 뒤, 계획을 세워 실행하고 검증하는 7단계 사이클.

**KG 방법론 노드**: `lesson-resolution-methodology`
**KG 온톨로지**: `lesson-resolution-ontology`

## 입력 형식

```
/solve <문제 설명>           # 새 문제 등록 + 해결
/solve lesson-XXX            # 기존 Lesson 해결
/solve --status              # 미해결 오답노트 현황
/solve --stress              # 스트레스 테스트 실행
```

## 7단계 사이클

### Step 1: 발견 → KG에 Lesson 즉시 기록

새 문제인 경우:
```cypher
-- 다음 lesson 번호 확인
MATCH (l:Lesson) WHERE l.name STARTS WITH 'lesson-'
RETURN l.name ORDER BY l.name DESC LIMIT 1

-- Lesson 생성
MERGE (l:AbstractNode:Lesson {name: 'lesson-XXX'})
SET l.category = '카테고리',
    l.problem = '문제 설명',
    l.wrongAssumption = '잘못된 가정',
    l.truth = '실제 진실 (아직 모르면 null)',
    l.solution = '해결법 (아직 모르면 null)',
    l.severity = 'CRITICAL/HIGH/MEDIUM/LOW',
    l.resolved = false,
    l.createdAt = datetime()
```

기존 Lesson인 경우:
```cypher
MATCH (l:Lesson {name: $lessonName})
RETURN l.problem, l.severity, l.resolved,
       [(l)-[:HAS_RESEARCH]->(r) | r.recommendation][0] as research,
       [(l)-[:HAS_PLAN]->(p) | p.action][0] as plan
```

### Step 2: 환경 조사 (해결 전 이해)

```bash
# 현재 클러스터 상태
kubectl get pods -A --no-headers | grep -v kube-system
kubectl get svc -A
docker ps --format "table {{.Names}}\t{{.Status}}"

# 문제 관련 로그
kubectl logs -n <ns> <pod> --tail=50
```

- 문제의 현재 영향도 판단
- 관련 설정 파일, 매니페스트 확인
- **해결 시도 전에 반드시 상태 파악**

### Step 3: haiku subagent 병렬 리서치

문제 도메인별로 haiku 에이전트를 분리하여 병렬 투입:

```
Agent(model=haiku, run_in_background=true) × N

에이전트 수 가이드:
- 단순 이슈 (1개 기술): 3~5개
- 복합 이슈 (여러 기술 교차): 6~10개
- 대규모 마이그레이션: 12~20개

각 에이전트 프롬프트에 반드시 포함:
1. Root cause 분석
2. 2025-2026 권장 해결법
3. 대안 2~3개
4. 설정 예제 / YAML / 명령어
5. 참고 링크
6. **WRITE_DEFERRED_TO_PARENT** clause (PROM 16 T3 2026-05-24 ship):
   "너는 KG 에 직접 write 할 수 없다. ResearchFinding / ActionPlan / Lesson MERGE 의도는
   `kg_write_intent_json` field 에 JSON 으로 반환만 한다. 실제 write 는 parent 가 Step 4
   (KG 리서치 구축) + Step 5 (ActionPlan 수립) 에서 수행. 금지 표현: `kg_writes_done=true` /
   'MERGE 완료' / 'lesson resolved 처리 완료' 류 claim. 위반 시 parent ReconciliationNode 발동."
   정전 anchor: `lesson-subagent-self-drift-kg-write-prom16-2026-05-24`.
```

> ⚠️ **Dispatch는 반드시 jaebaeman Phase 2 (single-message multi-call) 규약을 따른다** — N개 `Agent()` tool_use를 하나의 assistant message 안에 모두 emit. for-loop 분산 = sequential drift (GH#29181, `dispatch_pattern≠'single-message-multi-call'`). 정전: `SKILLS/jaebaeman/references/phases.md §Phase 2 L36-65`.
>
> # KG: finding-prom16-parallelism-bhgman-dep-D4 (GAP-1 patch, 2026-05-19)

### Step 4: KG에 리서치 결과 구축

```cypher
MATCH (l:Lesson {name: 'lesson-XXX'})

-- ResearchFinding 생성
MERGE (r:AbstractNode:ResearchFinding {name: 'research-XXX'})
SET r.rootCause = '근본 원인',
    r.recommendation = '권장 해결법',
    r.alternatives = ['대안1', '대안2'],
    r.benchmarks = '성능 데이터 (있으면)',
    r.documents = ['생성된 문서 경로'],
    r.deepResearch = true,
    r.status = 'RESEARCHED',
    r.researchedAt = datetime()
MERGE (l)-[:HAS_RESEARCH]->(r)

-- Benchmark 노드 (성능 데이터가 있으면)
MERGE (b:AbstractNode:Benchmark {name: 'bench-XXX'})
SET b.category = '카테고리', b.metrics = ['메트릭1', '메트릭2']
MERGE (r)-[:HAS_BENCHMARK]->(b)
```

### Step 5: ActionPlan 수립 (계획 없이 실행 금지)

```cypher
MATCH (l:Lesson {name: 'lesson-XXX'})
MERGE (p:AbstractNode:ActionPlan {name: 'plan-XXX'})
SET p.phase = 'ACTION/FUTURE/MAINTAIN/DONE',
    p.priority = 'HIGH/MEDIUM/LOW/RESOLVED',
    p.action = '구체적 실행 방법 (명령어 포함)',
    p.dependencies = ['선행 조건들'],
    p.estimatedEffort = '예상 소요 시간',
    p.createdAt = datetime()
MERGE (l)-[:HAS_PLAN]->(p)

-- MigrationPhase 연결 (해당시)
MATCH (phase:MigrationPhase {name: 'phase-X-xxx'})
MERGE (phase)-[:RESOLVES]->(l)

-- TechnologyDecision 연결 (해당시)
MATCH (td:TechnologyDecision {name: 'decision-xxx'})
MERGE (td)-[:SOLVES]->(l)

-- ResolutionDomain 연결
MATCH (dom:ResolutionDomain {name: 'domain-xxx'})
MERGE (l)-[:BELONGS_TO_DOMAIN]->(dom)
```

### Step 6: 실행 + KG 업데이트

계획대로 실행하고, 완료 후:

```cypher
-- resolved 처리
MATCH (l:Lesson {name: 'lesson-XXX'})
SET l.resolved = true, l.resolvedAt = datetime(),
    l.resolvedBy = '해결 방법 설명'

-- ActionPlan phase 업데이트
MATCH (p:ActionPlan {name: 'plan-XXX'})
SET p.phase = 'DONE'

-- ResearchFinding에 적용된 수정 기록
MATCH (r:ResearchFinding {name: 'research-XXX'})
SET r.appliedFix = '실제 적용한 수정 내용'
```

### Step 7: 검증 (4단계)

```bash
# 1. 내부 테스트
kubectl get pods -A | grep -v Running
curl -s -o /dev/null -w "%{http_code}" http://localhost/<service>/

# 2. DB 연결 테스트
kubectl exec -n data neo4j-0 -- cypher-shell -u neo4j -p neo4jpassword "RETURN 1"
kubectl exec -n data postgresql-0 -- psql -U postgres -d maindb -c "SELECT 1"
kubectl exec -n data redis-0 -- redis-cli -a redispassword PING
kubectl exec -n data mongodb-0 -- mongosh --quiet -u mongo -p mongopassword --eval "db.runCommand({ping:1})"

# 3. 스트레스 테스트 (hey)
hey -z 10s -c 100 http://localhost/<target>/

# 4. 외부 테스트 (check-host.net)
rid=$(curl -s "https://check-host.net/check-http?host=http://bhgman.iptime.org/<path>/&max_nodes=5" \
  -H "Accept: application/json" | python3 -c "import json,sys; print(json.load(sys.stdin)['request_id'])")
sleep 10
curl -s "https://check-host.net/check-result/$rid" -H "Accept: application/json"
```

검증 결과를 KG에 기록:
```cypher
MERGE (st:AbstractNode:StressTestResult {name: 'stress-test-YYYY-MM-DD'})
SET st.testedAt = datetime(), st.results = [...], st.verdict = 'PASS/FAIL'
MATCH (m:Methodology {name: 'lesson-resolution-methodology'})
MERGE (m)-[:PRODUCED]->(st)
```

## /solve --status 실행시

```cypher
-- 미해결 오답노트
MATCH (l:Lesson) WHERE l.resolved IS NULL OR l.resolved = false
OPTIONAL MATCH (l)-[:HAS_PLAN]->(p:ActionPlan)
RETURN l.name, l.severity, l.problem, p.phase, p.priority
ORDER BY l.severity

-- Phase별 진행 현황
MATCH (p:MigrationPhase)
OPTIONAL MATCH (p)-[:RESOLVES]->(l:Lesson)
WITH p.displayName as phase, p.status as status,
     count(l) as total, sum(CASE WHEN l.resolved = true THEN 1 ELSE 0 END) as done
RETURN phase, status, done + '/' + total as progress
ORDER BY phase
```

## /solve --stress 실행시

4단계 검증 전체 실행:
1. Pod 상태 확인 (kubectl get pods -A)
2. DB 4개 연결 테스트
3. hey 부하 테스트 (Traefik, 주요 서비스)
4. check-host.net 글로벌 테스트
5. Pod 삭제 복원력 테스트
6. 결과 KG StressTestResult에 기록

## 핵심 원칙

1. **해결 전 이해** — 환경 조사 없이 해결 시도 금지
2. **계획 먼저** — ActionPlan 없이 실행 금지
3. **KG가 진실의 원천** — 모든 발견, 리서치, 계획, 실행 결과는 KG에
4. **병렬 리서치** — haiku 에이전트로 비용 효율적 대량 검색
5. **검증 필수** — 내부/외부/스트레스/KG정합성 4단계

## KG 온톨로지 구조

```
LessonResolutionOntology
├── HAS_DOMAIN → ResolutionDomain (4개)
│   └── BELONGS_TO_DOMAIN ← Lesson, DocumentRef
├── HAS_PHASE → MigrationPhase (Phase 0→1→2→3)
│   └── RESOLVES → Lesson
├── HAS_DECISION → TechnologyDecision (9개)
│   ├── SOLVES → Lesson
│   ├── HAS_BENCHMARK → Benchmark
│   ├── HAS_COMPARISON → TechComparison
│   └── APPLIED_IN → MigrationPhase
└── FOLLOWS_METHODOLOGY → Methodology

Lesson
├── HAS_RESEARCH → ResearchFinding
├── HAS_PLAN → ActionPlan
└── BELONGS_TO_DOMAIN → ResolutionDomain

StressTestResult ← PRODUCED ─ Methodology
                 ─ DISCOVERED → Lesson (새 발견)
```

---

## 🌱 재배맨 v2 (MIC Slot Reference — 로직 복제 금지)

> 이 스킬의 subagent 운용은 **MIC_v1.SubagentSeeder** slot을 통해 resolve된다.
> 아래는 thin resolver. 로직 복제 = drift 유발.

### Slot Resolve
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot {name:'SubagentSeeder'})
RETURN s.currentConcrete, s.invocation, s.protocol
```

### 부모 Pre-fetch (v2 — MCP 우회)
```cypher
MATCH (l:Lesson)-[:HAS_RESEARCH]->(rf:ResearchFinding)
WHERE l.name CONTAINS $keyword RETURN rf.name, rf.domain, rf.oneLineSummary LIMIT 20
MATCH (ts:SubagentTaskSpec {skill:'solve'}) WHERE ts.status='READY'
RETURN ts.name, ts.role LIMIT 10
```

### WorkBuffer 연속성
```cypher
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
```

# KG: ATOM_재배맨_v2_solve, SA_methodology_v4_triple_upgrade
