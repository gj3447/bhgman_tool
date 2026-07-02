"""Deterministic judge for LakatosTree_BhgmanJaebaeman_20260702 / jbm_s7_theory_canon.

Recomputes both pre-registered metrics with the SAME oracle the test enforces
(imported from engine/tests/test_theory_canon.py — judge↔test drift 불가):

  improve  broken_symlink_count
      theory/ 아래 파손 심링크 수. Baseline 12 (audit wf_376c327b-8f3 G7 + 레포-와이드
      전수: 재배맨 2 · APT 3 · CHU 2 · PROMETHEUS 2 · TPA 1 · LONGINUS 1 · 00_공통 1),
      direction lower — prune+정직 스텁 후 0.

  novel    ghost_ref_discrimination   (judge-P2 independent axis: oracle 판별력)
      1.0 iff (a) 실 INDEX 들은 유령 링크 0 으로 통과하고, (b) 유령 링크를 주입한
      counterfactual INDEX 텍스트를 같은 oracle 이 RED 로 잡는다 — oracle 이 항상
      green 인 장식이 아님을 판별. 심링크 수 축과 독립.

Prints one JSON line; exit 0 (the VALUES carry the verdict).
Run from the repo root:  .venv/bin/python scripts/judge_theory_canon.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from engine.tests.test_theory_canon import (  # noqa: E402
    THEORY,
    broken_symlinks,
    missing_index_refs,
)


def main() -> int:
    # ── improve: 파손 심링크 실측 ────────────────────────────────────────────
    broken_symlink_count = len(broken_symlinks(THEORY))

    # ── novel: oracle 판별력 (실 INDEX 통과 ∧ 유령 주입 counterfactual RED) ──
    real_ghosts = [g for ix in THEORY.glob("*/INDEX.md") for g in missing_index_refs(ix)]
    with tempfile.TemporaryDirectory() as td:
        doctored = Path(td) / "INDEX.md"
        doctored.write_text("# counterfactual\n[유령](GHOST_DOES_NOT_EXIST.md)\n", encoding="utf-8")
        counterfactual_caught = missing_index_refs(doctored) == ["GHOST_DOES_NOT_EXIST.md"]
    ghost_ref_discrimination = 1.0 if (not real_ghosts and counterfactual_caught) else 0.0

    print(
        json.dumps(
            {
                "broken_symlink_count": broken_symlink_count,
                "ghost_ref_discrimination": ghost_ref_discrimination,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
