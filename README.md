<div align="center">

# bhgman_tool

**KG-anchored agent orchestration toolkit for Claude Code skill workflows.** Lean 4 verified confidence schema (7 theorems, `sorry=0`) · KG↔code drift audit (Python + APOC trigger, currently warn-mode).

<a href="https://github.com/gj3447/bhgman_tool/releases/download/v0.1.0-assets/hero.mp4"><img src="assets/hero.gif" width="600" alt="bhgman_tool hero (click for full mp4)"></a>

[English](README.md) | [한국어](README.ko-KR.md) | [中文](README.zh-CN.md) | [日本語](README.ja-JP.md)

[![Status: experimental](https://img.shields.io/badge/status-experimental-orange.svg?style=flat-square)](https://github.com/gj3447/bhgman_tool#status-experimental)
[![PyPI](https://img.shields.io/pypi/v/bhgman_tool.svg?style=flat-square)](https://pypi.org/project/bhgman_tool/)
[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Lean 4](https://img.shields.io/badge/Lean-4.29.1-purple.svg?style=flat-square)](https://leanprover.github.io/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg?style=flat-square)](https://www.python.org/)
[![Pytest engine](https://img.shields.io/badge/pytest%20engine-267%20PASS-green.svg?style=flat-square)](engine/longinus_drift_audit/tests/)
[![Pre-commit gate](https://img.shields.io/badge/pre--commit%20gate-447%20tests-blue.svg?style=flat-square)](.pre-commit-config.yaml)

</div>

---

## What you get in 30 seconds

```bash
pip install bhgman_tool
uv run bhgman-tool install-skills    # adds /apt /prom /tpa /tlb /longinus /harness /jaebaeman to Claude Code
```

Restart Claude Code. In a chat:

```
/prom 16 "investigate <topic>"
# parent dispatches 16 parallel research subagents (haiku),
# each returns JSON, parent batch-writes to your knowledge graph,
# every claim ends up with a citation_url and a reproducible cycle_id.
```

Ephemeral subagent runs become first-class, auditable records.

---

## Why bhgman_tool

- **Verifiable provenance** — every subagent run produces a KG-anchored, sha256-baselined `ResearchFinding` node with cycle_id, axis seeds, citation URLs, and parent-lesson edges. Re-running a cycle is idempotent. Claims survive past the chat session.
- **Drift audit built-in** — Longinus 7-layer reference model + sha256 baselining + forward/reverse orphan scan catches knowledge-graph ↔ source-code drift before it compounds. Run as a CLI, a pre-commit hook, or a CI job.
- **Methodology skills, ready to use** — one-liner `bhgman-tool install-skills` installs APT/TPA cycle orchestrators and the 5-tool stack (Prometheus / Longinus / Naesengmoon / Jaebaeman / Harness) as Claude Code slash commands. No custom MCP wiring required.

---

## Install

```bash
pip install bhgman_tool                       # minimal (CLI + Pydantic models)
pip install "bhgman_tool[resolver]"           # + APT v27 resolver (Jinja2 + Neo4j)
pip install "bhgman_tool[gate]"               # + APT v27 gate endpoint (FastAPI + Redis)
pip install "bhgman_tool[all]"                # everything
```

> The PyPI wheel ships `engine/` only. The `install-skills` / `verify` / `version` subcommands need the source repo (`skills/` + `lean/`) alongside — clone for full functionality. See [docs/PYPI_PUBLISH.md](docs/PYPI_PUBLISH.md).

---

## Quickstart (3 min)

```bash
git clone https://github.com/gj3447/bhgman_tool.git
cd bhgman_tool

# 1. engine — verify pytest
cd engine/longinus_drift_audit
uv run --with pytest pytest tests/ -q          # expected: 267 passed in ~2s

# 2. Lean 4 — verify formal claims (optional)
cd ../../lean
lean Longinus_ConfidenceSchema_GraphifyAbsorbed.lean   # exit 0, sorry=0

# 3. Install Claude Code skills
cd ../..
uv run bhgman-tool install-skills              # default: ~/.claude/skills

# 4. (Contributors only) pre-commit ratchet
uvx pre-commit install --hook-type pre-commit --hook-type pre-push
```

Restart Claude Code, then `/apt` `/prom` `/tpa` `/tlb` `/longinus` `/harness` `/jaebaeman` are live. Full guide: [docs/01-quickstart.md](docs/01-quickstart.md).

```mermaid
flowchart LR
    A([git clone]) --> B[engine pytest<br/>267 PASS]
    B --> C{Lean 4?<br/>optional}
    C -- yes --> D[lean verify<br/>sorry=0]
    C -- skip --> E[bhgman-tool install-skills]
    D --> E
    E --> F[restart Claude Code]
    F --> G[/apt · /prom · /tpa · /tlb<br/>/longinus · /harness · /jaebaeman/]
    E -. contributors only .-> H[pre-commit install<br/>4-ratchet gate]

    classDef startNode fill:#dcfce7,stroke:#166534,stroke-width:2px,color:#1f2937
    classDef endNode fill:#fce7f3,stroke:#9d174d,stroke-width:2px,color:#1f2937
    classDef optNode fill:#fef9c3,stroke:#854d0e,stroke-width:1px,stroke-dasharray:5 5,color:#1f2937
    class A startNode
    class G endNode
    class H optNode
```

---

## How it works

`/apt` runs a 5-phase cycle (SemanticAnchor → SemanticPyramid → SemanticTwin → SourceCodeWorld → MetaReview) and dispatches the right tool at each gate. `/tpa` is the reverse direction (code → design recovery). For the skill-dispatch graph and a 4-axis Harness / 3-tier family diagram, see [docs/02-concepts/skills-graph.md](docs/02-concepts/skills-graph.md) and [docs/02-concepts/harness.md](docs/02-concepts/harness.md).

---

## Reproducing the claims

Every numeric claim in this README ships with a one-command verifier. Run them on a fresh clone:

| Claim | Command | What it checks |
|---|---|---|
| `267 pytest PASS` (engine subset) | `cd engine/longinus_drift_audit && uv run --with pytest pytest -q` | engine subset pass count + runtime |
| `447 pytest PASS` (full repo) | `pytest -q` from root (or `uvx pre-commit run --all-files`) | full-repo pass count, single invocation |
| `Lean 4: sorry=0, build=OK` | `cd lean && lake build && grep -rn 'sorry' src/ \| wc -l` | proof skeleton integrity |
| `141+ theorems` | `cd lean && grep -rcE '^(theorem\|lemma) ' src/` | top-level theorem count |
| `KG cycle reproducibility` | `bhgman-tool replay-cycle <cycle_id>` | re-runs a cycle and diffs the KG output |

**Goodhart disclaimer:** these scripts verify *reproducibility of the indicator value*, not *validity of what the indicator measures*. Theorem count, sorry count, and pytest count are Goodhart-vulnerable — they confirm "this number is stable and reachable from a clean clone," not "this number means the system is correct." Validity lives in the proofs themselves, the test bodies, and the cycle outputs — not the count.

---

## Documentation

- [docs/01-quickstart.md](docs/01-quickstart.md) — full setup
- [docs/02-concepts/](docs/02-concepts/) — Harness, APT, TPA, the 5 weapons
- [docs/04-references/related-work.md](docs/04-references/related-work.md) — comparison with adjacent OSS (LangGraph, CrewAI, ruflo)
- [docs/06-philosophy/](docs/06-philosophy/) — the conceptual essence layer, including the SYMPOSIUM 12-apostle framework this tool was carved out of (optional reading)

---

## Status: experimental

Early-adopter stage. API surface, skill contracts, and badge counts may change without a deprecation cycle. Pinning a specific commit (or `pip install bhgman_tool==<version>`) is recommended for production use. The cycle that produced this README (PROM 16 persuasion-design + 3-lens Naesengmoon round-2) is tagged `EXPLORATORY_NOT_CONFIRMATORY` in the project KG — see `THEORY/bhgman_tool_readme_design/PROM_16_REPORT.md` in the SYMPOSIUM monorepo.

**Scope boundary (intentional).** bhgman_tool is the *tool layer*: skill installation, the Longinus KG↔code drift auditor, the resolver/gate libraries, and Lean proof skeletons. It does **not** ship a standalone APT *execution* engine — phase orchestration runs inside Claude Code (skills) and the dgx prototype runtime, not as an in-process engine here (see [ADRs/apt-engine-scope-decision-2026-05-25.md](ADRs/apt-engine-scope-decision-2026-05-25.md)). A self-audit scored APT-execution completeness at 0.42; that gap is this documented capability ceiling, not an unshipped promise.

## Contributing

Pre-commit 4-ratchet gate runs ruff lint+format, complexipy ≤15, deptry, and 447 pytest tests on every commit; lychee link-check on every push. Install with `uvx pre-commit install --hook-type pre-commit --hook-type pre-push`.

---

## License

MIT. Author: [gj3447@gmail.com](mailto:gj3447@gmail.com).

---

<sub>Built within the SYMPOSIUM 12-apostle / 5-weapon framework. The tool itself stands alone; the conceptual essence layer lives at [docs/06-philosophy/](docs/06-philosophy/). KG provenance: `github-mirror-bhgman-2026-05-13` (`:PublicReferenceRepo:Canonical`, scope=tool-layer-only).</sub>
