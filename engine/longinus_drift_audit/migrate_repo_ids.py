"""migrate-repo-ids — one-shot backfill of git anchoring onto pre-anchoring ReferenceSites.

Older :ReferenceSite nodes predate repo anchoring: they carry only ``sourcePath`` (+ maybe a
freeform ``repo_tag``) and a content ``sha256`` baseline. This lifts them into the portable
model (:mod:`repo_identity` / :mod:`repo_registry`) so old and new data resolve the same way.

Two passes:

1. **Disk-resolve** — resolve each site on THIS machine (registry-first, legacy
   ``resolve_path`` fallback). If the file is here, ``git_identity`` gives the authoritative
   ``repo_id`` / ``repo_relpath`` / ``commit`` / ``blob_oid``; we write them and set
   ``blob_oid_baseline = blob_oid`` (the recompute). The repo is registered so later runs
   resolve directly. We also learn ``repo_tag -> repo_id`` from each resolved site.
2. **Tag map** — sites we could not resolve here (their repo isn't on this machine) get a
   ``repo_id`` from the learned ``repo_tag -> repo_id`` map (scoping only, no blob baseline —
   the machine that has the repo will fill that on its own migrate/verify run). Sites with no
   resolvable file AND no known tag are left untouched.

Idempotent: a site that already has ``repo_id`` + ``repo_relpath`` + ``blob_oid_baseline`` is
skipped. ``--dry-run`` reports without writing.

    python -m engine.longinus_drift_audit.migrate_repo_ids --kg neo4j --dry-run
    python -m engine.longinus_drift_audit.migrate_repo_ids --kg neo4j            # write
    python -m engine.longinus_drift_audit.migrate_repo_ids --kg neo4j --repo-tag bhgman

# KG: ATOM_Skill_longinus
"""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass, field
from typing import Iterable, Optional

from engine.longinus_drift_audit.kg_client import KgClient
from engine.longinus_drift_audit.repo_identity import git_identity
from engine.longinus_drift_audit.sha256_baseline import DEFAULT_FS_BASE_CHAIN, resolve_site

logger = logging.getLogger(__name__)


@dataclass
class MigrateResult:
    # KG: ATOM_Skill_longinus
    total: int = 0
    already: int = 0  # already fully anchored (repo_id + repo_relpath + blob_oid_baseline)
    migrated: int = 0  # resolved on disk → full git anchor written
    tagged_only: int = 0  # not resolvable here; repo_id inferred from the repo_tag map
    unresolved: int = 0  # no disk file AND no known repo_tag → left untouched
    repos_registered: int = 0  # distinct repos auto-registered during the run
    details: list[dict] = field(default_factory=list)


def migrate(
    kg: KgClient,
    *,
    registry=None,
    base_chain: Iterable[str] = DEFAULT_FS_BASE_CHAIN,
    repo_tag: Optional[str] = None,
    dry_run: bool = False,
    register_repos: bool = True,
) -> MigrateResult:
    # KG: ATOM_Skill_longinus
    """Backfill repo_id / repo_relpath / commit / blob_oid(_baseline) onto legacy sites."""
    from engine.longinus_drift_audit.repo_registry import default_registry

    reg = registry or default_registry()
    chain = tuple(base_chain)
    sites = kg.list_reference_site_states(repo_tag)
    result = MigrateResult()
    tag_to_id: dict[str, str] = {}
    registered: set[str] = set()
    deferred = []

    # ── pass 1: disk-resolve + git_identity ──
    for site in sites:
        result.total += 1
        if site.repo_id and site.repo_relpath and site.blob_oid_baseline:
            result.already += 1
            if site.repo_tag:
                tag_to_id.setdefault(site.repo_tag, site.repo_id)
            continue
        res = resolve_site(site, base_chain=chain, registry=reg)
        if res.status == "FILE" and res.abs_path:
            ident = git_identity(res.abs_path)
            if ident["repo_id"] and ident["blob_oid"]:
                updates = {
                    "repo_id": site.repo_id or ident["repo_id"],
                    "repo_relpath": site.repo_relpath or ident["repo_relpath"],
                    "commit": ident["commit"],
                    "blob_oid": ident["blob_oid"],
                    "blob_oid_baseline": site.blob_oid_baseline or ident["blob_oid"],
                }
                if not dry_run:
                    kg.merge_reference_site_state(site.model_copy(update=updates))
                    if register_repos and ident["toplevel"]:
                        reg.register(
                            ident["repo_id"], ident["toplevel"], remote=ident["remote"], log=False
                        )
                registered.add(ident["repo_id"])
                if site.repo_tag:
                    tag_to_id.setdefault(site.repo_tag, ident["repo_id"])
                result.migrated += 1
                result.details.append(
                    {
                        "sourceId": site.sourceId,
                        "action": "migrated",
                        "repo_id": updates["repo_id"],
                        "repo_relpath": updates["repo_relpath"],
                    }
                )
                continue
        deferred.append(site)

    # ── pass 2: repo_tag → repo_id for the unresolvable ──
    for site in deferred:
        rid = tag_to_id.get(site.repo_tag) if site.repo_tag else None
        if rid:
            relpath = site.repo_relpath
            if relpath is None and not os.path.isabs(site.file):
                relpath = site.file  # sourcePath was repo-relative
            updates = {"repo_id": site.repo_id or rid, "repo_relpath": relpath}
            if not dry_run:
                kg.merge_reference_site_state(site.model_copy(update=updates))
            result.tagged_only += 1
            result.details.append(
                {
                    "sourceId": site.sourceId,
                    "action": "tagged_only",
                    "repo_id": updates["repo_id"],
                    "repo_relpath": relpath,
                }
            )
        else:
            result.unresolved += 1
            result.details.append({"sourceId": site.sourceId, "action": "unresolved"})

    result.repos_registered = len(registered)
    logger.info(
        "migrate-repo-ids%s: total=%d already=%d migrated=%d tagged_only=%d unresolved=%d "
        "repos_registered=%d",
        " (dry-run)" if dry_run else "",
        result.total,
        result.already,
        result.migrated,
        result.tagged_only,
        result.unresolved,
        result.repos_registered,
    )
    return result


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(
        prog="longinus-migrate-repo-ids", description=__doc__.splitlines()[0]
    )
    ap.add_argument("--kg", choices=["neo4j", "mock", "local", "mcp"], default="neo4j")
    ap.add_argument("--uri", default=os.environ.get("NEO4J_URI"))
    ap.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    ap.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"))
    ap.add_argument("--kg-path", default=os.environ.get("BHGMAN_KG_JSON"))
    ap.add_argument("--mcp-url", default=os.environ.get("BHGMAN_KG_MCP_URL"))
    ap.add_argument("--repo-tag", default=None, help="scope to one repo_tag (shared KG)")
    ap.add_argument("--dry-run", action="store_true", help="report without writing")
    args = ap.parse_args(argv)

    from engine.longinus_drift_audit.audit_runner import build_kg

    kg = build_kg(args)
    result = migrate(kg, repo_tag=args.repo_tag, dry_run=args.dry_run)
    print(
        f"{'[dry-run] ' if args.dry_run else ''}"
        f"total={result.total} already={result.already} migrated={result.migrated} "
        f"tagged_only={result.tagged_only} unresolved={result.unresolved} "
        f"repos_registered={result.repos_registered}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
