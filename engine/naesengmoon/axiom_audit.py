"""나생문 axiom-audit 렌즈 — "일관성" vs "참"의 간극을 결정론으로 드러냄.

외부 리뷰 비판 #1 자동화: Lean 정리는 *선언된 공리 위의 내부 일관성*을 증명하지 공리(=토대)가
*참*임을 증명하지 않는다. `axiom X`로 멈춘 곳(뮌하우젠 트릴레마 ③)을 찾아, 각 정리가
공리에 기대는지(consistency-relative-to-axiom) axiom-free인지(Lean 자체 토대) 분류한다.

이 렌즈는 *결정론* (LLM 아님, 판단렌즈 아님) — grep/import-graph 위상만으로 사실을 보고한다.
verdict는 PASS/FAIL이 아니라 **분리 보고**: 무엇이 일관성-전용이고 무엇이 axiom-tainted인지.
"참 증명"은 애초에 Lean이 못 하는 일(공리는 선택)이므로 이 렌즈도 truth를 *주장하지 않는다*.

비판 자체도 실측: 리뷰어의 "all N theorems rest on the axiom"이 맞는지 정량 확인.

# KG: 외부 리뷰 tension #1 (axiom CHU self-grounding), formal-cathedral-detection-2026-05-27
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_AXIOM = re.compile(r"^\s*axiom\s+(\w+)", re.MULTILINE)
_THEOREM = re.compile(r"^(?:theorem|lemma)\s+(\w+)", re.MULTILINE)
_OPAQUE = re.compile(r"^\s*opaque\s+(\w+)", re.MULTILINE)
_IMPORT = re.compile(r"^import\s+([\w.]+)", re.MULTILINE)
# proof-position sorry (주석 안 sorry는 제외 — repo 표준 패턴과 동일)
_SORRY = re.compile(r"(?::=|by)\s+sorry\b")


@dataclass(frozen=True)
class FileAxiomProfile:
    stem: str  # filename without .lean (= Lean module name)
    axioms: tuple[str, ...]
    opaques: tuple[str, ...]
    theorems: int
    sorry_in_proof: int
    sibling_imports: tuple[str, ...]  # imported local module stems


def _profile_file(path: Path) -> FileAxiomProfile:
    text = path.read_text(encoding="utf-8", errors="replace")
    return FileAxiomProfile(
        stem=path.stem,
        axioms=tuple(_AXIOM.findall(text)),
        opaques=tuple(_OPAQUE.findall(text)),
        theorems=len(_THEOREM.findall(text)),
        sorry_in_proof=len(_SORRY.findall(text)),
        sibling_imports=tuple(_IMPORT.findall(text)),
    )


def _tainted_stems(profiles: list[FileAxiomProfile]) -> set[str]:
    """axiom/opaque를 선언했거나, tainted 파일을 (전이적으로) import한 파일들의 stem 집합."""
    by_stem = {p.stem: p for p in profiles}
    tainted = {p.stem for p in profiles if p.axioms or p.opaques}
    # 전이 폐쇄: import한 게 tainted면 나도 tainted. fixpoint.
    changed = True
    while changed:
        changed = False
        for p in profiles:
            if p.stem in tainted:
                continue
            if any(imp in tainted for imp in p.sibling_imports if imp in by_stem):
                tainted.add(p.stem)
                changed = True
    return tainted


@dataclass(frozen=True)
class AxiomAuditReport:
    profiles: tuple[FileAxiomProfile, ...]
    tainted: frozenset[str] = field(default_factory=frozenset)

    @property
    def total_axioms(self) -> int:
        return sum(len(p.axioms) for p in self.profiles)

    @property
    def total_theorems(self) -> int:
        return sum(p.theorems for p in self.profiles)

    @property
    def axiom_resting_theorems(self) -> int:
        """tainted 파일(공리에 전이적으로 기댐)의 정리 수 = consistency-relative-to-axiom."""
        return sum(p.theorems for p in self.profiles if p.stem in self.tainted)

    @property
    def axiom_free_theorems(self) -> int:
        return self.total_theorems - self.axiom_resting_theorems

    @property
    def total_sorry(self) -> int:
        return sum(p.sorry_in_proof for p in self.profiles)

    @property
    def summary(self) -> str:
        ax = ", ".join(a for p in self.profiles for a in p.axioms) or "none"
        return (
            f"axiom-audit: axioms={self.total_axioms} ({ax}) | theorems={self.total_theorems} "
            f"→ {self.axiom_resting_theorems} rest on a declared axiom "
            f"(consistency-relative-to-axiom), {self.axiom_free_theorems} axiom-free "
            f"(consistency in Lean's own foundation) | proof-sorry={self.total_sorry}. "
            f"0 prove an axiom TRUE — not Lean-provable (axioms are chosen, not proven)."
        )


def audit_lean_dir(lean_dir: str | Path) -> AxiomAuditReport:
    """lean/ 의 .lean 파일들을 스캔해 axiom-vs-theorem 위상 보고. 결정론, neo4j/LLM 불필요."""
    root = Path(lean_dir)
    profiles = sorted((_profile_file(f) for f in root.glob("*.lean")), key=lambda p: p.stem)
    return AxiomAuditReport(
        profiles=tuple(profiles), tainted=frozenset(_tainted_stems(list(profiles)))
    )


def check_claim(report: AxiomAuditReport, claimed_resting: int | None) -> str:
    """리뷰/문서의 'N theorems rest on the axiom' 주장을 실측과 대조 (비판 자체의 검증)."""
    actual = report.axiom_resting_theorems
    if claimed_resting is None:
        return f"no claim to check (actual axiom-resting = {actual})"
    if claimed_resting == actual:
        return f"CONFIRMED: claimed {claimed_resting} == actual {actual}"
    return (
        f"OVERSTATED: claimed {claimed_resting} but only {actual}/{report.total_theorems} "
        f"rest on a declared axiom (the rest are axiom-free)"
    )


__all__ = ["AxiomAuditReport", "FileAxiomProfile", "audit_lean_dir", "check_claim"]
