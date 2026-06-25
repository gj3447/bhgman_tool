"""harness → 재배맨 seed 브릿지 — '하네스 자체가 재배맨 씨앗'을 닫는 배선.

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
from engine.jaebaeman.jaebaeman_models import Goal

_TASK_TYPE = "harness-compensation"


def harness_seed_goals(diagnosis: HarnessDiagnosis) -> list[Goal]:
    """Compile a harness diagnosis into 재배맨 seed Goals — one per canonical :class:`Axis` NOT
    confirmed PRESENT, to ensure that axis in the germinated subagent context.

    A 4-axis-complete harness yields ZERO Goals (no compensation); an axis-less one yields four.
    The harness thereby becomes plantable 재배맨 씨앗 (a harness IS a seed). ``target_domain`` =
    the diagnosed tier so the subagent context knows where it runs.
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
                anchor=None,
            )
        )
    return goals


__all__ = ["harness_seed_goals"]
