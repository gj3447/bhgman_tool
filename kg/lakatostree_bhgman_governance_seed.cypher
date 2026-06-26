// ============================================================================
//  LakatoTree onboarding — bhgman_tool as a Lakatos research programme
//  hub:    LakatosTree_BhgmanGovernance_20260624
//          (distinct from the live LakatosTree_VerdictProvenanceGate_20260620 —
//           no collision; that hub covers only OQ1, the legion verdict gate)
//  anchor: SA_BhgmanGovernanceAudit_20260624
//  source of truth: lakatotree/examples/bhgman_tool_programme.py (NODES/FRONTIER)
//
//  STATUS: APPLIED to the shared airo KG via airo-neo4j MCP write on 2026-06-24
//          (this dev box has no neo4j bolt route — HTTP-MCP is the only KG path,
//           so `sync_lakatos_programme_to_kg.py --apply` was NOT used). This file
//          is the committed record and is re-runnable: MERGE-only, idempotent,
//          NEVER DELETE/DETACH.
//
//  Verified live after write:  :LakatosNode=3 · :OpenQuestion=3 · BRANCHED_FROM=2 ·
//          :SemanticAnchor=1.  HAS_NODE children carry BOTH :PrismExperiment:LakatosNode
//          and HAS_FRONTIER children are :OpenQuestion — matching the existing
//          LakatosTree hubs' label convention (live-checked).
//
//  HAND-CORRECTION NOTE: sync_lakatos_programme_to_kg.py bakes GENERIC BPC/DC375
//  constants into the hub $props (HUB_SCOPE/HUB_PART/hard_core='2D seg…HALCON…PLC'/
//  canonical_node='dt_render'/created_at) AND into each node's metric_name
//  (='contract_output_count', scope='measurement'). Those are NOT bhgman facts.
//  The hub props and the per-branch metric descriptors below were hand-corrected
//  to bhgman-specific facts before the MCP write. The bhgman-specific NODE/FRONTIER
//  comments/limitations/verdict-stage-labels were already module-derived and are
//  unchanged.
//
//  ── HARD CORE (conjecture, NOT scored):
//     bhgman = deterministic governance/audit substrate
//     (determinism + exhaustiveness + idempotence + signed audit trail) — an
//     LLM-disjoint, zero-token, reproducible verification surface a reasoner CALLS.
//     It does NOT add reasoning capability (A/B self-disclosure; user 2026-06-04).
//
//  ── judge()-GENERATED runtime verdicts (from bhgman's OWN deterministic oracle via
//     an ABSOLUTE-venv subprocess — independent receipt, NOT self-report; produced
//     by run(), never hand-typed. The node .verdict below is a STAGE LABEL only —
//     'canonical_stage' — never a persisted progressivity claim; Rung.derived):
//       hard_core        → canonical_stage (root, not scored)
//       drift_governance → REJECTED     oracle drift-recount score=-436 passed=false
//                          (436 KG↔code drifts) — the HONEST non-progressive receipt.
//       lean_proof_gate  → PROGRESSIVE  oracle lean-goals score=8.0 passed=true
//                          (8 closed goals, exit-0 hard gate); novel metric
//                          (proof_checker_exit0) ≠ improvement metric (closed_lean_goals).
//     Oracle exit≠0 / score=-1000 sentinel → run() maps to pending(no-receipt)
//     (never NaN into judge()).
//
//  ── FRONTIER: q-bhg-capability-multiplier is OPEN BY DESIGN — bhgman's own A/B
//     evidence falsifies a capability-multiplier claim, so it is NOT registered as
//     a bold prediction; it stays open on the frontier.
// ============================================================================

