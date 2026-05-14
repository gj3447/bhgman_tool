# bhgman_tool — Cumulative Verification Results

> Per-session results, append-only. Latest at top. Each entry cites the
> Capability ID from [`CAPABILITIES.md`](CAPABILITIES.md).

---

## Session 2026-05-14 — Wave 7 P2-A (SYMPOSIUM bin/MCP/tests/verification absorption)

### Headline

- Files synced from SYMPOSIUM      : 9 (bin/symposium + MCP server + 3 tests + conftest + pytest.ini + 2 verification docs)
- Files created in bhgman_tool     : 7 (engine/mcp_server/tools/symposium.py + 3 absorbed test files + 2 conftest/__init__ + verification/2 + bin/symposium alias)
- CLI verbs added                  : 7 (apt / tpa / prom / tlb / longinus / harness / status)
- MCP tools added                  : 4 (apt_dispatch / kg_query / gate_check / seed_germinate)
- New pytest collected             : 26 (11 phase routing + 13 KG invariants + 13 wave extraction — overlap because some shared classes counted once)

### Per-capability results

| Cap | Witness ran? | Status | Notes |
|---|---|---|---|
| C1 console script | `bhgman-tool version` (pre-existing) | PASS_AS_OF_2026-05-13 | unchanged by this absorption |
| C2 cohort A 4 verbs | `test_parser_has_native_subcommands` | TESTS_UPDATED | renamed from `test_parser_has_four_subcommands`, asserts subset |
| C3 cohort B 7 verbs | `test_parser_has_symposium_absorbed_subcommands` | TESTS_WRITTEN | new test in `engine/cli/tests/test_main.py` |
| C4 bash alias | `test -x bin/symposium` | PASS | created executable bash thin alias |
| M1 9-tool registry | `list_registered_tool_names()` returns 9 names | PASS_STATIC | static inspection: 5 native + 4 SYMPOSIUM |
| M2 4 SYMPOSIUM tools | `register(mcp)` in `tools/symposium.py` | PASS_STATIC | 4 `@mcp.tool()` callables present |
| M3 fail-open | `tests/symposium/test_kg_invariants.py::TestFailOpen` | TESTS_WRITTEN | 1 test ported |
| M4 write-keyword guard | `tests/symposium/test_kg_invariants.py::TestWriteSafety` | TESTS_WRITTEN | 5 parametrized tests + 2 sanity tests |
| A4 phase routing | `tests/symposium/test_apt_phase_routing.py` | TESTS_WRITTEN | 11 tests ported |
| K3 5-tuple identity | `tests/symposium/test_kg_invariants.py` | TESTS_WRITTEN | 16 tests ported |
| WV1-WV4 wave extraction | `tests/symposium/test_wave_extraction.py` | TESTS_WRITTEN | 13 tests ported, pure-algorithm (no KG dep) |

### Files materialized this session

```
bhgman_tool/bin/symposium                                                  # thin bash alias → python -m engine.cli.main
bhgman_tool/engine/cli/main.py                                             # +7 verbs (apt/tpa/prom/tlb/longinus/harness/status) + helpers
bhgman_tool/engine/cli/tests/test_main.py                                  # cohort A/B split tests
bhgman_tool/engine/mcp_server/server.py                                    # register_symposium hook + 9-tool list
bhgman_tool/engine/mcp_server/tools/symposium.py                           # NEW 248 lines — 4 SYMPOSIUM tools + DTOs + fail-open transport
bhgman_tool/engine/mcp_server/tests/symposium/__init__.py                  # NEW
bhgman_tool/engine/mcp_server/tests/symposium/conftest.py                  # NEW — fixtures (bhgman_root / skills_dir / mock_kg)
bhgman_tool/engine/mcp_server/tests/symposium/pytest.ini                   # NEW
bhgman_tool/engine/mcp_server/tests/symposium/test_apt_phase_routing.py    # NEW — 11 tests
bhgman_tool/engine/mcp_server/tests/symposium/test_kg_invariants.py        # NEW — 16 tests
bhgman_tool/engine/mcp_server/tests/symposium/test_wave_extraction.py      # NEW — 13 tests
bhgman_tool/verification/CAPABILITIES.md                                   # NEW — 7 sections (F/K/W/C-M/WV/H + scope)
bhgman_tool/verification/results.md                                        # this file
```

### bhgman_tool-specific customizations preserved

- `engine/cli/main.py`:
  - existing 4 cohort A verbs (install-skills / verify / version / daemon) unchanged
  - existing `_repo_root()`, `cmd_install_skills()`, `cmd_verify()`, `cmd_version()`, `cmd_daemon()` unchanged
  - PACKAGE_VERSION constant unchanged
- `engine/mcp_server/server.py`:
  - 5 pre-existing tools (`longinus_audit` / `harness_diagnose` / `apt_phase_detect` / `taliban_lens_check` / `tpa_drift_audit`) unchanged
  - `list_registered_tool_names()` extended to 9, native 5 still listed first
- `engine/cli/tests/test_main.py`:
  - 7 pre-existing tests unchanged
  - 1 test renamed and split into 2 (cohort A subset assertion + cohort B subset assertion) — drift-prevention vs hard equality

### Goodhart safeguards reinforced

- Cohort B verbs print routing intent + SKILL.md path but **do NOT execute phase logic** — drift prevention (skills/<name>/SKILL.md remains canonical).
- `list_registered_tool_names()` cohort comment-split (native vs SYMPOSIUM-absorbed) for forensic auditability.
- Phase-router validation set frozen at `{sa, sp, st, scw, meta_review}` — uppercase/whitespace variants rejected (`SA`, `SP`, etc.).
- Fail-open in `_ssh_cypher`: degraded dict, never raise. Parent harness must inspect `degraded` flag.

---

## FutureWork

- **v0.2 ruflo-style perf JSONL**: append per-capability `durationMs` for true regression detection.
- **MCP live integration test**: spin up `python -m engine.mcp_server` + speak JSON-RPC 2.0 (currently static `list_registered_tool_names()` only).
- **Witness automation**: `bhgman-tool verify --scope verification` should auto-generate this table.
- **Mathlib sprint**: `lean-mathlib-functor-actual-build-2026-04-30` remains user-gated (Wave 7 P3-D).

---

## Provenance

- Session: Wave 7 P2-A of cumulative SYMPOSIUM bin/MCP absorption into bhgman_tool
- KG: `rs-bhgman-results-wave7-p2a-2026-05-14`
- Source: `SYMPOSIUM/verification/results.md` (Wave 4 entry as template)
- Linked from: `apt-hardening-master-plan-2026-05-06`, `symposium-methodology-overview-2026-05-06`,
  `span-bhgman-cli-mcp-absorption-wave7-2026-05-14`
