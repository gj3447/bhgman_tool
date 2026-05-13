# APT Progress: bhgman_tool

## Anchor: sa-bhgman_tool-ruflo-utility-parity-2026-05-13
## Domain: tool-layer-engineering
## Status: active
## Created: 2026-05-13T17:00:00+09:00 (Phase 1 SA bootstrap)
## Last Updated: 2026-05-13T18:00:00+09:00 (Phase 3 SA EXTEND)
## Context Budget: total=100K, per_span=8K
## APT version: v26.1
## Work kind: EXTEND (SHORT_CIRCUIT from Phase 1+2 anchor)

---

## Phase 1+2 Completed (prior commits, before this session)

| Commit | Date | Scope |
|---|---|---|
| `7e906c4` | 2026-05-11 | seed: bhgman v0.1 — academic-grounded multi-agent ontology |
| `08ee569` | 2026-05-11 | bhgman_tool buildout (frame + docs + skills + engine + lean + theory) |
| `0f00520` | 2026-05-11 | i18n: 비행기맨 + Harness 핵심 문서 4 언어 |
| `11255c6` | 2026-05-12 | docs(philosophy): 비행기맨 특화 철학적 함의 6 항 |
| `c27c76a` | 2026-05-12 | docs: 5 핵심 paper + Longinus tutorial + 50 theorem |
| `b3c5c5c` | 2026-05-12 | feat: Claude Code plugin packaging + 4 paper + APT cycle tutorial |
| `a22cd71` | 2026-05-13 | feat: 4 paper (Lakatos/Evans/Smith/Chu) + CRG daemon + bhgman_essence cross-link |
| `483313c` | 2026-05-13 | **feat(APT v26.1 Phase 1)**: CI + worked example 1 + MCP server skeleton (즉시 가용성 ruflo parity 진입) |
| `0127b3e` | 2026-05-13 | **feat(APT v26.1 Phase 2)**: worked-2 + HNSW memory + Phase 6 Cleanup baseline |

## Phase 3 Sprint (this session)

| Span | Status | Scope |
|---|---|---|
| `SPAN_bhgman_tool_phase3_ROOT` | open (depth=0, 50K ctx) | 3 sibling L1 branches |
| `SPAN_bhgman_tool_phase3_CLI` | open (depth=1, 50K ctx, **in_progress**) | parent pyproject `[project.scripts]` + `bhgman_tool/cli/` Click entry + `install-skills` automation |
| `SPAN_bhgman_tool_phase3_WORKED3` | open (depth=1, 50K ctx) | worked-3/ APT cycle dogfood example (review.md + tcw/st/sp/ta_report.md + test) |
| `SPAN_bhgman_tool_phase3_MCP_TOOLS` | open (depth=1, 50K ctx) | MCP server first-class tool expansion 2→5 (`apt_phase_detect` / `taliban_lens_check` / `tpa_drift_audit` 추가) |

---

### In Progress
- `SPAN_bhgman_tool_phase3_CLI`: SA bootstrap complete, ready to enter SP for decomposition

### Blocked
(none)

### KG Stats
- SemanticAnchor: `sa-bhgman_tool-ruflo-utility-parity-2026-05-13` (`:SemanticAnchor:Canonical:APT_Phase1`)
- Phase 3 L1 Spans: 3 (CLI / WORKED3 / MCP_TOOLS)
- 5 mandatory SA core fields: ✓ (objective / definition / keyAssertion / c_s_predicate / context_budget_total)
- Gate: gate_check_passed=true, gate_lensset=constitutional-9-full

### Next Steps
1. `SPAN_bhgman_tool_phase3_CLI` SP decomposition → Contract (parent pyproject [project.scripts] + bhgman_tool/cli/__init__.py + install-skills + verify subcommands)
2. `SPAN_bhgman_tool_phase3_WORKED3` SP decomposition → target selection (self-dogfood vs external)
3. `SPAN_bhgman_tool_phase3_MCP_TOOLS` SP decomposition → 3 new tool modules

### Session Log

- `[2026-05-13T17:00 KST]` Phase 1 SA bootstrap (commit 483313c)
- `[2026-05-13T~ KST]` Phase 2 worked-2 + HNSW memory (commit 0127b3e)
- `[2026-05-13T18:00 KST]` Phase 3 SA EXTEND — Root Span + 3 L1 sibling branches decomposed, context_budget allocated, domain/status filled. SA→SP gate ready.

## Honest Limitations (this anchor)

- Phase 1 SA was created without Root Span (KG Span tree empty until iter 2026-05-13T18:00). Phase 3 SA EXTEND fixed this retroactively.
- 3 L1 branches are *open*, not yet entering SP decomposition. SP atomicity (C(S) 5-predicate) not yet verified per branch.
- `bhgman-tool` umbrella CLI command does not exist yet — README Quickstart step 4 still requires manual `cp -R skills/* ~/.claude/skills/`.
- worked-3 target selection deferred to SP phase (recursive self-dogfood likely; max_depth=1 invariant must hold).
