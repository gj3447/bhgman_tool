# Longinus (롱기누스) — 공학 측 자료집

> **한 줄 정의:** *참조의 미학.* KG 의미 계층 ↔ source code 의 양방향 관통 — 7 Layer Reference Model + BX Lens Laws + 5 drift types + GED 정량 + Reverse Orphan Scan. 5무기 family `IS=KgCodeBinder` slot.
>
> *공학 측 정전 둥지.* 신화 측은 `METAHUMOTONIC/BHGMAN/longinus/SOURCES.md` (Holy Lance 위상).

---

## 0. 본 폴더의 위치

| 파일 | 본질 |
|---|---|
| 본 파일 (`SOURCES.md`) | 1차 소스 + 7 axis 학문 grounding |
| `INDEX.md` | navigation |
| `ABSTRACT.md` ~ `LEAN_REGRESSION_AUDIT.md` | 9 paper-track |
| `longinus_drift_audit_prototype/` | Python 3.11+ runtime (58 pytest PASS) |
| `lean_audit/` | Lean 4 v4.29.1 standalone (19 theorem, 0 sorry) |
| `PROM_32_REPORT.md` + `PROM_32_axis_findings/` | legacy cycle |
| `lessons/`, `_findings/raw/` | 회고 + raw dump |

---

## 1. 핵심 주장 (논문 골격용 6 주장)

1. **참조는 단일 개념이 아니라 7-Layer Reference Model bundle** (v3 신규).
2. **`# KG: lesson-xxx` 한 줄의 미학적 정당화** — Kolmogorov 압축 + 7 layer 동시 운반 (L6 + L7).
3. **BX Lens Laws** (Foster-Pierce-Walker 2007 POPL): GetPut / PutGet / PutPut. 양방향 변환의 형식 근거.
4. **5 drift types = lens law violation** 의 *surjective* 매핑 (T3 Lean 정리).
5. **GED Drift 정량화** (Sanfeliu-Fu 1983 / Riesen-Bunke 2009 bipartite Hungarian).
6. **Frege Sinn ↔ Bedeutung non-collapse** (T6 Lean): `sourceId` = Sinn, `sourcePath` = Bedeutung — 2-field structure 의 형이상학적 정당성.
7. **3-tier confidence enum 정전화 (2026-05-13 graphify 흡수)**: `EXTRACTED` / `INFERRED` / `AMBIGUOUS` — 모든 ReferenceSite edge 의 필수 confidence axis. `AMBIGUOUS` 가 unique human-verdict gate (T1 Lean). SYMPOSIUM `:PRELIMINARY` 라벨 + `user_verdict_trigger_required=true` 와 의미 직결. KG: `longinus-confidence-schema-3tier-2026-05-13`.

---

## 2. 1차 소스

### 2.1 공학 정본

