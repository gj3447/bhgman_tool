All confirmed. The findings are accurate against the live tree. I have enough to write the roadmap.

# bhgman_tool — Prioritized Hardening Roadmap

## 1. Honest overall verdict

bhgman_tool is **a well-engineered set of components whose orchestration layer does not deliver the system's stated essence end-to-end.** The deterministic cores are genuinely good — strong typing, DIP seams, honest stubs, ~1360 passing tests, real AST/libcst transforms, real Lean/pytest oracles, real Leiden/AMIE subprocesses, green CI/mypy/ruff. But the audit exposes a consistent pattern at every seam where a commander's *value* must actually flow into the KG or the next commander: **the wiring is missing while docstrings/tests/scoreboards claim it exists.** Five flagship pipelines are functionally dead in production (prometheus never fetches, legion never measures-to-dispatch, hades never receives an eureka-produced node, eureka kills its own best output at gate 4.5, longinus cron/daemon never persist). Several gates report PASS on REJECT/FAIL inputs, one "read-only" MCP path can mutate prod, and one destructive `occam --semantic --apply` runs on random noise. The codebase is *honest in its low-level docstrings* but *dishonest in its high-level test names and scoreboard claims*. The fix is not a rewrite — it is **wiring + gate-content inspection + a handful of honesty corrections**, and that work has very high leverage because the components it connects are already sound.

---

## 2. HONESTY RISKS — non-negotiable, do these regardless of schedule

These are cases where the tool **claims a capability or result it does not have**. Each is either a dishonest test/docstring or an over-claimed efficacy number. They must be fixed (by either delivering the capability or correcting the claim) before any new feature work, because they currently *manufacture false confidence in the audit trail itself*.

| # | [module] item | sev | the honesty fix |
|---|---|---|---|
| H1 | [eureka] `test_pipeline_runs_to_completion` passes while the pipeline halts at stage 4.5 and emits nothing | med | Rename to the truth, AND fix the gate (W1-E) so a real end-to-end test can exist. A test named "runs to completion" that green-lights a pipeline killing its own output is the single most dishonest artifact in the repo. |
| H2 | [efficacy] Headline "repair > best-of-N, p=0.016" rests on a non-deterministic run whose raw JSONL was never committed; the only test fabricates JSONL to match the published numbers | high | Until re-run + raw logs committed, **relabel the Run B numbers as "historical, raw logs lost — not authoritative"** in VERDICT.md / FAIRTEST / SWEEP_RESULTS. Do not cite a hand-typed table as a result. |
| H3 | [efficacy] SWEEP_RESULTS claims "no value is hand-authored / reproduced by the commands shown" but 7/9 scoreboard numbers need live neo4j+dgx with no committed fixtures | med | Qualify to "reproduced against the live KG snapshot on <date>"; only `scale_curve` + synthetic `Δ+0.227` reproduce offline — say so. |
| H4 | [efficacy] `dispatch_telemetry` measures error-rate but scoreboard labels it "dispatch fidelity (intent==actual) 1.000" | low | Rename to "dispatch success-rate"; keep "fidelity" explicitly UNMEASURED (the module docstring already admits this). |
| H5 | [hades] harness diagnose engine asserts axes PRESENT while its own notes label that mapping "미검증 단정 (unverified)" | low | Demote name-matched primitives to an INFERRED confidence distinct from signal-PRESENT. |
| H6 | [longinus] `nightly_drift_check.py` / `daemon.py` docstrings claim "emits :DriftCheck into the KG" / "compares with KG-stored baseline" but neither imports a KgClient or writes anything | high (covered in W1) | Either wire the write or correct the docstring — but the *claim* must die now. |
| H7 | [mcp_server] `longinus_audit` docstring claims it uses "production Pydantic models from longinus_drift_audit" — file imports only stdlib | low | Delete the false claim or actually import the package. |
| H8 | [legion] README labels `audit_prom_cycles.py` "HMAC tamper-evident audit" (zero hmac); omits half the module | low | Correct to "Stevens-scale violation scanner"; mark which layers are runtime-wired vs experimental. |

> The throughline: **every honesty risk is "a green test / confident docstring / scoreboard cell describing behavior that doesn't run."** Fixing the underlying wiring (Waves 1–2) discharges most of them; the rest are one-line label corrections that cost nothing and should ship immediately.

---

## 3. WAVES

### WAVE 1 — Correctness & honesty critical: make the essence actually run, stop silent-pass/destructive bugs

These are the highest-leverage items. They are the difference between "a tool that demonstrably acquires/binds/induces/realizes/verifies" and "a tool that prints plausible dicts." Order within the wave is annotated.

