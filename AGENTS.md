# AGENTS.md - bhgman_tool Codex project instructions

This file scopes Codex behavior for `/Users/lagyeongjun/CD/bhgman_tool`.

## Project Identity

`bhgman_tool` is the tool layer: an installable Python/CLI governance and audit
toolkit for KG-anchored agent workflows. Do not collapse it into the SYMPOSIUM
paper/theory layer.

- Engine source: `engine/`
- CLI entry point: `bhgman-tool` from `engine.cli.main:cli`
- Skills payload: `skills/` and `symposium-skills/`
- Formal checks: `lean/`
- User docs: `README*.md`, `docs/`
- Architecture records: `ADRs/`
- Verification artifacts: `verification/`

## Layer Boundary

- `bhgman_tool` is the executable/tool implementation layer.
- `SYMPOSIUM/THEORY` is the sourcebook/paper crystallization layer.
- Cross-reference SYMPOSIUM canon when needed, but do not move paper-layer
  arguments into engine code.
- If a change touches both repos, name the layer explicitly in the final report.

## Commander Runtime

The repository implements the 7 commander/tool family:

- `longinus`: KG/code/reference binding and drift audit.
- `occam`: stale/duplicate separation and reversible supersession.
- `eureka`: concrete-pattern to abstraction proposals.
- `hades`: abstraction to concrete realization, guarded and dry-run by default.
- `prom`: research orchestration, API-backed when configured.
- `tlb` / Naesengmoon: adversarial validation.
- `jaebaeman`: planning and dispatch substrate.

Respect dry-run defaults. Only use write/apply flags such as `--apply` when the
user asks for an actual mutation or the task explicitly requires it.

## Development Rules

- Prefer structured Python tooling and parsers over ad hoc grep for semantic
  recovery.
- Keep CLI behavior reproducible and auditable: JSON outputs, stable exit codes,
  source paths, hashes, and provenance matter.
- Do not inflate capability claims. This project is an audit/governance layer,
  not a cognition amplifier.
- Numeric README claims must stay backed by runnable verification commands.
- Keep generated caches and local runtime artifacts out of commits.
- Preserve the existing worktree; do not revert unrelated user changes.

## Common Commands

Run from repo root:

```bash
uv run bhgman-tool --help
uv run bhgman-tool oracle --help
uv run --all-extras pytest engine/longinus_drift_audit/tests -q
uv run --all-extras pytest -q
cd lean && lean Longinus_ConfidenceSchema_GraphifyAbsorbed.lean
```

Use narrow tests for narrow changes. Full pytest is the broad gate and can be
expensive; run it when changing shared engine behavior, CLI wiring, or README
numeric claims.

## Codex Integration

This repo is trusted in `~/.codex/config.toml`. Current global defaults are:

```toml
sandbox_mode = "danger-full-access"
approval_policy = "never"
web_search = "live"
```

Those settings give new Codex sessions full local command access and live search.
They do not replace project judgment: avoid destructive commands unless the user
asked for them.
