// TPA Phase Detection Queries
// # KG: ATOM_Skill_tpa_orchestrator_v10

// 1. 현재 phase 감지 (특정 execution)
MATCH (exec:TPA_Execution {name: $exec_name})
OPTIONAL MATCH (exec)-[:PHASE_OUTPUT {order:1}]->(tcw:TPA_TCW_Result)
OPTIONAL MATCH (exec)-[:PHASE_OUTPUT {order:2}]->(tt:TPA_ST_Result)
OPTIONAL MATCH (exec)-[:PHASE_OUTPUT {order:3}]->(tp:TPA_SP_Result)
OPTIONAL MATCH (exec)-[:PHASE_OUTPUT {order:4}]->(ta:TPA_TA_Result)
OPTIONAL MATCH (exec)-[:HAS_VALIDATION]->(vr:ValidationResult)
WITH exec, tcw, tt, tp, ta, collect(vr.phase) AS validated_phases
RETURN exec.name,
  CASE
    WHEN ta IS NOT NULL THEN 'COMPLETE'
    WHEN 'SP' IN validated_phases THEN 'TA'
    WHEN 'ST' IN validated_phases THEN 'SP'
    WHEN 'TCW' IN validated_phases THEN 'ST'
    WHEN tcw IS NOT NULL THEN 'TCW_UNVALIDATED'
    ELSE 'TCW'
  END AS current_phase;

// 2. 진행 중인 모든 TPA 목록
MATCH (e:TPA_Execution)
WHERE e.status STARTS WITH 'IN_PROGRESS' OR e.phase_current <> 'COMPLETE'
RETURN e.name, e.target, e.phase_current, e.status, e.started_at
ORDER BY e.started_at DESC LIMIT 10;

// 3. 완료된 TPA의 발견 요약
MATCH (exec:TPA_Execution {name: $exec_name})-[:PHASE_OUTPUT]->(result)
OPTIONAL MATCH (result)-[:IDENTIFIES]->(finding)
RETURN labels(finding)[0] AS finding_type, count(finding) AS count
ORDER BY count DESC;

// 4. 미해결 Lesson (TPA 발견)
MATCH (l:Lesson)
WHERE l.name STARTS WITH 'lesson-tpa-'
  AND (l.resolved IS NULL OR l.resolved = false)
RETURN l.name, l.severity, l.problem, l.category
ORDER BY l.severity;

// 5. ActionPlan 상태
MATCH (p:ActionPlan)
WHERE p.name STARTS WITH 'plan-' AND p.name CONTAINS 'quality'
RETURN p.name, p.status, p.improvements, p.project
ORDER BY p.createdAt DESC LIMIT 5;
