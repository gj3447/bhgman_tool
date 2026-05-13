# harness — KG Logging

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## 1. HarnessProfile (per instance)

```cypher
MERGE (h:HarnessProfile:AbstractNode {name: 'harness-profile-' + $instance})
SET h.tier = $tier,                              // L_MC|L_RT|L_IDE
    h.tier_evidence = $tier_ev,
    h.inform_score = $inform,
    h.constrain_score = $constrain,
    h.verify_score = $verify,
    h.correct_score = $correct,
    h.total_score = $inform + $constrain + $verify + $correct,
    h.evidence_inform = $ev_inform,
    h.evidence_constrain = $ev_constrain,
    h.evidence_verify = $ev_verify,
    h.evidence_correct = $ev_correct,
    h.anti_patterns_detected = $anti_pat_list,
    h.family_relation_position = $position,       // apex|substrate|end|none
    h.lakatos_classification = $lakatos,           // PROGRESSIVE|DEGENERATING|N/A
    h.diagnosed_at = datetime(),
    h.diagnosed_by = 'harness-diagnostician'
```

## 2. TierFamily relationships

```cypher
MATCH (h:HarnessProfile {name: $profile})
MERGE (tier_family:TierFamily {name: 'tier-family-' + h.tier})
ON CREATE SET tier_family.tier = h.tier, tier_family.canonical_examples = $examples
MERGE (h)-[:MEMBER_OF]->(tier_family)
```

## 3. AntiPattern Detection Log

```cypher
UNWIND $anti_patterns AS ap
MERGE (apl:HarnessAntiPatternLog {name: 'apl-' + ap.kind + '-' + $instance})
SET apl.kind = ap.kind,                           // HR_Family1to1|HR_TierConfusion|...
    apl.instance = $instance,
    apl.severity = ap.severity,
    apl.evidence = ap.evidence,
    apl.detected_at = datetime()
MERGE (h:HarnessProfile {name: 'harness-profile-' + $instance})
MERGE (apl)-[:DETECTED_FROM]->(h)
```

## 4. ComparisonReport (multi-instance)

```cypher
MERGE (cr:HarnessComparisonReport:AbstractNode {name: 'cmp-' + $report_id})
SET cr.instances = $instance_names,                // ["Cursor","Claude Code",...]
    cr.tier = $shared_tier,                        // 모두 같은 tier 인 경우
    cr.best_inform = $best_inform_instance,
    cr.best_constrain = $best_constrain,
    cr.best_verify = $best_verify,
    cr.best_correct = $best_correct,
    cr.collective_anti_patterns = $collective_aps,
    cr.compared_at = datetime()
WITH cr
UNWIND $instance_names AS inst
MATCH (h:HarnessProfile {name: 'harness-profile-' + inst})
MERGE (cr)-[:INCLUDES]->(h)
```

## 5. Audit Queries

```cypher
// Tier distribution
MATCH (h:HarnessProfile) RETURN h.tier, count(h), avg(h.total_score) ORDER BY count(h) DESC

// 4-axis distribution by tier
MATCH (h:HarnessProfile) RETURN h.tier, avg(h.inform_score) AS i, avg(h.constrain_score) AS c, avg(h.verify_score) AS v, avg(h.correct_score) AS r
```

# KG: ATOM_Skill_harness, fw-harness-references-apt-parity-2026-05-06
