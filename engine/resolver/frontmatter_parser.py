"""APT resolver — frontmatter parser.

`python-frontmatter` thin wrapper. SKILL.md를 (frontmatter dict, body string)으로 분리.

KG ref: rfc-apt-v26-A6-resolver-path-A-pre-prompt-hook-2026-04-30
Absorbed from SYMPOSIUM/THEORY/APT/resolver_prototype/frontmatter_parser.py (Wave 7 P3-H).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import frontmatter


@dataclass(frozen=True, slots=True)
class ParsedSkill:
    frontmatter: dict
    body: str
    source_path: Path


def parse(path: str | Path) -> ParsedSkill:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        post = frontmatter.load(f)
    return ParsedSkill(
        frontmatter=dict(post.metadata),
        body=post.content,
        source_path=p,
    )


def dump(skill: ParsedSkill, target: str | Path) -> None:
    """Resolved skill을 다시 frontmatter 형식으로 직렬화."""
    target_path = Path(target)
    post = frontmatter.Post(content=skill.body, **skill.frontmatter)
    with target_path.open("w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))
