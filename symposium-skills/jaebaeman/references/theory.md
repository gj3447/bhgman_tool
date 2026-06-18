# jaebaeman — Theory

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). KG: `jaebaeman-grounding-2026-05-05`, `재배맨-v2-subagent-runtime-protocol`, `lesson-jaebaeman-rebrand-SOP-2026-05-05`.

---

## 1. SOP — Subagent Orchestration Protocol

> 재배맨은 *서비스* 아닌 *프로토콜*. 부모 Claude가 따르는 규약.

```
KG seed (SubagentTaskSpec)  ←  외부 명세
            ↓
부모 Pre-fetch (KG → 컨텍스트, MCP 우회 GH#13605)
            ↓
부모 Dispatch (subagent N개 single-message multi-call)
            ↓
부모 Collect (FullFindingRecord JSON 수확 + 검증)
            ↓
부모 Write (UNWIND batch merge → KG)
            ↓
회수 — subagent 종료, 부모만 살아남음
```

---

## 2. MAS Misnomer 정정 (v2.1)

| Wooldridge BDI Agent (1995) | 재배맨 SOP |
|------------------------------|-----------|
| Beliefs (internal state) | **부재** — KG seed가 외부 명세 |
| Desires (goals) | **부재** — 외부 spec 따름 |
| Intentions (plans) | **부재** — taskspec.checkItems 가 plan |
| Reactive (env perceive) | **부재** — single-shot input |
| Persistent | **부재** — 1회 실행 후 종료 |

→ 학문적으로 "Multi-Agent System" 아님. **SOP** 가 정확. 재배맨은 한국어 alias 유지.

KG: `finding-prom32-jaebaeman-J1-F2` (MAS misnomer), `lesson-jaebaeman-rebrand-SOP-2026-05-05`.

---

## 3. 4-Stage Protocol

| Stage | 책무 | 도구 |
|-------|------|------|
| **Pre-fetch** | KG → 부모 컨텍스트 (MCP 우회) | `mcp__neo4j__read_neo4j_cypher` |
| **Dispatch** | seed_bundle 9-field 주입 + N개 subagent 병렬 출격 | Agent tool, single message multiple calls |
| **Collect** | JSON 수확 + FullFindingRecord schema 검증 + dedup | Read + parse |
| **Write** | UNWIND batch MERGE + Hyperedge reification | `mcp__neo4j__write_neo4j_cypher` |

각 stage 의 archetype: Holacracy 1:1 mirror.
- Phase 1 facilitator (Pre-fetch)
- Phase 2 lead_link (Dispatch)
- Phase 3 rep_link (Collect)
- Phase 4 secretary (Write)

---

## 4. Seed Bundle 9-Field (Dispatch invariant)

```yaml
seed_bundle:
  agent_id: "D<idx>"
  task_spec_name: "taskspec-<skill>-<phase>"
  axis: "<axis>"
  sub_axis: "<sub>"
  parent_intent: "<intent>"
  cypher_queries: [...]
  expected_outcome: "<schema>"
  treasure_coverage_min: 0.9
  provenance: "재배맨-<skill>-<idx>"
```

Single-message multiple-Agent-call 패턴 강제. GH#29181 self-check (intent N == actual N).

---

## 5. Anti-Patterns

| Anti-pattern | 증상 | 처방 |
|--------------|------|------|
| Inline subagent | 부모 자체에 critic 작업 | TR11 / D20 위반. subagent 1+ 강제 |
| MCP inheritance assumption | subagent 가 MCP server 자동 상속 가정 | GH#13605. 부모 pre-fetch 필수 |
| Self-check skip | dispatch 후 intent N != actual N | GH#29181. parent post-dispatch 검증 |
| Dedup skipped | 같은 axis/sub-axis 충돌 무시 | Step 3.3 dedup detection 의무 |
| Provenance "inline" | VR.provenance='inline' 박음 | Hook 차단 (TR11 + executor!=reviewer) |

---

## 6. KG Seed Discipline

> SubagentTaskSpec 은 *모든* subagent 호출의 단일 정전. SKILL.md 본문은 protocol pointer.

```cypher
MATCH (ts:SubagentTaskSpec)
RETURN ts.skill, ts.phase, ts.checkItems, ts.parallelism_min, ts.treasure_coverage_min,
       ts.fulfillment_gate_cypher, ts.expected_outcome_schema
ORDER BY ts.skill, ts.phase
```

새 seed 는 `MERGE`. 직접 호출 ❌. MIC `SubagentSeeder` slot 경유 ✓.

---

## 7. Holacracy Archetype Mapping

| Holacracy Role | 재배맨 Archetype | Subagent type (`.claude/agents/`) |
|----------------|------------------|-----------------------------------|
| Facilitator | Phase 1 (Pre-fetch + cycle entry) | `facilitator` |
| Lead Link | Phase 2 (Dispatch) | `lead_link` |
| Rep Link | Phase 3 (Collect) | `rep_link` |
| Secretary | Phase 4 (Write) | `secretary` |

각 archetype 은 specialized agent 로 결정화. **호출 측에서 archetype 식별은 prompt 본문 / KG metadata (HAS_SEED / DispatchHyperedge.subagent_type) 에 담음**. Anthropic Agent tool 시그니처는 `(model, run_in_background, prompt)` 3 param 만 받으므로 `subagent_type=...` 형태로는 전달 불가 (PROM_16 E2.1, SKILL.md §v2.3 Tool Param Binding).

---

## 8. Cycle Inheritance

```
APT (orchestrator)
  └── Step 6 cleanup
        └── 재배맨 Pre-fetch → Dispatch → Collect → Write
              └── inner subagent (haiku N parallel)
                    └── return FullFindingRecord JSON
TPA (orchestrator)
  └── TCW phase
        └── 재배맨 (file-level partition)
              └── inner agents (parser per chunk)
PROM (orchestrator)
  └── Step 3
        └── 재배맨 (axis × sub-axis matrix)
              └── inner haiku (per cell)
```

→ 재배맨 = 모든 multi-agent dispatch 의 *바닥*.

---

## 9. References

- `../SKILL.md`
- KG: `jaebaeman-grounding-2026-05-05`, `재배맨-v2-subagent-runtime-protocol`, `MIC_v1.SubagentSeeder` slot, `finding-prom32-jaebaeman-J1-F2`, `lesson-jaebaeman-rebrand-SOP-2026-05-05`
- archetype agents: `.claude/agents/facilitator.md`, `lead_link.md`, `rep_link.md`, `secretary.md`

# KG: ATOM_Skill_jaebaeman, fw-jaebaeman-references-apt-parity-2026-05-06 (planned)
