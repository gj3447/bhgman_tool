# APT Magic Number Canonical Table — v27 A6.1

> **RFC**: `rfc-apt-v26-A6.1-magic-selective-externalization-2026-04-30` (ACCEPTED 2026-04-30)
> **원칙**: Selective externalization. core declarative magic만 KG slot, context-specific magic은 prose 유지.
> **Schema**: `{symbolName, kgNodePath, defaultValue, rationale_lesson, evolvedAt_date}` 5열.

---

## I. Core Externalize (5 → KG slot)

> SKILL.md 본문에서 *직접 숫자 인용 금지*. cfg slot 참조로만 사용.

| # | symbolName | kgNodePath | defaultValue | rationale_lesson | evolvedAt |
|---|---|---|---|---|---|
| 1 | `vibe_coding_sweet_min` | `MethodologyConfig_default_v26.vibe_coding_sweet_min` | **200** | 사용자 vibe coding 검증 가능 단위 하한. AtomicSpan 한 task = 한 file 정규화 (lesson-apt-phase6-cleanup-missing-2026-04-28). | 2026-04-21 |
| 2 | `vibe_coding_sweet_max` | `MethodologyConfig_default_v26.vibe_coding_sweet_max` | **500** | 동상 상한. 초과 시 SP 재분해 강제. | 2026-04-21 |
| 3 | `lens_count_constitutional` | `LensSet_constitutional.lens_count` (참조: `MethodologyConfig.lens_count_constitutional`) | **9** | Taliban 기본 적대 검증 렌즈 수 (lesson-taliban-shortcut-antipattern-2026-04-21 — 3 lens shortcut 차단). | 2026-04-21 |
| 4 | `contract_default_fields` | `ContractSchema_default_v2.field_count` | **7** (v2 9) | Contract DTO 기본 필드 수. v2에서 9 canonical axis로 확장 (`SA_Contract_v2_DbC_Interface_2026-04-21_v2`). | 2026-04-21 |
| 5 | `st_decision_areas` | `MethodologyConfig_default_v26.st_decision_areas` | **8** | ST Cover Scope: AST/Workflow/DesignPattern/ProjectStructure/DataFlow/Algorithm/Store/ClassDesign (lesson-st-cover-scope-exhaustive-2026-04-29). Tier1 5★ + Tier3 3. | 2026-04-29 |

**SKILL.md 사용법** (apt-sp/st/scw 본문):
- ✗ "vibe coding sweet spot 200~500줄..."
- ✓ "vibe coding sweet spot `cfg.vibe_coding_sweet_min` ~ `cfg.vibe_coding_sweet_max` 줄 (현재 200~500)..."
- ✓ "Taliban `cfg.lens_count_constitutional`-lens 적대 검증 (현재 9)..."

→ 본문에 *현재 값* 괄호 표기는 reader-facing 안내 (drift 시 cfg 갱신 + 괄호 갱신). 정전은 KG.

---

## II. Prose 유지 (3 → context-specific, externalize ✗)

> 특정 cycle 결과 / 역사적 evolution / context-bound — coupling 비용 > externalization 이익.

| # | symbol | 위치 | 이유 (왜 prose 유지) |
|---|---|---|---|
| A | `96 ResearchFinding` | `lesson-st-cover-scope-exhaustive-2026-04-29` 본문 | **특정 PROM 96 사이클 결과** 수치. 다른 사이클이면 다른 N. cfg field로 굳히면 *다음 사이클이 96 따라야 한다*는 잘못된 신호. |
| B | `5/8 tier split` (Tier1=5★ + Tier3=3) | `apt-st` SKILL.md ST Cover Scope | ST decision areas 8개 *내부 우선순위 분배*. 8 자체는 cfg(`st_decision_areas`) but 5/3 분배는 *역사 evolution* — 변경 시 lesson 작성 후. |
| C | `vibe_coding_hard_max` | `apt-sp` SKILL.md SP 한계 표기 | hard max는 SP 단위 *경고/문턱* — 현재 미정 값 (1000? 무한?). 결정되기 전엔 prose 추정만. cfg field 만들면 *공식 결정* 시그널 잘못. |

**원칙**: 외부화 vs prose 결정 룰 — *다음 sprint에 다시 나타날 magic*만 외부화. *역사 결과*는 prose.

---

## III. Migration 작업 (sprint ap-skill-magic-migration, MEDIUM 2주)

`ap-prom16apt-resolver-prototype` (HIGH 3주) 완성 후 진행.

### 3.1 Pre-condition (resolver 구현 후)
- Python pre-prompt resolver(python-frontmatter + Jinja2 SandboxedEnv) 작동
- KG `MethodologyConfig_default_v27` 노드에 5 core magic field 적재
- SKILL.md `{{cfg.X}}` 마커 syntax 확정

### 3.2 변환 대상 8곳 → 5 core externalize
| 파일 | 위치 | 현재 | v27 |
|---|---|---|---|
| `apt-sp/SKILL.md` | "vibe coding sweet spot 200~500줄" | inline | `{{cfg.vibe_coding_sweet_min}}~{{cfg.vibe_coding_sweet_max}}` |
| `apt-sp/SKILL.md` | "9 lens constitutional" | inline | `{{cfg.lens_count_constitutional}} lens` |
| `apt-st/SKILL.md` | "7 default field" | inline | `{{cfg.contract_default_fields}}` |
| `apt-st/SKILL.md` | "8 decision areas" | inline | `{{cfg.st_decision_areas}}` |
| `apt-scw/SKILL.md` | (해당 magic 점검 후 mapping) | TBD | TBD |

### 3.3 변환 X — prose 유지
- `apt-st/SKILL.md` "5/8 tier split" — 그대로 prose
- `apt-sp/SKILL.md` "vibe_coding_hard_max" — 그대로 prose (TBD 표기)
- `lesson-st-cover-scope-exhaustive-2026-04-29` "96 ResearchFinding" — 그대로

### 3.4 Drift 검증
1. KG `MATCH (cfg) RETURN cfg.{vibe_coding_sweet_min, ...}` 5 field
2. `grep -c "{{cfg\." SKILL.md` ≥ 8 (각 magic 최소 한 번 참조)
3. `grep -P "\\b(200|500|9|7|8)\\b" SKILL.md` = 0 외 *괄호 안 reader-facing 안내*만 (e.g. "(현재 200)")
4. `python resolver.py --validate SKILL.md` zero error

---

## IV. Source of Truth

- **이 파일** `THEORY/APT/magic_number_table.md` = canonical 인덱스
- **KG** `MethodologyConfig_default_v27` node = runtime 정전 (resolver가 조회)
- **SKILL.md** = thin reference (`{{cfg.X}}` 마커 + 괄호 안 reader-facing 안내)

→ **3 위치 모두 변경 시 동시 갱신 의무**. drift 검증 룰 III.4 참고.

---

## V. 갱신 이력

| Date | 변경 | RFC |
|---|---|---|
| 2026-04-30 | 초안 작성 (5 core + 3 prose 분류) | rfc-apt-v26-A6.1-magic-selective-externalization-2026-04-30 ACCEPTED |

---

> **다음 라운드 hook**: SKILL.md 본문 magic 추가 발견 시 → 본 표에 row 추가 + 5/3 분류 + RFC 결정. `hook-apt-magic-table-evolution`로 KG 등록 권장.
