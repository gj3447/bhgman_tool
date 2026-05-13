# taliban — Gates

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). Sibling: [`./theory.md`](./theory.md).
> KG: `taliban-grounding`, `rfc-taliban-v08-concern-coverage-2026-05-04`.

---

## 1. Adversarial Round Gate Sequence

각 invocation 의 gate 흐름:

```
[/taliban <target> --lens <set>]
   ↓
G0: Pre-flight  — target 존재 + lens slot resolve
   ↓
G1: LensSet Resolution  — KG 에서 LensSet 노드 조회 + lensCount ≥ 9
   ↓
G2: Subagent Dispatch  — 재배맨 SubagentTaskSpec 씨앗 → N parallel critic
   ↓
G3: Findings Collection  — FullFindingRecord JSON + min finding count check
   ↓
G4: Coverage Calculation  — ensemble UNION concern-coverage (Pirsig holistic)
   ↓
G5: Anti-Rubber-Stamp Audit  — 10+ technique check (RTI/FVR enforcement)
   ↓
G6: Verdict Decision  — 5 verdict categories (APPROVED / REJECTED / ...)
   ↓
G7: ValidationResult Crystallization  — KG 결정화 + USED_LENS edge
   ↓
[VR returned to caller]
```

---

## 2. G0 Pre-flight

**Required**:
- target node 가 KG 에 존재 (Span / Contract / Code / DesignPattern / 기타)
- `--lens` 옵션 resolve OK (constitutional / mathematical / solid / longinus / custom)
- `MIC_v1.AdversarialValidator` slot resolution

**On fail**: BLOCK + LensSet 후보 목록 표시.

---

## 3. G1 LensSet Resolution Gate (v0.7 + v0.8.A1)

```cypher
MATCH (ls:LensSet {name: $lens_name})
WHERE ls.deprecated <> true
RETURN ls.name, ls.lensCount, ls.scope, ls.lenses, ls.coverage_concerns
```

**Required**:
- `ls.lensCount >= 9` (default constitutional 9 lens floor; mathematical 113; solid 5)
- `ls.deprecated = false`
- `ls.lenses` array non-empty

**On fail**:
- `ls.deprecated = true` (예: constitutional-sp-focused) → 3-lens shortcut 차단
- `ls.lensCount < 9` → BLOCK + LensSet completeness violation (HR13 mirror)

KG: `lesson-taliban-shortcut-antipattern-2026-04-21`.

---

## 4. G2 Subagent Dispatch Gate (TR11 / D20 — executor != reviewer)

**Required**:
- `subagent_count >= 1` (인라인 critic 금지)
- 부모와 다른 subagent_type (`taliban-ensemble-critic`)
- model 분리 (parent != critic — 같은 weights = bias 전염)
- `provenance != 'inline'`

```
역할: Taliban critic (agentId=C<idx>)
TaskSpec: MATCH (ts:SubagentTaskSpec {skill:'taliban', lensset:$lens}) RETURN ts.*
Target: <kg_node_name>. 출력: ValidationResult {verdict, findings[], evidence[]} JSON.
```

**On fail**:
- `subagent_count = 0` → BLOCK + TR11 violation (HR15 mirror)
- `provenance = 'inline'` → BLOCK + Anti-Rubber-Stamp #1 violation
- model = parent → BLOCK + model separation violation

---

## 5. G3 Findings Collection Gate

