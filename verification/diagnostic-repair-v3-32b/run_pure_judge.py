#!/usr/bin/env python3
"""Run LakatoTree's pure evidence-record judge and persist its raw response."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lakatos.programme.record_judge import judge_record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rc-output", type=Path, required=True)
    args = parser.parse_args()

    response = judge_record(args.evidence)
    encoded = (
        json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    args.output.write_text(encoded, encoding="utf-8")
    args.rc_output.write_text("0\n", encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
