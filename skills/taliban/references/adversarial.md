# taliban — Adversarial

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## 1. Self-Adversarial — Naesengmoon critiques Naesengmoon

가장 어려운 question: *critic 자체*를 누가 검증하는가?

답: **Tier2 mathematical lens (88-Naesengmoon / 113-lens)** 가 Tier1 (constitutional 9-lens) 의 *방법론* 메타검증.

```
Use the taliban-ensemble-critic agent with --lens mathematical to meta-verify the constitutional-9-full LensSet itself
```

→ 113 mathematical lens 가 9 constitutional lens 의 false positive / false negative / coverage gaps 검출.

## 2. Anti-Theater Mechanisms (Detail)

theory.md §4 의 10 technique 외 추가:

### 2.1 Critic Rotation Strategy

```cypher
MATCH (vr:ValidationResult) WHERE vr.validated_at >= datetime() - duration('P30D')
RETURN vr.critic_model, count(vr), avg(vr.findings_count)
ORDER BY count(vr) DESC
```

**Strategy**:
- Top 1 critic_model 사용 비율 > 50% → forced rotation
- Critic 별 finding rate variance 추적 (always = 3 → gaming)

### 2.2 Severity Distribution Audit (Anti-Rubber-Stamp #7)

```cypher
MATCH (vr:ValidationResult)<-[:VALIDATES]-(target)
WHERE vr.validated_at >= datetime() - duration('P7D')
WITH vr, target
UNWIND vr.findings AS f
WITH target, count(f) AS total,
     count(CASE WHEN f.severity = 'NITPICK' THEN 1 END) AS nitpicks
WHERE 1.0 * nitpicks / total > 0.8
RETURN target.name AS theater_suspected, nitpicks * 1.0 / total AS ratio
```

→ ratio > 0.8 across 5+ rounds = mode collapse alert.

### 2.3 Ground Truth Override History (Anti-Rubber-Stamp #6)

```cypher
MATCH (fb:TalibanFeedback)
WHERE fb.ground_truth_testable = true AND fb.ground_truth_result IS NOT NULL
WITH fb.ground_truth_result AS result, count(fb) AS n
RETURN result, n, n * 1.0 / sum(n) OVER () AS ratio
```

→ ground_truth = FAIL 비율이 너무 낮으면 critic hallucination 의심.

### 2.4 Blind Review Enforcement (#9)

```
critic 이 받는 컨텍스트:
- target node (KG)
- LensSet definition
- 이전 VR 의 verdict 만 (decided_by 는 mask)
```

→ 이전 sigma_oracle 결정 보지 않음 (anchoring 차단).

## 3. Constitutional 9-Lens vs Mathematical 113-Lens

| LensSet | Targets | Use Case |
|---------|---------|----------|
| constitutional-9-full | artifacts (Span/Contract/Code) | default — every gate |
| mathematical (113) | methodologies (skills, frameworks) | meta-verification |
| solid (5) | architecture decisions | quick SOLID check |
| longinus (n) | KG↔code binding | drift detection |

**Tier 분리 강제** (TR8 mirror):
- Tier1 9-lens for artifacts (산출물)
- Tier2 113-lens for methodology (방법론 자체)

→ 9-lens 로 methodology 검증 = scope mismatch.

## 4. Pirsig Holistic Synthesis (v0.8 ensemble UNION)

> "Quality cannot be defined, but Quality is the parent of subject and object" — Pirsig.

→ ensemble UNION coverage = 같은 concern 을 max(weight) lens 가 cover. Single LensSet 평가 폐기.

```
single LensSet evaluation:
  L_constitutional = 0.74 (borderline)  → REJECT
  L_solid = 0.62 (fail)                 → REJECT

ensemble UNION (constitutional + solid):
  concern_C1: max(L_const_C1=0.8, L_solid_C1=0.4) = 0.8
  concern_C2: max(0.6, 0.7) = 0.7
  ...
  ensemble_score / 9.0 = 0.85           → APPROVE
```

KG: `rfc-taliban-v08-concern-coverage-2026-05-04`.

## 5. RTI / FVR — Random + Forced Rotation

**RTI (Random Tactical Insertion)**:
- 매 round critic prompt 에 random vector 삽입
- vectors: security / concurrency / boundary / null / overflow
- adaptation 차단 (critic 가 같은 finding 반복 못함)

**FVR (Forced Verdict Rotation)**:
- consecutive verdict 패턴 추적
- 5+ APPROVED 연속 → 다음 round REJECT 시도 (critic 의심)
- 5+ REJECT 연속 → 다음 round APPROVE 시도 (target 진짜 망가졌는지 sigma_oracle)

## 6. The Human as Meta-Meta-Discriminator

자기 검증의 무한 후퇴 (Tier1 → Tier2 → ?) 는 *unavoidable*. 결국 sigma_oracle (HUMAN) 가 최종 stop.

→ `allow_agent_sigma=false` LOCKED (TR11 / HR15 / D20 mirror).

# KG: ATOM_Skill_taliban, fw-taliban-references-apt-parity-2026-05-06
