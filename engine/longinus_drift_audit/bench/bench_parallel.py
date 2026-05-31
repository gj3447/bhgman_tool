"""Benchmark — sequential vs L1 (scan parallel) vs L1+L2 (full parallel).

Synthetic corpus of N files: 10 / 100 / 500 / 2000. Each file ~20 LOC mix of
def/class with `# KG: xxx` comments. Real-repo bench: --root /path runs on
the given codebase.

Output: JSON to stdout, columns:
    file_count, sequential_s, l1_only_s, full_parallel_s, speedup_l1, speedup_full

# KG: longinus-parallel-bench-2026-05-18
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

# Path bootstrap when invoked as `python bench/bench_parallel.py` from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.longinus_drift_audit import code_scanner  # noqa: E402
from engine.longinus_drift_audit.audit_runner import LonginusAudit  # noqa: E402
from engine.longinus_drift_audit.kg_client import MockKgClient  # noqa: E402
from engine.longinus_drift_audit.models import KgRefRecord  # noqa: E402


def _seed_n_files(tmp: Path, n: int, loc_per_file: int = 80) -> None:
    """Generate n files each with roughly loc_per_file lines, mixing
    def/class + KG ref comments to approximate real-codebase regex work."""
    for i in range(n):
        lines: list[str] = []
        # Realistic file: ~loc_per_file lines with k=5 symbols + extra prose
        for j in range(max(1, loc_per_file // 8)):
            sym_idx = i * 100 + j
            if (i + j) % 7 == 0:
                lines.append(f"def helper_{sym_idx}(x): pass")
            elif (i + j) % 3 == 0:
                lines.append(f"def func_{sym_idx}(x): pass  # KG: kg-ref-{sym_idx}")
            else:
                lines.append(f"class Class_{sym_idx}:  # KG: kg-class-{sym_idx}")
                lines.append("    pass")
            # Filler lines (no symbol/ref) to approximate real LOC
            for k in range(5):
                lines.append(f"    # comment line {k} for symbol {sym_idx}")
        (tmp / f"mod_{i:04d}.py").write_text("\n".join(lines) + "\n")


def _build_kg(n: int) -> MockKgClient:
    refs = []
    for i in range(n):
        if i % 3 == 0 and i % 7 != 0:
            refs.append(KgRefRecord(sourceId=f"kg-ref-{i}", sourcePath=f"mod_{i:04d}.py:1"))
        elif i % 3 != 0 and i % 7 != 0:
            refs.append(KgRefRecord(sourceId=f"kg-class-{i}", sourcePath=f"mod_{i:04d}.py:1"))
            if i % 2 == 0:
                refs.append(KgRefRecord(sourceId=f"kg-helper-{i}", sourcePath=f"mod_{i:04d}.py:3"))
    return MockKgClient(refs=refs)


def _time(fn) -> float:
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


def bench_synthetic(file_counts: list[int], runs: int = 3) -> list[dict]:
    results = []
    for n in file_counts:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _seed_n_files(tmp, n)
            kg_factory = lambda: _build_kg(n)  # noqa: E731

            # Warm-up (prime pydantic / regex caches)
            LonginusAudit(kg=kg_factory(), code_root=tmp, parallel=False).run_full()

            seq_times = [
                _time(
                    lambda: LonginusAudit(kg=kg_factory(), code_root=tmp, parallel=False).run_full()
                )
                for _ in range(runs)
            ]
            l1_times = [
                _time(
                    lambda: (
                        code_scanner.scan_root(tmp, parallel=True, threshold=1),
                        LonginusAudit(kg=kg_factory(), code_root=tmp, parallel=False).run_full(),
                    )
                )
                for _ in range(runs)
            ]
            full_times = [
                _time(
                    lambda: LonginusAudit(kg=kg_factory(), code_root=tmp, parallel=True).run_full()
                )
                for _ in range(runs)
            ]
            seq = min(seq_times)
            l1 = min(l1_times)
            full = min(full_times)
            results.append(
                {
                    "file_count": n,
                    "sequential_s": round(seq, 4),
                    "l1_only_s": round(l1, 4),
                    "full_parallel_s": round(full, 4),
                    "speedup_l1": round(seq / l1, 2) if l1 > 0 else None,
                    "speedup_full": round(seq / full, 2) if full > 0 else None,
                    "runs_per_config": runs,
                }
            )
    return results


def bench_real_repo(root: Path, runs: int = 3) -> dict:
    # Warm-up
    LonginusAudit(kg=MockKgClient(), code_root=root, parallel=False).run_full()
    seq = min(
        _time(lambda: LonginusAudit(kg=MockKgClient(), code_root=root, parallel=False).run_full())
        for _ in range(runs)
    )
    full = min(
        _time(lambda: LonginusAudit(kg=MockKgClient(), code_root=root, parallel=True).run_full())
        for _ in range(runs)
    )
    file_count = len(sorted(code_scanner.iter_files(root)))
    return {
        "root": str(root),
        "file_count": file_count,
        "sequential_s": round(seq, 4),
        "full_parallel_s": round(full, 4),
        "speedup_full": round(seq / full, 2) if full > 0 else None,
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="bench_parallel")
    parser.add_argument(
        "--counts",
        default="10,100,500,2000",
        help="Comma-separated synthetic file counts (default: 10,100,500,2000)",
    )
    parser.add_argument("--runs", type=int, default=3, help="Runs per config (best-of)")
    parser.add_argument("--root", type=str, default=None, help="Real-repo bench root path")
    args = parser.parse_args()

    out: dict = {}
    if args.root:
        out["real_repo"] = bench_real_repo(Path(args.root).resolve(), runs=args.runs)
    counts = [int(x) for x in args.counts.split(",") if x.strip()]
    out["synthetic"] = bench_synthetic(counts, runs=args.runs)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
