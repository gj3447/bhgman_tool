# prometheus — Theory

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). KG: `prometheus-grounding-2026-05-05`, `fw-prometheus-references-apt-parity-2026-05-06`.

---

## 1. Knowledge-Action Spiral (v6.1 Hegel reframe)

| Phase | Hegel Phenomenology | Prometheus Step | When |
|-------|---------------------|-----------------|------|
| Thesis | initial Begriff (concept) | Step 0-2 (KG-first scan + axis derivation) | "먼저 불(지식) 훔쳐와" |
| Antithesis | self-movement → contradiction surfaces | Step 3-5 (subagent dispatch + finding collection) | findings reveal gaps |
| Synthesis | Aufhebung — preservation + sublation | Step 6-7 (UNWIND batch write + Lesson) | KG canonical update |

**v6.1 정정**: 단방향 "지식 선행"이 아니다. Begriff 자가운동(thesis 행동 없이 antithesis 못 만남) — paralysis-by-analysis 회피.

KG: `finding-prom32-prometheus-P1-F2` (OODA 충돌), `finding-prom32-prometheus-P1-F3` (Hegel spiral).

---

## 2. OODA / Lean Startup 충돌 해소

| Framework | Bias | Prometheus 채택? |
|-----------|------|------------------|
| OODA Loop (Boyd) | act-first, sense-second | hot-fix latency-critical 일 때만 KG-skip 허용 (post-hoc lesson 강제) |
| Lean Startup (Ries) | build-measure-learn 빠른 사이클 | sprint 단위 OK, 사이클 자체는 hypothesis 우선 |
| Lakatos research programme | progressive vs degenerating distinction | Step 4 distinguishability test 4-criterion 정전 (lakatos-progressive-vs-rescue-test-canonical-2026-05-06) |
| Hegel Phenomenology | thesis 자가운동 → antithesis | 정전 (v6.1) |

**Default**: KG-first thesis. **Exception**: latency-critical hot-fix → KG-skip + immediate action + post-hoc lesson 의무.

---

## 3. 9+1 Step Cycle

```
Step 0: KG Pre-fetch (parent-side, MCP 우회 GH#13605)
Step 1: Axis matrix template 생성 (axis × sub-axis × N)
Step 2: 사전 지식 scan (KG + filesystem dispersion)
Step 2.5: Step 2 KG Pre-fetch verification gate
Step 3: Subagent dispatch (haiku N parallel, max 100)
Step 3.3: Dedup detection (FullFindingRecord JSON schema)
Step 4: Distinguishability test (Lakatos 4-criterion)
Step 5: UNWIND batch write (single transaction, parent-side)
Step 6: Filesystem dispersion sub-step (KG↔fs drift 차단)
Step 6.5: Dispersion gate G6.5
Step 7: Lesson + ResearchFinding 결정화 (W3C PROV provenance)
Step 7.5: Cycle terminal — feedback loop 발동
```

---

## 4. Filesystem Dispersion Gate (v6 G6.5)

KG는 정전이지만 filesystem 도 source of truth. Drift 차단:

```
G6.5 invariants:
  - 모든 ResearchFinding.canonical_doc_path 가 실제 파일 존재
  - 모든 (file)-[:KG_REF]->(node) edge 양방향 유효
  - SHA256 일치 (sha256_hash field 검증)
  - line_range 가 실제 line count 안에 있음
```

위반 시 BLOCK + Longinus invocation 자동.

---

## 5. N-parameterization

| 문제 크기 | default N | 설명 |
|-----------|-----------|------|
| small | 4 | 단순 사실 확인 |
| medium | 8 | 일반 axis × sub-axis 매트릭스 |
| large | 16 | 복잡 도메인 |
| TOE | 64-100 | Theory-of-Everything급 |

`MethodologyConfig.prometheus_N_default_*` slot 으로 resolve. prose 직접 magic number 금지.

---

## 6. JSON Contract — FullFindingRecord

```json
{
  "agent_id": "D<idx>",
  "axis": "<axis>",
  "sub_axis": "<sub>",
  "claim": "...",
  "evidence": ["url1", "snippet"],
  "confidence": 0.85,
  "ground_truth_testable": true,
  "ground_truth_result": "PASS|FAIL|null",
  "verified": false,
  "provenance": "재배맨-prometheus-D<idx>",
  "dedup_hash": "<sha256-of-canonicalized-claim>"
}
```

부모가 UNWIND batch merge. dedup detection으로 중복 axis/sub-axis 충돌 검출.

---

## 7. Subagent 운용 — MIC 참조

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot {name:'SubagentSeeder'})
RETURN s.currentConcrete, s.invocation
-- 현재: 재배맨/SOP (jaebaeman-grounding-2026-05-05)
```

직접 호출 ❌. MIC slot 경유 ✓.

---

## 8. References

- `../SKILL.md` — protocol (얇은 entry)
- KG: `MIC_v1.SubagentSeeder` slot, `lakatos-progressive-vs-rescue-test-canonical-2026-05-06`, `lesson-prometheus-v5-kg-reference-lift-2026-04-18`, `rfc-prom-filesystem-dispersion-2026-04-29`
- 사이블 무기: `../taliban/references/theory.md` (gate validation), `../longinus/references/` (KG↔fs binding)

# KG: ATOM_Skill_prometheus, fw-prometheus-references-apt-parity-2026-05-06
