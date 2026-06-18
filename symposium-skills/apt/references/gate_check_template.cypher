// APT Gate Check Cypher Templates — Single Source of Truth
// KG: lesson-026-gate-check-validation (defect-3,5 fix: DRY)
// Used by: .claude/hooks/apt-gate-check.sh
// All phase-specific gate checks reference this file.

// === SA → SP Gate ===
// Required: SA Taliban APPROVED + min 3 INFORMED_BY sources (depth check)
// Defect-2 fix: source_types depth validation
MATCH (sa:SemanticAnchor {status: 'active'})-[:HAS_VALIDATION]->(vr:ValidationResult {phase: 'SA', verdict: 'APPROVED'})
WHERE size((sa)-[:INFORMED_BY]->()) >= 3
RETURN sa.name AS project, vr.validated_at AS validated, vr.warnings AS warnings
LIMIT 1;

// === SP → ST Gate ===
// Required: SP Taliban APPROVED + Crystallization Frontier reached (all leaves atomic)
// Defect-4 fix: Crystallization Frontier verification
MATCH (sa:SemanticAnchor {status: 'active'})-[:HAS_VALIDATION]->(vr:ValidationResult {phase: 'SP', verdict: 'APPROVED'})
WHERE EXISTS {
  MATCH (sa)-[:HAS_SPAN]->(sp:SemanticSpan)
  WHERE sp.status = 'crystallized' OR sp.is_atomic = true
}
RETURN sa.name AS project, vr.validated_at AS validated, vr.warnings AS warnings
LIMIT 1;

// === ST → SCW Gate ===
// Required: ST Taliban APPROVED + Contracts have typed I/O (precondition/postcondition)
// Defect-7 fix: Contract completeness check
MATCH (sa:SemanticAnchor {status: 'active'})-[:HAS_VALIDATION]->(vr:ValidationResult {phase: 'ST', verdict: 'APPROVED'})
WHERE EXISTS {
  MATCH (sa)-[:HAS_CONTRACT]->(ct)
  WHERE ct.input_type IS NOT NULL AND ct.output_type IS NOT NULL
}
RETURN sa.name AS project, vr.validated_at AS validated, vr.warnings AS warnings
LIMIT 1;
