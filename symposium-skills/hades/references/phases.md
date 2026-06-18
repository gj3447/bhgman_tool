# hades — Phases (per-stage responsibilities + anti-patterns)

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). KG: `hades-canonical-2026-05-27`.
> Hades verb = 실현한다 (추상→구체↓), 유레카의 dual. # src: KG hades-canonical-2026-05-27 (verb='실현한다 (구현한다)', status=CANONICAL_DELEGATED)
> materialize = engine-impl c6 "가장 위험" → every stage is a guard. # src: bhgman_tool/engine/hades/hades.py docstring

The hades engine has **two distinct pipelines** that share the realize covenant
(ACCEPTED-only / dry-run default / reversibility-first / ≤max_sites rollout):

- **KG backend** — `fetch → realize → apply` (orchestrated by `hades_runner.py`). # src: engine/hades/hades_runner.py docstring "fetch → core → apply"
- **code backend** — `scan → extract → gated-apply` (Extract-Superclass refactor). # src: engine/hades/extract_superclass.py + hades_apply.py

---

## KG backend pipeline

### Stage 1 — FETCH (select realizable abstractions)
- **Responsibility**: query KG for `AbstractClass` nodes that are `verdictStatus='ACCEPTED'` AND not yet `status='CANONICAL'` (excludes already-realized, prevents re-realization). `--concept X` narrows to one. `members = coalesce(a.extent, [])`. # src: engine/hades/hades_runner.py `_FETCH_ALL` / `_FETCH_ONE` / `fetch_accepted_cypher`
- **Anti-patterns**:
  - Realizing PROVISIONAL/REJECTED abstractions — only ACCEPTED (post eureka PROPOSE→fidelity→judgment) is eligible. # src: hades_runner.py comment "verdictStatus='ACCEPTED' …만 실현 대상"
  - Re-realizing an already-CANONICAL node (the `status <> 'CANONICAL'` filter exists to stop this). # src: hades_runner.py `_FETCH_ALL` WHERE clause

### Stage 2 — REALIZE (plan the materialization)
- **Responsibility**: per candidate, build a `MaterializationPlan` of forward `operations` + reverse `undo` ops. KG ops = `MERGE AbstractClass SET status='CANONICAL'` then `UNWIND members … MERGE (o)-[:INSTANCE_OF]->(a)`. # src: engine/hades/hades.py `realize_kg_abstraction` ops tuple
- **Guards enforced here** (all return `RealizeStatus.REFUSED`):
  - `verdict_status != 'ACCEPTED'` → REFUSED. # src: hades.py `realize_kg_abstraction` line 52
  - empty `member_names` (empty extent, nothing to realize) → REFUSED. # src: hades.py line 59
- **Anti-patterns**:
  - String-interpolating `concept_name` into Cypher — names go in as `$concept`/`$members` params (injection-safe, survives quotes in the name). # src: hades.py comment "파라미터화 cypher (injection 차단…)" + test_hades.py `test_kg_realize_uses_parameterized_cypher_no_injection`
  - The `INSTANCE_OF` op must **re-`MATCH (a:AbstractClass {name:$concept})`** — a bare `(a)` binding does not carry across the second query and would MERGE an anonymous new node (a real prior bug). # src: hades.py comment lines 65-66 + test_hades.py `test_kg_realize_instance_of_binds_named_abstractclass_not_anonymous`
  - Omitting `undo` — every plan must be reversible (KG undo = `SET status='SUPERSEDED'` + DELETE the named `INSTANCE_OF` edges; undo must be `$concept`-qualified, never a global `INSTANCE_OF` delete). # src: hades.py `undo` tuple + test_hades.py "전역 INSTANCE_OF 삭제 금지"

