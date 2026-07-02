"""harness → 재배맨 seed 브릿지 — '하네스 자체가 재배맨 씨앗'을 닫는 배선.

STATUS: G6-DEMOTED (jbm-s6, 2026-07-03) — bench/실험 전용, 프로덕션 소비자 0
(7군단장 실체감사 wf_376c327b-8f3 G6; engine/harness 는 이 모듈을 호출하지 않는다).
승격하려면 실제 배선 + 이 마커 제거 + engine/jaebaeman/tests/test_orphan_wiring.py
oracle 갱신이 *함께* 필요하다 (무음 승격 불가).

재배맨 v2 = subagent-runtime-protocol: 씨앗 = ``:SubagentTaskSpec`` = 하네스(subagent) 컨텍스트
(``lifecycle.agent_dispatcher`` 가 씨앗 → ``SubagentSpec`` 으로 컴파일). 하지만 harness *진단*
(``engine.harness`` 의 3계층/4축 ``HarnessDiagnosis``)과 재배맨 *씨앗* 은 직접 안 묶여 있었다
(양방향 grep = 0). 이 모듈이 그 갭을 닫는다.

``harness_seed_goals(diagnosis)`` — harness 진단을 받아 PRESENT 로 확인되지 않은 각 정규 축마다
plantable :class:`Goal`(씨앗)을 낸다. 4축 완비 harness → 0 씨앗(보완 불필요), 축 무신호 → 4.
그 Goal 들은 ``run_jaebaeman`` 으로 심기고 ``germinate_ready_seeds`` 로 subagent 컨텍스트로 발아한다
— 즉 harness 의 갭이 *심을 수 있는 subagent task* 가 된다.

정직: 미확인 축은 ``Presence.UNKNOWN`` (부재 ≠ 능력 없음 — harness.py 정직 공시). 그래서 씨앗
objective 는 'ensure/verify {axis} coverage'(harness 가 그 축을 광고하지 않으니 subagent 컨텍스트가
보장)이지 'harness 가 X 없음' 이 아니다.

# KG: 재배맨-v2-subagent-runtime-protocol, finding-jaebaeman-seed-dispatch-handoff-unwired-2026-06-07
"""

from __future__ import annotations

from engine.harness.harness_models import Axis, HarnessDiagnosis
from engine.jaebaeman.jaebaeman_models import Goal, SeedRecord

_TASK_TYPE = "harness-compensation"
_BASE_SYSTEM = "너는 계획 실행기다. 작업을 수행하고 결과를 보고하라."


def harness_seed_goals(diagnosis: HarnessDiagnosis, *, anchor: str | None = None) -> list[Goal]:
    """Compile a harness diagnosis into 재배맨 seed Goals — one per canonical :class:`Axis` NOT
    confirmed PRESENT, to ensure that axis in the germinated subagent context.

    A 4-axis-complete harness yields ZERO Goals (no compensation); an axis-less one yields four.
    The harness thereby becomes plantable 재배맨 씨앗 (a harness IS a seed). ``target_domain`` =
    the diagnosed tier so the subagent context knows where it runs.

    ``anchor`` (default None = self-anchored) FK-roots the seeds to a KG node — pass
    ``diagnosis.subject`` to anchor them to the planted ``:HarnessDiagnosis`` node (the harness
    diagnosis becomes the soil the compensation seeds grow in, via a ``HAS_SEED`` edge).
    """
    present = set(diagnosis.present_axes)
    goals: list[Goal] = []
    for axis in Axis:
        if axis in present:
            continue
        goals.append(
            Goal(
                name=f"harness::{diagnosis.subject}::ensure-{axis.value.lower()}",
                objective=(
                    f"ensure {axis.value} coverage for subagents under harness "
                    f"'{diagnosis.subject}' (tier {diagnosis.tier.value}); the harness does not "
                    "advertise this axis (Presence.UNKNOWN — 부재 ≠ 능력 없음)"
                ),
                task_type=_TASK_TYPE,
                target_domain=diagnosis.tier.value,
                anchor=anchor,
            )
        )
    return goals


def harness_germination_system(
    diagnosis: HarnessDiagnosis, *, base_system: str = _BASE_SYSTEM
) -> str:
    """The germination ENVIRONMENT a subagent runs in under a target harness — a system directive
    naming the tier + which 4-axis primitives the harness PROVIDES (use them) vs leaves UNKNOWN
    (supply yourself). The REVERSE of :func:`harness_seed_goals`: the harness is not only turned
    into a seed, it also shapes HOW a seed germinates (harness = soil, seed = WHAT, this = WHERE/HOW).
    """
    present = [a.value for a in diagnosis.present_axes]
    missing = [a.value for a in Axis if a not in set(diagnosis.present_axes)]
    lines: list[str] = []
    if base_system.strip():
        lines.append(base_system.strip())
    lines.append(
        f"[harness] tier={diagnosis.tier.value}; this harness provides "
        f"{', '.join(present) if present else 'no detected'} axis primitive(s) — use them."
    )
    if missing:
        lines.append(
            f"[harness] it does NOT advertise {', '.join(missing)} (Presence.UNKNOWN — "
            "부재 ≠ 능력 없음) — you must supply these yourself in your output."
        )
    return "\n".join(lines)


def germinate_under_harness(
    seed: SeedRecord,
    diagnosis: HarnessDiagnosis,
    *,
    model: str = "claude-haiku-4-5-20251001",
    base_system: str = _BASE_SYSTEM,
):
    """Compile a seed into a subagent context whose germination ENVIRONMENT is the target harness:
    the system prompt bakes in the harness tier + axis primitives (via :func:`harness_germination_system`)
    while the user prompt carries the seed's task. Seed = WHAT; harness = WHERE/HOW. Returns a
    ``SubagentSpec`` (lazy-imported to keep this module free of the agents dependency)."""
    from engine.agents.dispatch import SubagentSpec  # noqa: PLC0415

    return SubagentSpec(
        name=seed.name,
        system=harness_germination_system(diagnosis, base_system=base_system),
        user=f"{seed.display_name}\n기대 산출: {seed.expected_outcome}",
        model=model,
        web_search=False,
    )


__all__ = ["germinate_under_harness", "harness_germination_system", "harness_seed_goals"]
