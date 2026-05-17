"""Run the Longinus drift audit on sample.py with simulated KG.

KG: span-worked-example-longinus-simple-2026-05-13 (:AtomicSpan)
Reproducible — no network access, no external services.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
KG_PATH = HERE / "kg_simulated.json"
CODE_PATH = HERE / "sample.py"

KG_REF_RE = re.compile(r"#\s*KG:\s*(\S+)")


def extract_kg_refs(source: str) -> list[tuple[int, str]]:
    """Return [(line_number, kg_id)] for every `# KG: ...` comment."""
    refs: list[tuple[int, str]] = []
    for i, line in enumerate(source.splitlines(), start=1):
        m = KG_REF_RE.search(line)
        if m:
            refs.append((i, m.group(1)))
    return refs


def find_next_def(source: str, start_line: int) -> tuple[str, int] | None:
    """Find the next `def ...` after `start_line`. Returns (signature_str, line_no)."""
    tree = ast.parse(source)
    candidates = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.lineno > start_line:
            params = []
            args = node.args
            for arg, default in zip(
                args.args[-len(args.defaults) :] if args.defaults else [],
                args.defaults,
            ):
                default_repr = ast.unparse(default)
                params.append(
                    f"{arg.arg}: {ast.unparse(arg.annotation) if arg.annotation else 'Any'} = {default_repr}"
                )
            no_default_count = len(args.args) - len(args.defaults)
            no_default_params = [
                f"{a.arg}: {ast.unparse(a.annotation) if a.annotation else 'Any'}"
                for a in args.args[:no_default_count]
            ]
            sig_params = no_default_params + params
            returns = ast.unparse(node.returns) if node.returns else "Any"
            sig = f"{node.name}({', '.join(sig_params)}) -> {returns}"
            candidates.append((sig, node.lineno))
    candidates.sort(key=lambda x: x[1])
    return candidates[0] if candidates else None


def audit() -> list[dict]:
    source = CODE_PATH.read_text()
    kg = json.loads(KG_PATH.read_text())
    drifts: list[dict] = []

    for line, kg_id in extract_kg_refs(source):
        if kg_id not in kg:
            drifts.append(
                {
                    "drift_type": "Orphan",
                    "kg_id": kg_id,
                    "code_location": f"{CODE_PATH.name}:{line}",
                    "expected": "KG record",
                    "actual": "not found in kg_simulated.json",
                    "layer_violated": "L4_SemioticBinding",
                    "lens_law_violated": "GetPut",
                }
            )
            continue
        found = find_next_def(source, line)
        if found is None:
            continue
        actual_sig, def_line = found
        expected_sig = kg[kg_id]["expected_signature"]
        if expected_sig != actual_sig:
            drifts.append(
                {
                    "drift_type": "SigMismatch",
                    "kg_id": kg_id,
                    "code_location": f"{CODE_PATH.name}:{def_line}",
                    "expected": expected_sig,
                    "actual": actual_sig,
                    "layer_violated": kg[kg_id].get("layer", "L3_TypePermission"),
                    "lens_law_violated": "PutGet",
                }
            )

    return drifts


def render_report(drifts: list[dict], total_refs: int) -> str:
    lines = [
        "Longinus Audit Report",
        "=====================",
        f"Scanned: 1 file, {total_refs} KG references",
        f"Drifts detected: {len(drifts)}",
        "",
    ]
    for d in drifts:
        lines.append(f"[{d['drift_type']} @ {d['code_location']}]")
        lines.append(f"  KG: {d['kg_id']}")
        lines.append(f"  Expected: {d['expected']}")
        lines.append(f"  Actual:   {d['actual']}")
        lines.append(f"  Layer violated: {d['layer_violated']}")
        lines.append(f"  BX Lens law violated: {d['lens_law_violated']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    source = CODE_PATH.read_text()
    total_refs = len(extract_kg_refs(source))
    drifts = audit()
    print(render_report(drifts, total_refs))
    return 0 if not drifts else 1  # exit code reflects drift presence


if __name__ == "__main__":
    sys.exit(main())
