# ST World Reference (TPA-side)

> TPA v1.1 ST Phase 상세. Mirror sibling: `apt-st/references/st_world.md` (forward direction — design ST).
> 이 문서는 *역방향* ST: 코드에서 contract를 *추출*한다.

---

## 1. Phase Identity

**ST = TargetSemanticTwin** — 각 pub 심볼의 *암묵* 또는 *명시* 계약을 추출한다. APT의 ST(설계 → contract 결정화)와 정확히 같은 산출물 형태(Contract)를 갖되, 출발점이 다르다.

| 질문 | 답 |
|------|----|
| pre-gate | TCW VR APPROVED via Hook |
| post-gate | Naesengmoon 9-lens VR + Convention/Apt 라벨 분리 검증 + Longinus 바인딩 |
| 결정 | 명시 interface/trait → `:AptContract`, N≥3 implementor 공유 시그니처 → `:ConventionalContract` |
| 위임 | LOC>100 메서드는 SP phase로 (giant method, atomic 아님) |

---

## 2. AptContract vs ConventionalContract — 결정 트리

```
                    pub 심볼 발견
                       │
              명시 interface/trait/abstract?
                  ┌────┴────┐
                YES         NO
                 │           │
        :AptContract    구현 N개 시그니처 동등?
                            ┌────┴────┐
                          YES (≥3)   NO
                           │          │
              :ConventionalContract   no contract
                                    (skip; nominal)
```

LOC>100 → giant_method_deferred (SP phase로 위임), Contract 만들지 않음.

---

## 3. AptContract 결정화

```cypher
MERGE (c:AptContract:AbstractNode {name: 'AC_' + $target_id + '_' + $sym_name})
SET c.type = 'explicit',
    c.declared_in = $file,
    c.line = $line,
    c.sourcePath = $file + ':' + toString($line),
    c.extends = $parent_class,
    c.implements = $interfaces,
    c.protocol = $method_signatures_formal,
    c.preconditions = $pre_from_docstring,         // @precondition / Requires: / 전제:
    c.postconditions = $post_from_docstring,       // @postcondition / Ensures: / 보장:
    c.error_variants = $error_variants_list,       // throws / Result<E> / raise
    c.recovered_from_execution = $exec_name,
    c.created_at = datetime()
MERGE (sym:CodeSymbol {name: $qualified_name})-[:HAS_CONTRACT]->(c)
```

precondition/postcondition 누락 시 `'NONE — code contract only'` 명시 (blank 금지).

---

## 4. ConventionalContract 결정화

```cypher
MERGE (cv:ConventionalContract:AbstractNode {name: 'CC_' + $target_id + '_' + $shape_name})
SET cv.type = 'implicit',
    cv.inferred_from = toString($n_implementors) + ' 심볼이 공유하는 시그니처',
    cv.protocol = $shared_signature_pattern,
    cv.implementors = $implementor_names,           // [sym1, sym2, sym3, ...]
    cv.confidence = $overlap_ratio,                 // ≥ 0.8 권장
    cv.evidence = $concrete_snippets,
    cv.recovered_from_execution = $exec_name,
    cv.created_at = datetime()
WITH cv
UNWIND $implementor_names AS impl_name
MATCH (s:CodeSymbol {name: impl_name})
MERGE (s)-[:CONFORMS_TO]->(cv)
```

---

## 5. 절대 섞지 말 것 (TR_OntologyPollution)

| 실수 | 결과 |
|------|------|
| AptContract 노드에 `:ConventionalContract` 라벨도 추가 | V7 위반 — ontology 오염 |
| trait 인데 ConventionalContract 사용 | 컴파일러 강제 사실 누락 |
| 동일 name으로 두 contract 모두 생성 | Neo4j 유니크 제약 충돌 + 라벨 모호 |
| `confidence < 0.8` 인데 ConventionalContract 만듦 | 우연의 일치를 패턴으로 잘못 박음 |

---

## 6. pre/postcondition 파싱 — 언어별 마커

| Lang | Precondition 마커 | Postcondition 마커 |
|------|------------------|--------------------|
| Rust (rustdoc) | `# Errors`, `# Panics`, `requires` | `# Returns`, `ensures` |
| TypeScript (JSDoc) | `@param requires`, `@throws` | `@returns`, `@ensures` |
| Python (docstring) | `:raises:`, `Requires:`, `Args:` | `:returns:`, `Ensures:`, `Returns:` |
| Go (godoc) | "panics if", "requires" | "returns" |
| Korean | `전제:`, `요구:`, `사전조건:` | `보장:`, `결과:`, `사후조건:` |

파서가 마커를 못 찾으면 `inferred = 'NONE — code contract only'`. 이는 *발견 증거*이자 lesson 후보.