**W1-A · [mcp_server] kg_query "read-only" path can mutate/destroy prod KG** — *high, M, security*
Fix: replace substring guard with a tokenized word-boundary write-clause detector over the full vocabulary (`CREATE|MERGE|DELETE|REMOVE|SET|DROP|FOREACH|LOAD CSV` + a `CALL apoc.*` write allowlist), ideally stripping string literals first; or run reads with cypher-shell `--access-mode read`. Also re-categorize the tool away from `read`/`READS_PRIVATE_DATA`-only when `mutate=True` (covers the mcp registry/security finding). **Do this first — it is the only data-loss path reachable from a "safe" call.**
Acceptance: parametrized test — `SET`/`DROP`/`CALL apoc.*`/`LOAD CSV` with `mutate=False` are **blocked**, and benign reads containing `CREATEDBY`/`DELETED`/`MERGED_PR` as literals are **allowed**.

**W1-B · [infra] `occam --semantic --apply` supersedes nodes on random hash vectors when sentence-transformers absent** — *high, S, bug (destructive)*
Fix: in `cmd_occam_semantic`, after `emb = Embedder()`, if `not emb.is_real_model` → stderr warning + **refuse `--apply`** (require explicit `--allow-hash-embed`). Add a root `[memory]` extra so the real model is installable. **Second — cheap, stops noise-driven KG destruction.**
Acceptance: with hash-fallback embedder, `--apply` exits non-zero with a clear message; `--allow-hash-embed` overrides; a test asserts the refusal.

**W1-C · [gate] OPA adapter only reads `allow` → break_glass / kg_admission / taliban always DENY on valid input** — *high, S, bug* (+ its missing-test sibling)
Fix: make `_eval_opa` decision-rule aware — extend `_GATE_POLICY` entries to `(package, decision_rule)` and read `allow`/`allow_override`/`allow_mutation`/`approve` accordingly (or query `data.apt.<pkg>.<rule>` directly).
Acceptance: a real-OPA integration test (skip if `opa` absent) feeds each mapped policy's actual response and asserts break_glass/kg_admission/taliban can **PASS**; `_FakeOPA` parametrized to emit the per-policy key.

**W1-D · [legion] G2 gate reports PASS on REJECT, and hades realizes on ensemble=REJECT** — *high+med, S each, bug* (two gate bugs, one PR)
Fix: `eval_g2_adversary_ran` must inspect verdict *content* (`oracle != 'FAIL' AND ensemble not in {'REJECT','FAIL'}`), not `StageOutcome.ok`. `_run_realize` must skip when `oracle=='FAIL' OR ensemble in {'REJECT','FAIL'}`.
Acceptance: integration tests — `verdict.oracle/ensemble = FAIL/REJECT` ⇒ G2=FAIL; `oracle=PASS, ensemble=REJECT` ⇒ `realized.mode=='skipped'`. **These let an adversary's REJECT write to the KG today — pure correctness, no dependency.**

