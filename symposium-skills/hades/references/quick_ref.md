# hades — Quick Reference

> Lazy-load cheatsheet. Parent: [`../SKILL.md`](../SKILL.md). KG: `hades-canonical-2026-05-27`.
> 동사 = **실현한다** (추상→구체↓). 유레카(구체→추상↑)의 dual. 비행기맨 #4 7번째 군단장.

---

## 1. One-liner

ACCEPTED 추상(spec/Contract/개념)을 *구체 KG 구조 + 소스코드*로 materialize한다. TDD GREEN.
materialize = engine-impl c6 **"가장 위험"** → dry-run 기본 + ACCEPTED만 + reversible + ≤5 site.
# src: SKILL.md frontmatter L7-16, hades.py docstring L1-26, README.md

---

## 2. Invocation

| form | meaning | src |
|------|---------|-----|
| `/hades <concept>` | ACCEPTED 추상 1개 realize (자연어 트리거) | SKILL.md L11 |
| `bhgman-tool hades` | 모든 ACCEPTED 추상 fetch→realize (dry-run) | parser.py L169-208 |
| `bhgman-tool hades --concept X` | AbstractClass X 한 개만 | parser.py L173-175 |
| `bhgman-tool hades --apply` | 실제 write (omit = dry-run, c6 가드) | parser.py L176-180 |
| `bhgman-tool hades --local` | neo4j-free local KG (`~/.bhgman/kg.json`) | parser.py L181-185 |
| `bhgman-tool hades --extract-superclass PATH` | code mode: 디렉터리/파일 스캔→superclass patch (PLAN only) | parser.py L186-191 |
| `... --preserve-format` | libcst 백엔드 (주석/레이아웃 보존, `[hades-cst]` dep) | parser.py L192-196 |
| `... --show-patch` | 각 후보의 full unified diff 출력 | parser.py L197-201 |
| `... --extract-superclass FILE --apply --test-cmd 'pytest …'` | gated code apply (characterization test 통과 시만 keep) | parser.py L202-207, hades_apply.py |

**neo4j 부재 시**: write 안 하고 ACCEPTED-fetch cypher를 stdout으로 출력, exit 2.
# src: commands.py L750-762

---

## 3. Cycle (realize)

엔진 정본 = `bhgman_tool/engine/hades/hades.py`. SKILL은 프로토콜만.

**KG backend** — `realize_kg_abstraction(concept, verdict_status, member_names, dry_run=True)`:
- 가드: `verdict_status != 'ACCEPTED'` → `REFUSED`; `member_names` 비면 `REFUSED` (empty extent).
- ops: `MERGE (a:AbstractClass) SET status='CANONICAL', realizedBy='hades'` + `UNWIND members → (o)-[:INSTANCE_OF]->(a)`.
- undo: concept→`SUPERSEDED` + `INSTANCE_OF` edge DELETE (reversibility-first covenant).
- dry_run=True → `PLANNED` 반환 (write 없음). `dry_run=False` + `apply_cypher` 주입 → `APPLIED`.
# src: hades.py L40-88, hades_models.py

**Code backend** — `realize_code_template / realize_code_extract_superclass`:
- 가드: `len(sites) > max_sites(=5)` → `REFUSED` (분산 장애 차단); `verdict!='ACCEPTED'` → `REFUSED`.
- 구조 동일 공통 메서드(LGG) 없으면 → `REFUSED` ("lift 불가").
- `realize_code_template`은 **항상 dry-run `PLANNED`** — 실제 apply는 characterization test gate 후 별도 절차.
# src: hades.py L91-181, extract_superclass.py

**End-to-end runner** — `run_hades(run_cypher, apply_cypher=None, concept=None, apply=False)`:
- fetch: `verdictStatus='ACCEPTED' AND (status IS NULL OR status<>'CANONICAL')` (이미 CANONICAL=재실현 방지).
- `apply=True`라도 `apply_cypher`가 None이면 write 불가 → `PLANNED` 유지 (c6 차단).
- occam_runner와 대칭 (fetch → core → apply).
# src: hades_runner.py L23-88

---

## 4. RealizeStatus / verdict types

| status | 의미 | src |
|--------|------|-----|
| `PLANNED` | dry-run 계획만 (기본) | hades_models.py L13 |
| `REFUSED` | 가드 위반 (non-ACCEPTED / empty extent / >max_sites / no LGG) | hades_models.py L14 |
| `APPLIED` | 실제 실현됨 (`dry_run=False` + apply) | hades_models.py L15 |

- `MaterializationPlan(concept, kind∈{'kg','code'}, operations, undo, reversible=True)` — 모든 plan에 역연산.
- `RealizeVerdict(concept, status, plan, reason, applied=False)`.
- `GatedApplyResult(status∈{APPLIED|REVERTED|REFUSED}, reason, test_returncode)` — gated code apply.
# src: hades_models.py L18-36, hades_apply.py L29-32

---

## 5. The 4 guards (covenant)

1. **ACCEPTED만** — PROVISIONAL/REJECTED 거부 (유레카 PROPOSE→fidelity→judgment→ACCEPTED 후에만). # src: hades.py L52-58
2. **dry_run 기본** — PLANNED만 방출, auto-apply 금지; apply는 명시(`--apply`) + 검증 후. # src: hades_runner.py L58-71
3. **reversibility-first** — 모든 plan에 undo (KG=supersede / code=inline-back). gated apply 실패 시 byte-for-byte restore. # src: hades.py L74-77, hades_apply.py L117
4. **≤5 site 점진 rollout** — code materialize 초과 시 `REFUSED` (분산 장애 차단). # src: hades.py L103-109

