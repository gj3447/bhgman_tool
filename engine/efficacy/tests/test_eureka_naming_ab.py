"""eureka 개념명명 A/B TDD — 주입식 fake LLM 클라이언트로 게이트 발화를 결정론적으로 증명.

증명 항목:
  (1) offline run — 라이브 dgx vLLM 없이 fake 클라이언트로 전 경로 동작.
  (2) preflight 게이트 발화 — LLM이 *제 proposal을 제 라벨로* 우기면(순환) UNMEASURABLE.
  (3) A/B delta 계산 — floor handicap 시 vLLM proposal이 floor를 이기면 MEASURABLE_LIFT.
  + deferred(client 없음) + MEASURABLE_NULL(default ceiling) 정직 경로.

# KG: adr-seven-commander-engine-cli-mcp-vllm-2026-06-18, project_bhgman_ab_falsifier_2026_05_30,
#     efficacy-measurement-line-2026-06-01
"""

from __future__ import annotations

from collections.abc import Sequence

from engine.efficacy.eureka_naming_ab import (
    NamedAbstraction,
    run_eureka_naming_ab,
)
from engine.efficacy.eureka_oracle import build_planted_context


# ── fake LLM 클라이언트들 (결정론, 라이브 vLLM 미호출) ──────────────────────────────


class _FakeRecoversMissing:
    """floor가 놓친 planted 개념을 *정확히* 자연어 추상으로 proposal (정직한 lift 시나리오)."""

    def __init__(self, recover: Sequence[frozenset[str]]) -> None:
        self._recover = list(recover)

    def propose(self, context, fca_extents):  # noqa: ARG002 — context 미사용 (planted 직접 복원 fake)
        return [
            NamedAbstraction(extent=e, name=f"named_concept_{i}", source="vllm")
            for i, e in enumerate(self._recover)
        ]


class _FakeSelfLabeling:
    """LLM이 planted를 복원하는 추상을 내되 *제 라벨(circularity keyword)로* positive라 우김(순환).

    oracle는 이들을 is_positive=True로 채점하지만 provenance가 군단장-자기생성이라 self-prediction.
    이 경우 circularity_ratio가 임계를 넘어 CIRCULARITY 게이트가 발화해야 한다."""

    def __init__(self, planted: Sequence[frozenset[str]]) -> None:
        self._planted = list(planted)

    def propose(self, context, fca_extents):  # noqa: ARG002
        # planted를 *정확히* 복원(is_positive=True)하되 self_proposed/naming_self keyword를 단다.
        return [
            NamedAbstraction(extent=e, name="self_proposed naming_self", source="vllm")
            for e in self._planted
        ]


class _FakeUseless:
    """planted 못 잡는 추상만 proposal — floor 못 이김(MEASURABLE_NULL 또는 ceiling)."""

    def propose(self, context, fca_extents):  # noqa: ARG002
        return [NamedAbstraction(extent=frozenset(), name="empty", source="vllm")]


# ── (1) offline run + deferred ────────────────────────────────────────────────────


def test_deferred_when_no_client_runs_offline():
    """client 미주입 → Arm A(FCA floor)만, Arm B는 DEFERRED. 라이브 vLLM 0 호출."""
    res = run_eureka_naming_ab(client=None)
    assert res.verdict == "DEFERRED"
    assert res.arm_b_score is None
    assert res.delta is None
    assert res.arm_a_score == 1.0  # default planted에서 FCA floor는 전부 복원
    assert res.preflight is None
    assert "라이브" in res.reason


def test_offline_run_with_fake_client_full_path():
    """fake 클라이언트로 전 A/B 경로 동작 (라이브 vLLM 없이). preflight 산출됨."""
    res = run_eureka_naming_ab(client=_FakeUseless())
    assert res.preflight is not None
    assert res.arm_b_score is not None
    assert res.verdict in {"MEASURABLE_LIFT", "MEASURABLE_NULL", "UNMEASURABLE"}


# ── (2) preflight 게이트 발화 (순환) ───────────────────────────────────────────────


def test_preflight_fires_circularity_when_llm_self_labels():
    """LLM이 제 proposal을 제 circularity-keyword 라벨로 우김 → UNMEASURABLE (delta 날조 금지).

    floor를 4개 누락시켜(keep 2) self-labeled 복원 6개가 양성의 75%를 차지 → circularity>0.5 발화."""
    floor_fn, _ = _handicapped_floor(drop_last=4)
    _, planted = build_planted_context()
    res = run_eureka_naming_ab(client=_FakeSelfLabeling(planted), floor_fn=floor_fn)
    assert res.verdict == "UNMEASURABLE"
    assert res.delta is None  # 게이트 실패 시 delta 미보고
    assert res.preflight is not None
    assert not res.preflight.passed
    from engine.efficacy.models import FalsifierKind

    assert FalsifierKind.CIRCULARITY in res.preflight.failures


# ── (3) A/B delta 계산 (정직한 lift) ───────────────────────────────────────────────


def _handicapped_floor(drop_last: int = 2):
    """floor가 마지막 drop_last개 planted 개념을 *누락*하도록 handicap (FCA가 못 잡았다 가정)."""
    _, planted = build_planted_context()
    kept = planted[: len(planted) - drop_last]

    def floor_fn(context):  # noqa: ARG001
        return [
            NamedAbstraction(extent=e, name="", source="fca") for e in kept
        ]

    return floor_fn, planted[len(planted) - drop_last :]


def test_delta_computes_measurable_lift_when_vllm_recovers_missing():
    """floor가 2개 누락 → vLLM이 그 2개를 정확 복원 → arm_b > arm_a (MEASURABLE_LIFT)."""
    floor_fn, missing = _handicapped_floor(drop_last=2)
    res = run_eureka_naming_ab(client=_FakeRecoversMissing(missing), floor_fn=floor_fn)
    assert res.verdict == "MEASURABLE_LIFT"
    assert res.preflight is not None and res.preflight.passed
    assert res.delta is not None and res.delta > 0
    assert res.arm_b_score is not None
    assert res.arm_b_score > res.arm_a_score
    # floor가 4/6 = 0.667 복원, enrich가 6/6 = 1.0 → delta ≈ +0.333
    assert abs(res.arm_a_score - 4 / 6) < 1e-9
    assert abs(res.arm_b_score - 1.0) < 1e-9


def test_measurable_null_when_vllm_cannot_beat_floor():
    """default planted에서 FCA floor가 이미 전부 복원 → vLLM proposal 무용 → MEASURABLE_NULL."""
    res = run_eureka_naming_ab(client=_FakeUseless())
    assert res.verdict == "MEASURABLE_NULL"
    assert res.delta is not None and res.delta <= 0
    assert res.preflight is not None and res.preflight.passed


def test_diagnostics_count_arms():
    """diagnostics가 fca/vllm 후보 수를 정직 기록 (보고 투명성)."""
    floor_fn, missing = _handicapped_floor(drop_last=2)
    res = run_eureka_naming_ab(client=_FakeRecoversMissing(missing), floor_fn=floor_fn)
    assert res.diagnostics["n_fca_abstractions"] == 4
    assert res.diagnostics["n_vllm_proposed"] == 2