| 경로 | 내용 |
|---|---|
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/longinus/SKILL.md` | **정본 v3.2.** 7-Layer / BX Lens / Refinement Types / GED / Reverse Orphan |
| `/Users/lagyeongjun/CD/SERVER/06_KNOWLEDGE-GRAPH/LONGINUS_README.md` | KG side README |
| `/Users/lagyeongjun/CD/SERVER/06_KNOWLEDGE-GRAPH/LONGINUS_OPERATIONAL_GUIDE.md` | 운영 가이드 |
| `/Users/lagyeongjun/CD/SERVER/06_KNOWLEDGE-GRAPH/CATEGORICAL_FORMALIZATION_LONGINUS.md` | 범주론적 형식화 |
| `/Users/lagyeongjun/CD/SERVER/06_KNOWLEDGE-GRAPH/README_LONGINUS_88_COMPLETE.md` | 88-lens 종결 보고 |
| `/Users/lagyeongjun/CD/SERVER/06_KNOWLEDGE-GRAPH/README_LONGINUS_88_SECOND_VERDICT.md` | 88-lens 2차 판정 |
| `/Users/lagyeongjun/CD/SERVER/06_KNOWLEDGE-GRAPH/LONGINUS_88_SECOND_VERDICT_REPORT.md` | 2차 판정 상세 |
| `/Users/lagyeongjun/CD/SERVER/06_KNOWLEDGE-GRAPH/findings_reference_composition_2026-04-15.md` | 참조 합성 findings |

### 2.2 본 SYMPOSIUM 측 PoC

| 경로 | 내용 |
|---|---|
| `THEORY/LONGINUS/longinus_drift_audit_prototype/` | Python 3.11+ (58 pytest PASS) |
| `THEORY/LONGINUS/longinus_drift_audit_prototype/audit_runner.py` | `LonginusAudit` orchestrator |
| `THEORY/LONGINUS/longinus_drift_audit_prototype/bx_lens.py` | `Lens` 클래스 + 3-laws verifier |
| `THEORY/LONGINUS/longinus_drift_audit_prototype/drift_detector.py` | 5 drift type 분류기 |
| `THEORY/LONGINUS/longinus_drift_audit_prototype/ged_metric.py` | GED + severity |
| `THEORY/LONGINUS/longinus_drift_audit_prototype/reverse_orphan_scan.py` | v3.1 Code→KG blind-spot |
| `THEORY/LONGINUS/lean_audit/LonginusAudit.lean` | Mathlib-free Lean 4 (19 theorem, 0 sorry) |

### 2.3 산업 측 흡수 자료 (2026-05-13)

> *SYMPOSIUM TPA 5-drift audit (`tpa-5drift-audit-3-targets-2026-05-13`) 결과 3 외부 oss 의 흡수 가치 평가 후 결정화.* `SYMPOSIUM/GIT/` 둥지에 cloned (depth=1). 정전 격상은 사용자 verdict 게이트 (현재 :PRELIMINARY).

| 흡수 항목 | 산업 instance | TPA Mirror 강도 | SYMPOSIUM 적용 위치 | KG 결정화 |
|---|---|---|---|---|
| **3-tier confidence enum** (`EXTRACTED` / `INFERRED` / `AMBIGUOUS`) | **graphify** (safishamsi) `graphify/ARCHITECTURE.md` L40-66, `validate.py` schema enforcement | **STRONG_MIRROR_CANDIDATE** (confidence axis 1:1 의미 매칭) | 7-Layer Reference Model 의 confidence axis 정전화. `:PRELIMINARY` 라벨 정전과 직결. | `longinus-confidence-schema-3tier-2026-05-13` (:ConfidenceSchema:Canonical) |
| **3-tier confidence (float-scored variant)** | **code-review-graph** (tirth8205) edge confidence row in README + `graph.py` SQLite schema | PARTIAL (float vs enum, 시그니처 차이) | 위와 같은 위치, secondary instance | 위 노드의 `industry_instance_partial` 필드 |
| **sha256 drift detection daemon 패턴** (TOML config + 30s health check + child process auto-restart + TOCTOU-safe atomic read-hash-parse) | **code-review-graph** `crg-daemon` (`code_review_graph/daemon.py`, `daemon_cli.py`) + multi-repo watch.toml | DAEMON_IMPLEMENTATION (Longinus daemon 의 실제 구현 first-instance) | Longinus L4 (Crate-level) + L5 (ReferenceSite drift) + L6 (sha256 baseline) 측 daemon 구현 | `longinus-drift-daemon-pattern-2026-05-13` (:DaemonPattern:Canonical) |
| **Goodhart antipattern** (negative lesson, contrast case) | **ruflo** (ruvnet) "84.8% SWE-Bench" / "32% token reduction" / 100+ agent enumeration. Contrast: code-review-graph 의 honest limitations section + token budget discipline (≤5 tool calls, ≤800 tokens) = correct handling. | NEGATIVE_LESSON | Naesengmoon LensSet + 5무기 family ErrorPattern 측 적재. Goodhart 1975 / Strathern 1997 정전 grounding. | `errorpattern-goodhart-metric-optimization-marketing-2026-05-13` (:ErrorPattern:Negative5WeaponLesson) |

**Lean 4 형식화**: `MIND/lean_formalization/Longinus_ConfidenceSchema_GraphifyAbsorbed.lean` (Mathlib-free standalone, 7 theorem: T1 ambiguous_unique_human_gate / T2 sinn_bedeutung_non_collapse / T3 trust_strict_order / T4 bx_getput (Foster-Pierce-Walker 2007) / T5 bx_putget / T6 ambiguous_in_list_forces_preliminary / T7 goodhart_safeguard_confidence_not_scalar). **빌드 verification pending** — proof 모두 `decide` / `rfl` / `cases` 만 사용, 다른 SYMPOSIUM Mathlib-free Lean 4.30.0-rc2 패턴 따름.

**TPA 5-drift audit 정전**: `tpa-5drift-audit-3-targets-2026-05-13` (:ValidationResult). per-target Missing/Orphan/SigMismatch/PatternDiv/LabelRot 15 finding. Lakatos 판정: code-review-graph PROGRESSIVE ★ > graphify PROGRESSIVE_CONDITIONAL > ruflo DEGENERATING.

**Provenance**: SYMPOSIUM/GIT/CATALOG.md L1 location 3 repo 등록 (2026-05-13). User direct utterance "d" 위임 (3 absorption 일괄 한 sprint).

### 2.3 신화 측

| 경로 | 내용 |
|---|---|
| `/Users/lagyeongjun/CD/MIND/metahumotonic/` | Holy Lance / 십자가 의 예수를 찌른 창 |
| `METAHUMOTONIC/BHGMAN/longinus/SOURCES.md` | BHGMAN 측 신화 자료집 |

---

## 3. 핵심 인용

### 3.1 SKILL.md

> **롱기누스의 창이 관절을 관통하듯, KG의 의미 계층 사이사이를 소스코드 참조로 꿰뚫는다.**
> Span → Twin → Contract → SourceCode — 어느 층에서 시작하든 코드까지, 코드에서 어느 층까지든 추적 가능.

> **최소 엔트로피로 최대 의미를 관통한다.**
> `# KG: lesson-xxx` 한 줄이 아름다운 이유 — 7개 의미 층위를 동시에 관통하기 때문이다.

