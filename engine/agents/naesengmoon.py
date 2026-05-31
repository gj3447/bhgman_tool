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

from engine.agents.client import AgentClient
from engine.agents.dispatch import SubagentResult, SubagentSpec, dispatch_parallel
from engine.agents.agent_models import SYNTHESIS_MODEL
from engine.agents.grounding import GroundingSource, build_grounding

from engine.naesengmoon.decorrelation import DEFAULT_RHO, effective_n

# 렌즈별 적대 비평 system prompt (판단 lens-class). 첫 줄 'VERDICT: PASS|FAIL|CONDITIONAL' 강제.
LENS_PROMPTS: dict[str, str] = {
    "constitutional": (
        "You are a constitutional-lens adversarial critic (Naesengmoon). Judge the target against "
        "governance, spec-fidelity, honesty, and quality principles. Hunt for GENUINE over-claims "
        "(universal/absolute claims, overstated certainty, overgeneralization from little evidence) "
        "and unstated assumptions — but do not invent defects where the work is appropriately scoped."
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
    "Then your findings as bullet points.\n"
    "Calibration (anti-rubber-stamp AND anti-over-rejection — both matter):\n"
    "- VERDICT: FAIL ONLY if you can name and quote a specific violation (an over-claim, a "
    "counterexample, a concrete defect). If you cannot name one, it is NOT a FAIL.\n"
    "- VERDICT: CONDITIONAL only for a real, statable, non-blocking concern.\n"
    "- Appropriately hedged or scoped statements ('may not generalize', 'further testing needed', "
    "'in our experiments', 'preliminary', 'for the tested range') are sound epistemic practice, "
    "NOT defects — do not penalize honest hedging or caution.\n"
    "- If the target is sound with no nameable violation, VERDICT: PASS. "
    "Do not rubber-stamp, but do not manufacture defects either."
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
    n_eff: float = 0.0  # effective independent votes (Kish); same-model judgment lenses → ≪ N
    n_critics: int = 0
    grounded_facts: int = 0  # KG 사전지식으로 접지된 정전·교훈 수 (0 = 접지 없음/미가용)

    @property
    def summary(self) -> str:
        per = " ".join(f"{v.lens}={v.verdict}" for v in self.lens_verdicts)
        # Honest confidence: N same-model judgment lenses are correlated → n_eff ≪ N
        # (consensus-prom8-naesengmoon-decorrelation-2026-05-31). Raise n_eff via oracle lenses
        # or cross-family critics; never read N agreeing critics as N independent votes.
        neff = f" | {self.n_critics} judgment critics, n_eff≈{self.n_eff:.2f} (same-model → correlated)"
        g = f" grounded={self.grounded_facts}"
        return f"naesengmoon[{self.target}]: {self.verdict} ({self.aggregation}) — {per}{neff}{g}"


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
    grounding: GroundingSource | None = None,
) -> EnsembleVerdict:
    """N 판단렌즈 병렬 적대 비평 → 집계. claim = 검증 대상 주장/산출물 텍스트.

    grounding = KG 접지원. 주면 비평 *전* 하계에서 관련 정전·교훈을 읽어 각 렌즈 prompt에 주입
    → 렌즈가 기존 정전과의 정합/충돌을 근거로 판정(KG-first). None이면 무접지(graceful).
    """
    ctx, n_facts = build_grounding(
        grounding, f"{target} {claim}", header="관련 정전·교훈 (이 기준으로 판정)"
    )
    specs = [
        SubagentSpec(
            name=lens,
            system=LENS_PROMPTS.get(lens, f"You are a {lens}-lens adversarial critic.")
            + _VERDICT_RULE,
            user=f"{ctx}Target: {target}\n\nClaim / artifact to verify:\n{claim}",
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

    # All lenses here are same-model JUDGMENT critics → correlated; report honest n_eff.
    n_critics = len(lens_verdicts)
    n_eff = effective_n(n_oracle=0, n_judgment=n_critics, rho=DEFAULT_RHO)
    return EnsembleVerdict(
        target=target,
        lens_verdicts=tuple(lens_verdicts),
        verdict=_aggregate(lens_verdicts),
        n_eff=n_eff,
        n_critics=n_critics,
        grounded_facts=n_facts,
    )


__all__ = ["DEFAULT_LENSES", "EnsembleVerdict", "LensVerdict", "critique"]
