"""나생문 oracle 렌즈 TDD — 유레카 hard-gate 동작 spec + pipeline 와이어링.

RED(테스트 실패)=verdict.is_red, GREEN=passed. 나생문=GAN의 D, 코드=G.
# KG: naesengmoon-wired-ensemble-upgrade-2026-05-27, naesengmoon-tdd-connection-2026-05-27,
#     eureka-canonical-2026-05-26
"""

from __future__ import annotations

from collections.abc import Sequence

from oracle_lens import OracleLens, default_eureka_lenses, run_oracle_gate
from pipeline import PipelineConfig, PipelineRun, stage_4_7_oracle_gate


def _fake(code: int, out: str = ""):
    return lambda cmd: (code, out)


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


# ---- pipeline 와이어링 (stage 4.7) ----


def _cfg(**kw) -> PipelineConfig:
    return PipelineConfig(cycle_id="test-oracle", **kw)


def test_pipeline_gate_skips_when_no_lenses():
    pr = PipelineRun(config=_cfg())
    assert stage_4_7_oracle_gate(pr.config, pr) is True
    rec = pr.stages[-1]
    assert rec.stage == "4.7-naesengmoon-oracle-gate"
    assert rec.ok is True
    assert "skipped" in rec.payload


def test_pipeline_gate_blocks_on_oracle_fail():
    cfg = _cfg(
        oracle_lenses=(OracleLens("pytest", "test", ("pytest",)),),
        oracle_runner=_fake(1, "1 failed"),
    )
    pr = PipelineRun(config=cfg)
    assert stage_4_7_oracle_gate(cfg, pr) is False  # HARD GATE
    rec = pr.stages[-1]
    assert rec.ok is False
    assert rec.error and "pytest" in rec.error


def test_pipeline_gate_passes_on_oracle_green():
    cfg = _cfg(
        oracle_lenses=default_eureka_lenses("."),
        oracle_runner=_fake(0, ""),
    )
    pr = PipelineRun(config=cfg)
    assert stage_4_7_oracle_gate(cfg, pr) is True
    rec = pr.stages[-1]
    assert rec.ok is True
    assert len(rec.payload["verdicts"]) == 2
