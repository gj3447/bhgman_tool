"""W2-C: the nightly drift check must actually persist its :DriftCheck record into the
KG (it built the payload and threw it away before) — and honestly print-only when no
KgClient is wired.

# KG: ATOM_Skill_longinus
"""

from __future__ import annotations

import datetime as dt

import engine.longinus_drift.nightly_drift_check as ndc
from engine.longinus_drift_audit.kg_client import MockKgClient


def test_nightly_persists_blocked_drift_check_when_gds_absent():
    """Default path (GDS not installed) records a BLOCKED :DriftCheck — and now PERSISTS it."""
    kg = MockKgClient()
    assert ndc.main(kg) == 0
    assert len(kg.drift_checks) == 1
    assert kg.drift_checks[0]["status"] == "BLOCKED_GDS_NOT_INSTALLED"
    assert kg.reinduction_triggers == []  # blocked → no fire


def test_nightly_no_kg_client_does_not_crash(capsys):
    """No KgClient wired → print-only, never a silent claim of a write."""
    assert ndc.main(None) == 0
    assert "not persisted" in capsys.readouterr().out


def test_nightly_persists_reinduction_trigger_on_fire(monkeypatch):
    """When the τ gate fires, a :ReinductionTrigger is also persisted."""
    monkeypatch.setattr(
        ndc,
        "compute_community_signals",
        lambda: {"nged": 0.9, "nmi": 0.2, "silhouette": 0.1, "history": []},
    )

    class _Dec:
        phase = "steady-state"
        threshold = 0.5
        nged = 0.9
        fire = True
        reasons = ("nged 0.9 > q90 0.5",)

    monkeypatch.setattr(ndc, "evaluate_drift", lambda **_k: _Dec())
    kg = MockKgClient()
    assert ndc.main(kg) == 0
    assert len(kg.drift_checks) == 1
    assert kg.drift_checks[0]["fire"] is True
    assert len(kg.reinduction_triggers) == 1


def test_merge_drift_check_default_raises_on_base_client():
    """A KgClient that doesn't override merge_drift_check must raise, not silently no-op."""
    import pytest

    from engine.longinus_drift_audit.kg_client import KgClient

    class _Bare(KgClient):
        def list_reference_sites(self, repo_tag=None):
            return []

        def has_node(self, name):
            return False

        def merge_reference_site(self, record):
            pass

        def list_reference_site_states(self, repo_tag=None):
            return []

        def merge_reference_site_state(self, site):
            pass

        def emit_drift_event(self, event):
            pass

        def list_knowledge_hubs(self):
            return []

        def set_knowledge_hub_path(self, *, name, package_path, source_file=None, ruflo_grade=None):
            pass

    with pytest.raises(NotImplementedError):
        _Bare().merge_drift_check({"name": "x"})


# ── Goodhart cap (MAX_REINDUCTION_PER_WEEK) enforcement ──────────────────────
class _FireDec:
    phase = "steady-state"
    threshold = 0.5
    nged = 0.9
    fire = True
    reasons = ("nged 0.9 > q90 0.5",)


def _arm_fire(monkeypatch):
    monkeypatch.setattr(
        ndc,
        "compute_community_signals",
        lambda: {"nged": 0.9, "nmi": 0.2, "silhouette": 0.1, "history": []},
    )
    monkeypatch.setattr(ndc, "evaluate_drift", lambda **_k: _FireDec())


def test_nightly_enforces_goodhart_reinduction_cap(monkeypatch):
    # Two fires in the same week: MAX_REINDUCTION_PER_WEEK=1 must cap :ReinductionTrigger to 1,
    # while BOTH :DriftCheck records still persist (the cap suppresses the trigger, not the audit).
    _arm_fire(monkeypatch)
    kg = MockKgClient()
    ndc.main(kg)
    ndc.main(kg)  # second fire, same week
    assert len(kg.reinduction_triggers) == 1  # was 2 (cap never enforced) = RED
    assert len(kg.drift_checks) == 2


def test_nightly_reinduction_re_arms_after_a_week(monkeypatch):
    # The cap is a rolling 7-day window, not a one-shot latch: once the prior trigger ages out,
    # a new fire re-arms.
    _arm_fire(monkeypatch)
    kg = MockKgClient()
    ndc.main(kg)
    kg.reinduction_triggers[0]["createdAt"] = (
        dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)
    ).isoformat()
    ndc.main(kg)
    assert len(kg.reinduction_triggers) == 2  # outside the window → re-armed
