# Production Factory Patterns — Harness L_RT Recipe

> revfactory/harness (2026, sha256 `ee84902c...`) frame 을 SYMPOSIUM Harness 3-tier + 4축 정전과 정합 매핑.
> 본 reference = SKILL.md body (meta-level *diagnose frame*) 의 *object-level companion*.
> External canonical: `revfactory-harness-2026-05-09` (`:ExternalFrontierHarness`, L_RT instance, git `6400bf6`).

---

## 1. 6 Team Pattern × 5 Orchestration Model — cross-ref

5 orchestration model (§3) 은 *control-flow primitive*. 6 team pattern 은 그 위 *agent collaboration recipe*. 다른 위상 → cross-product.

| Team Pattern | 의미 | 5 Model 매핑 | SYMPOSIUM 4축 강조 |
|---|---|---|---|
| **Pipeline** | 순차 의존 작업 | LangGraph (linear edge) / ADK (sub-agent chain) | Constrain (전후 dependency) |
| **Fan-out / Fan-in** | 병렬 독립 → 통합 | LangGraph (conditional) / Agents SDK (handoff) | Inform (병렬 정보 수집) |
| **Expert Pool** | 상황별 선택 호출 | CrewAI (`Process.hierarchical`) | Inform (전문성 매칭) |
| **Producer-Reviewer** | 생성 + 품질 검수 | AutoGen (GroupChat critic) / Agents SDK | **Verify** (D20 executor != reviewer 거울) |
| **Supervisor** | 중앙 동적 분배 | CrewAI manager / ADK root | Constrain + Correct |
| **Hierarchical Delegation** | 재귀 위임 (top-down) | ADK A2A protocol / Agents SDK | Constrain (책임 split) |

→ 6 pattern 은 5 model 위 cross-cutting *recipe*. L_RT instance 설계 시 *(model, pattern)* 짝 명시 필수.
→ Producer-Reviewer ↔ Naesengmoon D20 (executor != reviewer) 정전 1:1 거울 — Anti-Rubber-Stamp 의 industry independent confirm.

---

## 2. QA Agent — Boundary-Cross Verification

revfactory Phase 3 정전: QA agent 는 *general-purpose* type (`Explore` 읽기 전용으로 검증 스크립트 못 돌림).

핵심 정의 3:

1. **존재 확인 ≠ QA**. QA 핵심 = **경계면 교차 비교** (boundary-cross verification).
   - 예: API response shape ↔ frontend hook expected shape 동시 read 후 비교.
   - SYMPOSIUM 매핑: Longinus L4 FILE_LINE binding × 양쪽 reference 동시 sha256 verify.

2. **Incremental QA**. 전체 완성 후 1회 ✗. 각 모듈 완성 직후 점진 실행.
   - SYMPOSIUM 매핑: APT v0.8-per-span gate (각 AtomicSpan 완료 시 VR enforce) 거울.

3. **`general-purpose` type forced** (Anthropic Claude Code agent 제약).
   - 빌트인 타입이라도 `.claude/agents/{qa-agent}.md` 정의 파일 mandatory.

→ Naesengmoon 의 *specific QA instance* — boundary-cross 가 lensSet 의 unspecified 영역. SYMPOSIUM 추가 lens 후보: `boundary_cross_shape_match` (LL.10 candidate).

---

## 3. Trigger Validation — should-trigger / should-NOT-trigger

revfactory Phase 6 정전: Skill description 자체 validation.

| Suite | 개수 | 작성 원칙 |
|------|-----|---------|
| **should-trigger** | 8-10 | 다양한 표현 (공식/캐주얼, 명시/암시) — 모두 트리거 기대 |
| **should-NOT-trigger (near-miss)** | 8-10 | 키워드 유사하지만 다른 도구/스킬 적합 — *경계가 모호한 쿼리*가 좋은 테스트 |

near-miss 작성 핵심: "피보나치 함수 작성" 같은 명백 무관 ✗. "이 엑셀 차트를 PNG 추출" (xlsx 스킬 vs 이미지 변환) ✓ — 경계 모호.

SYMPOSIUM 매핑:
- 모든 신규 SKILL.md 추가 시 trigger validation suite 16-20 자동 생성 (Phase 4 mandatory)
- KG 결정화: `:TriggerValidationSuite` { skill_name, should_trigger[], should_not_trigger[], conflict_with[] }
- 기존 skill 과 trigger 충돌 detection — Pseudepigrapha 확장: trigger overlap = description drift 신호.

→ SYMPOSIUM Skill 28+개 retroactive trigger validation backfill candidate sprint.

---

## 4. `_workspace/` Artifact Convention

revfactory Phase 5 정전: 중간 산출물 file-based 보존 컨벤션.

```
project_root/
└── _workspace/
    ├── 01_analyst_requirements.md      # phase=01, agent=analyst, artifact=requirements
    ├── 02_designer_architecture.md
    ├── 03_qa_validation_report.md
    └── _workspace_prev/                # 이전 실행 archive (재실행 시 mv)
```

