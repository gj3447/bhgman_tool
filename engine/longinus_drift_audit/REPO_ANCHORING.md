# Longinus repo anchoring — "what" vs "where"

A Longinus binding must resolve to the same code on **any clone, on any machine**. To do
that it separates two concerns that used to be tangled in one absolute path:

| layer | answers | stored where | portable? |
|---|---|---|---|
| **Binding (what)** | "which repo + which file + which content" | git + KG (committed/shared) | ✅ machine-independent |
| **Registry (where)** | "where is that repo checked out on THIS box" | `~/.config/longinus/repos.toml` (per-hardware, never committed) | ⛔ machine-specific, by design |

Resolution is just the join: **`abs_path = registry.resolve(repo_id) / repo_relpath`**.

## The binding (`repo_identity.py`)

A binding addresses code by `(repo_id, repo_relpath, blob_oid)` — never an absolute path.

- **`repo_id`** — the portable, machine-independent key. Resolved layered, first hit wins:
  1. `.longinus/repo.toml` → `id = "..."` at the git toplevel (explicit; survives fork/rename)
  2. normalized `origin` remote → `github.com/<owner>/<repo>`
  3. root-commit SHA → `rootcommit:<sha>` (remote-less local repos)
- **`repo_relpath`** — POSIX path relative to the git toplevel (identical across OSes).
- **`blob_oid`** — `git hash-object` of the file: content-addressed, so the drift signal is
  reproducible across clones (preferred over `sha256`; `sha256` kept as a fallback).
- **`commit`** — the revision the baseline was validated at.

`git_identity(path)` returns all of the above (each `None` outside a git work tree — the
offline invariant holds and callers fall back to the legacy resolver).

## The registry (`repo_registry.py`)

Machine-local map of `repo_id → local checkout path`. Location (first that applies):
`$LONGINUS_HOME/repos.toml` → `$XDG_CONFIG_HOME/longinus/repos.toml` → `~/.config/longinus/repos.toml`.

```toml
[[repo]]
id     = "github.com/gj3447/bhgman_tool"
path   = "/data/kjra/PROJECT/PI/bhgman_tool"
remote = "https://github.com/gj3447/bhgman_tool.git"
```

`locate(repo_id, repo_relpath)` = `resolve` → `discover_for` (auto-register from CWD /
`$LONGINUS_SEARCH_PATHS` / `$CD_ROOT` / `~`, with a log line) → else raise `NotRegistered`
(an actionable error — it never guesses a wrong file).

## CLI

```bash
python -m engine.longinus_drift_audit.repo_cli id .            # print this dir's repo_id
python -m engine.longinus_drift_audit.repo_cli discover .      # auto-register this repo
python -m engine.longinus_drift_audit.repo_cli list
python -m engine.longinus_drift_audit.repo_cli register <repo_id> <local_path>
python -m engine.longinus_drift_audit.repo_cli locate <repo_id> <repo_relpath>
```

## Why this also fixes shared-Neo4j multi-repo audits

The dgx Neo4j holds ReferenceSites from several repos at once. With a portable `repo_id`,
an audit on machine M can tell *"this site belongs to a repo not checked out here"*
(`NOT_LOCAL`, skipped) apart from *"this site's file is missing"* (real Orphan/drift) — so a
single-repo audit no longer false-flags another repo's sites.

`sha256_baseline.resolve_site()` resolves registry-first: a `repo_id` miss → `NOT_LOCAL`;
the repo present but the file gone → `MISSING` (genuine drift); no repo anchor → the legacy
`resolve_path` heuristic. `init_baseline`/`verify_baseline` count `not_local` and set the
`Sha256Status.NOT_LOCAL` state instead of emitting a drift event; `AuditReport` carries
`sha256_not_local_count`.

## Status

**Landed:**
- `repo_identity`, `repo_registry`, `repo_cli`, the `ReferenceSite` fields
  (`repo_id`/`repo_relpath`/`commit`/`blob_oid`/`blob_oid_baseline`), `locate_site()`.
- `Sha256Status.NOT_LOCAL` + `resolve_site()`; `init_baseline`/`verify_baseline`/`audit_runner`
  wired through it (shared-KG multi-repo false-flagging fixed).
- `kg_client` (Neo4j) persists/returns the new fields.
- `daemon.py`: `WatchConfig.from_registry()` + `_load_config` falls back to the registry when
  no `watch.toml` exists — the registry is the single source of truth for "repos on this box".
- `migrate_repo_ids.py`: one-shot backfill of git anchoring onto pre-anchoring ReferenceSites
  (disk-resolve → `git_identity` for `repo_id`/`repo_relpath`/`commit`/`blob_oid_baseline`;
  `repo_tag → repo_id` map for sites whose repo isn't on this machine; idempotent; `--dry-run`).

      python -m engine.longinus_drift_audit.migrate_repo_ids --kg neo4j --dry-run

The model is complete: new bindings are born git-anchored; legacy KG data is lifted in by the
migration.