---

## 7. Giant Method 처리

```cypher
MERGE (gm:GiantMethodDeferred:AbstractNode {name: 'GM_' + $sym_qualified})
SET gm.loc = $loc,
    gm.file = $file + ':' + toString($line),
    gm.reason = 'LOC>100 — SP 패턴 분석 후 재평가',
    gm.deferred_to = 'SP',
    gm.recovered_from_execution = $exec_name
MERGE (st:TPA_ST_Result {name: $st_name})-[:DEFERS_TO_SP]->(gm)
```

SP가 deferred 메서드를 받아서 패턴 분류 (Strategy / State / God Object 등) 후 *그때* 분해/contract 화 결정.

---

## 8. Longinus 바인딩 (TR12)

각 Contract마다 `:ReferenceSite` 생성:

```cypher
MATCH (c:AptContract|ConventionalContract {name: $contract_name})
MERGE (rs:ReferenceSite:AbstractNode {name: 'RS_' + $contract_name})
SET rs.sourcePath = c.sourcePath,
    rs.file = c.declared_in,
    rs.line = c.line,
    rs.layer = 'contract-recovery',
    rs.bound_at = datetime()
MERGE (c)-[:BOUND_TO]->(rs)
```

ReferenceSite 누락 = TR_LongiusBindingMissing (V11). Hook이 ST gate에서 차단.

---

## 9. TPA_ST_Result 결정화

```cypher
MERGE (st:TPA_ST_Result:AbstractNode {name: 'ST_' + $target_id + '_' + $date})
SET st.sourcePath = $target,
    st.totalContracts = $apt_n + $conv_n,
    st.aptContracts = $apt_n,
    st.conventionalContracts = $conv_n,
    st.giantMethodsDeferred = $giants_n,
    st.prePostParsed = $pp_parsed_n,
    st.prePostInferredNone = $pp_none_n,
    st.referenceSitesBound = $rs_n,
    st.created_at = datetime()
MERGE (exec)-[:PHASE_OUTPUT {order:2}]->(st)
```

---

## 10. FulfillmentGate ST (7 checks)

1. [ ] 모든 Contract `sourcePath = file:line` 채워짐
2. [ ] `:AptContract` 와 `:ConventionalContract` 라벨 *명확 분리* (V7 통과)
3. [ ] precondition / postcondition 필드 존재 (없으면 explicit NONE)
4. [ ] giant_methods_deferred 목록 → SP phase로 전달 표시
5. [ ] Longinus ReferenceSite 모든 Contract마다 ≥1
6. [ ] taskspec.checkItems 전부 pass
7. [ ] TPA_ST_Result + PHASE_OUTPUT order=2 + 모든 메타 필드 SET

---

## 11. Naesengmoon 9-lens 종료 의식

Critic 입력:
- AptContract:ConventionalContract 비율 (이상한 분포 → 의심)
- precondition/postcondition NONE 비율 (너무 높으면 docstring 누락 의심)
- giant_methods_deferred 카운트
- Longinus ReferenceSite 누락 노드

```cypher
MERGE (vr:ValidationResult {name:'VR_TPA_ST_'+$target+'_'+$date, phase:'ST'})
SET vr.verdict = $verdict,
    vr.evidence = [...],
    vr.validator = 'Naesengmoon-9lens',
    vr.provenance = 'subagent-taliban-st',
    vr.validated_at = datetime()
```

REJECT 사유:
- Apt vs Conventional 라벨 섞임 → 명확 분리 후 재실행
- ReferenceSite 누락 → Longinus 호출 후 재실행
- precondition/postcondition NONE 비율 > 80% → docstring 파서 재확인 (TR4 paste-only 의심)

---

## 12. Common Failure Modes

| 증상 | 원인 | 처방 |
|------|------|------|
| AptContract == ConventionalContract count 차이 0 | 분류 알고리즘 buggy | references/error_handling.md §1 |
| pp_none_n / total > 0.8 | docstring 자체 부재 OR 파서 미작동 | 다른 파서로 시도, lesson 기록 |
| 동일 시그니처 N=2 인데 ConventionalContract 만듦 | 우연 일치 (N≥3 미충족) | confidence downgrade, RESEMBLES로 |
| ReferenceSite 누락 다수 | Longinus auto-fire 미작동 | KgCodeBinder slot resolve 확인 |

---

## 13. References

- `../tpa/references/phases.md` §2
- `../tpa/references/error_handling.md` §1, §3 (parser fail)
- `../tpa/references/validation.md` V7 (label disjointness), V11 (ReferenceSite)
- `../apt-st/references/st_world.md` (mirror — forward direction)

# KG: ATOM_Skill_tpa_st, fw-tpa-references-apt-parity-2026-05-06