// ── 1) hub ──────────────────────────────────────────────────────────────────
MERGE (h:KnowledgeHub:LakatosTree {name:'LakatosTree_BhgmanGovernance_20260624'})
ON CREATE SET h += {
  scope: 'governance/audit substrate — KG-anchored reproducibility · provenance · drift detection · contract enforcement · Lean-verified confidence schema; NOT a capability multiplier',
  part: 'bhgman_tool (비행기맨 #4 사도 / Harness 도구층) — 7-commander legion: prometheus·longinus·eureka·occam·naesengmoon·jaebaeman·hades',
  metric_rule: 'substrate-disjoint deterministic oracle verdict (bhgman-tool oracle: lean-goals·pytest-ratio·drift-recount·occam-twins; exit 0=pass/1=fail/2=KG-unavailable→pending). progress = oracle-verified governance gates; per-branch metric carried on nodes (drift lower=better, closed-goals higher=better)',
  hard_core: 'bhgman = 결정론 거버넌스/감사 substrate (determinism + exhaustiveness + idempotence + signed audit trail); LLM-disjoint, zero-token, reproducible verification surface a reasoner CALLS — does NOT add reasoning capability (A/B self-disclosure; user verdict 2026-06-04)',
  canonical_node: 'hard_core',
  certified: false,
  status: 'ACTIVE',
  source_python: 'examples.bhgman_tool_programme',
  named_by: 'lakatotree onboarding (bhgman governance); hub facts hand-corrected from generic BPC sync constants 2026-06-24',
  created_at: '2026-06-24'
}
ON MATCH SET h += {
  scope: 'governance/audit substrate — KG-anchored reproducibility · provenance · drift detection · contract enforcement · Lean-verified confidence schema; NOT a capability multiplier',
  part: 'bhgman_tool (비행기맨 #4 사도 / Harness 도구층) — 7-commander legion: prometheus·longinus·eureka·occam·naesengmoon·jaebaeman·hades',
  metric_rule: 'substrate-disjoint deterministic oracle verdict (bhgman-tool oracle: lean-goals·pytest-ratio·drift-recount·occam-twins; exit 0=pass/1=fail/2=KG-unavailable→pending). progress = oracle-verified governance gates; per-branch metric carried on nodes (drift lower=better, closed-goals higher=better)',
  hard_core: 'bhgman = 결정론 거버넌스/감사 substrate (determinism + exhaustiveness + idempotence + signed audit trail); LLM-disjoint, zero-token, reproducible verification surface a reasoner CALLS — does NOT add reasoning capability (A/B self-disclosure; user verdict 2026-06-04)',
  canonical_node: 'hard_core',
  certified: false,
  status: 'ACTIVE',
  source_python: 'examples.bhgman_tool_programme',
  named_by: 'lakatotree onboarding (bhgman governance); hub facts hand-corrected from generic BPC sync constants 2026-06-24',
  created_at: '2026-06-24'
};

// ── 2) nodes (HAS_NODE) — :PrismExperiment:LakatosNode (live convention).
//      verdict = STAGE LABEL only; progressivity is judge()-owned at runtime,
//      never persisted as a scored claim here. metric_name = the real per-branch
//      improvement metric (hand-corrected from the generic 'contract_output_count').
MATCH (h:KnowledgeHub:LakatosTree {name:'LakatosTree_BhgmanGovernance_20260624'})
UNWIND [
  {name:'LakatosTree_BhgmanGovernance_20260624/hard_core', tag:'hard_core',
   verdict:'canonical_stage',
   comment:'추측: bhgman = 결정론 거버넌스/감사 substrate(determinism+exhaustiveness+idempotence+signed audit trail), NOT a capability multiplier (채점 대상 아님, 루트).',
   limitation:'하드코어 추측: bhgman=결정론 거버넌스/감사 substrate, NOT capability multiplier',
   algorithm:'conjecture',
   metric_name:null, metric_direction:null, metric_scope:'governance',
   branch:'canonical_path'},
  {name:'LakatosTree_BhgmanGovernance_20260624/drift_governance', tag:'drift_governance',
   verdict:'canonical_stage',
   comment:'감사 가지: KG↔code drift 를 결정론 recount 로 *전수* 적발(exhaustiveness). 개선=drift 0 으로 감소(현재 436 → passed=false, 정직한 비진보). novel=재실행 idempotence(다른 축).',
   limitation:'novel metric != 개선 metric (judge P2 독립성): improve=kg_code_drift_count / novel=recount_idempotent',
   algorithm:'deterministic-oracle',
   metric_name:'kg_code_drift_count', metric_direction:'lower', metric_scope:'governance',
   branch:'canonical_path'},
  {name:'LakatosTree_BhgmanGovernance_20260624/lean_proof_gate', tag:'lean_proof_gate',
   verdict:'canonical_stage',
   comment:'검증 가지: 자족 .lean 의 proof-goal 을 substrate-disjoint proof-checker(lean) 로 검증. 개선=closed-goal count(higher). novel=exit-0 하드게이트(건전성의 독립 측정, count 와 다른 축).',
   limitation:'novel metric != 개선 metric (judge P2 독립성): improve=closed_lean_goals / novel=proof_checker_exit0',
   algorithm:'deterministic-oracle',
   metric_name:'closed_lean_goals', metric_direction:'higher', metric_scope:'governance',
   branch:'canonical_path'}
] AS row
MERGE (n:PrismExperiment:LakatosNode {name:row.name})
SET n.tag = row.tag,
    n.verdict = row.verdict,
    n.comment = row.comment,
    n.limitation = row.limitation,
    n.algorithm = row.algorithm,
    n.metric_name = row.metric_name,
    n.metric_direction = row.metric_direction,
    n.metric_scope = row.metric_scope,
    n.branch = row.branch
