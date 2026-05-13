# taliban — Error Handling

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## 1. Critic Returns < 3 Findings (G3)

```
IF findings_count < 3:
  1. Escalated prompt 재호출 (theory.md §4 #4 anti-checklist)
  2. 여전히 < 3 → critic model rotation
  3. 재호출 후에도 < 3 → BLOCK + Anti-Rubber-Stamp #2 violation
  4. critic 가 3 NITPICK 강제 시 documented review methodology 요구
```

## 2. Mode Collapse (5+ rounds NITPICK only)

```
IF severity_distribution skew detected (>80% NITPICK 5+ rounds):
  1. Alert: Anti-Rubber-Stamp #7 violation
  2. critic model rotation 강제 (#10)
  3. RTI vector 다양화
  4. 여전히 NITPICK only → 인간 sigma_oracle meta-discriminator 호출
```

## 3. LensSet Incomplete (G1)

```
IF ls.lensCount < 9 OR ls.deprecated = true:
  1. BLOCK
  2. constitutional-9-full default 로 fallback
  3. 또는 다른 적절한 lens 후보 (mathematical/solid/longinus) 제안
  4. Lesson TL_LensSetIncomplete 자동
```

## 4. Executor == Reviewer (G2)

```
IF parent_model == critic_model:
  1. BLOCK 즉시
  2. 다른 model spawn (haiku/sonnet/opus 분리)
  3. provenance 가 'inline' 이면 추가 BLOCK (TR11)
  4. Lite Mode (single model 만 사용 가능) 면 Anti-Rubber-Stamp 모두 mandatory + Lesson
```

## 5. Ground Truth Override (D23)

```
IF critic finding 가 ground_truth_testable = true:
  1. 자동 ground truth 명령 실행 (cargo test / lint / WebSearch)
  2. ground truth = PASS → finding override (dismissed)
  3. ground truth = FAIL → finding 강화 (BLOCKER 격상)
  4. Override history 추적 (3+ overrides → critic prompt 재검토)
```

## 6. sigma_oracle No Response

```
IF sigma_oracle prompt 발송 + no response in conversation:
  1. DO NOT proceed
  2. DO NOT auto-approve
  3. Re-state question with:
     - 제안 요약
     - critic findings (count + severities)
     - ground truth results
     - drift table (TPA-측 인 경우)
  4. wait for human response
  5. 다른 주제로 conversation 진행 시 pending approval reminder
```

## 7. Adversarial Theater Detection

```
IF anti-rubber-stamp 10 technique 중 ≥ 3 violation:
  1. Theater suspected flag 설정
  2. Lesson TL_Theater 생성
  3. critic model rotation
  4. 다음 round 부터 RTI/FVR enforcement 강화
```

## 8. Common Failure Modes

| 증상 | 원인 | 처방 |
|------|------|------|
| 항상 APPROVED 반복 | rubber-stamp | model rotation + RTI |
| 매번 정확히 3 finding | gaming the minimum (#8) | finding rate 추적 |
| ground_truth 반복 dismiss | critic hallucination | critic prompt 재검토 |
| coverage_score 항상 0.79 (just below threshold) | bias 의심 | LensSet expansion |
| inline provenance 시도 | TR11 violation | BLOCK + 강제 subagent dispatch |

# KG: ATOM_Skill_taliban, fw-taliban-references-apt-parity-2026-05-06
