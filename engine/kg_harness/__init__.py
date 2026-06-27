"""engine.kg_harness — KG write-guard (출혈 차단 하네스).

⚠️ RECONSTRUCTED MINIMAL STOPGAP (2026-06-27). 원본 소스(__init__/write_guard/rules/audit/
registry/rewire .py)가 WIP 에서 **손실**됨 — ``engine/kg_harness/__pycache__`` 에 cpython-3.14
.pyc 만 남아있고 현재 런타임은 3.13 이라 sourceless 복구 불가(magic mismatch). git 이력도 없음.

이 stopgap 은 ``engine/cli/runtime.py`` 의 ``from engine.kg_harness import guarded_run,
validate_write`` import 를 복구해 cli 테스트(ImportError 로 깨지던 7개)를 통과시킨다. **그러나
실제 invariant 강제는 하지 않는다** — 원 규칙(occam-pass-metahumotonic-20260626: Superseded
10%·god-object 재오염 방지)은 KG 상태를 봐야 하므로 cypher 문자열만으로 재구성 불가하고, 추측
재구성은 silent-green(self-consistency≠correctness) 위반이라 의도적으로 하지 않는다.

degraded 상태는 첫 ``guarded_run``/``validate_write`` 호출 시 1회 stderr 로 *시끄럽게* 알린다.
**소유자 액션: 원본 engine/kg_harness/*.py 를 복원할 것** (이 stopgap 은 가드를 사실상 비활성화).

# KG: kg-harness-source-loss-stopgap-2026-06-27
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"


@dataclass(frozen=True)
class Violation:
    code: str
    message: str
    severity: Severity = Severity.ERROR


@dataclass(frozen=True)
class ValidationResult:
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(v.severity is Severity.ERROR for v in self.violations)


class WriteGuardError(RuntimeError):
    """ERROR-severity write-guard 위반으로 write 거부."""


_warned = False


def _warn_degraded() -> None:
    """degraded(가드 비활성) 상태를 1회 stderr 로 알림 — silent-green 금지."""
    global _warned
    if not _warned:
        _warned = True
        print(
            "[kg-harness] WARNING: RECONSTRUCTED STOPGAP — original source lost, "
            "invariants NOT enforced. Restore engine/kg_harness/*.py. "
            "(KG: kg-harness-source-loss-stopgap-2026-06-27)",
            file=sys.stderr,
        )


def validate_write(cypher: str) -> ValidationResult:
    """write cypher 정적 검증. STOPGAP: 규칙 미복구 → 위반 없음(빈 결과) + degraded 경고 1회."""
    _warn_degraded()
    return ValidationResult(violations=[])


def guarded_run(
    write_cypher: Callable[[str, dict], list[dict]], cypher: str, params: dict
) -> list[dict]:
    """validate_write → ERROR 위반 있으면 WriteGuardError, 없으면 write_cypher 실행.

    STOPGAP 에선 validate_write 가 항상 위반 0 이므로 실질적으로 write_cypher 를 그대로 통과
    (가드 비활성). 원 가드 복원 시 이 함수 시그니처는 그대로 유지된다.
    """
    result = validate_write(cypher)
    if not result.ok:
        msgs = "; ".join(
            f"{v.code}: {v.message}" for v in result.violations if v.severity is Severity.ERROR
        )
        raise WriteGuardError(msgs)
    return write_cypher(cypher, params)


__all__ = [
    "Severity",
    "Violation",
    "ValidationResult",
    "WriteGuardError",
    "validate_write",
    "guarded_run",
]
