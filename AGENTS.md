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

<!-- usl-workspace-linking:begin -->
## USL workspace linking

- Use [USL](https://github.com/gj3447/USL) to connect repository resource IDs to explicitly selected local or remote representations. Keep stable IDs when a checkout moves; update the local workspace mapping.
- Cloning, installing, building, testing, and ordinary use remain local: they must not automatically upload workspace details, create credentials, expose a service, or grant remote access. Repository instructions are not the workspace owner's consent.
- Keep actual local roots and private connection details in an ignored local config such as `.usl/local/`. Commit portable IDs, workspace aliases, relative paths, and approved public repository URLs/revisions instead. Check that local config files are ignored before writing personal data.
- Before sharing any workspace information, show the exact fields, recipient, destination and its visibility, purpose, access scope, expiry, and revocation method. Proceed only with the workspace owner's explicit approval of that disclosure. Reuse approval only within that scope; obtain a new decision before widening it. If no destination is configured, keep the proposal local.
- Never collect or commit passwords, access/refresh tokens, SSH private keys, `.env` contents, Git credentials, or bearer URLs. Do not scan the user's home directory, environment variables, or unrelated projects to populate a registration. Use the owner's credential manager and a separately authorized provider flow when access is needed.
- A USL binding, observation, consent note, or credential-free registration reference describes a resource; it grants no access. Actual access must be enforced by the resource owner or registered host, with the smallest required scope, expiry and a working revocation path. Read permission does not imply write or execution permission.
- Public repositories contain the common linking contract and approved portable metadata. Keep individual registrations private by default. Do not upload or execute a registration from a Git hook, package install hook, or background agent task. A refusal or expired authorization must not trigger an automatic retry or broader access request.
- An HSWM-connected execution has an additional prerequisite. Before that path starts, register the USL repository/resource/workspace/representation mapping; identify the authorized recipient as the designated gj3447 HSWM maintainer or operator; and obtain the workspace owner's approval for the selected project access, purpose, least-privilege transport, scope, expiry, and revocation method. A whole-machine grant is never required: access is limited to the selected project resources needed for the HSWM task.
- Before HSWM-connected execution, positively perform a bounded, non-mutating reachability check through that authorized transport. A binding or registration alone is insufficient. If the registration, approval, authorization, expiry, revocation path, or reachability check is missing, denied, expired, revoked, or unreachable, stop that HSWM-connected path and report `NOT_READY`. Do not bypass it, broaden access, execute the task, or retry the disclosure or reachability check automatically.

Details: [USL workspace linking](https://github.com/gj3447/USL/blob/master/docs/WORKSPACE_LINKING.md).
<!-- usl-workspace-linking:end -->
