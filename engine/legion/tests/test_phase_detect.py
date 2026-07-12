"""Tests for apt-run phase navigation (deterministic). KG-free (fake run_cypher).

KG: project-apt-ultracode-roadmap-2026-06-02
"""

from engine.legion.phase_detect import (
    PhaseFacts,
    classify_phase,
    detect_all,
    detect_phase,
    fetch_facts,
    list_active_sas,
)


# ---- pure classify_phase: every branch ----
def test_unusable_facts_is_unknown():
    assert classify_phase(PhaseFacts(sa_exists=None)).phase == "UNKNOWN"


def test_no_sa_is_bootstrap():
    s = classify_phase(PhaseFacts(sa_exists=False))
    assert s.phase == "PH1_2_BOOTSTRAP" and s.next_skill == "/apt-sa"


def test_source_present_is_scw_feedback():
    s = classify_phase(PhaseFacts(sa_exists=True, atomic_count=3, contract_count=2, source_count=1))
    assert s.phase == "PH5_6_SCW_FEEDBACK" and s.next_skill == "/apt-scw"


def test_contract_no_source_is_scw():
    s = classify_phase(PhaseFacts(sa_exists=True, atomic_count=3, contract_count=2, source_count=0))
    assert s.phase == "PH5_SCW"


def test_atomic_no_contract_is_st():
    s = classify_phase(PhaseFacts(sa_exists=True, atomic_count=3, contract_count=0, source_count=0))
    assert s.phase == "PH4_ST" and s.next_skill == "/apt-st"


def test_sa_only_is_sp():
    s = classify_phase(PhaseFacts(sa_exists=True, atomic_count=0, contract_count=0, source_count=0))
    assert s.phase == "PH3_SP" and s.next_skill == "/apt-sp"


# ---- fetch_facts via fake run_cypher ----
def _runner(counts):
    """fake run_cypher dispatching by query content -> [{'c': N}]."""

    def run_cypher(cypher, params):  # noqa: ARG001
        if "SourceCodeNode" in cypher:
            return [{"c": counts["source"]}]
        if "HAS_CONTRACT" in cypher and "MATERIALIZES" not in cypher:
            return [{"c": counts["contract"]}]
        if "AtomicSpan" in cypher and "HAS_CONTRACT" not in cypher:
            return [{"c": counts["atomic"]}]
        return [{"c": counts["sa"]}]

    return run_cypher


def test_fetch_facts_reads_counts():
    facts = fetch_facts("Proj", _runner({"sa": 1, "atomic": 4, "contract": 2, "source": 0}))
    assert facts.sa_exists is True
    assert (facts.atomic_count, facts.contract_count, facts.source_count) == (4, 2, 0)


def test_detect_phase_end_to_end():
    s = detect_phase("Proj", _runner({"sa": 1, "atomic": 4, "contract": 0, "source": 0}))
    assert s.phase == "PH4_ST"


def test_fetch_facts_graceful_when_backend_raises():
    def raising(cypher, params):  # noqa: ARG001
        raise RuntimeError("UnsupportedLocalQuery")

    facts = fetch_facts("Proj", raising)
    assert facts.usable is False
    assert classify_phase(facts).phase == "UNKNOWN"


def test_fetch_facts_empty_rows_is_zero():
    facts = fetch_facts("Proj", lambda c, p: [])
    assert facts.sa_exists is False  # 0 SA


# ---- all-SA batch navigation ----
def _multi_runner(sas):
    """fake run_cypher: list-all-SA query returns names; per-SA counts vary by name."""

    def run_cypher(cypher, params):  # noqa: ARG001
        if "ORDER BY sa.name" in cypher:  # list_active_sas
            return [{"name": n} for n in sas]
        target = params.get("target")
        counts = sas[target]
        if "SourceCodeNode" in cypher:
            return [{"c": counts["source"]}]
        if "HAS_CONTRACT" in cypher and "MATERIALIZES" not in cypher:
            return [{"c": counts["contract"]}]
        if "AtomicSpan" in cypher and "HAS_CONTRACT" not in cypher:
            return [{"c": counts["atomic"]}]
        return [{"c": counts["sa"]}]

    return run_cypher


def test_list_active_sas():
    r = _multi_runner({"A": {}, "B": {}})
    assert list_active_sas(r) == ["A", "B"]


def test_list_active_sas_graceful():
    def raising(c, p):  # noqa: ARG001
        raise RuntimeError("unsupported")

    assert list_active_sas(raising) is None


