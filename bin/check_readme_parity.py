#!/usr/bin/env python3
"""README structural-parity guard (bhg-f-readme-translation-drift).

Flags translations that have drifted from README.md (the English source) by section
count — catching *silently* missing sections (the finding's root complaint: EN-only
sections quietly absent from ko/ja/zh). Language-agnostic (counts ``##``/``###``
anchors, not titles). Informational by default (exit 0, emits a GitHub ::warning::);
pass ``--strict`` to fail CI once the translations are re-synced by a human.
"""

# KG: bhg-f-readme-translation-drift-2026-06-16, audit-bhgman-tool-codex-feedback-and-deep-review-2026-06-16

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = "README.md"
TRANSLATIONS = ("README.ko-KR.md", "README.ja-JP.md", "README.zh-CN.md")

_SECTION = re.compile(r"(?m)^#{2,3}[ \t]")


def section_count(path: Path) -> int:
    return len(_SECTION.findall(path.read_text(encoding="utf-8")))


def check(root: Path = ROOT) -> list[str]:
    """Return the list of translation filenames that have fewer sections than the source."""
    en_n = section_count(root / SOURCE)
    print(f"README parity — source {SOURCE} = {en_n} sections")
    drifted: list[str] = []
    for name in TRANSLATIONS:
        path = root / name
        if not path.is_file():
            continue
        n = section_count(path)
        ok = n >= en_n
        print(f"  {name}: {n} sections — {'OK' if ok else f'DRIFT (-{en_n - n})'}")
        if not ok:
            drifted.append(name)
    return drifted


def main(argv: list[str]) -> int:
    drifted = check()
    if drifted:
        print(
            f"::warning::README translations drifted from {SOURCE}: {', '.join(drifted)} "
            "(fewer sections than the English source — re-sync the missing sections)"
        )
        if "--strict" in argv:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
