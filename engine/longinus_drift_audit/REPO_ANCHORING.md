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
an audit on machine M can tell *"this site belongs to a repo not checked out here"* (skip)
apart from *"this site's file is missing"* (real Orphan/drift) — so a single-repo audit no
longer false-flags another repo's sites.

## Status / follow-ups

Landed: `repo_identity`, `repo_registry`, `repo_cli`, the `ReferenceSite` fields
(`repo_id`/`repo_relpath`/`commit`/`blob_oid`/`blob_oid_baseline`), and `locate_site()`
(registry-first, legacy base-chain fallback). Next: wire `audit_runner`/`sha256_baseline`
to resolve via `locate_site` and add a `NOT_LOCAL` verdict; fold `daemon.py`'s `watch.toml`
into the shared registry.
