"""APT v27 A6 path A — Pre-prompt resolver entry point.

사용법 (standalone module mode):
    python -m engine.resolver.resolver render --input <SKILL.md> --output <resolved.md>
    python -m engine.resolver.resolver validate <SKILL.md>

CLI integration:
    bhgman-tool resolver render --input <SKILL.md> --output <resolved.md>
    bhgman-tool resolver validate <SKILL.md>

Composition Root 정책 (eager validation):
1. KG 연결 health check
2. MethodologyConfig 5 core field 존재 검증
3. SandboxedEnv 보안 정책 확인
4. fail → startup exception (SKILL.md 부분-resolved 절대 출력 안 함)

KG ref: rfc-apt-v26-A6-resolver-path-A-pre-prompt-hook-2026-04-30
Absorbed from SYMPOSIUM/THEORY/APT/resolver_prototype/resolver.py (Wave 7 P3-H, 2026-05-14).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from . import frontmatter_parser
from .cypher_kg_client import (
    CORE_MAGIC_FIELDS,
    CypherKGClient,
    KGConfig,
    MissingConfigError,
)
from .jinja_env import build_env, UnresolvedMarkerError


CFG_MARKER_RE = re.compile(r"\{\{\s*cfg\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
INLINE_NUMBER_RE = re.compile(r"(?<![\w./])(\d{2,4})(?![\w./])")  # 2-4 digit, word boundary
PARENTHETICAL_HINT_RE = re.compile(r"\(\s*현재\s+\d+(?:[-~]\d+)?\s*\)")


# ─── DTOs ────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResolveResult:
    rendered_body: str
    used_markers: tuple[str, ...]
    cfg_snapshot: dict


@dataclass(frozen=True, slots=True)
class ValidateReport:
    skill_path: Path
    markers_found: tuple[str, ...]
    missing_in_kg: tuple[str, ...]
    bare_inline_numbers: tuple[tuple[int, str], ...]  # (line, number)
    orphan_kg_fields: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not (self.missing_in_kg or self.bare_inline_numbers)


# ─── Composition Root ───────────────────────────────────────────────────


def boot_kg_client() -> CypherKGClient:
    from neo4j.exceptions import DriverError, Neo4jError  # noqa: PLC0415

    try:
        cfg = KGConfig.from_env()
    except KeyError as e:
        # missing NEO4J_* env → clean BOOT FAIL, not a raw KeyError traceback.
        raise SystemExit(
            f"[BOOT FAIL] KG env not configured (missing {e}). Set NEO4J_URI / "
            "NEO4J_PASSWORD (NEO4J_USER optional), or run via parent Claude MCP. "
            "Resolver refuses partial render."
        )
    client = CypherKGClient(cfg)
    try:
        healthy = client.health_check()
    except (DriverError, Neo4jError) as e:
        # server unreachable / bad auth → clean BOOT FAIL, not a raw neo4j traceback.
        client.close()
        raise SystemExit(
            f"[BOOT FAIL] KG unreachable ({type(e).__name__}). Resolver refuses partial render."
        )
    if not healthy:
        client.close()
        raise SystemExit("[BOOT FAIL] KG unreachable. Resolver refuses partial render.")
    try:
        client.verify_core_magic_present()
    except MissingConfigError as e:
        client.close()
        raise SystemExit(f"[BOOT FAIL] {e}")
    return client


# ─── render path ────────────────────────────────────────────────────────


def resolve(skill_path: Path, client: CypherKGClient) -> ResolveResult:
    skill = frontmatter_parser.parse(skill_path)
    cfg = client.fetch_methodology_config()
    markers = tuple(sorted(set(CFG_MARKER_RE.findall(skill.body))))

    env = build_env()
    template = env.from_string(skill.body)
    try:
        rendered = template.render(cfg=cfg)
    except UnresolvedMarkerError as e:
        raise SystemExit(f"[RESOLVE FAIL] {e}")

    return ResolveResult(
        rendered_body=rendered,
        used_markers=markers,
        cfg_snapshot={k: cfg[k] for k in markers if k in cfg},
    )


# ─── validate path (drift detection) ────────────────────────────────────


def validate(skill_path: Path, client: CypherKGClient) -> ValidateReport:
    skill = frontmatter_parser.parse(skill_path)
    cfg = client.fetch_methodology_config()
    markers = tuple(sorted(set(CFG_MARKER_RE.findall(skill.body))))

    # 1) KG 누락 검사
    missing = tuple(m for m in markers if m not in cfg)

    # 2) bare inline number 검사 (괄호 안 reader-facing 안내는 OK)
    bare: list[tuple[int, str]] = []
    for lineno, line in enumerate(skill.body.splitlines(), start=1):
        # 괄호 안 "(현재 200)" 같은 안내는 제거 후 검사
        cleaned = PARENTHETICAL_HINT_RE.sub("", line)
        for m in INLINE_NUMBER_RE.finditer(cleaned):
            num = m.group(1)
            # core magic 후보 숫자만 위반 (200/500/9/7/8 등)
            if num in {"200", "500", "9", "7", "8"}:
                bare.append((lineno, num))

    # 3) orphan KG field (KG에 있는데 SKILL 어디서도 참조 안 됨)
    orphans = tuple(f for f in CORE_MAGIC_FIELDS if f in cfg and f not in markers)

    return ValidateReport(
        skill_path=skill_path,
        markers_found=markers,
        missing_in_kg=missing,
        bare_inline_numbers=tuple(bare),
        orphan_kg_fields=orphans,
    )


# ─── CLI ────────────────────────────────────────────────────────────────


def _cmd_render(args: argparse.Namespace, client) -> int:
    result = resolve(args.input, client)
    args.output.write_text(result.rendered_body, encoding="utf-8")
    print(f"[OK] Rendered → {args.output} (markers: {len(result.used_markers)})")
    return 0


def _print_validate_report(report) -> None:
    print(f"[VALIDATE] {report.skill_path}")
    print(f"  markers found: {len(report.markers_found)}")
    if report.missing_in_kg:
        print(f"  ✗ missing in KG: {report.missing_in_kg}")
    if report.bare_inline_numbers:
        print("  ✗ bare inline numbers (RFC A6.1 위반):")
        for ln, n in report.bare_inline_numbers:
            print(f"      line {ln}: {n}")
    if report.orphan_kg_fields:
        print(f"  ⚠ orphan cfg fields (KG에 있으나 SKILL 미참조): {report.orphan_kg_fields}")


def _cmd_validate(args: argparse.Namespace, client) -> int:
    report = validate(args.path, client)
    _print_validate_report(report)
    return 0 if report.ok else 1


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="APT v27 A6 pre-prompt resolver")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_render = sub.add_parser("render", help="resolve {{cfg.X}} markers")
    p_render.add_argument("--input", required=True, type=Path)
    p_render.add_argument("--output", required=True, type=Path)

    p_val = sub.add_parser("validate", help="KG ↔ SKILL drift check")
    p_val.add_argument("path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)
    client = boot_kg_client()
    try:
        if args.cmd == "render":
            return _cmd_render(args, client)
        if args.cmd == "validate":
            return _cmd_validate(args, client)
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
