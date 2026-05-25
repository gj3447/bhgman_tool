"""dispatch_eval — deterministic eval of subagent dispatch OUTPUT (Wave 12, 2026-05-25).

Addresses PROM 16 ``prom16-ai-dev-tools-2026-05-25`` lever ③ ("evals as the new
unit tests", D-axis consensus). Per PROM DS2/DS4: the reliable baseline is
**deterministic checks (100% coverage, ~0 cost)** — LLM-as-judge is biased and
costly, so it is NOT used here. This module encodes the project's *own existing
contracts* as deterministic eval rules, runnable in the pre-commit ratchet:

    - FullFindingRecord shape (jaebaeman / prometheus FullFindingRecord contract)
    - citation covenant (Longinus L4: ``citation_url`` OR ``references`` OR an
      explicit ``no_external_citation_reason`` — same gate the KG trigger enforces)
    - WRITE_DEFERRED_TO_PARENT (subagents must NOT self-claim KG writes —
      ``lesson-subagent-self-drift-kg-write-prom16-2026-05-24``)
    - cardinality intent==actual (jaebaeman V5, mirror of :mod:`dispatch_audit`)

Sibling of :mod:`dispatch_audit` (which audits dispatch *cardinality drift* via
the KG); this module audits dispatch *output quality* of the returned records,
offline, with zero KG/network dependency — so it runs in sandboxed CI.

# KG: finding-aidev-dispatch-eval-2026-05-25 (PROM 16 lever ③)
# KG: lesson-subagent-self-drift-kg-write-prom16-2026-05-24 (WRITE_DEFERRED rule)
# KG: CONTRACT_SharedType_FullFindingRecord
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

_VALID_CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "MEDIUM_HIGH"}

# Phrases a subagent must NOT emit (it cannot write KG; parent defers).
# lesson-subagent-self-drift-kg-write-prom16-2026-05-24.
_SELF_WRITE_CLAIMS: list[re.Pattern[str]] = [
    re.compile(r"kg_writes_done\s*[:=]\s*true", re.I),
    re.compile(r"\bMERGE\s+(완료|complete|done|성공)", re.I),
    re.compile(r"(\d+\s*(개|nodes?)\s*(생성|created|written))", re.I),
    re.compile(r"write\s+(성공|succeeded|complete)", re.I),
]


class CheckResult(BaseModel):
    name: str
    passed: bool
    detail: str = ""


class FindingEvalResult(BaseModel):
    finding_id: str
    checks: list[CheckResult]

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failures(self) -> list[str]:
        return [c.name for c in self.checks if not c.passed]


class DispatchEvalReport(BaseModel):
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    results: list[FindingEvalResult]
    failed_check_counts: dict[str, int]
    verdict: str  # PASS | WARN | FAIL

    @property
    def all_passed(self) -> bool:
        return self.verdict == "PASS"


def _has_citation(rec: dict[str, Any]) -> bool:
    """Longinus L4 covenant: citation_url OR non-empty references OR explicit waiver."""
    if rec.get("citation_url"):
        return True
    refs = rec.get("references")
    if isinstance(refs, (list, tuple)) and len(refs) > 0:
        return True
    return bool(rec.get("no_external_citation_reason"))


def _no_self_write_claim(rec: dict[str, Any]) -> tuple[bool, str]:
    """True if the record makes NO forbidden self-KG-write claim."""
    if rec.get("kg_writes_done") is True:
        return False, "kg_writes_done=true (WRITE_DEFERRED violation)"
    blob = " ".join(str(v) for v in rec.values() if isinstance(v, str))
    for pat in _SELF_WRITE_CLAIMS:
        if pat.search(blob):
            return False, f"self-write claim matched /{pat.pattern}/"
    return True, ""


def evaluate_finding(rec: dict[str, Any]) -> FindingEvalResult:
    """Deterministic eval of one FullFindingRecord-shaped dict (pure)."""
    fid = str(rec.get("findingId") or rec.get("name") or "<missing>")
    no_claim_ok, claim_detail = _no_self_write_claim(rec)
    conf = str(rec.get("confidence", "")).upper()
    checks = [
        CheckResult(
            name="has_finding_id",
            passed=bool(rec.get("findingId") or rec.get("name")),
            detail="" if (rec.get("findingId") or rec.get("name")) else "missing findingId/name",
        ),
        CheckResult(
            name="has_summary",
            passed=bool(str(rec.get("oneLineSummary", "")).strip()),
            detail="" if str(rec.get("oneLineSummary", "")).strip() else "empty oneLineSummary",
        ),
        CheckResult(
            name="has_citation",
            passed=_has_citation(rec),
            detail=""
            if _has_citation(rec)
            else "no citation_url / references / waiver (L4 covenant)",
        ),
        CheckResult(
            name="valid_confidence",
            passed=conf in _VALID_CONFIDENCE,
            detail=""
            if conf in _VALID_CONFIDENCE
            else f"confidence '{conf}' not in {sorted(_VALID_CONFIDENCE)}",
        ),
        CheckResult(name="no_self_write_claim", passed=no_claim_ok, detail=claim_detail),
        CheckResult(
            name="has_agent_id",
            passed=bool(str(rec.get("agentId", "")).strip()),
            detail="" if str(rec.get("agentId", "")).strip() else "missing agentId",
        ),
    ]
    return FindingEvalResult(finding_id=fid, checks=checks)


def evaluate_dispatch(
    records: list[dict[str, Any]],
    *,
    intent_n: int | None = None,
    warn_threshold: float = 0.90,
) -> DispatchEvalReport:
    """Evaluate a batch of returned finding records (pure, offline).

    Args:
        records: subagent-returned FullFindingRecord dicts.
        intent_n: if given, adds a cardinality check (len(records) == intent_n),
            mirroring :mod:`dispatch_audit` jaebaeman V5 invariant.
        warn_threshold: pass_rate below this → WARN; a cardinality miss or any
            ``no_self_write_claim`` failure forces FAIL (these are hard contracts).

    Verdict: PASS (all checks pass) / WARN (soft-check shortfall) /
    FAIL (hard-contract breach: cardinality miss or self-write claim).
    """
    results = [evaluate_finding(r) for r in records]
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    pass_rate = (passed / total) if total else 1.0

    failed_counts: dict[str, int] = {}
    for r in results:
        for f in r.failures:
            failed_counts[f] = failed_counts.get(f, 0) + 1

    cardinality_ok = intent_n is None or total == intent_n
    if not cardinality_ok:
        failed_counts["cardinality_match"] = abs((intent_n or 0) - total)

    hard_breach = (not cardinality_ok) or failed_counts.get("no_self_write_claim", 0) > 0
    if hard_breach:
        verdict = "FAIL"
    elif pass_rate < warn_threshold:
        verdict = "WARN"
    else:
        verdict = "PASS"

    return DispatchEvalReport(
        total=total,
        passed=passed,
        pass_rate=pass_rate,
        results=results,
        failed_check_counts=failed_counts,
        verdict=verdict,
    )