---

## 6. Key files

| file | role | src |
|------|------|-----|
| `engine/hades/hades.py` | 코어 — realize_kg_abstraction / realize_code_template / realize_code_extract_superclass | 본체 |
| `engine/hades/hades_runner.py` | fetch ACCEPTED → realize e2e (orchestration) | |
| `engine/hades/hades_models.py` | RealizeStatus / MaterializationPlan / RealizeVerdict | |
| `engine/hades/extract_superclass.py` | 진짜 Extract-Superclass (stdlib ast LGG + libcst format-preserving) | |
| `engine/hades/hades_apply.py` | characterization-test-gated apply (libcst) | |
| `engine/cli/commands.py` | `cmd_hades` (L746) + `cmd_hades_extract_superclass` (L715) | |
| `engine/cli/parser.py` | `hades` subparser (L169-208) | |
| `SKILLS/hades/SKILL.md` | 프로토콜/경계 정전 | |
| `THEORY/하데스/INDEX.md` | identity + 탄생 경위 + dual 표 (62 lines, thin) | |

---

## 7. Boundaries (bright-line)

- **vs 유레카**: 유레카=추출·귀납·발상(↑, Galois α/catamorphism). 하데스=실현·연역·벼림(↓, Galois γ/anamorphism). 같은 수직축 정반대. # src: SKILL.md L24, INDEX.md §3
- **vs 재배맨**: 재배맨=출격(누가 일할지 분배). 하데스=실현(실제 코드 써냄). 분배 ≠ 써냄. # src: SKILL.md L25, KG boundary_vs_jaebaeman
- **vs 하네스**: 하네스=바닥/場(수동 scaffold). 하데스=그 場에 써내리는 능동 행위. **同一 존재 두 측면** (정식명=하네스, 별칭=하데스, 둘 다 동작; INDEXED_PAIR (Place, Realize-Action)). # src: SKILL.md L26, KG formal_status / unified_entity=true

---

## 8. Measurement & conditional dispatch (2026-05-30)

고정 USES edge retract → measurement-driven conditional dispatch. `HadesMeasurement(CommanderBase)`:

| metric | scale | threshold → dispatch | src |
|--------|-------|----------------------|-----|
| `spec_ambiguity_score` | interval | `>0.5` → **eureka** (추가 추상화 필요) | measurement.py L536-543, 620 |
| `TDD_GREEN_failure_count` | ratio | `>3` → **prometheus** (외부 지식 필요) | measurement.py L544-551, 621 |
| `binding_completeness` | ratio | `<0.7` → **longinus** (binding 필요) | measurement.py L552-559, 622 |

# src: SKILL.md L70-90, measurement.py L531-560, thresholds.toml L93-100, KG 7cmd-measurement-driven-conditional-dispatch-2026-05-30

---

## 9. Gotchas

- **op1 재-MATCH 버그 history**: KG realize op1은 op0의 `(a)` 바인딩이 안 넘어옴 → `AbstractClass`를 재-MATCH 해야 함 (옛 bare `(a)`는 익명 신규 노드 MERGE 버그). 파라미터화 cypher = injection + 따옴표 안전. # src: hades.py L64-73
- **재실현 방지**: runner fetch가 `status<>'CANONICAL'`로 이미 실현된 것 제외. # src: hades_runner.py L23-32
- **code apply는 절대 자동 아님**: `realize_code_template`은 status를 무조건 PLANNED로 hardcode; 실 디스크 write는 `hades_apply` gated path (caller가 `--test-cmd` 명시)로만, 그것도 self-refactor용 (테스트 신뢰하는 repo 한정, e.g. bhgman_tool pytest). # src: hades.py L116-122, hades_apply.py L1-15
- **ast.unparse 포맷 손실**: 기본 extract_superclass는 canonical 재출력 (주석/포맷 미보존). 보존하려면 `--preserve-format` (libcst, optional dep). # src: extract_superclass.py L11-15
- **same-file only (gated apply)**: `apply_extract_superclass_to_module`은 base class를 첫 lifted class 앞에 삽입 — 같은 파일 클래스만. # src: hades_apply.py L13-14
- **neo4j 없으면 exit 2**: write 안 하고 fetch cypher만 출력 (parent Claude MCP로 실행하거나 `--local`). # src: commands.py L756-762

---

## 10. References

- `../SKILL.md`
- KG: `hades-canonical-2026-05-27` (CANONICAL_DELEGATED, INDEXED_PAIR formal_status), `eureka-canonical-2026-05-26` (dual), `consensus-eureka-engine-impl-2026-05-26` (c6 materialize danger), `bihaenggiman-harness-demoted-3layer-2026-05-27`, `7cmd-measurement-driven-conditional-dispatch-2026-05-30`
- THEORY: `../../../THEORY/하데스/INDEX.md`
- 사이블: `../longinus/references/theory.md` (binding lens — dispatch target)

# KG: ATOM_Skill_hades, hades-canonical-2026-05-27, eureka-canonical-2026-05-26 (dual)
