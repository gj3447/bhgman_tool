#!/usr/bin/env python3
"""APT Lean metrics — single source of truth generator (W3 + W4 fix).

Why this exists (APT-zero roadmap, 2026-06-02):
  W3 — APT docs cite Lean theorem/sorry/file counts that DON'T reconcile to disk
       (245+ / 220 / 203 / 187 / 103 all appear; none match the real 32 files / 340
       theorem lines). Hand-typed numbers drift. This generator makes the numbers a
       *generated artifact* (with sha256 per file). Docs should reference the JSON, not
       retype numbers. `--check` flags hand-typed Lean counts that disagree.
  W4 — "0 sorry = proven" absorbs trivial-discharge. `APT_WaveIndex_Mirsky.lean` itself
       documents "all sorry replaced by disjunct-discharge or surface trivial witness".
       This separates SORRY / live-ADMIT / disjunct-discharge-documented and, when a Lean
       toolchain is available, can deepen to `#print axioms`. Without a lakefile/toolchain
       the axiom-level classification is honestly reported as UNKNOWN (no false "proven").

Usage:
  python3 apt_metrics_gen.py                 # generate -> THEORY/APT/_metrics/lean_metrics.json
  python3 apt_metrics_gen.py --check         # scan active docs for drifting hand-typed counts (exit 1 on mismatch)
  python3 apt_metrics_gen.py --print         # print aggregate to stdout, no write

KG: project-apt-ultracode-roadmap-2026-06-02 (W3/W4 measurement-first)
    lesson-stale-corrupted-read-before-writeup-2026-05-30 (verify before writeup)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Defaults — overridable via CLI. Cross-repo (tool layer reads paper-layer Lean).
DEFAULT_LEAN_ROOT = Path("/Users/lagyeongjun/CD/MIND/lean_formalization")
DEFAULT_DOCS_ROOT = Path("/Users/lagyeongjun/CD/SYMPOSIUM/THEORY/APT")
DEFAULT_OUT = DEFAULT_DOCS_ROOT / "_metrics" / "lean_metrics.json"

THEOREM_RE = re.compile(r"(?m)^[ \t]*theorem\b")
LEMMA_RE = re.compile(r"(?m)^[ \t]*lemma\b")
SORRY_RE = re.compile(r"\bsorry\b")
ADMIT_RE = re.compile(r"\badmit\b")
# Documented trivial-discharge / stub markers (W4 honesty heuristic)
DISJUNCT_RE = re.compile(
    r"DISCHARGED via disjunct|sorry replaced by disjunct"
    r"|=\s*sorry\s*/\s*TODO|disjunct-discharge|surface trivial witness",
    re.IGNORECASE,
)


def strip_comments(src: str) -> str:
    """Remove Lean string literals, block (/- -/, incl. /-- -/ docstrings) and line (--)
    comments — so `sorry`/`admit` are counted only as live PROOF terms, not as words inside
    docstrings, error-message strings, or enum-to-string maps (e.g. "Mathlib-free 0 sorry").
    Strings stripped first (a `--` inside a string is content, not a comment). Non-nested
    block-comment approximation — sufficient to separate live code from documentation.
    Measurement-accuracy pre-filter (feedback_efficacy_via_borrowed_theory_tests:
    'Lean sorry docstring over-count 걸러냄')."""
    src = re.sub(r'"(?:[^"\\]|\\.)*"', " ", src)  # string literals (incl. s!"..." bodies)
    src = re.sub(r"/-.*?-/", " ", src, flags=re.DOTALL)
    src = re.sub(r"--[^\n]*", " ", src)
    return src


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def measure_file(p: Path) -> dict:
    raw = p.read_text(errors="ignore")
    code = strip_comments(raw)
    total_sorry = len(SORRY_RE.findall(raw))
    live_sorry = len(SORRY_RE.findall(code))
    total_admit = len(ADMIT_RE.findall(raw))
    live_admit = len(ADMIT_RE.findall(code))
    return {
        "file": p.name,
        "sha256": sha256_of(p),
        "theorems": len(THEOREM_RE.findall(raw)),
        "lemmas": len(LEMMA_RE.findall(raw)),
        "live_sorry": live_sorry,
        "comment_sorry": total_sorry - live_sorry,
        "live_admit": live_admit,
        "comment_admit": total_admit - live_admit,
        "disjunct_discharge_documented": len(DISJUNCT_RE.findall(raw)),
    }


def compute(lean_root: Path, glob: str = "APT*.lean", *, with_axioms: bool = False) -> dict:
    files = sorted(p for p in lean_root.glob(glob) if p.is_file())
    per_file = [measure_file(p) for p in files]
    agg = {
        "n_files": len(per_file),
        "n_theorems": sum(f["theorems"] for f in per_file),
        "n_lemmas": sum(f["lemmas"] for f in per_file),
        "n_live_sorry": sum(f["live_sorry"] for f in per_file),
        "n_comment_sorry": sum(f["comment_sorry"] for f in per_file),
        "n_live_admit": sum(f["live_admit"] for f in per_file),
        "n_disjunct_discharge_documented": sum(
            f["disjunct_discharge_documented"] for f in per_file
        ),
    }
    # W4: authoritative "no hidden sorry" via lean `#print axioms` (opt-in --axioms, slow).
    if with_axioms:
        from engine.efficacy.lean_axiom_probe import probe_all  # noqa: PLC0415

        oracle = probe_all(lean_root, glob)
        agg["axiom_oracle"] = oracle
        if oracle.get("available"):
            agg["axiom_classification"] = "MEASURED"
            agg["axiom_classification_note"] = (
                f"lean #print axioms: n_sorry_tainted={oracle['n_sorry_tainted']} (transitive sorryAx), "
                f"n_genuinely_proven={oracle['n_genuinely_proven']}/{oracle['n_theorems_probed']}. "
                "Authoritative for hidden sorry; does NOT detect statement-weakening "
                "(disjunct-discharge) — see n_disjunct_discharge_documented."
            )
        else:
            agg["axiom_classification"] = "UNKNOWN"
            agg["axiom_classification_note"] = oracle.get("note", "axiom oracle unavailable")
    else:
        agg["axiom_classification"] = "UNKNOWN"
        agg["axiom_classification_note"] = (
            "per-theorem `#print axioms` not run (use --axioms). '0 live_sorry' is regex/proof-TERM "
            "level only and does NOT certify deep theorems are non-trivially proven "
            "(see n_disjunct_discharge_documented). Do not read 'proven'."
        )
    return {
        "schema": "apt_lean_metrics_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lean_root": str(lean_root),
        "glob": glob,
        "aggregate": agg,
        "per_file": per_file,
        "provenance": "generated by bhgman_tool/engine/efficacy/apt_metrics_gen.py — do not hand-edit",
    }


# ---- W3 drift check: scan active docs for hand-typed Lean counts that disagree ----
CLAIM_PATTERNS = [
    (re.compile(r"(\d+)\+?\s*(?:Lean\s+)?theorems?\b", re.IGNORECASE), "n_theorems"),
    (re.compile(r"(\d+)\s*(?:Lean\s+)?files?\b", re.IGNORECASE), "n_files"),
    (re.compile(r"across\s+(\d+)\s+files", re.IGNORECASE), "n_files"),
]
ZERO_SORRY_RE = re.compile(r"\b0\s+sorry\b", re.IGNORECASE)
TOKEN_RE = re.compile(r"\{\{\s*metric:")  # allowed: {{metric:n_theorems}}


MIN_COUNT = {"n_theorems": 20, "n_files": 5}  # ignore tiny incidental numbers


def _finding(md_name: str, i: int, line: str, key: str, claimed: int, actual: int) -> dict:
    return {
        "file": md_name,
        "line": i,
        "key": key,
        "claimed": claimed,
        "actual": actual,
        "text": line.strip()[:120],
    }


def _claim_findings(md_name: str, i: int, line: str, agg: dict, tolerance: int) -> list[dict]:
    out: list[dict] = []
    for pat, key in CLAIM_PATTERNS:
        actual = agg.get(key)
        if actual is None:
            continue
        for m in pat.finditer(line):
            claimed = int(m.group(1))
            if claimed < MIN_COUNT.get(key, 0):
                continue
            if abs(claimed - actual) > tolerance:
                out.append(_finding(md_name, i, line, key, claimed, actual))
    return out


def _line_findings(md_name: str, i: int, line: str, agg: dict, tolerance: int) -> list[dict]:
    if TOKEN_RE.search(line):
        return []  # references the generated token — fine
    low = line.lower()
    if not any(k in low for k in ("theorem", "lean", "sorry", "file")):
        return []
    out = _claim_findings(md_name, i, line, agg, tolerance)
    if ZERO_SORRY_RE.search(line) and agg["n_live_sorry"] != 0:
        out.append(_finding(md_name, i, line, "n_live_sorry", 0, agg["n_live_sorry"]))
    return out


def check_docs(docs_root: Path, agg: dict, tolerance: int = 0) -> list[dict]:
    """Return list of drift findings. A finding = a hand-typed count that mismatches agg."""
    findings: list[dict] = []
    for md in sorted(docs_root.glob("*.md")):
        try:
            text = md.read_text(errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            findings.extend(_line_findings(md.name, i, line, agg, tolerance))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lean-root", type=Path, default=DEFAULT_LEAN_ROOT)
    ap.add_argument("--docs-root", type=Path, default=DEFAULT_DOCS_ROOT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--check",
        action="store_true",
        help="scan docs for drifting hand-typed counts (exit 1 on mismatch)",
    )
    ap.add_argument(
        "--print", dest="do_print", action="store_true", help="print aggregate, no write"
    )
    ap.add_argument(
        "--max-drift",
        type=int,
        default=-1,
        help="ratchet: with --check, exit 1 only if drift COUNT exceeds this baseline "
        "(grandfathers existing drift, blocks net-new). -1 (default) = strict (any drift fails).",
    )
    ap.add_argument(
        "--axioms",
        action="store_true",
        help="run the lean `#print axioms` oracle (slow, authoritative no-hidden-sorry). "
        "Sets axiom_classification=MEASURED.",
    )
    args = ap.parse_args()

    data = compute(args.lean_root, with_axioms=args.axioms)
    agg = data["aggregate"]

    if args.check:
        findings = check_docs(args.docs_root, agg)
        limit = args.max_drift
        over = len(findings) if limit < 0 else max(0, len(findings) - limit)
        if findings and over > 0:
            kind = "exceed strict 0" if limit < 0 else f"exceed ratchet baseline {limit}"
            print(
                f"[apt-metrics --check] {len(findings)} hand-typed Lean count(s) disagree with disk "
                f"({over} {kind}):",
                file=sys.stderr,
            )
            for f in findings[:40]:
                print(
                    f"  {f['file']}:{f['line']} claims {f['key']}={f['claimed']} but disk={f['actual']} | {f['text']}",
                    file=sys.stderr,
                )
            print(f"\n  Disk truth: {json.dumps(agg, ensure_ascii=False)}", file=sys.stderr)
            return 1
        msg = (
            "no drifting hand-typed Lean counts found."
            if not findings
            else f"{len(findings)} drift(s) within ratchet baseline {limit} (grandfathered; "
            f"migrate to {{{{metric:...}}}} tokens to ratchet down)."
        )
        print(f"[apt-metrics --check] {msg}")
        return 0

    if args.do_print:
        print(json.dumps(agg, indent=2, ensure_ascii=False))
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"wrote {args.out}")
    print(json.dumps(agg, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
