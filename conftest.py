"""Top-level pytest conftest — F7: APT-invariant test recording.

For every test marked `@pytest.mark.apt_invariant`, records a row to
`.pytest_apt_invariant_results.tsv` at repo root. A separate cron job
(or end-of-session script) batch-MERGEs those rows as `:TestRunResult`
nodes in Neo4j, linked to `:Lesson` / `:Contract` / `:APTInvariantRule`.

Why TSV-first instead of direct KG write: tests must run in offline /
sandboxed environments where neo4j is unreachable. TSV-first keeps the
test surface decoupled from KG availability; the batch step handles
ingestion separately.

# KG: wqi-bhgman-apt-F7-test-tagging-apt-invariants-2026-05-25
# KG: cycle-bhgman-apt-completeness-remediation-2026-05-25
# KG: APT_methodology_v27, adr-apt-phase-contract-2026-05-25
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

RESULTS_TSV = Path(__file__).parent / ".pytest_apt_invariant_results.tsv"
RESULTS_HEADER = "ts\tnodeid\trule\toutcome\tduration_s\n"


def _ensure_header() -> None:
    if not RESULTS_TSV.exists():
        RESULTS_TSV.write_text(RESULTS_HEADER, encoding="utf-8")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture call-phase outcome and write a TSV row for apt_invariant tests."""
    outcome = yield
    if call.when != "call":
        return
    marker = item.get_closest_marker("apt_invariant")
    if marker is None:
        return
    rule = marker.kwargs.get("rule") or (marker.args[0] if marker.args else "<unspecified>")
    rep = outcome.get_result()
    _ensure_header()
    row = (
        "\t".join(
            [
                time.strftime("%Y-%m-%dT%H:%M:%S%z", time.gmtime()),
                item.nodeid.replace("\t", " "),
                str(rule).replace("\t", " "),
                rep.outcome,
                f"{getattr(rep, 'duration', 0):.4f}",
            ]
        )
        + "\n"
    )
    with RESULTS_TSV.open("a", encoding="utf-8") as f:
        f.write(row)
