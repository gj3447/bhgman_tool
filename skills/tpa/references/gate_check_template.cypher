// TPA Gate Check Cypher Templates — Single Source of Truth
// KG: tpa-hardening-master-plan-2026-05-06, lesson-tpa-hardening-bootstrap-2026-05-06
// Used by: .claude/hooks/apt-gate-check.sh (shared infrastructure with APT)
// Mirror file: SYMPOSIUM/SKILLS/apt/references/gate_check_template.cypher

// === TCW Gate (entry — no pre-gate) ===
// Required: Taliban VR APPROVED + manifest assertion + AST parser used
MATCH (exec:TPA_Execution {name: $exec_name})-[:HAS_VALIDATION]->(vr:ValidationResult {phase: 'TCW', verdict: 'APPROVED'})
      -[:USED_LENS]->(ls:LensSet)
WHERE ls.lensCount >= 9 AND (ls.deprecated IS NULL OR ls.deprecated = false)
  AND EXISTS {
    MATCH (exec)-[:PHASE_OUTPUT {order:1}]->(tcw:TPA_TCW_Result)
    WHERE tcw.skipped_files = 0
      AND tcw.parsed_with IS NOT NULL
      AND tcw.parsed_with <> 'grep'
      AND tcw.symbol_count = tcw.parser_symbol_count
  }
RETURN exec.name AS execution, vr.validated_at AS validated, ls.name AS lensSet
LIMIT 1;

// === ST Gate ===
// Pre-req: TCW VR APPROVED via Hook
// Required: ST Taliban APPROVED + Convention discrimination clean (no dual-label) + Longinus binding present
MATCH (exec:TPA_Execution {name: $exec_name})-[:HAS_VALIDATION]->(vr:ValidationResult {phase: 'ST', verdict: 'APPROVED'})
      -[:USED_LENS]->(ls:LensSet)
WHERE ls.lensCount >= 9 AND (ls.deprecated IS NULL OR ls.deprecated = false)
  AND NOT EXISTS {
    // V7: no dual-label contract
    MATCH (n) WHERE n:AptContract AND n:ConventionalContract
  }
  AND EXISTS {
    MATCH (exec)-[:PHASE_OUTPUT {order:2}]->(st:TPA_ST_Result)
    WHERE st.totalContracts > 0
  }
RETURN exec.name AS execution, vr.validated_at AS validated, ls.name AS lensSet
LIMIT 1;

// === SP Gate ===
// Pre-req: ST VR APPROVED
// Required: SP Taliban APPROVED + Pattern Library >= 38 + every Distributed pattern has SP-MetaVerify VR
MATCH (exec:TPA_Execution {name: $exec_name})-[:HAS_VALIDATION]->(vr:ValidationResult {phase: 'SP', verdict: 'APPROVED'})
      -[:USED_LENS]->(ls:LensSet)
WHERE ls.lensCount >= 9 AND (ls.deprecated IS NULL OR ls.deprecated = false)
  AND EXISTS {
    MATCH (p:DesignPattern)
    WITH count(p) AS pc
    WHERE pc >= 38
    RETURN pc
  }
  AND NOT EXISTS {
    // No Distributed INSTANCE_OF without SP-MetaVerify VR
    MATCH (sp:TPA_SP_Result)<-[:PHASE_OUTPUT]-(exec)
    MATCH (sp)-[:MATCHED_PATTERN]->(p:DesignPattern {category: 'Distributed'})
    WHERE NOT EXISTS {
      MATCH (exec)-[:HAS_VALIDATION]->(mv:ValidationResult {phase: 'SP-MetaVerify', verdict: 'APPROVED'})
    }
  }
RETURN exec.name AS execution, vr.validated_at AS validated, ls.name AS lensSet
LIMIT 1;

// === TA Gate ===
// Pre-req: SP VR APPROVED
// Required: TA Taliban APPROVED + drift table populated + coverage_ratio policy applied
MATCH (exec:TPA_Execution {name: $exec_name})-[:HAS_VALIDATION]->(vr:ValidationResult {phase: 'TA', verdict: 'APPROVED'})
      -[:USED_LENS]->(ls:LensSet)
WHERE ls.lensCount >= 9 AND (ls.deprecated IS NULL OR ls.deprecated = false)
  AND EXISTS {
    MATCH (exec)-[:PHASE_OUTPUT {order:4}]->(ta:TPA_TA_Result)
    WHERE ta.coverage_ratio IS NOT NULL
      AND ta.drift_missing IS NOT NULL
      AND ta.drift_orphan IS NOT NULL
      AND ta.drift_sigmismatch IS NOT NULL
      AND ta.drift_patterndiv IS NOT NULL
      AND ta.drift_labelrot IS NOT NULL
      // Either coverage >= threshold OR SemanticAnchor properly suspended
      AND (
        ta.coverage_ratio >= 0.8
        OR EXISTS {
          MATCH (ta)-[:ANCHORS_TO]->(sa:SemanticAnchor {status: 'SUSPENDED'})
        }
      )
  }
RETURN exec.name AS execution, vr.validated_at AS validated, ls.name AS lensSet
LIMIT 1;

// === Per-AtomicSpan VR Enforcement (mirrors APT v0.8-per-span) ===
// For each recovered :AptContract / :ConventionalContract, require a per-leaf VR.
// Excludes pre_hardcore=true executions (analogous to APT pre_hardcore anchors).
MATCH (exec:TPA_Execution)
WHERE (exec.pre_hardcore IS NULL OR exec.pre_hardcore = false)
  AND (exec.exempt_from_perspan IS NULL OR exec.exempt_from_perspan = false)
MATCH (exec)-[:PHASE_OUTPUT]->(:TPA_ST_Result)-[:RECOVERS_CONTRACT]->(c)
WHERE (c:AptContract OR c:ConventionalContract)
  AND NOT EXISTS {
    MATCH (c)<-[:VALIDATES]-(vr2:ValidationResult)
    WHERE coalesce(vr2.target_phase, vr2.phase) = $required_phase
      AND vr2.verdict IN ['APPROVED', 'APPROVED_PENDING_EXTERNAL_D20']
      AND (vr2.status IS NULL OR vr2.status <> 'SUPERSEDED')
  }
RETURN count(c) AS unvalidated_count, collect(c.name)[..5] AS sample_orphans;
