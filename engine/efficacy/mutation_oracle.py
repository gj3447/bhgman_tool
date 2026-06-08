"""부채(naesengmoon 검증) — mutation testing = 검증 효능의 진짜 독립 oracle.

naesengmoon "검증" 효능을 비순환으로 재는 정석: **버그를 주입**하고 oracle-lens(테스트
스위트)가 *잡는가*. catch rate = caught/total. 독립(주입 버그는 우리가 만든 ground truth,
naesengmoon 판정과 무관) + 정량.

순수(generate_mutants: 소스→변이본들) + IO(run_mutation_test: write/pytest/restore).
**covenant: try/finally로 원본 항상 복원** (소스 파괴 금지).

# KG: efficacy-naesengmoon-2026-06-01, efficacy-measurement-line-2026-06-01,
#     ATOM_Skill_taliban, naesengmoon-canonical-2026-05-19, project_naesengmoon_two_lens_class_2026_05_27
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

# (찾을 패턴, 바꿀 값, 설명) — 첫 출현 1곳만 변이 (mutant 1개 = 1 주입버그).
_MUTATIONS: tuple[tuple[str, str, str], ...] = (
    (" > ", " >= ", "relational > → >="),
    (" < ", " <= ", "relational < → <="),
    (" >= ", " > ", "relational >= → >"),
    (" + ", " - ", "arith + → -"),
    (" - ", " + ", "arith - → +"),
    (" * ", " / ", "arith * → /"),
    (" and ", " or ", "boolean and → or"),
    (" or ", " and ", "boolean or → and"),
    ("1.0", "1.5", "const 1.0 → 1.5"),
    ("0.0", "1.0", "const 0.0 → 1.0"),
    (" == ", " != ", "equality == → !="),
    ("not ", "", "drop negation"),
)


@dataclass(frozen=True)
class Mutant:
    description: str
    source: str


@dataclass(frozen=True)
class MutationResult:
    total: int
    caught: int
    escaped: int
    escaped_descriptions: tuple[str, ...] = ()

    @property
    def catch_rate(self) -> float:
        return self.caught / self.total if self.total else 0.0


def generate_mutants(source: str, mutations=_MUTATIONS) -> list[Mutant]:
    """소스에서 적용 가능한 변이 1곳씩 적용한 변이본 리스트 (패턴당 첫 출현)."""
    out: list[Mutant] = []
    for find, repl, desc in mutations:
        if find in source:
            out.append(Mutant(description=desc, source=source.replace(find, repl, 1)))
    return out


def run_mutation_test(
    target_file: str, test_cmd: list[str], mutations=_MUTATIONS
) -> MutationResult:  # pragma: no cover — subprocess/IO
    """target_file에 변이 주입 → test_cmd 실행 → caught(테스트 실패)/escaped(여전히 통과).

    covenant: 원본 바이트 보관 후 finally에서 항상 복원."""
    from pathlib import Path  # noqa: PLC0415

    path = Path(target_file)
    original = path.read_text(encoding="utf-8")
    mutants = generate_mutants(original, mutations)
    caught = 0
    escaped: list[str] = []
    try:
        for m in mutants:
            path.write_text(m.source, encoding="utf-8")
            proc = subprocess.run(test_cmd, capture_output=True, text=True)  # noqa: S603, PLW1510
            if proc.returncode != 0:
                caught += 1  # 테스트 실패 = 버그 잡음
            else:
                escaped.append(m.description)  # 여전히 통과 = 테스트 구멍
    finally:
        path.write_text(original, encoding="utf-8")  # 원본 복원 (필수)
    return MutationResult(
        total=len(mutants),
        caught=caught,
        escaped=len(escaped),
        escaped_descriptions=tuple(escaped),
    )


def main() -> int:  # pragma: no cover — IO 진입점
    # 기본 타겟: scoring.py (잘 테스트된 순수 모듈) + 그 테스트.
    target = sys.argv[1] if len(sys.argv) > 1 else "engine/occam/scoring.py"
    test_path = sys.argv[2] if len(sys.argv) > 2 else "engine/occam/tests/test_scoring.py"
    cmd = ["uv", "run", "pytest", test_path, "-q", "-x"]
    res = run_mutation_test(target, cmd)
    print(
        f"naesengmoon mutation oracle [{target}]: caught={res.caught}/{res.total} "
        f"catch_rate={res.catch_rate:.3f} escaped={list(res.escaped_descriptions)}"
    )
    return 0


__all__ = ["Mutant", "MutationResult", "generate_mutants", "run_mutation_test"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
