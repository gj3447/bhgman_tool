"""symreg 게이트 gate-first 검증 — 돌리기 전에 공정·발화 확인 (주입식 fake, y=x² 통제 데이터).

(1) score_fit이 좋은 fit에 고득점, (2) read-back 도움되면 ARM2>ARM1, (3) read-back 무관이면
ARM2≈ARM1(spurious 승리 없음=공정).

# KG: prom16-evolve-loop-revival-2026-06-02
"""

from __future__ import annotations

from engine.efficacy.funsearch_symreg import _arm_best_of_n, _arm_island_evolve, score_fit

_GOOD = "def f(x):\n    return x * x"  # y=x² 데이터에 완벽
_BAD = "def f(x):\n    return 0"
_PUB = [[float(x), float(x * x)] for x in range(-4, 5)]
_HID = [[x + 0.5, (x + 0.5) ** 2] for x in range(-4, 5)]


def _fake_helps(messages, seed):
    text = " ".join(m["content"] for m in messages)
    code = _GOOD if "prior f" in text else _BAD
    return f"```python\n{code}\n```", 150


def _fake_flat(messages, seed):
    return f"```python\n{_GOOD}\n```", 150


def test_score_fit_rewards_good_over_bad():
    good = score_fit(_GOOD, _HID)
    bad = score_fit(_BAD, _HID)
    assert good > 0.9  # 완벽 fit ≈ 1.0
    assert good > bad  # 연속 oracle 차별


def test_readback_beats_no_readback_when_it_helps():
    a1, _ = _arm_best_of_n(_PUB, _HID, _fake_helps, 900, 1)  # read-back 無 → 항상 BAD
    a2, _ = _arm_island_evolve(_PUB, _HID, _fake_helps, 900, 1, n_islands=2)  # read-back → GOOD
    assert a2 > a1 + 0.5  # island-evolve가 read-back으로 GOOD 도달, best-of-N은 BAD에 갇힘


def test_fair_no_spurious_win_when_readback_ignored():
    a1, _ = _arm_best_of_n(_PUB, _HID, _fake_flat, 900, 1)
    a2, _ = _arm_island_evolve(_PUB, _HID, _fake_flat, 900, 1, n_islands=2)
    assert abs(a2 - a1) < 1e-9  # 동일 generator → 동일 결과 (하네스가 ARM2 안 편듦)
