"""오캄 σ 보정 — Platt scaling + ECE + 비용기반 reject 임계값 (PROM 6 C6 / rf-occam-adv-A5).

decision_log 의 (σ, verdict_label) 페어로 raw σ → P(supersession-correct) 보정한다.
verdict_label = 크리틱(나생문/롱기누스) PASS/FAIL(=calibration label). 라벨 부족/degenerate
면 machinery 는 준비된 채 fitted=False 로 보고(데이터 쌓이면 활성). archive-only=가역이라
false-archive 비용 d 가 bounded → 단일 컷이 아닌 escalation *밴드*(Chow reject)가 정당.

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A5-2026-07-19,
#     occam-kam-canonical-2026-05-26
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

_PASS = {True, 1, "PASS", "APPROVED", "APPROVED_AFTER_FIX", "CONFIRM", "CONFIRMED"}
_FAIL = {False, 0, "FAIL", "REJECT", "REJECTED"}


def label_to_bool(v) -> int | None:
    """크리틱 verdict → 1(correct)/0(wrong)/None(불명, CONDITIONAL 등 skip)."""
    if v in _PASS:
        return 1
    if v in _FAIL:
        return 0
    return None


def load_decision_log(path: str | Path) -> list[tuple[float, int]]:
    """decision_log jsonl → [(sigma, label)] — verdict_label 채워진 것만."""
    p = Path(path).expanduser()
    if not p.exists():
        return []
    out: list[tuple[float, int]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        lab = label_to_bool(r.get("verdict_label"))
        sig = r.get("sigma")
        if lab is None or sig is None:
            continue
        out.append((float(sig), lab))
    return out


def fit_platt(pairs: list[tuple[float, int]]) -> tuple[float, float] | None:
    """Platt scaling(1-var 로지스틱) → (a,b) for sigmoid(a*σ+b). 소데이터 과적합 저위험.

    라벨 < 10 또는 단일 클래스면 None(fit 불가)."""
    if len(pairs) < 10:
        return None
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    y = [lab for _, lab in pairs]
    if len(set(y)) < 2:
        return None
    x = np.array([[s] for s, _ in pairs])
    lr = LogisticRegression().fit(x, np.array(y))
    return float(lr.coef_[0][0]), float(lr.intercept_[0])


def calibrated_prob(sigma: float, a: float, b: float) -> float:
    """보정된 P(correct) = sigmoid(a*σ + b)."""
    return 1.0 / (1.0 + math.exp(-(a * sigma + b)))


def expected_calibration_error(pairs: list[tuple[float, int]], bins: int = 10) -> float:
    """ECE: bin 별 |mean σ − 실제 correct 비율| 을 bin 크기로 가중 평균. σ=0.81 이 정말
    81% 맞는지의 척도(0=완벽 보정)."""
    if not pairs:
        return 0.0
    ece = 0.0
    n = len(pairs)
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        sel = [
            (s, lab)
            for s, lab in pairs
            if (s >= lo and (s < hi or (i == bins - 1 and s <= hi)))
        ]
        if not sel:
            continue
        mean_sig = sum(s for s, _ in sel) / len(sel)
        emp = sum(lab for _, lab in sel) / len(sel)
        ece += (len(sel) / n) * abs(mean_sig - emp)
    return ece


def reject_thresholds(cost_false_archive: float, cost_escalate: float) -> tuple[float, float]:
    """Chow reject 밴드: auto-archive if P≥τ_high=1−c_e/d; escalate in (τ_low,τ_high); else keep.

    c_e(escalation 비용) ≪ d(false-archive 비용)면 밴드가 넓어짐(더 escalate). archive-only=가역
    이라 d 가 bounded → τ_high < 1.0. τ_low=0.5(그 아래는 supersede 근거 부족)."""
    d = max(cost_false_archive, 1e-9)
    tau_high = min(0.999, max(0.5, 1.0 - cost_escalate / d))
    return 0.5, tau_high


@dataclass(frozen=True)
class CalibrationResult:
    n: int
    ece: float
    fitted: bool
    note: str
    a: float | None = None
    b: float | None = None


def calibrate(pairs: list[tuple[float, int]], *, bins: int = 10) -> CalibrationResult:
    """(σ,label) 페어 → Platt fit + ECE. 라벨 부족이면 fitted=False(machinery ready)."""
    ece = expected_calibration_error(pairs, bins)
    ab = fit_platt(pairs)
    if ab is None:
        return CalibrationResult(
            n=len(pairs),
            ece=ece,
            fitted=False,
            note=f"insufficient/degenerate labels ({len(pairs)}) — machinery ready; "
            "accumulate decision_log verdict_labels then re-run",
        )
    return CalibrationResult(
        n=len(pairs), ece=ece, fitted=True, a=ab[0], b=ab[1],
        note=f"Platt fit on {len(pairs)} labels; ECE={ece:.3f}",
    )


__all__ = [
    "CalibrationResult", "calibrate", "calibrated_prob", "expected_calibration_error",
    "fit_platt", "label_to_bool", "load_decision_log", "reject_thresholds",
]
