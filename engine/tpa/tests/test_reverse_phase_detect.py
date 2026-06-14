"""Phase C — reverse phase navigation (the dual of legion phase_detect), fake-runner tested."""

from __future__ import annotations

from engine.tpa.reverse_phase_detect import (
    ReversePhaseFacts,
    classify_reverse_phase,
    detect_reverse_phase,
)


def test_highest_recovery_branch_wins():
    # no code -> TCW
    assert classify_reverse_phase(ReversePhaseFacts(code_count=0)).phase == "TCW"
    # code, nothing recovered -> ST
    assert classify_reverse_phase(ReversePhaseFacts(code_count=5)).phase == "ST"
    # contract recovered, no pattern -> SP
    assert classify_reverse_phase(ReversePhaseFacts(5, contract_count=3)).phase == "SP"
    # pattern recovered, no anchor -> TA
    assert classify_reverse_phase(ReversePhaseFacts(5, 3, pattern_count=2)).phase == "TA"
    # anchor recovered -> COMPLETE (even with everything below also present)
    assert classify_reverse_phase(ReversePhaseFacts(5, 3, 2, anchor_count=1)).phase == "COMPLETE"


def test_unusable_backend_is_unknown_not_false_start():
    st = classify_reverse_phase(ReversePhaseFacts(code_count=None))
    assert st.phase == "UNKNOWN"
    assert st.next_skill == "(none)"


def test_next_skill_mapping():
    assert classify_reverse_phase(ReversePhaseFacts(0)).next_skill == "/tpa-tcw"
    assert classify_reverse_phase(ReversePhaseFacts(5)).next_skill == "/tpa-st"
    assert classify_reverse_phase(ReversePhaseFacts(5, 3)).next_skill == "/tpa-sp"
    assert classify_reverse_phase(ReversePhaseFacts(5, 3, 2)).next_skill == "/tpa-ta"


class _FakeRunner:
    def __init__(self, code=0, contract=0, pattern=0, anchor=0, blind=False):
        self.vals = {
            "EXTRACTED": code,
            "Contract": contract,
            "Pattern": pattern,
            "SemanticAnchor": anchor,
        }
        self.blind = blind

    def __call__(self, cypher: str, params: dict) -> list[dict]:
        if self.blind:
            raise RuntimeError("backend cannot answer")
        for token, v in self.vals.items():
            if token in cypher:
                return [{"c": v}]
        return [{"c": 0}]


def test_detect_reverse_phase_against_fake_kg():
    assert detect_reverse_phase("cyc-x", _FakeRunner(code=10, contract=4)).phase == "SP"
    assert detect_reverse_phase("cyc-x", _FakeRunner(blind=True)).phase == "UNKNOWN"
