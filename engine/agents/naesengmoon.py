"""나생문(Naesengmoon 羅生門) 실엔진 — 판단렌즈 ensemble critic.

2 lens-class (naesengmoon-two-lens-class-2026-05-27):
  - **판단(judgment) 렌즈 = 이 엔진** (LLM): N개 독립 적대 렌즈 병렬 비평 → UNANIMOUS_PASS 집계.
  - oracle(컴파일러나생문) 렌즈 = engine/{occam,eureka}/oracle_lens.py (실행형, ruff/pytest/lean).
    여기선 판단렌즈만 — oracle은 결정론이라 그쪽 모듈이 실행.

N중 = N 독립 lens (default 1:1, lesson-naesengmoon-cardinality-direct-1to1-not-orthogonal).
executor != reviewer (D20) — 호출자가 빌더면 이 엔진은 별도 critic. graceful degrade.

# KG: naesengmoon-canonical-2026-05-19, naesengmoon-two-lens-class-2026-05-27,
#     bhgman-llm-commander-runtime-2026-05-28
"""

from __future__ import annotations

from dataclasses import dataclass

from client import AgentClient
from dispatch import SubagentResult, SubagentSpec, dispatch_parallel
from agent_models import SYNTHESIS_MODEL

# 렌즈별 적대 비평 system prompt (판단 lens-class). 첫 줄 'VERDICT: PASS|FAIL|CONDITIONAL' 강제.
LENS_PROMPTS: dict[str, str] = {
    "constitutional": (
        "You are a constitutional-lens adversarial critic (Naesengmoon). Judge the target against "
        "governance, spec-fidelity, honesty, and quality principles. Hunt for over-claims and "
        "unstated assumptions."
    ),
    "mathematical": (
        "You are a mathematical-lens adversarial critic (Naesengmoon). Judge logical rigor, "
        "quantifier correctness (∀/∃), and counterexamples. A single counterexample falsifies a "
        "universal claim — say so explicitly."
    ),
    "solid": (
        "You are a SOLID-lens adversarial critic (Naesengmoon). Judge design: SRP, DIP, coupling, "
        "cohesion, abstraction boundaries. Flag concrete-dependency and responsibility-bundling."
    ),
}
_VERDICT_RULE = (
    "\n\nOutput format — first line EXACTLY one of:\n"
    "VERDICT: PASS\nVERDICT: FAIL\nVERDICT: CONDITIONAL\n"
    "Then your findings as bullet points. Do not rubber-stamp; ground every verdict in a specific "
    "fact about the target."
)
DEFAULT_LENSES = ("constitutional", "mathematical", "solid")


@dataclass(frozen=True)
class LensVerdict:
    lens: str
    verdict: str  # PASS | FAIL | CONDITIONAL | ERROR
    findings: str
    ok: bool = True


@dataclass(frozen=True)
class EnsembleVerdict:
    target: str
    lens_verdicts: tuple[LensVerdict, ...]
    verdict: str  # PASS | FAIL | CONDITIONAL
    aggregation: str = "UNANIMOUS_PASS"

    @property
    def summary(self) -> str:
        per = " ".join(f"{v.lens}={v.verdict}" for v in self.lens_verdicts)
        return f"naesengmoon[{self.target}]: {self.verdict} ({self.aggregation}) — {per}"


def _parse_verdict(text: str) -> tuple[str, str]:
    """첫 줄에서 VERDICT 추출. 없으면 본문에 FAIL/CONDITIONAL 단서 탐색, 기본 CONDITIONAL(보수)."""
    head = text.strip().splitlines()[0].upper() if text.strip() else ""
    for v in ("PASS", "FAIL", "CONDITIONAL"):
        if f"VERDICT: {v}" in head or head == v:
            return v, text
    up = text.upper()
    if "FAIL" in up:
        return "FAIL", text
    if "CONDITIONAL" in up:
        return "CONDITIONAL", text
    return "CONDITIONAL", text  # 판정 불명 = 보수적(PASS 아님)


def _aggregate(verdicts: list[LensVerdict]) -> str:
    """UNANIMOUS_PASS: 전원 PASS만 PASS, 하나라도 FAIL이면 FAIL, 그 외 CONDITIONAL."""
    vs = [v.verdict for v in verdicts]
    if any(v in ("FAIL", "ERROR") for v in vs):
        return "FAIL"
    if all(v == "PASS" for v in vs):
        return "PASS"
    return "CONDITIONAL"


def critique(
    target: str,
    claim: str,
    client: AgentClient,
    *,
    lenses: tuple[str, ...] = DEFAULT_LENSES,
    model: str = SYNTHESIS_MODEL,
) -> EnsembleVerdict:
    """N 판단렌즈 병렬 적대 비평 → 집계. claim = 검증 대상 주장/산출물 텍스트."""
    specs = [
        SubagentSpec(
            name=lens,
            system=LENS_PROMPTS.get(lens, f"You are a {lens}-lens adversarial critic.")
            + _VERDICT_RULE,
            user=f"Target: {target}\n\nClaim / artifact to verify:\n{claim}",
            model=model,
            max_tokens=2048,
        )
        for lens in lenses
    ]
    results: list[SubagentResult] = dispatch_parallel(specs, client)

    lens_verdicts: list[LensVerdict] = []
    for lens, r in zip(lenses, results):
        if not r.ok:
            lens_verdicts.append(LensVerdict(lens, "ERROR", r.error, ok=False))
            continue
        v, findings = _parse_verdict(r.text)
        lens_verdicts.append(LensVerdict(lens, v, findings))

    return EnsembleVerdict(
        target=target,
        lens_verdicts=tuple(lens_verdicts),
        verdict=_aggregate(lens_verdicts),
    )


__all__ = ["DEFAULT_LENSES", "EnsembleVerdict", "LensVerdict", "critique"]
