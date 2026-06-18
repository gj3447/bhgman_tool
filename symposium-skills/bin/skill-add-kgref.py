#!/usr/bin/env python3
"""Idempotently add `kg_ref: ATOM_Skill_<x>` to SKILL.md frontmatter.

Mapping is hardcoded from the KG query at 2026-04-26. Re-run safe — already-set files are skipped.
"""
import sys
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parent.parent

MAPPING = {
    "88-taliban": "ATOM_Skill_88taliban",
    "apt": "ATOM_Skill_apt_orchestrator",
    "apt-meta-review": "ATOM_Skill_apt_meta_review",
    "apt-sa": "ATOM_Skill_apt_sa",
    "apt-scw": "ATOM_Skill_apt_scw",
    "apt-sp": "ATOM_Skill_apt_sp",
    "apt-st": "ATOM_Skill_apt_st",
    "backup": "ATOM_Skill_backup",
    "db-query": "ATOM_Skill_db_query",
    "deploy": "ATOM_Skill_deploy",
    "docker-logs": "ATOM_Skill_docker_logs",
    "harness": "ATOM_Skill_harness",
    "jaebaeman": "ATOM_Skill_jaebaeman",
    "kafka-manage": "ATOM_Skill_kafka_manage",
    "longinus": "ATOM_Skill_longinus",
    "prom": "ATOM_Skill_prom_alias",
    "prometheus": "ATOM_Skill_prometheus",
    "server-status": "ATOM_Skill_server_status",
    "skill-creator": "ATOM_Skill_skill_creator",
    "solve": "ATOM_Skill_solve",
    "taliban": "ATOM_Skill_taliban",
    "tlb": "ATOM_Skill_tlb_alias",
    "tpa": "ATOM_Skill_tpa_orchestrator_v10",
    "tpa-ta": "ATOM_Skill_tpa_ta",
    "tpa-tcw": "ATOM_Skill_tpa_tcw",
    "tpa-tp": "ATOM_Skill_tpa_tp",
    "tpa-tt": "ATOM_Skill_tpa_tt",
}


def patch(skill_dir: str, atom: str, dry_run: bool) -> str:
    p = SKILLS_ROOT / skill_dir / "SKILL.md"
    if not p.exists():
        return f"MISSING {p}"

    lines = p.read_text().splitlines(keepends=True)
    if not lines or not lines[0].startswith("---"):
        return f"NO_FM   {p}"

    # Find frontmatter end
    fm_end = None
    for i, ln in enumerate(lines[1:], start=1):
        if ln.startswith("---"):
            fm_end = i
            break
    if fm_end is None:
        return f"NO_FM_END {p}"

    fm = lines[1:fm_end]
    # idempotent: skip if kg_ref already present
    for ln in fm:
        if ln.lstrip().startswith("kg_ref:"):
            return f"SKIP    {skill_dir} (already has kg_ref)"

    # Insert after `name:` line
    insert_idx = None
    for i, ln in enumerate(fm):
        if ln.lstrip().startswith("name:"):
            insert_idx = i + 1
            break
    if insert_idx is None:
        insert_idx = 0

    new_line = f"kg_ref: {atom}\n"
    new_fm = fm[:insert_idx] + [new_line] + fm[insert_idx:]
    new_lines = lines[:1] + new_fm + lines[fm_end:]

    if dry_run:
        return f"DRY     {skill_dir} -> kg_ref: {atom}"
    p.write_text("".join(new_lines))
    return f"PATCH   {skill_dir} -> kg_ref: {atom}"


def main() -> int:
    dry = "--dry-run" in sys.argv
    rc = 0
    for skill_dir, atom in sorted(MAPPING.items()):
        try:
            print(patch(skill_dir, atom, dry))
        except Exception as e:
            print(f"ERR     {skill_dir}: {e}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
