"""재배맨(Jaebaeman) 엔진 — 계획→씨앗 결정화 (meta-planning → seed materialization).

재배맨 본질(사용자 정전 2026-06-01): *AI가 "계획에 대한 계획 / 계획 자체"를 연쇄적으로
짜서, context를 KG에 씨앗(SubagentTaskSpec)으로 심는 것.* 씨앗 심기 = 계획 짜기.

기존 `engine/agents/dispatch.py` = LLM fan-out(출격) 실행형. 그 dispatch는 A/B falsifier상
인지 기여 0(가치=operational only)이었다. 이 엔진은 그 *앞 단계* — dispatch가 소비할
씨앗 트리를 결정론으로 짜고 KG에 심는 본체. 다른 6군단장과 동형(결정론 코어 floor + apply gate).

형식: 계획 = `μX.(CHUPiece + List X)` initial algebra의 anamorphism(unfold). depth≤3
(SKILL v2.4 fractal hard limit). 씨앗 materialize = MERGE-only covenant(삭제 없음, reversible).

# KG: jaebaeman-planfirst-essence-reframe-2026-05-27, 재배맨-v2-subagent-runtime-protocol,
#     lesson-prom64-jaebaeman-chu-agentfolder-2026-04-29 (μX initial algebra),
#     project-legion-unification-kg-engine-2026-06-01 (결정론 코어 = 정체성)
"""
