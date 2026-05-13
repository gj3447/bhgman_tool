# harness — Theory

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). KG: `harness-grounding`, `lesson-harness-drift-corrected-2026-04-29`, `lesson-harness-citation-drift-bockeler-2026-04-30`.

---

## 1. 12사도 #4 비행기맨의 공학 측 결정화

```
12사도 #4 비행기맨 (∀x:CHU, j.covers x)
        ↓ (공학 결정화)
Harness sibling family (1:N, NOT 1:1)
```

**중요**: Harness는 *family* 이지 *single instance* 아님. 1:1 매핑 = drift (lesson-harness-drift-corrected-2026-04-29).

---

## 2. 3-Tier Sibling Family

| Tier | 역할 | Instance 예시 |
|------|------|---------------|
| **L_MC (IDE-host)** | coding harness | Cursor / Claude Code / Aider / SWE-agent / Cline / OpenHands |
| **L_RT (application agent runtime)** | loop runtime | Google ADK / LangGraph / CrewAI / AutoGen |
| **L_IDE (managed cloud)** | infra + control plane | Anthropic Managed Agents / OpenAI Assistants / Vertex AI Agent Engine |

각 tier는 *다른 책임*을 cover. 한 tier 만으로는 비행기맨 ∀-cover 불가능.

**Anthropic 진영 3-tuple** (한 진영 안에서 family 분해):
- Skills (declarative capability) [L_MC 측]
- Agent SDK (loop) [L_RT 측]
- Managed Agents (infra) [L_IDE 측]
- **MCP**: 위 모든 instance 연결 어댑터 (호스트 책임 정반대)

KG: `family-expansion-pattern-canonical-2026-04-30`.

---

## 3. 4축 모델 (각 instance *내부* 조직 원리)

> 4축은 family 정의가 아님. *instance 내부*의 organization principle.

| 축 | 역할 | Detector |
|----|------|----------|
| **Inform** | agent에게 정보 주입 | KG retrieve, RAG, context window |
| **Constrain** | agent 행동 제약 | hooks, schema validation, permission denylist |
| **Verify** | post-hoc 검증 | tests, Taliban gate, ground truth |
| **Correct** | feedback loop | Lesson → ActionPlan → re-execute |

각 instance가 4축에 어떻게 위치하는지 = harness profile.

KG: `lesson-harness-drift-corrected-2026-04-29` (4축 = family 정의 X, instance 내부 O).

---

## 4. Family-Relation Mirror Hypothesis

비행기맨(#4)의 Family 구조 ↔ #4 참여 Relation hyperedge position 구조 = **structural mirror**.

| Family (도구측 1:N) | Relation (사도측 n-ary) |
|---------------------|------------------------|
| L_MC (apex) | VerticalAxisHyperedge {#4, #8, #10}[1] (apex) |
| L_RT (substrate) | VerticalAxisHyperedge[2] (substrate) |
| L_IDE (end) | VerticalAxisHyperedge[3] (end) |

**Mirror 강도**: STRONG (responsibility_split + cardinality match). 비행기맨이 5무기 중 유일 STRONG mirror.

KG: `family-relation-mirror-hypothesis-2026-04-30`.

---

## 5. Industry Citation Drift History

v2 → v3 정정 (2026-04-30): Bockeler citation drift 해소.

| 잘못된 출처 | 정정된 출처 |
|-------------|-------------|
| "Böckeler 2018 — agent harness" | (Bockeler는 Microservice Tooling 저자, agent harness 논문 없음) |
| (citation 자체 제거) | family-expansion-pattern-canonical-2026-04-30 KG 노드가 정전 |

KG: `lesson-harness-citation-drift-bockeler-2026-04-30`.

---

## 6. SOLID-DIP 사용 (MIC 참조)

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot {name:'Harness'})
RETURN s.currentConcrete, s.invocation
```

Harness slot은 *구조적 제약*만 제공 — 직접 invocation 적음 (4축 진단 시 호출).

---

## 7. Lakatos PROGRESSIVE 입증

Family-as-1:N 가설은 1:1 가설보다 4 distinguishability test 통과:

| Test | 1:1 | 1:N |
|------|-----|-----|
| theory_laden_anomaly | 인정 | 인정 |
| independent_testable_consequence | 약함 | 강함 (각 tier 별 책임 분리 검증 가능) |
| excess_empirical_content | 적음 | 많음 (Anthropic 3-tuple 같은 sibling 발견) |
| principled_grounding_in_hard_core | 약함 | 강함 (CHU "모든것은 하이퍼그래프" 공리 거울) |

KG: `lakatos-progressive-vs-rescue-test-canonical-2026-05-06`.

---

## 8. References

- `../SKILL.md`
- 정전: `THEORY/00_공통/세계관_정전.md §5-C` (3계층 표 + MCP + Anthropic 3-tuple)
- KG: `family-expansion-pattern-canonical-2026-04-30`, `family-relation-mirror-hypothesis-2026-04-30`, `lesson-harness-drift-corrected-2026-04-29`, `lesson-harness-citation-drift-bockeler-2026-04-30`

# KG: ATOM_Skill_harness, fw-harness-references-apt-parity-2026-05-06 (planned)