### 3.2 Foster-Pierce-Walker 2007

> *A lens has a structure for both forward and reverse transformations satisfying GetPut and PutGet laws.*
> (TOPLAS 29(3) Article 17)

### 3.3 Frege 1892

> *In dem Sinne aber liegt die Art des Gegebenseins.*
> (Sinn 은 *주어지는 방식* 을 담는다 — Bedeutung 과 다르다)

본 prototype 2-field structure (`sourceId` + `sourcePath`) 의 정확 grounding.

---

## 4. 학문 정전 정확 인용 (7 axis)

상세는 `AXIS_DEEP_GROUNDING.md`. 본 절은 path 만.

### 4.1 A. BX Lens Laws
- **Foster, Pierce, Walker 2007** *Combinators for bi-directional tree transformations* — ACM POPL / TOPLAS 29(3) Article 17.
- **Bohannon-Pierce-Vaughan 2006** *Relational Lenses* — PODS.

### 4.2 B. GED
- **Sanfeliu-Fu 1983** *IEEE Trans. SMC* 13(3):353.
- **Riesen-Bunke 2009** *Image and Vision Computing* 27:950.

### 4.3 C. W3C PROV-DM
- **W3C 2013** *PROV-DM Recommendation*.

### 4.4 D. SLSA
- **slsa.dev 2022+** (Google).

### 4.5 E. Frege Sinn/Bedeutung
- **Frege 1892** *Über Sinn und Bedeutung* — Zeitschrift für Philosophie 100:25-50.

### 4.6 F. Yoneda Lemma
- **Yoneda 1954** (formalized later via Mac Lane).
- **Mac Lane 1971** *Categories for the Working Mathematician* Springer GTM 5, III.2.

### 4.7 G. Cellular Sheaf
- **Hansen-Gebhart 2020** *Sheaf Neural Networks* — NeurIPS Workshop.

---

## 5. Industry 비교 (10 방법론)

→ `COMPARISON_METHODOLOGIES.md` §1.1~1.5 + §2 차별 점수.

Longinus 만이 5축 (KG↔Code / 7-Layer / BX 3-laws / Drift quant / Lean) 모두 hard-positive.

---

## 6. 논문 작성 시 발전 가능 축 (6)

- **(a) 7 layer 정확히 무엇인가** — SKILL.md 하단 분해 자체가 논문 한 편.
- **(b) BX Lens 도메인 이식** — DB BX (Foster) → KG↔code.
- **(c) GED metric design** — uniform cost vs weighted, threshold 결정.
- **(d) 신화 측면** — 롱기누스의 창: *상처가 의미를 만든다* — drift 자체가 의미적 연결의 증거 역설.
- **(e) Space Girl 동형성** — 경계 횡단의 두 변종 (존재 층 vs 의미 층).
- **(f) 사도 아닌 도구** — 12사도 측 부재, 5무기 측 hard-positive.

---

## 7. 신화 측 짝패 cross-ref (BHGMAN)

