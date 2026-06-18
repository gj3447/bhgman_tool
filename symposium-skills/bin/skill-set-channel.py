#!/usr/bin/env python3
"""skill-set-channel.py — idempotently set/update `channel:` in SKILL.md frontmatter.

Usage:
  skill-set-channel.py <skill_name> <channel>          # single
  skill-set-channel.py --all-default-stable            # bulk: add channel:stable to all (no overwrite)
  skill-set-channel.py ... --dry-run                   # preview
"""
import sys
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parent.parent
VALID_CHANNELS = {"experimental", "beta", "stable"}


def patch(skill_dir, new_channel, dry_run=False):
    p = SKILLS_ROOT / skill_dir / "SKILL.md"
    if not p.exists():
        return f"MISSING {p}"
    if new_channel not in VALID_CHANNELS:
        return f"INVALID channel '{new_channel}' (allowed: {sorted(VALID_CHANNELS)})"

    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines or not lines[0].startswith("---"):
        return f"NO_FM   {p}"

    fm_end = None
    for i, ln in enumerate(lines[1:], start=1):
        if ln.startswith("---"):
            fm_end = i
            break
    if fm_end is None:
        return f"NO_FM_END {p}"

    fm = lines[1:fm_end]
    for i, ln in enumerate(fm):
        if ln.lstrip().startswith("channel:"):
            current = ln.split(":", 1)[1].strip()
            if current == new_channel:
                return f"SKIP    {skill_dir} (already channel:{current})"
            if dry_run:
                return f"DRY     {skill_dir} channel:{current} -> {new_channel}"
            fm[i] = f"channel: {new_channel}\n"
            new_lines = lines[:1] + fm + lines[fm_end:]
            p.write_text("".join(new_lines), encoding="utf-8")
            return f"UPDATE  {skill_dir} channel:{current} -> {new_channel}"

    insert_idx = None
    for i, ln in enumerate(fm):
        if ln.lstrip().startswith("version:"):
            insert_idx = i + 1
            break
    if insert_idx is None:
        for i, ln in enumerate(fm):
            if ln.lstrip().startswith("name:"):
                insert_idx = i + 1
                break
    if insert_idx is None:
        insert_idx = 0

    if dry_run:
        return f"DRY     {skill_dir} -> channel:{new_channel}"
    new_line = f"channel: {new_channel}\n"
    new_fm = fm[:insert_idx] + [new_line] + fm[insert_idx:]
    new_lines = lines[:1] + new_fm + lines[fm_end:]
    p.write_text("".join(new_lines), encoding="utf-8")
    return f"PATCH   {skill_dir} -> channel:{new_channel}"


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    if args and args[0] == "--all-default-stable":
        rc = 0
        for skill_dir in sorted(SKILLS_ROOT.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            if not (skill_dir / "SKILL.md").exists():
                continue
            try:
                print(patch(skill_dir.name, "stable", dry))
            except Exception as e:
                print(f"ERR     {skill_dir.name}: {e}", file=sys.stderr)
                rc = 1
        return rc

    if len(args) != 2:
        print("usage: skill-set-channel.py {<skill_name> <channel>|--all-default-stable} [--dry-run]", file=sys.stderr)
        return 2
    print(patch(args[0], args[1], dry))
    return 0


if __name__ == "__main__":
    sys.exit(main())
