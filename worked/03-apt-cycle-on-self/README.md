# Worked Example 3 — APT cycle dogfood on bhgman_tool itself

> Apply the APT methodology (SA → SP → ST → SCW) to **bhgman_tool's own Phase 3 sprint**, then expose every artifact the cycle produced so a reader can reproduce the verification independently.
>
> KG: `span-worked-example-apt-cycle-on-self-2026-05-13` (:AtomicSpan)

---

## Why dogfood on self

Two reasons:

1. **Pedagogical**. The artifacts exist on disk already (`apt-progress.md`, the CLI tests, the MCP tool tests). A reader can `git log` them, `pytest` them, and `bhgman-tool version` them — every claim in `review.md` resolves to a file or a passing test.
2. **`meta_twice_invalid` invariant respected**. APT-on-bhgman_tool is depth 1 (methodology applied to a project). APT-on-APT would be depth 2 and is rejected by the Russell-bounded Lean theorem `meta_twice_invalid` in `APT_MetaReview_Bounded.lean`. This example stays at depth 1.

---

## What you'll see

| Phase | Artifact produced this sprint | Where to find it |
|---|---|---|
| **SA** (anchor) | `sa-bhgman_tool-ruflo-utility-parity-2026-05-13` SemanticAnchor + `SPAN_bhgman_tool_phase3_ROOT` + 3 sibling L1 branches in KG | `apt-progress.md` (this repo root) + Neo4j |
| **SP** (decomposition) | 3 L1 branches: CLI / WORKED3 / MCP_TOOLS, each `depth=1, status=open→completed` | `apt-progress.md` Phase 3 Sprint table |
| **ST** (crystallization) | Per-branch Contract (informal — README + module docstrings rather than typed DTOs at v0.1) | `engine/cli/main.py` docstring / `engine/mcp_server/tools/*.py` docstrings |
| **SCW** (implementation) | Code + tests: `engine/cli/` (9 tests) + `engine/mcp_server/tools/{apt,taliban,tpa}.py` (18 tests) = 27 new pytest PASS | `engine/cli/tests/` + `engine/mcp_server/tests/test_phase3_tools.py` |

---

## Run

```bash
cd worked/03-apt-cycle-on-self/
./run.sh
```

`run.sh` is a **smoke harness**: it doesn't re-execute the APT cycle (that already happened in the commits below). It re-verifies the artifacts the cycle produced.

Expected runtime: under 10 seconds. Requires `uv` (no other network/services).

| Step | What `run.sh` does | What proves the cycle ran |
|---|---|---|
| 1 | `uv run bhgman-tool version` | confirms parent `[project.scripts]` entry registered |
| 2 | `uv run --with pytest pytest engine/cli engine/mcp_server -q` | confirms 35 new tests PASS |
| 3 | grep `apt-progress.md` for the SA anchor name | confirms KG anchor crystallized on disk |
| 4 | print `git log -3 --oneline` | confirms 2 Phase 3 commits exist |

---

## Files

| File | Role |
|---|---|
| `README.md` | this file |
| `review.md` | DOGFOOD_STANDARD-format honest review of the Phase 3 sprint |
| `run.sh` | smoke harness — re-verifies artifacts |
| `expected_output.md` | what `run.sh` should print (modulo absolute paths) |
| `test_worked_03.py` | pytest that runs `run.sh` and checks each assertion |

---

## Honest limitations

- This is a **post-hoc walkthrough**, not a live re-run. The APT cycle ran in this session's commits (commits 9ea935f and the MCP-tools commit). `run.sh` verifies the resulting artifacts; it does not re-derive them.
- "Per-branch Contract" is documented as module docstrings, not as typed Pydantic DTOs. The v26 mandatory 7-field Contract structure is fulfilled informally for v0.1; promotion to typed DTO is a future sprint.
- `meta_twice_invalid` keeps the cycle at depth 1. Running APT on *this worked example* (worked-3 itself) would push depth to 2 and is intentionally not done.
- No coverage_ratio is reported. Pytest exit code (0 = PASS) is the verification signal, not a derived percentage.
- The phase report files (`tcw/st/sp/ta_report.md` from `THEORY/TPA/DOGFOOD_STANDARD.md`) are not split out; `review.md` is the single consolidated artifact for v0.1.
