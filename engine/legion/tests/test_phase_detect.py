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
