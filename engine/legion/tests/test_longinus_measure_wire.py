"""longinus measurement 배선 — 정직-None 팩토리 (광역 측정 재배선 2026-07-10, slice 4 이중가드).

설계(2026-07-09): drift/orphan 실카운트는 full-audit(kg+code_root infra)에서만 존재한다 —
어떤 기본 진입점도 그 infra 를 주입하지 않으므로(infra 기아, 3층 deadness ③) in-loop
롱기누스는 float 모드다. 이 슬라이스는 '실값 급여'(별도 infra 캠페인)가 아니라 *정직*을
배선한다:
  1. audit_context 가 실측 카운트(sha256_drift_count/reference_orphan_count)를 bindings 에
     공시한다 — full-audit 이 돌았을 때만 존재하는 키.
  2. longinus 스테이지가 measure=_measure_longinus 팩토리를 지닌다.
  3. float 모드는 kg_node_unbound_count(부동 노드 수, threshold 없음=발화 불가 정직
     텔레메트리)만 실측하고, drift/orphan 은 미측정(None) — full-audit 없이 '측정된 0
     drift'를 위장하지 않는다.

guard_defect(음성): float/degraded 모드에서 sha256_drift_count·reference_orphan_count 가
어떤 상수로도 나타나지 않는다(발화 원리적 불가). guard_mechanism(양성): full-audit 실행
시 실카운트가 등장하고 >5 drift → occam / >10 orphan → prometheus 발화 규칙이 산다.

# KG: bhgman-measurement-rewire-design-20260709 (slice 4: longinus 정직-None)
# KG: ATOM_Skill_longinus
"""

from __future__ import annotations

from engine.legion.commanders import _measure_longinus, _run_bind, default_stages
from engine.longinus_drift_audit.kg_client import MockKgClient
from engine.longinus_drift_audit.models import KgRefRecord


def _full_audit_bindings(tmp_path) -> dict:
    """실 LonginusAudit full-audit 을 tmp code root + MockKgClient 로 구동 —
    reverse orphan 1개(c.py, KG ref 없는 심볼)가 실측으로 잡히는 최소 하네스."""
    (tmp_path / "a.py").write_text("def foo(x):  # KG: lesson-foo-2026-05-12\n    pass\n")
    (tmp_path / "c.py").write_text("def baz(): pass\n")  # no KG ref → reverse orphan
    kg = MockKgClient(refs=[KgRefRecord(sourceId="lesson-foo-2026-05-12", sourcePath="a.py:1")])
    out = _run_bind({"run_cypher": lambda c, p: [], "kg": kg, "code_root": tmp_path})
    return out["bindings"]


# ── 배선 1: 스테이지가 measure 팩토리를 지닌다 ────────────────────────────────
def test_longinus_stage_carries_measure_factory():
    stage = next(s for s in default_stages() if s.name == "longinus")
    assert stage.measure is not None, "longinus 스테이지에 measure= 팩토리가 배선돼야"


# ── 배선 2 (mechanism): full-audit 이 실카운트를 공시하고 팩토리가 측정한다 ────
def test_full_audit_exposes_real_counts(tmp_path):
    bindings = _full_audit_bindings(tmp_path)
    assert bindings["mode"] == "full-audit"
    assert "sha256_drift_count" in bindings, "full-audit 실측 카운트가 공시돼야"
    assert "reference_orphan_count" in bindings
    assert bindings["reference_orphan_count"] >= 1  # c.py reverse orphan 실측


def test_factory_measures_full_audit_counts(tmp_path):
    bindings = _full_audit_bindings(tmp_path)
    m = _measure_longinus({"bindings": bindings})
    assert m is not None
    metrics = m.measure()
    assert metrics["reference_orphan_count"] >= 1.0
    assert "sha256_drift_count" in metrics


def test_full_audit_firing_rules_alive():
    """>5 drift → occam, >10 orphan → prometheus 발화 규칙이 팩토리 경로에서 산다
    (값은 합성 — 발화 규칙 생존 증명; 실측 발화는 infra 캠페인 몫)."""
    m = _measure_longinus(
        {
            "bindings": {
                "mode": "full-audit",
                "sha256_drift_count": 6,
                "reference_orphan_count": 11,
            }
        }
    )
    targets = {d.target_commander for d in m.decide_dispatch(cycle_id="lmw-fire")}
    assert {"occam", "prometheus"} <= targets


# ── guard_defect (음성): float/degraded 모드는 drift/orphan 미측정 ─────────────
def test_float_mode_measures_only_unbound_count():
    """in-loop float 모드: kg_node_unbound_count 만 실측(threshold 없음=발화 불가),
    sha256_drift_count/reference_orphan_count 는 미측정 — full-audit 없이 '측정된
    0 drift'를 위장하면 안 된다."""
    out = _run_bind({"run_cypher": lambda c, p: [{"n": 7}]})
    assert out["bindings"]["mode"] == "kg-deterministic"
    m = _measure_longinus({"bindings": out["bindings"]})
    assert m is not None
    assert m.measure() == {"kg_node_unbound_count": 7.0}
    assert m.decide_dispatch(cycle_id="lmw-float") == []  # 발화 원리적 불가 (정직 텔레메트리)


def test_degraded_bindings_is_unmeasured():
    def _boom(c, p):
        raise RuntimeError("kg unreachable")

    out = _run_bind({"run_cypher": _boom})
    assert out["bindings"]["mode"] == "degraded"
    assert _measure_longinus({"bindings": out["bindings"]}) is None
    assert _measure_longinus({}) is None  # bindings 부재
    # 구식 full-audit 출력(카운트 미공시)도 측정 근거 없음 — 상수 날조 금지.
    assert _measure_longinus({"bindings": {"mode": "full-audit", "is_clean": True}}) is None
