"""naesengmoon measurement 배선 — LLM 조건부 (광역 측정 재배선 2026-07-10, slice 3 이중가드).

설계(2026-07-09): 나생문의 lens_disagreement_ratio 는 LLM 판단렌즈가 실제로 표결했을
때만 측정 가능한 'LLM 조건부' 메트릭이다 — 기본 결정론 루프(LLM 부재)에서는 미측정.
prometheus grounding-wire / occam measure-wire 와 동형의 배선:
  1. _run_verify 가 판단렌즈 표결을 verdict["judgment_lens_verdicts"] 로 공시한다
     (aggregate 의 집계값만으론 불일치율 재도출 불가 — 관측면 부재가 3층 deadness ①).
  2. naesengmoon 스테이지가 measure=_measure_naesengmoon 팩토리를 지닌다.
  3. 팩토리는 echo-배제 후 독립 판단렌즈 2표 이상일 때만 불일치율을 측정한다 —
     1표 이하로는 '불일치'가 정의되지 않는다(빈집합축약 금지, vacuous 0.0 위장 금지).

guard_defect(음성): oracle-only(LLM 부재)·단일 렌즈·echo-축출 후 1표 이하 → 미측정,
발화 0 — 상수 위장 없음. guard_mechanism(양성): 렌즈 2표 분열(disagreement 0.5>0.4)
→ user_verdict_trigger dispatch 가 legion.run 경로에서 실제 발화·수집된다.

# KG: naesengmoon-wired-ensemble-upgrade-2026-05-27
# KG: bhgman-measurement-rewire-design-20260709 (slice 3: naesengmoon LLM 조건부)
"""

from __future__ import annotations

from engine.kg_local.runner import make_local_runner
from engine.kg_local.store import LocalKgStore
from engine.legion.commanders import _measure_naesengmoon, _run_verify, default_stages
from engine.legion.legion import Legion
from engine.legion.legion_models import CommanderStage

_UP = {
    "acquired": {"mode": "kg-deterministic"},
    "bindings": {"mode": "kg-deterministic"},
    "abstractions": {"mode": "fca"},
    "hygiene": {"mode": "occam"},
}


def _lens(lens: str, passed: bool, echo: bool = False) -> dict:
    return {"lens": lens, "passed": passed, "echo_suspect": echo}


# ── 배선 1: 스테이지가 measure 팩토리를 지닌다 ────────────────────────────────
def test_naesengmoon_stage_carries_measure_factory():
    stage = next(s for s in default_stages() if s.name == "naesengmoon")
    assert stage.measure is not None, "naesengmoon 스테이지에 measure= 팩토리가 배선돼야"


# ── 배선 2: _run_verify 가 판단렌즈 표결을 공시한다 (LLM 부재 = 빈 목록) ───────
def test_run_verify_exposes_judgment_lens_observability():
    rc = make_local_runner(LocalKgStore(), autosave=False)
    out = _run_verify({"run_cypher": rc, **_UP})["verdict"]
    assert "judgment_lens_verdicts" in out, "판단렌즈 관측면이 verdict 에 공시돼야"
    assert out["judgment_lens_verdicts"] == []  # LLM 부재 = 표결 0


# ── guard_defect: LLM 부재/표본 부족 = 미측정 (상수 위장·오발화 금지) ──────────
def test_oracle_only_verdict_is_unmeasured():
    """기본 결정론 루프(LLM 부재): 팩토리는 None — lens_disagreement_ratio 가
    0.0(만장일치 위장)으로도 1.0 으로도 나타나지 않는다."""
    assert _measure_naesengmoon({"verdict": {"oracle": "PASS", "judgment_lens_verdicts": []}}) is (
        None
    )
    assert _measure_naesengmoon({"verdict": {"oracle": "PASS"}}) is None  # 관측면 자체 부재
    assert _measure_naesengmoon({}) is None  # verdict 부재


def test_single_lens_cannot_measure_disagreement():
    """1표로는 불일치가 정의되지 않는다 — vacuous 0.0(전-일치 위장) 금지."""
    v = {"judgment_lens_verdicts": [_lens("constitutional", True)]}
    assert _measure_naesengmoon({"verdict": v}) is None


def test_echo_excluded_lenses_do_not_vote():
    """echo-축출 렌즈는 독립 표가 아니다 — 축출 후 1표 이하면 미측정."""
    v = {
        "judgment_lens_verdicts": [
            _lens("constitutional", True),
            _lens("adversarial", False, echo=True),  # executor framing 반향 → 배제
        ]
    }
    assert _measure_naesengmoon({"verdict": v}) is None


# ── guard_mechanism: 독립 2표 이상 → 불일치율 실측 + 발화 ─────────────────────
def test_split_lenses_measure_disagreement_and_fire():
    """2표 분열 → disagreement 0.5 > 0.4 → user_verdict_trigger 발화 (LLM 조건부
    3번째 live 메트릭의 존재 증명)."""
    v = {
        "judgment_lens_verdicts": [
            _lens("constitutional", True),
            _lens("adversarial", False),
        ]
    }
    m = _measure_naesengmoon({"verdict": v})
    assert m is not None
    assert m.measure()["lens_disagreement_ratio"] == 0.5
    fired = [
        d
        for d in m.decide_dispatch(cycle_id="nmw-fire")
        if d.metric_name == "lens_disagreement_ratio"
    ]
    assert fired and fired[0].target_commander == "user_verdict_trigger"


def test_unanimous_lenses_measure_zero_and_do_not_fire():
    """판별 반대쪽: 3표 만장일치 → disagreement 0.0 측정(측정된 영), 발화 없음."""
    v = {
        "judgment_lens_verdicts": [
            _lens("constitutional", True),
            _lens("adversarial", True),
            _lens("empirical", True),
        ]
    }
    m = _measure_naesengmoon({"verdict": v})
    assert m.measure()["lens_disagreement_ratio"] == 0.0
    assert not [
        d
        for d in m.decide_dispatch(cycle_id="nmw-nofire")
        if d.metric_name == "lens_disagreement_ratio"
    ]


def test_legion_run_collects_naesengmoon_dispatch_decision():
    """end-to-end: legion.run 이 naesengmoon 팩토리를 집어 분열 표결에서
    user_verdict_trigger decision 을 수집한다(런타임 배선 증명)."""
    stage = CommanderStage(
        "naesengmoon",
        "검증",
        ("run_cypher",),
        ("verdict",),
        lambda ctx: {
            "verdict": {
                "oracle": "PASS",
                "judgment_lens_verdicts": [
                    _lens("constitutional", True),
                    _lens("adversarial", False),
                ],
            }
        },
        measure=_measure_naesengmoon,
    )
    run = Legion().register(stage).run({"run_cypher": lambda c, p: [], "cycle_id": "nmw-e2e"})
    assert run.completed
    fired = [
        d
        for d in run.dispatch_decisions
        if d.metric_name == "lens_disagreement_ratio"
        and d.target_commander == "user_verdict_trigger"
    ]
    assert fired, f"legion.run 이 naesengmoon dispatch 를 수집해야; got {run.dispatch_decisions}"
