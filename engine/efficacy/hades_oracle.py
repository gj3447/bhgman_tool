"""부채 — hades(실현) 독립 oracle: Contract(소스 모듈) → 테스트 도달 → GREEN.

hades 동사 = "실현"(추상 spec → 구체 코드, TDD GREEN). 효능 측정을 막던 건
"Contract↔test suite 결과" 귀속 엣지 부재였다. 이를 **정적 import 그래프 + pytest**로
연다: 테스트 파일이 import해 도달(transitive)하는 소스 모듈 = 그 Contract가 *실현되어
테스트로 검증됨*. import 엣지·테스트 존재·green 상태는 전부 테스트러너가 만든 것이지
hades가 아니다 → 순환성 0 (occam의 disk_present, 나생문의 컴파일러 oracle과 같은 급).

realization_rate = 테스트 도달 모듈 / 전체 소스 모듈 (universe). 높을수록 추상 spec이
구체 코드로 실현되어 GREEN으로 잠겼다 = hades 실현 완전성.

정직 라벨: 이건 **operational/state 측정**(realization 완전성)이지 *cognitive* 효능이
아니다 — hades-구현 vs naive-구현 반사실이 없다(코드 생성은 본질적 LLM, 결정론 baseline
부재). longinus drift_oracle(in_sync)·jaebaeman dispatch(fidelity)와 같은 급의 정직값.

순수(reachable_modules) + IO(파일 읽기/pytest) 분리.

# KG: efficacy-hades-2026-06-01, efficacy-measurement-line-2026-06-01,
#     hades-canonical-2026-05-27, bihaenggiman-harness-demoted-3layer-2026-05-27
"""

from __future__ import annotations

import ast
import subprocess
from collections import deque
from pathlib import Path

_ENGINE = "engine"


def module_name(path: Path, root: Path) -> str:
    """파일 경로 → dotted 모듈명 (engine/occam/occam.py → engine.occam.occam)."""
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _resolve_from(node: ast.ImportFrom, pkg: str) -> str | None:
    """ImportFrom 의 base 모듈명 해석 (상대 import 는 self 패키지 기준). engine.* 아니면 None."""
    if node.level:
        base = pkg.split(".")
        base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
        mod = ".".join(base + ([node.module] if node.module else []))
    elif node.module:
        mod = node.module
    else:
        return None
    return mod if mod.startswith(_ENGINE) else None


def _imports_of(path: Path, self_mod: str) -> set[str]:
    """파일이 import하는 engine.* 모듈명 집합 (절대 + 상대 해석). 파싱 실패 시 빈셋."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return set()
    pkg = self_mod.rsplit(".", 1)[0] if "." in self_mod else self_mod
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names if a.name.startswith(_ENGINE)}
        elif isinstance(node, ast.ImportFrom):
            mod = _resolve_from(node, pkg)
            if mod is None:
                continue
            out.add(mod)
            # `from pkg import submod` — submod도 모듈 후보 (universe 교집합이라 무해).
            out |= {f"{mod}.{a.name}" for a in node.names}
    return out


def reachable_modules(universe: set[str], edges: dict[str, set[str]], seeds: set[str]) -> set[str]:
    """seeds(테스트가 직접 import)에서 import 엣지로 도달 가능한 universe 모듈 (순수 BFS)."""
    seen: set[str] = set()
    dq: deque[str] = deque(seeds)
    while dq:
        m = dq.popleft()
        if m in seen:
            continue
        seen.add(m)
        for nxt in edges.get(m, set()):
            if nxt not in seen:
                dq.append(nxt)
    return seen & universe


def _git_tracked(root: Path) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "engine/*.py"], cwd=root, capture_output=True, text=True, check=True
    )
    return [root / line for line in out.stdout.splitlines() if line]


def collect(root: Path) -> tuple[set[str], dict[str, set[str]], set[str]]:
    """git-tracked engine 파일 → (universe 소스모듈, import 엣지, 테스트 seed 모듈)."""
    universe: set[str] = set()
    edges: dict[str, set[str]] = {}
    seeds: set[str] = set()
    files = _git_tracked(root)
    name_by_path = {p: module_name(p, root) for p in files}
    is_test = {p: (p.name.startswith("test_") or "/tests/" in p.as_posix()) for p in files}
    for p in files:
        mod = name_by_path[p]
        imps = _imports_of(p, mod)
        if is_test[p]:
            seeds |= imps
        else:
            if p.name == "__init__.py":
                continue
            universe.add(mod)
            edges[mod] = imps
    return universe, edges, seeds


def main() -> int:  # pragma: no cover — IO 진입점
    root = Path(__file__).resolve().parents[2]
    universe, edges, seeds = collect(root)
    realized = reachable_modules(universe, edges, seeds)
    rate = len(realized) / len(universe) if universe else 0.0
    unrealized = sorted(universe - realized)
    print(
        f"hades realization oracle: realized={len(realized)}/{len(universe)} "
        f"(rate={rate:.3f}) — 테스트-도달 소스 모듈 / 전체 (비순환: import+pytest oracle)"
    )
    if unrealized:
        print(f"  unrealized (테스트 미도달 Contract) {len(unrealized)}:")
        for m in unrealized[:25]:
            print(f"    - {m}")
        if len(unrealized) > 25:
            print(f"    … +{len(unrealized) - 25} more")
    print(
        "  주의: realization 완전성(operational/state) — cognitive 효능 아님(반사실 부재). "
        "GREEN 조건은 pre-commit 수트(1153 tests)가 전역 강제; 여기선 test-도달성만 측정."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