### Stage 3 — APPLY (write, only on explicit opt-in)
- **Responsibility**: with `apply=True` AND a real `apply_cypher` runner, execute the two ops (MERGE concept + INSTANCE_OF) and mark `APPLIED`; otherwise stay `PLANNED`. # src: hades.py lines 80-88 + hades_runner.py `run_hades` `do_write = apply and apply_cypher is not None`
- **Anti-patterns**:
  - Auto-applying — `dry_run=True` / `apply=False` is the **default**; dry-run must never write. # src: hades_runner.py docstring "dry-run 기본 … apply_cypher 없으면 절대 write 안 함" + test_hades_runner.py `test_run_hades_dry_run_default_plans_not_applies` (`apply.calls == []`)
  - Treating `apply=True` as sufficient — with no `apply_cypher` runner it stays PLANNED (c6 danger guard, can't write without a real backend). # src: hades_runner.py `run_hades` docstring + test_hades_runner.py `test_run_hades_apply_without_runner_stays_dry_run`
- **CLI degrade**: if neo4j is unavailable the CLI prints the fetch Cypher to stderr and returns 2 (no silent skip). # src: engine/cli/commands.py `cmd_hades` lines 752-762

---

## Code backend pipeline (Extract-Superclass)

### Stage 1 — SCAN (find LGG candidates)
- **Responsibility**: scan a dir/file for ≥2 classes sharing a **structurally identical** method (LGG = least general generalization). Structural identity = equal `ast.dump` (line numbers excluded), so a method matches across classes regardless of source formatting. dunder/non-shared methods are not lifted. # src: engine/hades/extract_superclass.py `common_methods` docstring + impl
- **Anti-patterns**:
  - Lifting from a single class or a near-match — requires `len(classdefs) >= 2` and **all** dumps identical (`len(dumps) == 1`); a structural mismatch yields no candidate. # src: extract_superclass.py `common_methods` (returns `[]` if <2; appends only when all dumps equal)

### Stage 2 — EXTRACT (build a real patch)
- **Responsibility**: generate a real superclass holding the lifted methods + rewrite each subclass (drop lifted methods, add base, leave `pass` if body empties) + emit a human-reviewable unified diff. `extract_superclass` (stdlib `ast.unparse`, no deps) OR `extract_superclass_cst` (libcst, format-preserving). Returns `None` if nothing to lift. # src: extract_superclass.py `extract_superclass` / `extract_superclass_cst` / `_rewrite_subclass`
- **Guards here** (in `realize_code_*`, return REFUSED):
  - `verdict_status != 'ACCEPTED'` → REFUSED. # src: hades.py `realize_code_extract_superclass` line 143
  - `len(sites) > max_sites` (default 5) → REFUSED ("점진 rollout 초과, 분산장애 위험, 배치 분할 필요"). # src: hades.py `realize_code_template` line 103 + `realize_code_extract_superclass` line 147 + test_hades.py `test_code_realize_refuses_over_max_sites`
  - no structurally-identical common method → REFUSED ("lift 불가"). # src: hades.py line 156
- **Anti-patterns**:
  - Believing `ast.unparse` preserves comments/layout — it re-emits canonically; use the libcst backend (`[hades-cst]`, `--preserve-format`) when comments/quoting must survive. # src: extract_superclass.py module docstring "정직 공시: ast.unparse는 원본 포맷/주석을 보존하지 않고…"
  - The old `realize_code_template` only emitted a **string plan** ("EXTRACT shared template …"), not real code — superseded by the ast/cst extractors. # src: extract_superclass.py docstring "이전 realize_code_template은 *문자열 plan*만 냈다"

### Stage 3 — GATED APPLY (characterization-test gate)
- **Responsibility**: the covenant defers code apply to "apply = characterization test gate 후". Write the rewrite → run the **caller-supplied** `test_cmd` → keep iff it passes (`APPLIED`), else restore the original file **byte-for-byte** (`REVERTED`); `REFUSED` if nothing to lift. Same-file classes only (base inserted before the first lifted class). # src: engine/hades/hades_apply.py `apply_extract_superclass_gated` + module docstring
- **Anti-patterns**:
  - Generic auto-refactor of arbitrary code — this is deliberately **scoped** to a repo whose tests you trust (caller supplies the exact test command). # src: hades_apply.py docstring "deliberately scoped … not a generic auto-refactor"
  - Leaving a failing gate's partial write on disk — a failing gate restores the tree exactly (reversibility-first); CLI returns 1 on REVERTED. # src: hades_apply.py "covenant: reversible" line 117 + commands.py `_cmd_hades_apply` return + test_hades_apply.py
  - CLI `--apply` without `--test-cmd` or with a multi-file `--extract-superclass` → rejected (return 2). # src: engine/cli/commands.py `_cmd_hades_apply` lines 696-702

---

## Cross-cutting covenant (applies to every stage)

| Guard | Where enforced | Source |
|---|---|---|
| ACCEPTED only (no PROVISIONAL/REJECTED) | FETCH filter + REALIZE/EXTRACT REFUSE | hades_runner.py `_FETCH_*`; hades.py lines 52, 143 |
| dry-run default (PLANNED, no auto-apply) | APPLY (KG) / GATED-APPLY (code) | hades_runner.py `do_write`; hades.py code path "항상 dry-run PLANNED" line 116 |
| reversibility-first (every plan has `undo`) | REALIZE / EXTRACT plan build | hades_models.py `MaterializationPlan.undo`; hades.py undo tuples |
| ≤max_sites (default 5) progressive rollout | REALIZE / EXTRACT guard | hades.py lines 103, 147 |
| boundary: realize ≠ discover (eureka) / ≠ dispatch (재배맨) / ≠ scaffold (harness) | identity | KG hades-canonical-2026-05-27 (boundary_vs_eureka / boundary_vs_jaebaeman / boundary_vs_harness); SKILL.md "What NOT To Do" |

---

## References
- `../SKILL.md` (protocol; engine is canonical)
- Engine: `bhgman_tool/engine/hades/{hades,hades_runner,hades_apply,extract_superclass,hades_models}.py` + `tests/`
- CLI: `bhgman_tool/engine/cli/{parser.py,commands.py}` (`hades` verb)
- THEORY: `SYMPOSIUM/THEORY/하데스/INDEX.md`
- KG: `hades-canonical-2026-05-27`, `eureka-canonical-2026-05-26` (dual), `consensus-eureka-engine-impl-2026-05-26` (c6 materialize danger)

# KG: hades-canonical-2026-05-27, eureka-canonical-2026-05-26, consensus-eureka-engine-impl-2026-05-26
