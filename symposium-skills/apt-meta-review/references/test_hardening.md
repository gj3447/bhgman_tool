# test_skill_hardening.sh — Acceptance Test Rationale

> apt-meta-review가 SCW 종료 후 *자기 자신을 포함한 5 SKILL.md*를 검증하는 RED-phase bash test. 본 파일은 그 *이유*와 *각 check의 lesson grounding*.

---

## TDD RED Phase as Skill Verification

apt-meta-review는 SKILL 패치 의례를 따름:

```
1. test_skill_hardening.sh 실행 (RED phase)
2. FAILURES 발견 → SKILL.md 어디가 빠졌는지 명시
3. SKILL.md 패치 (GREEN phase)
4. 재실행 → ALL PASS
5. Naesengmoon gate (외부 검증)
```

→ apt-meta-review가 *직접 코드 수정하기 전*에 RED phase로 *gap*을 명시화. AP3 (Test Afterthought) 회피.

---

## TASK 1: Naesengmoon Sentinel

```bash
grep "IS NOT NULL" taliban/SKILL.md      # HARD BLOCK
grep "RUBBER_STAMP" taliban/SKILL.md     # null findings → REJECTED rule
```

**Lesson grounding**: `lesson-apt-vr-self-fulfilled-executor-reviewer-2026-04-16`. Naesengmoon이 null findings를 그냥 통과시키면 (rubber stamp) 검증이 무력화. HARD BLOCK으로 강제.

---

## TASK 2: AtomicSpan Label in Cypher

```bash
grep ":AtomicSpan" apt-sp/SKILL.md             # label 사용
grep "SET.*:AtomicSpan\|MERGE.*:AtomicSpan" apt-sp/SKILL.md  # SET/MERGE 패턴
```

**Lesson grounding**: 일반 `:AptSpan`과 `:AtomicSpan`은 의미 다름. 후자는 C(S) 5-predicate 모두 PASS한 단위. cypher가 후자를 명시적으로 SET해야 SCW가 안전하게 atom 받음. 누락 = SCW에서 잘못된 atom 처리.

---

## TASK 3: SCW Session Guard + FulfillmentGate

```bash
grep "세션 재개\|context compression" apt-scw/SKILL.md   # session resume guard
grep "FulfillmentGate\|executor.*reviewer" apt-scw/SKILL.md  # gate + V15
```

**Lesson grounding**: `lesson-apt-scw-tdd-skipped-context-compression-2026-04-16`. 세션 재개 시 컨텍스트 압축으로 TDAD baseline이 잊혀짐 → AP2 (Spec Amnesia). Session Startup Protocol 7-step ([../references/session_startup.md](../../apt-scw/references/session_startup.md))가 강제.

---

## TASK 4: MetaReview SKILL.md self-existence

```bash
test -f apt-meta-review/SKILL.md
grep "max_depth\|delta.*0\|self.*application.*forbidden" apt-meta-review/SKILL.md
grep "Naesengmoon\|taliban\|검증" apt-meta-review/SKILL.md
```

**Lesson grounding**: MetaReview는 자기 자신을 재귀 호출하면 무한 루프. `self_application_forbidden, max_depth=1, delta=0` 종료 조건 명시 필수. 또한 자기 검증이 아닌 *외부 Naesengmoon gate* 통과 강제.

---

## 실행 + 결과 해석

```bash
$ bash test_skill_hardening.sh
=== Skill Hardening Acceptance Tests ===
--- Naesengmoon Sentinel ---
[PASS] Naesengmoon: 'IS NOT NULL' HARD BLOCK present
[PASS] Naesengmoon: null findings → REJECTED rule present
--- APT-SP AtomicSpan Label ---
[PASS] apt-sp: ':AtomicSpan' label in Cypher examples
[PASS] apt-sp: AtomicSpan SET/MERGE Cypher present
--- APT-SCW Session Guard ---
[PASS] apt-scw: session resume guard present
[PASS] apt-scw: FulfillmentGate / executor!=reviewer rule present
--- MetaReview SKILL.md ---
[PASS] apt-meta-review: SKILL.md exists
[PASS] apt-meta-review: termination conditions present
[PASS] apt-meta-review: Naesengmoon Gate section present

=== Results: PASS=9 FAIL=0 ===
ALL PASS ✓
```

`FAIL > 0` 시:
1. 어떤 SKILL.md가 어떤 grep을 실패했는지 정확히 출력
2. apt-meta-review가 해당 SKILL.md 패치 작업으로 진입
3. 패치 후 재실행 → ALL PASS 확인 → Naesengmoon gate

---

## 검증 cypher (KG 측 보완)

bash test가 *파일 내용*을 본다면, cypher는 *KG 노드 일관성* 확인:

```cypher
-- V-MR-1: SkillVersion이 Lesson에 연결되어 있는지
MATCH (sv:SkillVersion) WHERE sv.skill IN ['apt','apt-sa','apt-sp','apt-st','apt-scw']
OPTIONAL MATCH (sv)-[:MATERIALIZES]->(oq:OpenQuestion)
WITH sv, count(oq) AS oq_count
WHERE oq_count = 0 AND sv.released_at > datetime() - duration({days: 7})
RETURN 'V_MR_1_SkillVersionNoOQ' AS validation, sv.name

-- V-MR-2: Lesson이 5 SKILL.md 중 어디에도 반영 안 됨
MATCH (l:Lesson {status:'open'}) WHERE l.created_at > datetime() - duration({days: 14})
OPTIONAL MATCH (l)-[:APPLIED_TO_SKILL]->(s:Skill)
WITH l, count(s) AS s_count
WHERE s_count = 0
RETURN 'V_MR_2_LessonOrphan' AS validation, l.name
```

# KG: APT_MR_TestHardening_canonical, lesson-apt-skill-drift-audit-2026-04-17
