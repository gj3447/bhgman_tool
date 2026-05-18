# 롱기누스 (Longinus) — Index

> 공학 측 정전 둥지. 신화 측은 `METAHUMOTONIC/BHGMAN/longinus/`.
> 한 줄: **참조의 미학.** KG 의미 계층 ↔ source code 의 양방향 관통 (BX Lens). 5무기 family 의 `IS=KgCodeBinder`.

---

## 0. 본 폴더의 위치

| 측면 | 위치 |
|---|---|
| **공학 측 자료집 (본 폴더)** | `THEORY/LONGINUS/` — 7-Layer + BX Lens + 5 drift + GED + Reverse Orphan |
| **공학 정본 (SKILL)** | `SERVER/.claude/skills/longinus/SKILL.md v3.2` |
| **신화 측 자료집** | `METAHUMOTONIC/BHGMAN/longinus/SOURCES.md` |
| **신화 1차** | `MIND/metahumotonic/` (롱기누스의 창 / Holy Lance) |
| **KG 운영** | `SERVER/06_KNOWLEDGE-GRAPH/LONGINUS_*.md` (88-lens 검증 + 범주론 형식화) |

---

## 1. 파일 지도

| 파일 | 내용 |
|---|---|
| `SOURCES.md` | 1차 소스 + 7 axis 학문 grounding (BX/GED/PROV/SLSA/Frege/Yoneda/Sheaf) |
| `INDEX.md` | 본 파일 |
| `ABSTRACT.md` | 5 단락 초록 |
| `PAPER_SKELETON.md` | 논문 골격 |
| `AXIS_DEEP_GROUNDING.md` | 7 axis 정확 정의 |
| `COMPARISON_METHODOLOGIES.md` | vs LSP / tree-sitter / GumTree / Bidirectional Programming / DOI / Linked Data / W3C PROV / SLSA / Source Maps / OpenTelemetry traces |
| `CITATION_TABLE.md` | 인용 표 |
| `GLOSSARY.md` | 용어집 |
| `FINAL_VERDICT.md` | verdict + 후속 sprint |
| `LEAN_REGRESSION_AUDIT.md` | Lean 4 6 theorem group audit |
| `longinus_drift_audit_prototype/` | Python 3.11+ runtime (58 pytest PASS) |
| `lean_audit/LonginusAudit.lean` | 19 theorem, 0 sorry |
| `lessons/`, `_findings/raw/` | 회고 + raw dump |
| `PROM_32_REPORT.md` + `PROM_32_axis_findings/` | legacy cycle |

---

## 2. 5무기 family 안에서의 위치

```
롱기누스 (KG↔Code 관통)
   ├─ IS slot   : KgCodeBinder  (MIC_v1.currentConcrete = "Longinus")
   ├─ USES slot : SubagentSeeder (간접 — audit cycle 측 subagent dispatch 시 재배맨/SOP 4-Phase 따름)
   ├─ 호출자    : APT SCW 단계 / TPA TCW / 모든 코드 작성 직후
   ├─ 도구      : 12사도가 아닌 5무기 中 하나 (사도 아닌 도구)
   └─ 메타포    : 롱기누스의 창 — 십자가의 예수를 관통. *상처가 의미*.
```

**재배맨 의존성**: 본 prototype 의 `audit_runner.LonginusAudit.run_full()` 은 *측정* 만 한다. 측정 결과로 drift fix subagent 출격이 필요할 때는 **재배맨 SOP 4-Phase 따름** (Seed → Dispatch → Collect → Write). 즉 *측정은 독립*, *fix 발화는 재배맨 위*.

12사도 직접 매핑 없음. 스페이스 걸(#5) 의 *경계 횡단* 과 동형 — 스페이스걸이 존재 층(network/sexvoid) 관통, 롱기누스는 의미 층(KG/code) 관통.

---

## 3. 권장 읽기 순서

1. `SOURCES.md` — 1차 소스 + 7 axis
2. `ABSTRACT.md` — 5 단락
3. `longinus_drift_audit_prototype/README.md` — 작동 PoC
4. `AXIS_DEEP_GROUNDING.md` — BX/GED/Frege/Yoneda/Sheaf
5. `COMPARISON_METHODOLOGIES.md`

---

## 4. Prometheus 와의 closure

Prometheus 가 만든 `FullFindingRecord.sourceKgBindings` 필드 = Longinus 의 `ReferenceSite (sourceId, sourcePath)` 의 *공급원*. 즉:

```
Prometheus  ─FEEDS_BINDING→  Longinus
  (KG nodes via                (검증 via 7-Layer + 5 drift)
   sourceKgBindings)
        ↑VERIFIES_KG_OF────────┘
```

**프랙탈 순환의 닫힘** (SKILL.md prometheus L533): `프로메테우스 → (재배맨 + 롱기누스) → edge data → 하네스↔나생문 → 검증된 씨앗`. 즉 Prometheus 가 KG 를 *만들고*, 재배맨이 *씨앗으로 결정화*, 롱기누스가 *코드까지 관통*, 나생문-하네스가 *적대적 검증*. 4 weapon 의 협력 lifecycle.

KG: Schema `schema-prom-long-isomorphism-2026-05-12` (hard core).

---

## 5. 한 줄 정리

**롱기누스 = 7-Layer 참조 + BX Lens Laws + 5 drift detector + GED 정량 + Reverse Orphan. SKILL.md 정본 + Python PoC + Lean 19 theorem 3중. Prometheus 의 KG-supplier closure (FEEDS_BINDING) + 재배맨 SOP 간접 의존.**

# KG: ATOM_Skill_longinus, sv-longinus-v3.2.1-2026-05-12, longinus-drift-audit-prototype-2026-05-12
