# APT Progress: bhgman_tool

## Anchor: sa-bhgman_tool-ruflo-utility-parity-2026-05-13
## Domain: tool-layer-engineering
## Status: active
## Last Updated: 2026-05-31 (full refresh — 122-commit drift 정정, 17-engine Wave 반영)
## Context Budget: total=100K, per_span=8K
## APT version: v26.1
## Work kind: EXTEND

> **2026-05-31 정정**: 본 문서가 2026-05-17(Wave 11)에서 멈춘 채 122커밋 동안 stale였음.
> "CLI 없음 / 268 pytest / manual cp" 등 옛 Honest Limitations는 *이미 해소된 걸 미해소로* 적은 역방향 drift였음.
> Longinus 관점 = code↔doc drift. 아래로 현재 실측 동기화.

---

## 현재 상태 실측 (2026-05-31)

| 항목 | 값 (실측) | 소스 |
|---|---|---|
| `bhgman-tool` CLI | **존재** (`pyproject [project.scripts] = engine.cli.main:cli`) | venv 설치됨 |
| pytest collected | **910** (working tree) | `pytest --co` (README는 891 — 약간 stale) |
| engine 모듈 | **17** (아래) | `ls engine/` |
| Lean | 7 theorem `sorry=0` (standalone) + Mathlib sister 12 | README badge |
| 최근 Wave | 2026-05-19 → 05-31 (17-engine buildout) | git log |

### engine/ 17 모듈 (Wave 11 이후 신설 다수)

`cli` · `mcp_server` · `longinus_drift_audit`(31 test) · `longinus_drift` · `eureka`(15) · `legion`(7) · `kg_local`(5) · `occam`(4) · `hades`(4) · `code_to_kg`(4) · `agents`(4) · `resolver`(2) · `gate`(2) · `naesengmoon`(1) · `harness`(1) · `memory`(1) · `provexport`(1)

> **7군단장 실엔진화 완료** (memory `project_bhgman_7commanders_real_engines_2026_05_28`): 4 KG-엔진(occam/eureka/hades/longinus, `--local`로 neo4j 0) + 3 LLM-엔진(prom/tlb/재배맨). worked/04-falsifier-click = 실제 OSS(pallets/click) 대상 falsifier.

---

## Wave 요약 (시간순, 완료분 압축)

| Wave | 기간 | 핵심 산출 | 비고 |
|---|---|---|---|
| Phase 1-2 | ~05-13 | seed v0.1 + buildout + i18n 4-lang + 5 paper + CI skeleton | commits 7e906c4~0127b3e |
| Phase 3 + Wave 7 | 05-13~14 | CLI 7 verbs / MCP 9 tools / longinus sha256 baseline + forward orphan / resolver+gate (RFC A6.1/A7, 23 pytest) / Mathlib sister (sorry 19→0) / CI-CD 4 workflow | `span-bhgman-*-wave7-2026-05-14` ×7 |
| Wave 11 | 05-17 | pre-commit 4-ratchet local gate (ruff/complexipy/deptry/pytest/lychee) | `lesson-bhgman-tool-quality-ratchet-drift-2026-05-17` |
| **17-engine** | **05-19~31** | **7군단장 실엔진화** (occam/eureka/hades/longinus KG-엔진 + prom/tlb/재배맨 LLM-엔진) · PROM-8 naesengmoon decorrelation(n_eff) · PROM-16 instrument+Bayesian MAP+CUSUM+threshold derivation · libcst Hades + true-Leiden Eureka · longinus structural SigMismatch · A/B falsifier 실측 · dgx vLLM/ollama backend | 122 commits, feat 50 |

> 상세 per-commit = `git log`. Wave 7 verbose 행들은 본 압축으로 대체 (working-set diet, KG = 정본).

### 17-engine Wave 핵심 lesson (memory 정전)

- **A/B falsifier 실측** (`project_bhgman_ab_falsifier_2026_05_30`): longinus drift 엔진 vs base LLM, 도구예산 통제 후 **cognitive 우위 0**. 가치는 operational(scale·재현성·audit)뿐. "현미경" 재배치 확증.
- **self-critique balanced** (`project_bhgman_self_critique_2026_05_28`): self-citation loop / 재발명 비율 높음(통합력은 진짜, 신규 원리 적음) / 메타-방법론 LOC 50%+ / 외부 임팩트 미측정.
- **비동기 결과 확인 후 문서화** (`feedback_verify_async_results_before_writeup`): OQ8/9/10 stale·corrupted read 3회 자기적발.

---

## Honest Limitations (2026-05-31 정정 — 옛 항목 전부 stale였음)

| 옛 limitation (Wave 11) | 현재 |
|---|---|
| ~~`bhgman-tool` CLI 없음~~ | **해소** — pyproject scripts + venv 설치 |
| ~~manual `cp -R skills/*` 필요~~ | **해소** — `install-skills` verb |
| ~~268 pytest~~ | **910 collected** |

### 진짜 현재 limitation (2026-05-31 Longinus 실측)

1. **engine/ ~1443 코드 심볼이 KG ReferenceSite 미바인딩** — 17-engine Wave가 Longinus 바인딩 없이 쌓임 (`feedback_bind_concept_to_source_at_creation` float 증상). `--record-signatures` 결과 0 recorded = 묶을 ReferenceSite 자체가 없음.
2. **Longinus audit 노이즈가 architectural** — bhgman·SYMPOSIUM·SERVER가 **같은 dgx neo4j DB 공유** → bhgman code-root만 audit하면 타 repo ReferenceSite가 Orphan(518 중 다수)으로, 타 repo skill baseline이 sha256 drift(78)로 잡힘. baseline 재초기화로 안 풀림 — code-root별 repo-tag 필터가 필요 (engine 미노출, 후속 작업).
3. **README 수치 drift** — 891 collected claim vs 실측 910 (badge 306은 longinus 서브셋). 다음 commit에서 reconcile 권장.

---

## Next Steps

1. **engine/ Longinus 바인딩** (limitation #1, 본령) — 17 engine 심볼 → ReferenceSite 7-tuple. 바인딩 후에야 signature/sha256 baseline 재초기화가 의미 가짐.
2. **audit repo-scope 필터** (limitation #2) — `audit_runner`에 `--repo-tag` 추가, 공유 KG에서 bhgman ReferenceSite만 audit.
3. **README 수치 reconcile** (limitation #3) — 891→910, badge 통일.

# KG: sa-bhgman_tool-ruflo-utility-parity-2026-05-13, project_bhgman_7commanders_real_engines_2026_05_28, project_bhgman_ab_falsifier_2026_05_30, lesson-concept-nodes-created-without-longinus-binding-float-2026-05-29
