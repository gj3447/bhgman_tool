# Error Pattern Template (Cross-Skill Shared)

> APT 모든 phase에서 `E-{PHASE}{N}` 에러 사례 기록 시 사용하는 3절 양식. KG `:ErrorPattern` 노드 정전.

---

## 3절 양식 (mandatory)

### Context (무엇이 일어났나)
실제 발견된 시나리오 1–2문장. 추상 표현 금지, 구체적 행동 명시.

### Lesson (왜 그게 문제인가)
근본 원리. 자주 KG의 `:Lesson` 노드 또는 axiom 인용.

### Guard (어떻게 방지하나)
다음에 안 일어나게 하는 자동/반자동 메커니즘. validation query, gate, hook 등.

---

## 작성 예시

### E-SA1: KG 중복 앵커

**Context:** KG 탐색 없이 새 앵커를 생성. 기존 동일/유사 프로젝트 앵커가 이미 존재.

**Lesson:** 앵커 생성 전 KG 탐색 필수. SA의 가장 흔한 실수. 단일 SA가 정체성 인덱스이므로 중복 = 향후 모든 phase가 두 갈래로 갈라짐.

**Guard:** SA Step 1의 KG 탐색을 반드시 선행. MERGE 사용으로 중복 방지. V-SA2 cypher로 사후 탐지:

```cypher
MATCH (sa:SemanticAnchor)
WHERE sa.name CONTAINS $keyword OR sa.description CONTAINS $keyword
RETURN sa.name, sa.description, sa.status
```

---

## Naming convention

```
E-{PHASE_PREFIX}{INDEX} — {short name}
```

| Phase | Prefix | 예시 |
|---|---|---|
| SA | `E-SA` | E-SA1 (KG 중복), E-SA2 (PD 무시), E-SA3 (앵커 없이 SP 진입) |
| SP | `E-SP` | E-SP1 (blind decomposition), E-SP2 (1-child), E-SP3 (형제 의존) |
| ST | `E-ST` | E-ST1 (Contract draft 폐기), E-ST2 (Twin Contract 누락) |
| SCW | `E-SCW` 또는 `AP{N}` | AP1 (Gold Plating), AP2 (Spec Amnesia), ... AP9 |
| _common | `E-PD/CB/PTC/V` | E-PD1 (전체 KG load), E-CB1 (하드코딩), E-PTC1 (전부 보존), E-V1 (정상 잡음) |

---

## KG 결정화

```cypher
MERGE (e:ErrorPattern:AbstractNode {name:'E-'+$prefix+toString($n)+'-'+$shortName})
SET e.phase = $phase,                -- 'SA' | 'SP' | 'ST' | 'SCW' | '_common'
    e.context = $context,
    e.lesson = $lesson,
    e.guard = $guard,
    e.severity = $severity,          -- 'P1' | 'P2' | 'P3' | 'P4'
    e.discoveryType = $discoveryType,-- (선택) PH6 6 discovery type 중 하나
    e.category = $category,          -- (선택) PH6 10 category 중 하나
    e.created_at = datetime(),
    e.created_by = $agent
WITH e
OPTIONAL MATCH (l:Lesson {name:$linked_lesson})
FOREACH (_ IN CASE WHEN l IS NOT NULL THEN [1] ELSE [] END | MERGE (e)-[:GROUNDED_IN_LESSON]->(l))
RETURN e
```

---

## phase별 ErrorPattern 위치

| Phase | references 파일 |
|---|---|
| SA | `apt-sa/references/sa_errors.md` |
| SP | `apt-sp/references/sp_errors.md` |
| ST | `apt-st/references/st_errors.md` (드물면 SKILL.md inline) |
| SCW | `apt-scw/references/anti_patterns.md` (AP1-AP9) |
| _common | 본 폴더의 각 개념 파일 끝 절 (e.g. `progressive_disclosure.md`의 anti-pattern 절) |

---

## anti-pattern (이 양식 자체)

- **E-EPT1: Lesson 없음** — Context와 Guard만. 왜 문제인지 모르면 Guard가 자의적.
- **E-EPT2: Guard 없음** — Context + Lesson만. 다음에 재발 가능.
- **E-EPT3: 추상 Context** — "잘못 분해함". 어떻게? 어떤 입력? Guard 설계 불가.
- **E-EPT4: KG 미결정화** — `:ErrorPattern` 노드 없이 prose만. 다른 phase에서 검색 불가.

---

## Academic Grounding

Context/Lesson/Guard 3절 양식은 *human factors + safety engineering*의 결정화:

### 1. Reason's Swiss Cheese Model (Reason 1990)

> Reason, J. (1990). *Human Error*. Cambridge University Press.
>
> Reason, J. (2000). *Human error: models and management*. BMJ, 320(7237), 768-770.

핵심: 사고는 *latent failures* (계: organization/management) + *active failures* (개인 행동)가 *swiss cheese 구멍 정렬*할 때 발생.

→ E-XX의 **Context** = active failure (어떤 행동), **Lesson** = latent failure (왜 발생 가능했나), **Guard** = barrier (구멍 막기). 3절 = Reason 의 3 layer accident causation 직접 매핑.

### 2. Norman's Slip-Lapse-Mistake (Norman 1988)

> Norman, D. A. (1988). *The Design of Everyday Things*. Basic Books.
>
> Reason, J. (1990) 의 GEMS framework도 동일 taxonomy.

3 종 인간 오류:
- **Slip**: 의도 옳음, 실행 잘못 (typo, 잘못 클릭)
- **Lapse**: 의도 잊음 (단계 누락)
- **Mistake**: 의도 자체 잘못 (잘못된 모델/지식)

→ E-XX의 *severity* 매핑:
- Slip → P3-P4 (즉시 발견 + 쉬운 fix)
- Lapse → P2-P3 (Guard로 reminder 가능)
- Mistake → P1-P2 (Lesson으로 mental model 갱신 필요)

### 3. Post-Mortem Methodology (Allspaw 2012)

> Allspaw, J. (2012). *Blameless PostMortems and a Just Culture*. CodeAsCraft blog (Etsy).

핵심: *blame*이 아닌 *systemic learning* 지향. fact 분리 (what happened) + interpretation 분리 (why). 시간 순서 reconstruction.

→ E-XX의 Context는 *blame-free* 사실 기술. Lesson은 systemic 분석. AP4 Silent Patch 같은 사례에서 "agent X가 나빠서"가 아닌 "KG 결정화 의무 미명시"로 작성.

### 4. Pattern Language (Alexander 1977)

> Alexander, C. (1977). *A Pattern Language: Towns, Buildings, Construction*. Oxford University Press.

핵심: 반복되는 문제 → 반복되는 해결책 → *pattern name*. Christopher Alexander 의 250 architectural pattern.

→ E-XX naming convention (`E-SA1`, `AP4`, etc.) 은 Alexander pattern naming. 식별자가 *재사용 가능 어휘*가 되어 cross-skill 참조 가능.

### 5. KG embedding: CONTRACT_AgentMistakeLog_v1

기존 SYMPOSIUM KG의 `CONTRACT_AgentMistakeLog_v1_2026-04-27` 도 동일 양식 (assumed↔actual symmetric pair). E-XX는 그것의 markdown 표현.

# KG: APT_ErrorPattern_template_canonical, CONTRACT_AgentMistakeLog_v1_2026-04-27, lesson-reason-swiss-cheese-grounding-2026-05-11