def test_detect_all_navigates_every_sa():
    sas = {
        "Proj_SP": {"sa": 1, "atomic": 0, "contract": 0, "source": 0},
        "Proj_SCW": {"sa": 1, "atomic": 5, "contract": 3, "source": 0},
    }
    out = dict((n, s.phase) for n, s in detect_all(_multi_runner(sas)))
    assert out == {"Proj_SP": "PH3_SP", "Proj_SCW": "PH5_SCW"}


def test_detect_all_empty_when_backend_unusable():
    def raising(c, p):  # noqa: ARG001
        raise RuntimeError("unsupported")

    assert detect_all(raising) == []


# ---- delta-gap blockers ----
from engine.legion.phase_detect import Blocker, fetch_blockers  # noqa: E402


def _blocker_runner(counts, *, sp=None, st=None, scw=None):
    """fake run_cypher: facts by count + phase-specific blocker rows by unique query marker."""

    def run_cypher(cypher, params):  # noqa: ARG001
        if "IS NULL AS objective" in cypher:  # PH3_SP blocker query
            return sp or []
        if "NOT (leaf)-[:HAS_CONTRACT]" in cypher:  # PH4_ST blocker query
            return st or []
        if "NOT (c)-[:MATERIALIZES]" in cypher:  # PH5_SCW blocker query
            return scw or []
        if "SourceCodeNode" in cypher:
            return [{"c": counts["source"]}]
        if "HAS_CONTRACT" in cypher and "MATERIALIZES" not in cypher:
            return [{"c": counts["contract"]}]
        if "AtomicSpan" in cypher and "HAS_CONTRACT" not in cypher:
            return [{"c": counts["atomic"]}]
        return [{"c": counts["sa"]}]

    return run_cypher


def test_phasestatus_blockers_default_empty():
    assert classify_phase(PhaseFacts(sa_exists=True)).blockers == ()


def test_fetch_blockers_sp_reports_missing_predicates():
    rows = [
        {
            "node": "span_x",
            "objective": False,
            "definition": False,
            "keyAssertion": True,
            "verification": True,
            "c_s_predicate": False,
        }
    ]
    bl = fetch_blockers("Proj", "PH3_SP", _blocker_runner({}, sp=rows))
    assert bl == (Blocker("span_x", "missing C(S): keyAssertion, verification"),)


def test_fetch_blockers_sp_all_null_degrades_to_coarse():
    # KG that doesn't populate C(S) fields → every flag True → coarse msg, not "missing all 5".
    rows = [{"node": "span_z", **{f: True for f in ("objective", "definition", "keyAssertion", "verification", "c_s_predicate")}}]
    bl = fetch_blockers("Proj", "PH3_SP", _blocker_runner({}, sp=rows))
    assert bl == (Blocker("span_z", "needs crystallization (not yet AtomicSpan)"),)


def test_fetch_blockers_st_simple():
    bl = fetch_blockers("Proj", "PH4_ST", _blocker_runner({}, st=[{"node": "leaf_a"}]))
    assert bl == (Blocker("leaf_a", "no Contract (HAS_CONTRACT edge missing)"),)


def test_fetch_blockers_scw_simple():
    bl = fetch_blockers("Proj", "PH5_SCW", _blocker_runner({}, scw=[{"node": "Contract_c"}]))
    assert bl == (Blocker("Contract_c", "no code (MATERIALIZES→SourceCodeNode missing)"),)


def test_fetch_blockers_terminal_phase_none():
    assert fetch_blockers("Proj", "PH5_6_SCW_FEEDBACK", _blocker_runner({})) == ()


def test_fetch_blockers_graceful_on_raise():
    def raising(c, p):  # noqa: ARG001
        raise RuntimeError("UnsupportedLocalQuery")

    assert fetch_blockers("Proj", "PH4_ST", raising) == ()


def test_detect_phase_with_blockers_attaches_delta():
    counts = {"sa": 1, "atomic": 2, "contract": 0, "source": 0}  # → PH4_ST
    r = _blocker_runner(counts, st=[{"node": "leaf_a"}, {"node": "leaf_b"}])
    s = detect_phase("Proj", r, with_blockers=True)
    assert s.phase == "PH4_ST"
    assert [b.node for b in s.blockers] == ["leaf_a", "leaf_b"]


def test_detect_phase_without_blockers_stays_empty():
    counts = {"sa": 1, "atomic": 2, "contract": 0, "source": 0}
    r = _blocker_runner(counts, st=[{"node": "leaf_a"}])
    assert detect_phase("Proj", r).blockers == ()  # default off = back-compat