**Required (Anti-Rubber-Stamp #2)**:
- `findings_count >= 3` (minimum)
- 각 finding 에 `severity ∈ {BLOCKER, PERFORMANCE, DESIGN_DEBT, NITPICK}`
- 각 finding 에 `evidence` 필드 non-empty

**On fail**:
- `findings_count < 3` → escalated prompt 재호출 (theory.md §4 #4)
- `evidence empty` → BLOCK + reject single finding
- 모든 finding NITPICK only (severity distribution skew) → Anti-Rubber-Stamp #7 violation → 재호출 OR critic model rotation

---

## 6. G4 Coverage Calculation Gate (v0.8.A1 ensemble UNION)

```cypher
MATCH (vr:ValidationResult)-[:USED_LENS]->(ls:LensSet)
WITH vr, collect(DISTINCT ls) AS used_lensets
MATCH (ls2:LensSet)-[cv:COVERS_CONCERN]->(c:Concern)
WHERE ls2 IN used_lensets
WITH vr, c, max(cv.weight) AS w  // Pirsig: max weight per concern
WITH vr, sum(w) AS coverage_score, count(c) AS concerns_covered
RETURN coverage_score / 9.0 AS normalized
```

**Required**:
- `coverage_score / 9.0 >= 0.8` (default `APT_GATE_COVERAGE_THRESHOLD`)
- 단일 LensSet 평가 폐기 (Phase 2 discovery: 모든 active LensSet borderline/fail)
- ensemble UNION 만 정전

**On fail**:
- `< 0.8` → REJECTED + Lesson `lesson-taliban-coverage-insufficient`
- COVERS_CONCERN edge 부재 (LensSet 미정전화) → fall-back 단일 LensSet 평가 + Lesson

KG: `rfc-taliban-v08-concern-coverage-2026-05-04`, `lesson-taliban-v08-single-lensset-insufficient-2026-05-04`.

---

## 7. G5 Anti-Rubber-Stamp Audit Gate

10 technique 자동 체크 (theory.md §4 참조):

| # | Technique | Pass criterion |
|---|-----------|----------------|
| 1 | Model separation | parent_model != critic_model |
| 2 | Min findings ≥ 3 | count check |
| 3 | Core assumption challenge | ≥1 finding targets core assumption |
| 4 | Anti-checklist 10-item | critic addresses checklist explicitly |
| 5 | Falsifiability | every finding testable/verifiable |
| 6 | Ground truth cross-check | ground_truth_testable findings auto-verified |
| 7 | Severity distribution audit | not 100% NITPICK |
| 8 | Historical finding rate | not always exactly 3 (gaming) |
| 9 | Blind review | critic doesn't see prior sigma_oracle |
| 10 | Rotation | model rotated after 5+ rounds |

**On fail**: 어느 technique 위반 → Lesson + flag `theater_suspected = true` + sigma_oracle escalate.

KG: `lesson-prom16-skillver-progressive-disclosure-drift-2026-04-29` (mode collapse 정전).

---

## 8. G5.5 RTI / FVR Gate (Random-Tactical-Insertion / Forced-Verdict-Rotation)

**RTI**:
- 매 round 마다 critic prompt 에 random attack vector 주입 (`security` / `concurrency` / `boundary` / `null` / `overflow`)
- adaptation 차단

**FVR**:
- N rounds 후 verdict rotation enforce
- `consecutive_APPROVED >= 5` → 다음 round 강제 REJECT 시도 (critic 의심)
- 패턴 균형 검사 (history: APPROVED:REJECTED:CONDITIONAL_PASS 비율)

**On fail**: critic rotation + Lesson.

---

## 9. G6 Verdict Decision Gate

| Verdict | 조건 | 다음 |
|---------|------|------|
| `APPROVED` | findings_count ≥ 3, coverage ≥ 0.8, 0 BLOCKER, RTI/FVR pass | gate pass |
| `APPROVED_PENDING_EXTERNAL_D20` | 자체-executor 보완 + sigma_oracle consent | 최종 gate, external retest 필요 |
| `REJECTED` | ≥1 unresolved BLOCKER OR coverage < 0.8 | re-design / re-recover |
| `CONDITIONAL_PASS` | PERFORMANCE finding only | sigma_oracle 결정 |
| `SUPERSEDED` | 후속 VR 가 대체 | gate query 에서 제외 |

---

## 10. G7 ValidationResult Crystallization

```cypher
MERGE (vr:ValidationResult:AbstractNode {name: 'VR_' + $skill + '_' + $target + '_' + $date})
SET vr.target_phase = $phase,
    vr.phase = $phase,
    vr.verdict = $verdict,
    vr.findings = $findings_array,
    vr.findings_count = size($findings_array),
    vr.findings_categories = $categories,
    vr.evidence = $evidence_array,
    vr.warnings = $warnings,
    vr.critics_dispatched = $critics_n,
    vr.validator = 'Taliban-' + $lens_name,
    vr.provenance = 'subagent-taliban-' + $skill,
    vr.validated_at = datetime()
WITH vr
MATCH (ls:LensSet {name: $lens_name})
MERGE (vr)-[:USED_LENS]->(ls)
WITH vr
MATCH (target {name: $target_name})
MERGE (target)<-[:VALIDATES]-(vr)
RETURN vr.name
```

**Required**:
- `(vr)-[:USED_LENS]->(:LensSet)` edge
- `vr.evidence` non-empty (HR11 mirror)
- `vr.provenance != 'inline'`
- `vr.target_phase` set

---

## 11. Multi-Phase Coordination (APT/TPA hook 통합)

`apt-gate-check.sh` v0.8-per-span (default 2026-05-06) 가 다음 phase 호출 시 직전 VR 검증:

```cypher
MATCH (sa:SemanticAnchor {status: 'active'})-[:HAS_VALIDATION]->(vr:ValidationResult)-[:USED_LENS]->(ls:LensSet)
WHERE vr.phase = $REQUIRED_PHASE AND vr.verdict IN ['APPROVED','APPROVED_PENDING_EXTERNAL_D20']
  AND ls.lensCount >= 9 AND ls.deprecated <> true
RETURN sa.name, vr.validated_at LIMIT 1
```

**On fail**: 다음 phase BLOCK + `permissionDecision: deny`.

---

## 12. Anti-Patterns Detection (Tier1 — 9-lens artifact validation)

| # | Anti-pattern | 검출 |
|---|--------------|------|
| TL_RubberStamp | findings = 0 + APPROVED | G3 count check |
| TL_LensSetIncomplete | lensCount < 9 | G1 |
| TL_ExecutorEqReviewer | parent_model = critic_model | G2 |
| TL_Theater | 5+ rounds NITPICK only | G5 audit |
| TL_EvidenceFreeApproval | evidence empty + APPROVED | G7 |
| TL_DistributedNameOnly | Distributed pattern matched without SP-MetaVerify | TPA-측 contracts |
| TL_InlineProvenance | provenance = 'inline' | G2 |
| TL_DeprecatedLens | constitutional-sp-focused 사용 | G1 |

---

## 13. Tier2 Mathematical (88-Taliban / 113-lens)

mathematical lens는 *방법론 자체* meta-verification 전용. Tier1 (artifact) ≠ Tier2 (methodology):

```
Use the taliban-ensemble-critic agent with --lens mathematical to meta-verify <Methodology Skill name>
```

113 mathematical lens 는 stratified sampling (taliban-mathematical-sampler-poc-2026-05-06).

---

## 14. References

- theory: `./theory.md`
- skill: `../SKILL.md`
- sibling: `../prometheus/references/gates.md` (G6 Lakatos), `../longinus/references/gates.md` (--lens longinus)
- KG: `rfc-taliban-v08-concern-coverage-2026-05-04`, `lesson-taliban-shortcut-antipattern-2026-04-21`, `taliban-mathematical-sampler-poc-2026-05-06`, `MIC_v1.AdversarialValidator` slot

# KG: ATOM_Skill_taliban, fw-taliban-references-apt-parity-2026-05-06
