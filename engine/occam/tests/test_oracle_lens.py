"""나생문 oracle 렌즈 TDD — 컴파일러나생문 hard-gate 동작 spec.

RED(테스트 실패)=verdict.is_red, GREEN=passed. 나생문=GAN의 D.
# KG: naesengmoon-wired-ensemble-upgrade-2026-05-27, naesengmoon-tdd-connection-2026-05-27
"""

from __future__ import annotations

from collections.abc import Sequence

from oracle_lens import OracleLens, run_oracle_gate


def _fake(code: int, out: str = ""):
    return lambda cmd: (code, out)


def test_pass_verdict_green():
    lens = OracleLens("python", "test", ("pytest",))
    v = lens.verify(runner=_fake(0, "ok"))
    assert v.passed is True
    assert v.is_red is False
    assert v.kind == "test"


def test_fail_verdict_red():
    lens = OracleLens("c-compiler", "compiler", ("gcc", "-fsyntax-only", "x.c"))
    v = lens.verify(runner=_fake(1, "x.c:3: error: expected ';'"))
    assert v.passed is False
    assert v.is_red is True  # TDD RED
    assert "error" in v.detail
    assert v.hard_gate is True


def test_gate_short_circuits_on_first_fail():
    calls: list[Sequence[str]] = []

    def counting_runner(cmd):
        calls.append(cmd)
        # 첫 렌즈(compile) FAIL, 둘째(test)는 호출되면 안 됨
        return (1, "compile error") if cmd[0] == "gcc" else (0, "")

    lenses = [
        OracleLens("c-compiler", "compiler", ("gcc", "x.c")),
        OracleLens("python", "test", ("pytest",)),
    ]
    passed, verdicts = run_oracle_gate(lenses, runner=counting_runner)
    assert passed is False
    assert len(verdicts) == 1  # hard gate: 둘째 안 돎
    assert len(calls) == 1
    assert verdicts[0].is_red


def test_gate_all_pass():
    lenses = [
        OracleLens("ruff", "typecheck", ("ruff", "check")),
        OracleLens("pytest", "test", ("pytest",)),
    ]
    passed, verdicts = run_oracle_gate(lenses, runner=_fake(0, ""))
    assert passed is True
    assert len(verdicts) == 2
    assert all(v.passed for v in verdicts)
