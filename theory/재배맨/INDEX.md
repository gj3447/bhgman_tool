# 재배맨 (Jaebaeman / SOP) — Index

> *공학 측 정전 둥지. 신화 측은 `METAHUMOTONIC/BHGMAN/seedman/`.*
> 한 줄: **씨앗(SubagentTaskSpec)에서 에이전트를 재배하는 프로토콜.** SOP (Subagent Orchestration Protocol). 4-Phase: Seed → Dispatch → Collect → Write. 모든 AI subagent 동작의 바닥.

---

## 0. 본 폴더의 위치

| 측면 | 위치 |
|---|---|
| **공학 측 자료집 (본 폴더)** | `THEORY/재배맨/` — 학문 정전 + industry + Lean + production PoC |
| **공학 측 정본 (SKILL)** | `SERVER/.claude/skills/jaebaeman/SKILL.md v2.2` |
| **수학 측 정본 (Lean)** | `MIND/lean_formalization/AirplaneMan.lean`, `JaebaeManInf.lean` |
| **신화 측 자료집** | `METAHUMOTONIC/BHGMAN/seedman/SOURCES.md` |
| **신화 측 1차 소스** | `MIND/metahumotonic/비행기맨꼐서_지켜주실꺼야.md` 등 |

본 폴더 *집필 전 단계*. 논문 본문은 별도.

---

## 1. 파일 지도

### 정전 자료집

| 파일 | 내용 |
|---|---|
| `SOURCES.md` | 1차 소스 + 학문 정전 6 axis (μX algebra/fold/Sheaf/Whitehead/Smarandache/Lawvere) + industry |
| `INDEX.md` | 본 파일 |
| `ABSTRACT.md` | 5 단락 논문 초록 |
| `PAPER_SKELETON.md` | 논문 골격 (서론·관련연구·핵심정리·평가·결론) |
| `AXIS_DEEP_GROUNDING.md` | 6 axis 학문 정전 정확 정의 + cross-ref |
| `COMPARISON_METHODOLOGIES.md` | LangGraph / CrewAI / AutoGen / Saga(GarciaMolina-Salem) / MCP / Actor model / Sagas v2 / Akka / Erlang OTP 와 대조 |
| `CITATION_TABLE.md` | 인용 표 |
| `GLOSSARY.md` | 용어집 |
| `FINAL_VERDICT.md` | 결정화 verdict + 향후 sprint |
| `LEAN_REGRESSION_AUDIT.md` | Lean 4 5 theorem audit (μX algebra + cata + Phase order + GH#29181 + Saga) |

### 사이클 산출 (legacy)

| 파일 | 내용 |
|---|---|
| `IMPLEMENTATION_GUIDE.md` | 구현 가이드 (legacy, 2026-04-29) |
| `PROM_32_REPORT.md` + `PROM_32_axis_findings/` | PROM 32 cycle |
| `PROM_64_REPORT.md` + `PROM_64_REPORT_v2.md` + `PROM_64_axis_findings/` | PROM 64 cycle 2종 |

### Production runtime PoC

| 파일 | 내용 |
|---|---|
| `jaebaeman_sop_runtime_prototype/` | Python 3.11+ 4-Phase runtime (56 pytest PASS, APT/Prometheus 패리티) |
| `jaebaeman_sop_runtime_prototype/sop_runner.py` | `JaebaemanSop` orchestrator |
| `jaebaeman_sop_runtime_prototype/phase1_seed.py` | Seed 관리 |
| `jaebaeman_sop_runtime_prototype/phase2_dispatch.py` | Dispatch + GH#29181 self-check |
| `jaebaeman_sop_runtime_prototype/phase3_collect.py` | Collect + outputSchema validation + dedup |
| `jaebaeman_sop_runtime_prototype/phase4_write.py` | UNWIND idempotent + Saga compensation |
| `jaebaeman_sop_runtime_prototype/saga_compensation.py` | v2.1 J3-F2 |

### Lean audit

| 파일 | 내용 |
|---|---|
| `lean_audit/JaebaemanAudit.lean` | 5 theorem Lean 4 standalone (0 sorry) |
| `lean_audit/lakefile.toml` | lake config |
| `lean_audit/lean-toolchain` | `leanprover/lean4:v4.29.1` |

### Lessons + Findings

| 파일 | 내용 |
|---|---|
| `lessons/INDEX.md` | lesson 인덱스 |
| `lessons/lesson-jaebaeman-paper-track-grounding-2026-05-12.md` | 본 시공 회고 |
| `_findings/INDEX.md` | raw findings dump 인덱스 |
| `_findings/raw/` | Phase 4 결과 jsonl (큰 cycle 시 자동 생성) |

---

## 2. 권장 읽기 순서

### 처음 보는 사람

1. `SOURCES.md` — 1차 소스 + 6 axis 학문 grounding
2. `ABSTRACT.md` — 5 단락
3. `jaebaeman_sop_runtime_prototype/README.md` — 작동하는 PoC
4. `AXIS_DEEP_GROUNDING.md` — μX initial algebra / Bird-Meertens fold / Sheaf / Whitehead / Smarandache / Lawvere-Tierney
5. `COMPARISON_METHODOLOGIES.md`

### 엔지니어

1. `jaebaeman_sop_runtime_prototype/README.md`
2. `jaebaeman_sop_runtime_prototype/sop_runner.py` (코드)
3. `LEAN_REGRESSION_AUDIT.md`
4. `GLOSSARY.md`

### 논문 집필자

1. `PAPER_SKELETON.md`
2. `CITATION_TABLE.md`
3. `AXIS_DEEP_GROUNDING.md`
4. `FINAL_VERDICT.md`

---

## 3. 5대 무기 가족 안에서의 위치

```
재배맨 (SOP — 4-Phase 프로토콜)
   ├─ IS slot   : SubagentSeeder  (MIC_v1.currentConcrete = "재배맨")
   ├─ 직접 소비자 : Prometheus (ResearchProvider) / Naesengmoon (AdversarialValidator) / Solve / APT-* / TPA-*
   ├─ 간접 소비자 : Longinus (KgCodeBinder) — audit cycle 측 subagent dispatch 시 4-Phase 따름
   ├─ self      : 모든 subagent 동작의 *바닥* — 5 무기 중 가장 lower-level
   └─ math      : Lean μX algebra `inductive JaebaeMan { atomic | governs }`
                  (비행기맨 #4 의 inductive type 하부)
```

12사도 #4 비행기맨의 *공학 측 결정화* 중 하나의 sibling family (Harness 와 짝).

---

## 4. 버전 사다리 (현재)

| Version | Date | Headline |
|---|---|---|
| `sv-jaebaeman-v2.3.0-2026-05-12` (CURRENT) | 본 production runtime PoC + paper-track + Lean 5 theorem | KG update pending |
| `sv-jaebaeman-v2.2.0` | Saga compensation (J3-F2) + MCP inputSchema (J4-F3) | — |
| `sv-jaebaeman-v2.1.0-2026-05-05` | SOP rebrand (MAS misnomer 정정) | — |
| `sv-jaebaeman-v2.0.0` | 4-Phase 프로토콜 정전화 | — |

# KG: ATOM_Skill_jaebaeman, sv-jaebaeman-v2.3.0-2026-05-12, jaebaeman-sop-runtime-prototype-2026-05-12

---

## 5. 한 줄 정리

**재배맨 = 4-Phase SOP. SKILL.md 정본 + Python runtime PoC + Lean 4 μX algebra 짝패.**