규칙:
- 파일명: `{phase}_{agent}_{artifact}.{ext}`
- 최종 산출물만 사용자 지정 경로 출력
- 중간 파일 보존 — *사후 검증 + 감사 추적*
- 재실행 시 `_workspace/` → `_workspace_prev/` mv (overwrite ✗)

SYMPOSIUM 매핑:
- W3C PROV-DM 6 relations 의 *generation* + *revision* 직접 대응
- Prometheus `_findings/` raw JSON 보존 패턴과 정합
- Longinus L4 FILE_LINE binding 의 *intermediate* tier (L3.5 candidate)
- BIZ_IDEA `001_distributed_llm_inference_mining.md` 의 ResumptionHook 도 `_workspace_prev/` 참조 가능

→ SYMPOSIUM 표준 채택 권장. Skills 산출물 컨벤션 통일.

---

## 5. Evolution 3-Signal

revfactory Phase 7-4 정전: 사용자 명시 명령 *밖* 진화 trigger.

| Signal | 감지 | 자동 행동 |
|---|---|---|
| 같은 유형 피드백 2회+ 반복 | KG `:Verdict` count + EXPLAINED_BY 같은 RootCause | Lesson 결정화 + Skill 본문 패치 propose |
| 에이전트 반복 실패 패턴 | KG `:ValidationResult` REJECTED count by skill | Skill drift audit dispatch (Naesengmoon) |
| 사용자가 오케스트레이터 *우회* 수동 작업 관찰 | Skill 호출 vs 직접 작업 비율 | Skill description "pushy" 강화 + trigger overlap 검사 |

SYMPOSIUM 매핑:
- APT meta-review Phase 5 자동 trigger 조건 (지금까지는 수동)
- `agent-feedback-loop-canonical-2026-04-27` 의 F1-F4 failure mode 와 정확 정합
- `MT_LessonHoarding` / `MT_OverCautiousFromCorrections` MistakeType 의 *반대 방향* 신호 (signal 누락 = drift)

→ KG 자동 ratio measurement query 결정화 (자동 trigger):
```cypher
MATCH (l:Lesson)-[:GENERALIZES]->(rc:RootCause)<-[:EXPLAINED_BY]-(v:Verdict)
WITH rc, count(v) AS occurrence
WHERE occurrence >= 2
RETURN rc.name, occurrence ORDER BY occurrence DESC
```

---

## 6. SYMPOSIUM ↔ revfactory 5 invariant 정합 (재확인)

| invariant | SYMPOSIUM | revfactory | 격차 |
|---|---|---|---|
| CLAUDE.md = thin pointer + 변경 이력 | ✓ (2026-05-09 longinus L4 적용) | ✓ Phase 5-4 정전 | 0 |
| Skills < 500 line + references/ Progressive Disclosure 3-stage | ✓ (310 line + 8 ref) | ✓ Phase 4-4 정전 | 0 |
| Pushy descriptions (적극적 트리거) | ✓ (frontmatter Invoke when:) | ✓ Phase 4-2 정전 | 0 |
| Producer-Reviewer (executor != reviewer) | ✓ (Naesengmoon D20 / HR11) | ✓ Phase 2 6-pattern 4번 | 0 |
| Anthropic Skills format (`name`/`description` frontmatter) | ✓ | ✓ | 0 |

→ 독립 convergence 5/5. 정전성 industry-confirmed.

---

## 7. SYMPOSIUM 보완 추가 가치 (revfactory 가 명시 안 한 것)

revfactory 가 *흡수 안 한* SYMPOSIUM 우위 (보완 reference 받아도 SYMPOSIUM 측 우위):

1. **3-tier family taxonomy** (L_IDE / L_RT / L_MC) — revfactory 는 단일 L_RT 위상 한정
2. **External canonical citation discipline** (PseudepigraphaValidationGate 5-step) — revfactory 는 self-contained
3. **KG-first body** (Cypher in skill) — revfactory 는 file-only artifact
4. **Meta-trap guards 7종** (카테고리 mismatch / MetaphorValidationGate / Pseudepigrapha) — revfactory 는 Phase 7 진화 정도
5. **5 무기 ↔ Böckeler 2축 정합표** (§6) — revfactory 외부 도구 cross-ref 없음
6. **MIC slot resolve** (`SubagentSeeder` etc) — revfactory 는 inline subagent dispatch

→ 양쪽 보완 = complementary, not competing. SYMPOSIUM = 진단/분류 + KG 정전 / revfactory = production-recipe specifics.

---

# KG: revfactory-harness-2026-05-09 (`:ExternalFrontierHarness`), production-factory-patterns-reference-2026-05-09 (`:HarnessReference`), trigger-validation-backfill-sprint-2026-05-09 (`:FutureWork` candidate), workspace-convention-canonical-2026-05-09 (`:ArtifactConvention` candidate), evolution-3-signal-canonical-2026-05-09 (`:FeedbackTrigger` candidate)
