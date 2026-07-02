"""Deterministic judge for LakatosTree_BhgmanJaebaeman_20260702 / jbm_s4_dispatch_identity_honest.

Recomputes both pre-registered metrics from the ADR text + a counterfactual, never
from a self-report:

  improve  dispatch_identity_honesty_clauses
      G5 demotion clauses (G5-C1..C4) present in the ADR *and* carrying their
      load-bearing phrase inside the clause's own region — the shared
      ``check_adr_clauses`` oracle from test_dispatch_identity.py is imported, so
      judge and test cannot drift. Baseline 0 (the retrospective limit lived only in
      a docstring — no ADR record, no enforcement; audit wf_376c327b-8f3 gap G5).

  novel    doc_oracle_discrimination   (judge-P2 independent axis: revert-proof)
      1.0 iff the oracle passes on the REAL ADR text AND fails all clauses on a
      counterfactual text with the G5 Addendum section stripped — the oracle
      discriminates on the section itself, independent of how many clauses exist.

Prints one JSON line; exit 0 (the VALUES carry the verdict).
Run from the repo root:  .venv/bin/python scripts/judge_jaebaeman_s4.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from engine.legion.tests.test_dispatch_identity import (  # noqa: E402
    ADR_PATH,
    REQUIRED_CLAUSES,
    check_adr_clauses,
)

_SECTION_HEADING = "## G5 Addendum"


def _strip_addendum(text: str) -> str:
    """Counterfactual: the ADR as if the G5 Addendum section were reverted."""
    start = text.find(_SECTION_HEADING)
    if start < 0:
        return text
    end = text.find("\n# KG:", start)
    return text[:start] + (text[end:] if end >= 0 else "")


def main() -> int:
    text = ADR_PATH.read_text(encoding="utf-8")

    # ── improve: enforced honesty clauses in the real ADR ───────────────────
    real = check_adr_clauses(text)
    dispatch_identity_honesty_clauses = sum(1 for ok in real.values() if ok)

    # ── novel: the oracle discriminates on the stripped counterfactual ──────
    stripped = check_adr_clauses(_strip_addendum(text))
    doc_oracle_discrimination = (
        1.0
        if (
            dispatch_identity_honesty_clauses == len(REQUIRED_CLAUSES)
            and not any(stripped.values())
        )
        else 0.0
    )

    print(
        json.dumps(
            {
                "dispatch_identity_honesty_clauses": dispatch_identity_honesty_clauses,
                "doc_oracle_discrimination": doc_oracle_discrimination,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
