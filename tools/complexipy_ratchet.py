#!/usr/bin/env python3
"""complexipy ratchet — 기존 부채는 동결, *악화·신규*만 차단.

왜 필요한가 (2026-07-15 실측):
    훅이 `complexipy engine/ -mx 15`(flat threshold, always_run)였는데 코드베이스엔
    위반이 58건 있었다. 즉 게이트는 **한 번도 통과할 수 없었고**, 결과적으로 모두를
    `--no-verify`로 몰아 잘 동작하던 나머지 게이트(ruff/mypy/기본검사)까지 함께 껐다.
    죽은 게이트는 아무것도 막지 않으면서 우회를 훈련시킨다.

    SYMPOSIUM 정전(apt-cleanup SKILL)은 원래 "complexipy --ratchet"을 요구하지만
    complexipy엔 그런 플래그가 없다(정전↔도구 drift). 이 스크립트가 그 자리를 채운다.

동작:
    baseline(tools/complexipy_baseline.json) 대비
      - 신규 위반(임계 초과인데 baseline에 없음) → FAIL
      - 악화(baseline보다 복잡도 증가)          → FAIL
      - 동일·개선                               → PASS (개선은 --update로 baseline 조임)
    baseline에 있는 항목이 사라지면 조용히 무시(파일 삭제/리네임 허용).

사용:
    python tools/complexipy_ratchet.py            # 게이트 (pre-commit)
    python tools/complexipy_ratchet.py --update   # 개선분을 baseline에 반영(조이기)

# KG: lesson-precommit-autofix-plus-concurrent-sessions-commit-failure-loop-2026-07-15
# KG: cycle-longinus-elegant-binding-prom16-2026-07-15
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "tools" / "complexipy_baseline.json"
TARGET = "engine/"
MAX_COMPLEXITY = 15


def measure() -> dict[str, int]:
    """{'path::function': complexity} — 임계 초과분만."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        out = Path(tmp.name)
    try:
        subprocess.run(
            [
                "uvx",
                "complexipy",
                TARGET,
                "-mx",
                str(MAX_COMPLEXITY),
                "--output-format",
                "json",
                "--output",
                str(out),
                "-q",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        rows = json.loads(out.read_text())
    finally:
        out.unlink(missing_ok=True)
    return {
        f"{r['path']}::{r['function_name']}": r["complexity"]
        for r in rows
        if r["complexity"] > MAX_COMPLEXITY
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="개선분을 baseline에 반영")
    args = ap.parse_args()

    current = measure()
    if not BASELINE.exists():
        BASELINE.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"complexipy-ratchet: baseline 신규 생성 — {len(current)}건 동결")
        return 0

    base = json.loads(BASELINE.read_text())
    new = {k: v for k, v in current.items() if k not in base}
    worse = {k: (base[k], v) for k, v in current.items() if k in base and v > base[k]}
    better = {k: (base[k], v) for k, v in current.items() if k in base and v < base[k]}
    gone = [k for k in base if k not in current]

    if args.update:
        BASELINE.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(
            f"complexipy-ratchet: baseline 갱신 — {len(current)}건 (개선 {len(better)} / 소멸 {len(gone)})"
        )
        return 0

    if new or worse:
        print("complexipy-ratchet: FAILED — 복잡도 부채가 늘었다 (기존 부채는 허용, 악화만 차단)")
        for k, v in sorted(new.items()):
            print(f"  [신규] {k}  복잡도 {v} > 임계 {MAX_COMPLEXITY}")
        for k, (b, v) in sorted(worse.items()):
            print(f"  [악화] {k}  {b} → {v}")
        print("\n  해당 함수를 분해하거나, 의도된 것이면 baseline을 갱신하라:")
        print("    python tools/complexipy_ratchet.py --update")
        return 1

    msg = f"complexipy-ratchet: PASSED — 동결 {len(base)}건, 신규·악화 0"
    if better:
        msg += f" (개선 {len(better)}건 — --update로 조일 것)"
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