`BHGMAN/longinus/SOURCES.md` 의 *형식적 grounding — 7 axis* 섹션:

- A. BX Lens Laws (Foster-Pierce-Walker POPL 2007)
- B. GED (Sanfeliu-Fu 1983 / Hungarian bipartite Riesen-Bunke 2009)
- C. W3C PROV-DM (6 relations)
- D. SLSA L1-L4
- E. Frege Sinn vs Bedeutung (1892)
- F. Yoneda Lemma (1954) — Hom(A,-) ≅ F(A)
- G. Sheaf-theoretic foundation (Hansen-Gebhart 2020 cellular sheaf)

→ 신화 측 ↔ 공학 측 *짝패*. KG: `formal-grounding-longinus-bhgman-2026-05-09`.

---

## 8. KG 정전 노드

| 노드 | 의미 |
|---|---|
| `ATOM_Skill_longinus` | anchor |
| `sv-longinus-v3.2.0` | 이전 정전 |
| `sv-longinus-v3.2.1-2026-05-12` | 신버전 (본 grounding, PENDING) |
| `longinus-hardening-master-plan-2026-05-06` | hardening plan — COMPLETE_FINAL_PLATEAU (→ GROUNDED PENDING) |
| `longinus-drift-audit-prototype-2026-05-12` | 본 PoC anchor (PENDING write) |
| `longinus-lean-audit-2026-05-12` | Lean audit anchor (PENDING write) |
| `formal-grounding-longinus-bhgman-2026-05-09` | 신화 측 7 axis grounding |
| `MIC_v1` | 5 무기 통합 계약 |
| `MethodologySlot:KgCodeBinder` | 본 무기 slot (IS) |
| `MethodologySlot:SubagentSeeder` | 간접 의존 slot (audit→fix lifecycle 측) |

## 9. Prometheus 의 KG-supplier 관계 (closure)

Longinus 의 `ReferenceSite (sourceId, sourcePath)` 의 *대량 공급자* = Prometheus 의 `FullFindingRecord.sourceKgBindings` 필드. 즉 Prometheus 가 만든 ResearchFinding 의 KG 노드들이 Longinus 의 검증 대상이 된다.

**SKILL.md prometheus L893** 정확 인용:
> 롱기누스: 프로메테우스가 구축한 KG를 코드까지 관통

**SKILL.md prometheus L533** (프랙탈 순환의 닫힘):
> 프로메테우스 → (재배맨/RAG + 롱기누스/실측) → edge data → 하네스↔나생문 GAN → 검증된 씨앗

→ KG: `(ATOM_Skill_prometheus)-[:FEEDS_BINDING]->(ATOM_Skill_longinus)` + `(ATOM_Skill_longinus)-[:VERIFIES_KG_OF]->(ATOM_Skill_prometheus)` (역방향)
→ Prototype: `(prom-cycle-runtime-prototype)-[:FEEDS_KG_FOR_BINDING]->(longinus-drift-audit-prototype)`
→ Schema: `schema-prom-long-isomorphism-2026-05-12` — `FullFindingRecord.sourceKgBindings` ↔ `ReferenceSite.sourceId` 1:1 (Frege L4 Sinn 보존)

---

## 10. 재배맨/SOP 와의 관계

Longinus 자체는 *측정 도구* — `audit_runner.LonginusAudit.run_full()` 은 7-Layer / 5 drift / GED / Reverse Orphan 측정만 수행하고 KG/코드를 변경하지 않는다. 단 측정 결과로 *fix* subagent 출격이 필요할 때 (예: Missing drift 발견 → KG ref 생성 subagent 발화, Orphan drift → 코드 patch subagent 발화):

- **재배맨 4-Phase 따름** (Seed → Dispatch → Collect → Write)
- `failure_mode='saga_compensate'` 사용 시 partial-failure 복구
- `idempotency_key` 활용한 dedup

→ KG: `(ATOM_Skill_longinus)-[:USES_SLOT {dependency:'indirect-via-audit-cycle'}]->(MethodologySlot:SubagentSeeder)`
→ `(longinus-drift-audit-prototype-2026-05-12)-[:CONSUMES_SOP {dependency:'indirect-via-audit-cycle'}]->(jaebaeman-sop-runtime-prototype-2026-05-12)`

# KG: ATOM_Skill_longinus, sv-longinus-v3.2.1-2026-05-12