MERGE (h)-[:HAS_NODE]->(n);

// ── 3) lineage (BRANCHED_FROM) ───────────────────────────────────────────────
UNWIND [
  {child:'LakatosTree_BhgmanGovernance_20260624/drift_governance', parent:'LakatosTree_BhgmanGovernance_20260624/hard_core'},
  {child:'LakatosTree_BhgmanGovernance_20260624/lean_proof_gate',  parent:'LakatosTree_BhgmanGovernance_20260624/hard_core'}
] AS row
MATCH (c:LakatosNode {name:row.child})
MATCH (p:LakatosNode {name:row.parent})
MERGE (c)-[:BRANCHED_FROM]->(p);

// ── 4) frontier (HAS_FRONTIER) — :OpenQuestion (live convention).
//      q-bhg-capability-multiplier OPEN by design ───────────────────────────────
MATCH (h:KnowledgeHub:LakatosTree {name:'LakatosTree_BhgmanGovernance_20260624'})
UNWIND [
  {name:'q-bhg-capability-multiplier', status:'OPEN',
   body:'A/B says bhgman adds no reasoning capability — open by design. substrate 가치는 검증이지 추론력 증대가 아니다(user verdict 2026-06-04). bold prediction 으로 등록하지 않음(자기 증거가 반증).',
   domain:'governance', closed_by:[]},
  {name:'q-bhg-drift-exhaustive', status:'OPEN',
   body:'KG↔code drift 0 으로 전수 봉쇄(현재 436 drift, passed=false). drift_governance 가지가 judge() 로 채점 — 현 receipt 는 *정직한 비진보*(rejected). 0 도달 시 재실행이 자동 채점.',
   domain:'governance', closed_by:[]},
  {name:'q-bhg-lean-proof-gate', status:'OPEN',
   body:'자족 .lean proof-goal 을 substrate-disjoint lean checker(exit-0 하드게이트)로 검증. lean_proof_gate 가지가 judge() 로 채점. 툴체인 가용 시 progressive, 부재 시 pending.',
   domain:'governance', closed_by:[]}
] AS row
MERGE (q:OpenQuestion {name:row.name})
SET q.status = row.status,
    q.body = row.body,
    q.domain = row.domain,
    q.closed_by = row.closed_by
MERGE (h)-[:HAS_FRONTIER]->(q);

// ── 5) grounding to a SemanticAnchor (MERGE-only) ────────────────────────────
MATCH (h:KnowledgeHub:LakatosTree {name:'LakatosTree_BhgmanGovernance_20260624'})
MERGE (a:SemanticAnchor {name:'SA_BhgmanGovernanceAudit_20260624'})
ON CREATE SET a.created_at='2026-06-24', a.about='bhgman_tool governance/audit substrate onboarding (LakatoTree)'
MERGE (h)-[:DOCUMENTS]->(a);

// expected KG totals (drift alarm): :LakatosNode=3, :OpenQuestion=3, :BRANCHED_FROM=2, :SemanticAnchor(DOCUMENTS)=1
