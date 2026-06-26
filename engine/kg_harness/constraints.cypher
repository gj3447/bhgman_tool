// kg_harness stable-id constraints — DB-level 백스톱. 설치: bolt 운영자(MCP는 DDL 거부). 2026-06-26.

// ── 즉시 설치 가능 (14개; dup 0 실측[Superseded 포함], 복합키는 null 면제 UNIQUE) ──
CREATE CONSTRAINT kgh_Apostle_roman_unique IF NOT EXISTS FOR (n:Apostle) REQUIRE n.roman IS UNIQUE;
CREATE CONSTRAINT kgh_BreakGlassEntry_auditId_unique IF NOT EXISTS FOR (n:BreakGlassEntry) REQUIRE n.auditId IS UNIQUE;
CREATE CONSTRAINT kgh_DispatchEvent_source_commander_unique IF NOT EXISTS FOR (n:DispatchEvent) REQUIRE n.source_commander IS UNIQUE;
CREATE CONSTRAINT kgh_DriftCheck_name_unique IF NOT EXISTS FOR (n:DriftCheck) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT kgh_GateAuditEntry_auditId_unique IF NOT EXISTS FOR (n:GateAuditEntry) REQUIRE n.auditId IS UNIQUE;
CREATE CONSTRAINT kgh_HarnessDiagnosis_name_unique IF NOT EXISTS FOR (n:HarnessDiagnosis) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT kgh_JaebaemanDispatchTelemetry_name_unique IF NOT EXISTS FOR (n:JaebaemanDispatchTelemetry) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT kgh_JaebaemanRun_name_unique IF NOT EXISTS FOR (n:JaebaemanRun) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT kgh_KnowledgeHub_name_unique IF NOT EXISTS FOR (n:KnowledgeHub) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT kgh_ReferenceSite_sourceId_name_unique IF NOT EXISTS FOR (n:ReferenceSite) REQUIRE (n.sourceId, n.name) IS UNIQUE;
CREATE CONSTRAINT kgh_ReinductionTrigger_name_unique IF NOT EXISTS FOR (n:ReinductionTrigger) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT kgh_ResearchFinding_findingId_unique IF NOT EXISTS FOR (n:ResearchFinding) REQUIRE n.findingId IS UNIQUE;
CREATE CONSTRAINT kgh_SourceCodeDriftEvent_name_unique IF NOT EXISTS FOR (n:SourceCodeDriftEvent) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT kgh_SubagentTaskSpec_sourceId_name_unique IF NOT EXISTS FOR (n:SubagentTaskSpec) REQUIRE (n.sourceId, n.name) IS UNIQUE;

// ── 제외: UNCONSTRAINABLE=['SourceCodeNode'] (archive-model 영구충돌), NEEDS_DEDUP=[] ──
// CREATE CONSTRAINT kgh_SourceCodeNode_sourcePath_unique IF NOT EXISTS FOR (n:SourceCodeNode) REQUIRE n.sourcePath IS UNIQUE;
