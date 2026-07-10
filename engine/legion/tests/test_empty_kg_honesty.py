"""빈-KG 측정 정직성 종착 가드 (광역 측정 재배선 2026-07-10 — 슬라이스 0~4 의 합산 오라클).

설계(2026-07-09)의 정직 종착: "빈/깨끗 KG 에서 default loop 의 crossable = 0/7" —
정직 배선은 live-crossable 수를 *줄인다*. 이 파일은 그 종착을 기본 legion 루프 전체에
대해 실측으로 잠근다:

  before(측정 재배선 이전 실측, 빈 LocalKgStore):
    prometheus  {research_finding_count: 0.0}            ← fetch 미실행인데 '측정된 0' 위장
    occam       {supersession_confidence: 1.0,
                 dead_node_count: 0.0,
                 twin_status_score: 1.0}                 ← 후보 0건인데 전-확신/전-정상 위장
    (위장 상수 노출 4키, 발화 0)
  after:
    실행된 카운트의 측정된 영(occam dead_node_count=0.0)만 남고, 비율/확신 위장 0,
    발화 0/7. 미측정은 키 부재로 흐른다.

eureka/hades 의 measure 비배선은 *의도적*이며 여기서 잠근다(잠금예측):
  eureka — binding_density 구조적 DEAD: 유도 floor(PipelineConfig.fca_min_stability)와
    품질 게이트 floor(quality_gate.FCA_STABILITY_MIN)가 동일 상수라 survived≡induced,
    ratio 는 {1.0, 미측정} 밖을 못 벗어나 <0.5 발화가 원리적으로 불가. floor 분리(별건)
    전의 배선은 죽은 장식이다. 이 floor 동일성 자체도 아래에서 핀한다 — 분리되는 날
    이 잠금이 깨지며 '이제 배선 가능'을 알린다.
  hades — 스테이지 출력에 측정 가능한 런타임 소스 부재(오라클 신설 선행 필요).

# KG: bhgman-measurement-rewire-design-20260709 (정직 종착: 빈 KG 0/7)
# KG: 7cmd-measurement-driven-conditional-dispatch-2026-05-30
"""

from __future__ import annotations

from engine.kg_local.runner import make_local_runner
from engine.kg_local.store import LocalKgStore
from engine.legion.commanders import build_default_legion, default_stages


def _stage_metrics_on_empty_kg() -> dict[str, dict[str, float]]:
    """빈 KG 위에서 기본 6-stage 를 순차 실행하며 각 stage 의 measure 팩토리 산출을 수집."""
    rc = make_local_runner(LocalKgStore(), autosave=False)
    ctx: dict = {"run_cypher": rc, "cycle_id": "empty-kg-honesty"}
    out: dict[str, dict[str, float]] = {}
    for stage in default_stages():
        ctx.update(stage.run(dict(ctx)))
        if stage.measure is not None:
            m = stage.measure(ctx)
            if m is not None and m.measure():  # 빈 dict = 전-미측정 (정직) — 노출 아님
                out[stage.name] = m.measure()
    return out


def test_empty_kg_fires_zero_of_seven():
    """정직 종착의 발화 축: 빈 KG 기본 루프 = dispatch 0/7 (오발화 없음)."""
    rc = make_local_runner(LocalKgStore(), autosave=False)
    run = build_default_legion().run({"run_cypher": rc, "cycle_id": "empty-kg-0of7"})
    assert run.dispatch_decisions == (), (
        f"빈 KG 에서 발화는 0 이어야 한다: {run.dispatch_decisions}"
    )


def test_empty_kg_exposes_no_fabricated_constants():
    """정직 종착의 보고 축: 빈 KG 에서 노출되는 메트릭은 '실행된 스캔의 측정된 영'
    (occam dead_node_count=0.0)뿐 — 비율/확신(0.0/1.0 어느 방향의) 위장 상수 금지.
    (longinus float 쿼리는 LocalKgStore 미지원 → degraded → 정직 미측정.)"""
    metrics = _stage_metrics_on_empty_kg()
    assert metrics == {"occam": {"dead_node_count": 0.0}}, (
        f"빈 KG 위장 측정 노출: {metrics} — 미측정은 키 부재로 흘러야 한다"
    )


def test_intentionally_unwired_stages():
    """잠금예측: eureka/hades 는 measure 비배선(의도적) — 배선하려면 아래 floor 잠금
    해제(eureka) 또는 런타임 오라클 신설(hades)이 선행돼야 한다."""
    by_name = {s.name: s for s in default_stages()}
    assert by_name["eureka"].measure is None
    assert by_name["hades"].measure is None
    # 배선된 4 stage (양성 대조 — 잠금이 '전부 비배선'의 vacuous 통과가 아님을 증명).
    for wired in ("prometheus", "longinus", "occam", "naesengmoon"):
        assert by_name[wired].measure is not None, f"{wired} 팩토리가 배선돼 있어야"


def test_eureka_floor_collision_is_pinned():
    """정정 1(적대검증 2026-07-09): binding_density 구조적 DEAD 의 근거인 floor 동일성 —
    유도 floor == 게이트 floor(0.5) 인 한 survived≡induced 라 <0.5 발화 불가.
    이 핀이 깨지는 날(floor 분리) eureka 측정 배선이 별건으로 열린다."""
    from engine.eureka.pipeline import PipelineConfig
    from engine.eureka.quality_gate import FCA_STABILITY_MIN

    cfg = PipelineConfig(cycle_id="floor-pin")
    assert cfg.fca_min_stability == FCA_STABILITY_MIN == 0.5
