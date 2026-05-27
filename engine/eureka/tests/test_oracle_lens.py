"""나생문 oracle 렌즈 TDD — 유레카 hard-gate 동작 spec + pipeline 와이어링.

RED(테스트 실패)=verdict.is_red, GREEN=passed. 나생문=GAN의 D, 코드=G.
# KG: naesengmoon-wired-ensemble-upgrade-2026-05-27, naesengmoon-tdd-connection-2026-05-27,
#     eureka-canonical-2026-05-26
"""

from __future__ import annotations

from collections.abc import Sequence

from types import SimpleNamespace

from oracle_lens import (
    OracleLens,
    default_eureka_lenses,
    kg_oracle_gate,
    run_oracle_gate,
)
from pipeline import PipelineConfig, PipelineRun, stage_4_7_oracle_gate


def _fake(code: int, out: str = ""):
    return lambda cmd: (code, out)


def _ac(name="ac0", extent=("a", "b", "c"), intent=("p",), stability=0.8):
    """fake AbstractClass 후보 (kg_oracle_gate는 getattr 기반)."""
    return SimpleNamespace(
        name=name, extent=list(extent), intent=list(intent), stabilityScore=stability
    )


# ---- primitive (occam mirror) ----


def test_lens_pass_verdict_green():
    lens = OracleLens("pytest", "test", ("pytest",))
    v = lens.verify(runner=_fake(0, "ok"))
    assert v.passed is True
    assert v.is_red is False
    assert v.kind == "test"


def test_lens_fail_verdict_red():
    lens = OracleLens("ruff", "typecheck", ("ruff", "check", "."))
    v = lens.verify(runner=_fake(1, "E501 line too long"))
    assert v.passed is False
    assert v.is_red is True  # TDD RED
    assert "E501" in v.detail
    assert v.hard_gate is True


def test_gate_short_circuits_on_first_fail():
    calls: list[Sequence[str]] = []

    def counting_runner(cmd):
        calls.append(cmd)
        return (1, "lint error") if cmd[0] == "ruff" else (0, "")

    lenses = [
        OracleLens("ruff", "typecheck", ("ruff", "check")),
        OracleLens("pytest", "test", ("pytest",)),
    ]
    passed, verdicts = run_oracle_gate(lenses, runner=counting_runner)
    assert passed is False
    assert len(verdicts) == 1  # hard gate: 둘째(pytest) 안 돎
    assert len(calls) == 1
    assert verdicts[0].is_red


def test_gate_all_pass():
    passed, verdicts = run_oracle_gate(default_eureka_lenses("."), runner=_fake(0, ""))
    assert passed is True
    assert len(verdicts) == 2
    assert all(v.passed for v in verdicts)


def test_default_eureka_lenses_shape():
    lenses = default_eureka_lenses("engine/eureka")
    kinds = {ln.kind for ln in lenses}
    assert kinds == {"typecheck", "test"}
    assert any(ln.command[0] == "ruff" for ln in lenses)
    assert any(ln.command[0] == "pytest" for ln in lenses)


# ---- KG oracle (concept 불변식) ----


def test_kg_oracle_pass_wellformed():
    passed, verdicts = kg_oracle_gate([_ac()], min_extent=2, min_stability=0.5)
    assert passed is True
    assert verdicts[-1].passed is True


def test_kg_oracle_fail_extent_too_small():
    passed, verdicts = kg_oracle_gate([_ac(extent=("a",))], min_extent=2)
    assert passed is False
    assert verdicts[-1].kind == "recount"
    assert "extent" in verdicts[-1].detail


def test_kg_oracle_fail_empty_intent():
    passed, verdicts = kg_oracle_gate([_ac(intent=())], min_extent=2)
    assert passed is False
    assert verdicts[-1].kind == "schema"


def test_kg_oracle_fail_self_loop():
    passed, verdicts = kg_oracle_gate([_ac(name="x", extent=("x", "y", "z"))])
    assert passed is False
    assert verdicts[-1].kind == "acyclic"


def test_kg_oracle_fail_low_stability():
    passed, verdicts = kg_oracle_gate([_ac(stability=0.1)], min_stability=0.5)
    assert passed is False
    assert "stability" in verdicts[-1].detail


# ---- pipeline 와이어링 (stage 4.7: KG oracle + optional shell) ----


def _cfg(**kw) -> PipelineConfig:
    return PipelineConfig(cycle_id="test-oracle", **kw)


def test_pipeline_gate_kg_only_passes_on_good_candidate():
    pr = PipelineRun(config=_cfg())
    assert stage_4_7_oracle_gate([_ac()], pr.config, pr) is True
    rec = pr.stages[-1]
    assert rec.stage == "4.7-naesengmoon-oracle-gate(KG)"
    assert rec.ok is True


def test_pipeline_gate_kg_blocks_malformed_concept():
    pr = PipelineRun(config=_cfg())
    assert stage_4_7_oracle_gate([_ac(intent=())], pr.config, pr) is False  # HARD GATE
    assert pr.stages[-1].ok is False


def test_pipeline_gate_shell_blocks_after_kg_pass():
    cfg = _cfg(
        oracle_lenses=(OracleLens("pytest", "test", ("pytest",)),),
        oracle_runner=_fake(1, "1 failed"),
    )
    pr = PipelineRun(config=cfg)
    assert stage_4_7_oracle_gate([_ac()], cfg, pr) is False  # KG pass, shell FAIL
    rec = pr.stages[-1]
    assert rec.stage == "4.7b-naesengmoon-oracle-gate(shell)"
    assert rec.ok is False
    assert rec.error and "pytest" in rec.error


def test_pipeline_gate_both_green():
    cfg = _cfg(oracle_lenses=default_eureka_lenses("."), oracle_runner=_fake(0, ""))
    pr = PipelineRun(config=cfg)
    assert stage_4_7_oracle_gate([_ac()], cfg, pr) is True
    assert pr.stages[-1].payload["verdicts"][0]["passed"] is True