**W1-E · [eureka] Goodhart cap rejects stability=1.0 (the strongest abstractions) → pipeline kills its own best output** — *med, S, bug* (unblocks H1)
Fix: exempt `fca_stability` from the `>GOODHART_CAP` loop (it is not a Goodhart-prone proxy); gate **per-concept** (`min ≤ σ ≤ 1.0`) instead of failing the whole batch on `avg_stability`; pass operator-appropriate metrics (modularity for Leiden, fca_stability only for FCA). This also fixes the avg_stability batch-coupling finding.
Acceptance: a stability=1.0 concept survives to `5-naesengmoon-gate`; new honest end-to-end test reaches stage 5 with VERDICT_PENDING acs (retires H1's dishonest test name).

**W1-F · [naesengmoon] lean oracle counts `sorry`/`admit` inside comments → underreports closed goals behind a passing gate** — *high, S, bug*
Fix: strip Lean comments (`--`→EOL, nested `/- -/`) before `_LEAN_HOLE`/`_LEAN_DECL`, OR reuse `axiom_audit`'s proof-position-anchored `_SORRY` regex (the same repo already does this correctly elsewhere — this is internal inconsistency).
Acceptance: a compiling theorem with `sorry`/`admit` in comments scores the true closed-goal count, not a penalty.

**W1-G · [occam] exact-duplicate supersession is a silent no-op but reported applied; `applied_count` never validated against returned rows** — *high, M + high, S, bug* (one PR)
Fix: make `write_cypher` return rows; count only candidates whose `RETURN` yields a superseded row; surface planned-N vs actual-M in `ApplyResult.notes`. Disambiguate exact dups by `elementId()` of chosen stale/current (fetched at read time) or special-case them. This is the highest-impact occam bug: it *lies about having archived a duplicate.*
Acceptance: a fake runner returning 0 rows ⇒ `applied_count==0` and a mismatch note; the urdna2015 exact-dup case produces a correct distinguishing write or a flagged refusal.

**W1-H · [jaebaeman] KG-anchored DAG/cycle decomposition silently fail-closed-BLOCKS any diamond or cycle** — *high, M, bug*
Fix: add a visited-set (by node name) in `kg_decompose`/`plan` so shared nodes expand/emit once (collapsing DAG to a per-name-unique seed set the downstream MERGE is already idempotent on); detect cycles explicitly with a dedicated diagnostic.
Acceptance: diamond and cycle KG fixtures produce a valid deduped plan (not a generic `DUP_SEED_NAME`/`E3` block); new DAG+cycle tests on the `kg_decompose` path.

**W1-I · [hades↔eureka] realization pipeline is dead — eureka never writes the `verdictStatus='ACCEPTED'` hades queries for** — *high, M, incomplete-wiring* (depends on W1-E)
Fix: pick ONE property and reconcile both ends. Recommended: add a real eureka **KG-persist stage** that, after the naesengmoon gate passes, writes the AbstractClass with the field hades filters on (and add an `ACCEPTED` transition gate PROPOSED→ACCEPTED). Add an integration test: eureka pipeline → persist → hades fetch → **>0 candidates**, replacing the hand-mirrored fixture.
Acceptance: a run of eureka against a local KG followed by hades fetch returns ≥1 candidate without a hand-built fixture. **Order after W1-E** (eureka must reach stage 5 before it can persist an accepted concept).

---

### WAVE 2 — Make the *named* essence real (wiring the components the docs already promise)

High leverage but larger / dependent. These convert "built but unwired" subsystems into live ones. They are what make the tool meaningfully *more* than its deterministic cores.

**W2-A · [legion] measurement-driven conditional dispatch is fully built+tested but wired into NOTHING** — *high, L, incomplete-wiring*
This is the module's NAMED essence (`7cmd-measurement-driven-conditional-dispatch`). `Legion.run()` executes a hardcoded `CANONICAL_ORDER` and never calls `measure()`/`decide_dispatch()`.
Fix (choose and commit honestly): **(a)** make `Legion.run()`/commanders consult `measure()`+`decide_dispatch()` to insert/skip stages and emit `DispatchDecision`/`DispatchEvent` records; OR **(b)** if static order is genuinely the intended production behavior, **demote** `measurement.py` + `threshold_derivation/` (1157 LOC) to an explicitly-labeled experimental module and correct every docstrING/KG/SPEC claiming runtime measurement-driven dispatch. **Do not leave it ambiguous.**
Acceptance: if (a) — an integration run shows a stage skipped/inserted by a measured threshold + ≥1 DispatchDecision record; if (b) — grep finds no remaining claim of "runtime measurement-driven dispatch" and the subpackage README says "experimental/offline."
Sub-items folded in once (a) is chosen: wire `PrometheusMeasurement.update(finding_count=…)`; wire `config.load_thresholds()` into `CommanderBase`; inject `DispatchInstrumentLog` + `record_outcome` so calibration has fresh data; implement-or-remove the orphan `STEVENS_SCALE` entries (`archival_reason_category`/`lens_count`).

**W2-B · [prometheus] deterministic acquire pipeline is never given a fetcher → never fetches/ingests; `acquire --apply` is structurally dead; `WebSearchFetcher` is dead code** — *3 findings, net M, incomplete-wiring*
Fix: add a `--web` flag that injects the already-implemented `WebSearchFetcher` into `run_acquire` and sets `ctx['fetcher']` in `cmd_legion`'s deterministic path; gate `--apply` behind "no fetcher → nothing to write" with an explicit warning. This resolves three findings at once.
Acceptance: `acquire --web --apply` against a fake URL opener ingests ≥1 idempotent `:ResearchFinding`; `--apply` without a fetcher prints "`--apply ignored: no fetcher wired`."
Bundle: default `researched_at` to ISO-8601 UTC (currently structurally always `''`); add the http/https scheme allowlist in `_default_url_open`/`_unwrap_ddg` (latent SSRF/file-read) **before shipping `--web`** — the fetcher becomes live, so the SSRF stops being theoretical.

**W2-C · [longinus] nightly_drift_check + daemon never persist to KG despite docstrings** — *high+med, M, incomplete-wiring* (discharges H6)
Fix: inject a `KgClient` (mirror `sha256_baseline`'s DIP), MERGE the `emit_drift_check_record` payload as `:DriftCheck` (+ `:ReinductionTrigger` on fire); make the daemon load baseline via `list_reference_site_states` and emit on real KG mismatch — OR honestly downgrade both to "in-process / prints-only, not KG-backed." Add the missing tests for these zero-coverage production modules (`nightly_drift_check`, `refresh_drifted_baselines`, `daemon_cli`, watcher internals).
Acceptance: a `MockKgClient` spy proves the nightly write occurs and BLOCKED status when signals are None; a watcher test drives a changed file through `_watcher_main` and asserts a drift event.

**W2-D · [efficacy] git_oracle.py raw-text parsers (the non-circular ground-truth oracle) have zero direct tests on main** — *high, S, missing-test*
This oracle is load-bearing for *every* real-data efficacy number; untested parsers = the ground truth itself is unverified.
Fix: cherry-pick/port `test_git_oracle.py` from `feat/evolve-loop-efficacy-experiment` to main covering `parse_name_status`, `parse_diff_status` (incl. R100/C075 similarity renames), `parse_ref_comment_patch`, `feature_test_commits` with realistic raw git fixtures. **While porting, fix the copy-as-RENAME bug** (`C…` status mislabels a copied file's source as moved).
Acceptance: ≥6 parser fixture tests pass on main; `parse_diff_status('C075\tx.py\ty.py')` no longer yields a source-MOVE label.

**W2-E · [efficacy] re-pin the Lean-headroom result OR keep it labeled historical** — *high, M, weakness* (discharges H2)
Fix: re-run `lean_headroom_run.py --k 4 --replications 10 --out-dir verification/lean_headroom_runB` against the pinned model, commit the raw JSONL (records backend/model per record), and have VERDICT/FAIRTEST cite `analyze_lean_headroom <dir>` output. Until then the H2 relabel stands. Also assert the resolved model+backend at run start (model attribution currently depends on uncommitted env).
Acceptance: `verification/lean_headroom_runB/*.jsonl` exists and committed; the published p-value is regenerable from it via the analyzer; no hand-typed table is cited as authoritative.

---

### WAVE 3 — Correctness polish: real bugs, low blast radius

**W3-A · [occam] `_pick_current` non-deterministic on equal line_count ties** — *med, S* — add a lexicographic/sha tiebreak. AC: `occam_pass([a,b])==occam_pass([b,a])`.
**W3-B · [occam] production never supplies `disk_truth` → HIGH disk-sha confirmation is dead; line-count heuristic is sole arbiter** — *med, M* — wire `disk_truth` in `occam_runner` when `repo_root` is given (the scan already walks disk); until then downgrade same-path-diff-sha auto-supersede to VERIFY.
**W3-C · [occam] `semantic_dedup` default key='name' (nullable/non-unique) — the exact regression #12 kg_adapter moved away from** — *med, S* — require a non-nullable unique key; assert matched-node count==1 before write.
**W3-D · [naesengmoon] n_eff anti-inflation bypassed for a single judgment critic (clean PASS at n_eff=1.0)** — *med, S* — put the "no oracle ⇒ no clean PASS" invariant *before* the all_pass shortcut; cap lone judgment critic at CONDITIONAL_PASS.
**W3-E · [naesengmoon] axiom-taint fails on dotted/namespaced Lean imports** — *med, S* — normalize captured import to final module segment before the `by_stem` test (latent until any namespaced import lands).
**W3-F · [naesengmoon] occam-twins oracle drops `repo_root` through `verify()`/`cmd_oracle`** — *med, S* — add `repo_root` param + `--repo-root` arg so mode-2/3 disk-truth detection is active by default.
**W3-G · [gate] circuit breaker persists `time.monotonic()` to Redis but claims restart-survivable → stuck OPEN forever after reboot** — *med, S* — use `time.time()` for persisted `opened_at`; add Redis TTL on OPEN keys.
**W3-H · [gate] break-glass route ignores break_glass.rego (no actor/expiry/reason-length; allowlists gate-names not actors)** — *med, M, security* — route through OPA (after W1-C) or replicate actor/reason-len/expiry checks inline.
**W3-I · [hades] INSTANCE_OF op matches members by bare name with no label → binds arbitrary same-named nodes** — *med, S* — constrain to intended member label(s) or pass elementIds from eureka's extent.
**W3-J · [hades] `_find_classdef` returns the WRONG class when requested name absent but file has one class** — *low, S* — remove the single-class fallback; return None.
**W3-K · [cli] resolver `validate` cannot flag single-digit magic numbers 9/7/8 (3 of 5 core fields)** — *med, S* — regex `\d{1,4}` relying on the `{200,500,9,7,8}` allowlist; add bare-9/7/8 tests.
**W3-L · [longinus] MCP backend misroutes legitimate READ cypher to write tool via substring match** — *low, S* — same word-boundary fix family as W1-A.
**W3-M · [infra] `LocalKgStore.add_edge` resolves node by value-equality → aliasing for empty/identical nodes** — *low, S* — use identity lookup (`n is src`).
**W3-N · [naesengmoon] `prompt_echo_score` normalizes by hint size → short hints trivially flag echo** — *low, S* — symmetric Jaccard + minimum-hint-bigram floor.

---

### WAVE 4 — Honesty/docs/cleanup (cheap, ship alongside their parent fix)

- [efficacy] H3, H4 scoreboard relabels (success-rate, live-snapshot qualifier).
- [hades] H5 INFERRED-confidence demotion; unify the **two divergent harness-diagnosis impls** (MCP skeleton "always unknown / Phase 2" vs real engine) — delegate MCP tool to `engine.harness.diagnose` or delete the duplicate; remove/rename dead `realize_code_template` symbolic stub; ast-backend `unified_diff` round-trip noise.
- [mcp_server] H7 longinus_audit false-Pydantic-claim; `prometheus_research` plan-only relabel; `gate_check` fail-open fix (catch `OSError` not just `TimeoutExpired`) + the "Resilience4j 4-layer / 500ms vs actual 10s" claim correction; add the missing `gate_check`/`seed_germinate` functional tests.
- [legion] H8 README corrections (audit_prom_cycles, missing files, runtime-vs-experimental layers).
- [prometheus] MCP `prometheus_research` rename-to-planner + extraction-truncation tests.
- [jaebaeman] tautological covenant asserts (move check to the write boundary), coinductive `plan` frontier-stub + `leaf_count` frontier mislabel, substrate positional-index→verb-keyed mapping.
- [longinus] GED docstring overclaim, sig-drift default-value omission doc, stale parallel-threshold docstring (100→5000).
- [eureka] dead `_RULE_HEADER_PAT` regex.
- [gate] composition-root README trim to match honest status table.
- [cli] dead `nargs="+"` usage guards; `cmd_status` password-in-argv exposure (drop hardcoded `neo4jpassword` default, feed via env/stdin); vestigial eureka/occam collision test + dead `evict=` args.
- [infra] add `deptry` job to `ci.yml` (currently only pre-push, routinely `--no-verify`'d); `code_to_kg` builtin-method CodeExternal pollution + CLI not wired into main entrypoint + INHERITS omitted from summary + newline/control-char escaping in `to_cypher`.

---

### SEPARATE — branch hygiene (blocks nothing, but blocks W2-D/W2-E source)

**[infra] `feat/evolve-loop-efficacy-experiment` is stale, 14 conflict hunks across 11 files, not cleanly mergeable** — *low, M*. It holds the `test_git_oracle.py` (W2-D) and evolve-loop work. Rebase onto main, resolve (prioritize `schema.py` + `evolve_loop.py`), full pytest, then merge — do **not** fast-merge. Either rebase it or cherry-pick just `test_git_oracle.py` for W2-D and let the branch die.

---

## 4. Dependencies & ordering

- **W1-A (mcp write guard) first** — only reachable prod data-loss path; W3-L and the W4 mcp word-boundary fixes share its solution.
- **W1-E (eureka gate) → W1-I (hades persist)** — eureka must reach stage 5 before it can persist an ACCEPTED concept for hades to consume. Also unblocks honesty risk H1.
- **W2-B (`--web`) requires the SSRF scheme allowlist landed in the same PR** — wiring the fetcher makes the latent SSRF live.
- **W2-A must resolve as (a) wire OR (b) demote** before its sub-items (PrometheusMeasurement.update, load_thresholds, DispatchInstrumentLog, STEVENS_SCALE) are meaningful — they all hang off the dispatch loop existing.
- **W3-H (break-glass) depends on W1-C** (OPA `allow_override` must be readable first).
- **W2-D/W2-E depend on the stale-branch decision** (cherry-pick `test_git_oracle.py` or rebase).
- **H2/H3/H4/H6/H7/H8 relabels ship immediately, independent of everything** — they cost a line each and stop the audit trail from lying today.

**Leverage summary:** Wave 1 + W2-A/B/C are where the tool stops *claiming* and starts *doing* — that is ~80% of the real value. Everything in Waves 3–4 is genuine but bounded correctness/honesty polish. The single worst current state is the cluster of **green tests and confident scoreboards describing pipelines that don't run**; killing that illusion (H1–H8 + the Wave-1 wiring) is non-negotiable and comes first.