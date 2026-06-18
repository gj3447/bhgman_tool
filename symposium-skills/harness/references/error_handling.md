# harness — Error Handling

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## 1. Tier Identification Failure (G1)

```
IF tier 결정 불가 (multi-tier sibling family 가능성):
  1. Anthropic 3-tuple 같이 한 진영이 여러 tier 분해 cover 인지 확인
  2. 각 tier 별 별도 HarnessProfile 생성 (분해)
  3. 또는 'hybrid' tier 임시 표시 + sigma_oracle escalate
  4. tier_evidence 충분히 인용
```

## 2. Evidence-Free Scoring (G2 → V4)

```
IF score >= 2 AND evidence_<axis> IS NULL:
  1. BLOCK
  2. 추가 조사 (WebSearch + docs grep)
  3. evidence 인용 후 재점수
  4. evidence 못 찾음 → score 1 로 downgrade (보수적)
  5. Lesson 후보 (evidence drought)
```

## 3. Anti-Pattern HR_BockelerCitationDrift Detection

```
IF citation 에 "Böckeler" 등 잘못된 출처 발견:
  1. citation 즉시 제거
  2. family-expansion-pattern-canonical-2026-04-30 KG 노드 만 정전 사용
  3. lesson-harness-citation-drift-bockeler-2026-04-30 참조
  4. 새 출처 확보 (외부 정전 1차 source 만)
```

## 4. Family-as-1:1 Drift (HR_Family1to1)

```
IF instance 한 개로 family 전체 결정:
  1. sibling list 외부 조사 (WebSearch)
  2. 다른 tier instance 추가 검토
  3. 1:N hypothesis 로 reframe
  4. lesson-harness-drift-corrected-2026-04-29 정전 사용
```

## 5. MCP Role Confusion (HR_MCPRoleConfusion)

```
IF MCP 를 framework 으로 분류 시도:
  1. BLOCK
  2. MCP = adapter (호스트 책임 정반대) 명시
  3. THEORY/00_공통/세계관_정전.md §5-C 참조
  4. 분류 반려 + 사용자 verdict
```

## 6. Lakatos DEGENERATING (1:1 hypothesis 가 더 강함)

```
IF 4-criterion test 결과 1:1 가설 우세:
  1. Harness 정전 (1:N family) 자체 의심
  2. 새 evidence 조사 (WebSearch)
  3. 정정 candidate Lesson 생성
  4. 사용자 verdict: family 정전 redefine OR specific instance 예외 처리
```

## 7. Common Failure Modes

| 증상 | 원인 | 처방 |
|------|------|------|
| 한 instance 만 가지고 결론 | HR_Family1to1 | sibling 검색 강제 |
| Bockeler citation 출현 | HR_BockelerCitationDrift | family-expansion-pattern-canonical-2026-04-30 fallback |
| 4축 score 모두 0 | 진단 자체 실패 | tier 재확인 |
| MCP 가 frame 으로 분류 | HR_MCPRoleConfusion | adapter 정의 강제 |
| family_relation_position = 'none' | 비행기맨(#4) 외 무기 | OK (5무기 중 비행기맨만 STRONG mirror) |

# KG: ATOM_Skill_harness, fw-harness-references-apt-parity-2026-05-06
