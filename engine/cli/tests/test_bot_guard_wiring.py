"""`bhgman-tool bot` 가드 배선 (FIX-A) — 테스트에서만 닿는 가드는 고쳐진 게 아니다.

PROM16: "가드가 프로덕션 엔트리포인트에서 도달 가능해야 한다". cmd_bot 은 BotConfig 를
interval/max_ticks/topics/apply 만으로 짓고 AgentClient 를 계측하지 않았으며 CLI 손잡이도
없었다 — 즉 지출 kill-switch 와 저널은 *주입 전용* 이라 실배포 데몬엔 존재하지 않았다.

여기서는 진짜 argv 를 진짜 parser 에 넣고 진짜 cmd_bot 을 돌려, 그 값이 BotConfig /
spend_probe / 계측된 client 로 도달하는지 검사한다 (KG·LLM 만 fake).

# KG: prom16-harness-loop-standard, bhgman-bot-daemon-2026-06-16
"""

from __future__ import annotations

import types

from engine.cli import commands
from engine.cli.parser import build_parser


def _fake_kg(_args):
    return (lambda *_a, **_k: [], lambda *_a, **_k: None, lambda: None)


class _FakeCompletion:
    def __init__(self, i: int, o: int) -> None:
        self.input_tokens, self.output_tokens, self.text = i, o, "ok"


class _FakeAgentClient:
    """cmd_bot 이 만든 인스턴스를 붙잡아 계측 여부를 확인한다."""

    made: list["_FakeAgentClient"] = []

    def __init__(self, *_a, **_k) -> None:
        _FakeAgentClient.made.append(self)

    def complete(self, **_kw):
        return _FakeCompletion(60, 40)


def _install(monkeypatch, *, llm: bool = False):
    captured: dict = {}

    def fake_run_bot(*, build_ctx, run_tick, cfg, pick_work=None, spend_probe=None, **_kw):
        from engine.legion.daemon import BotRun  # noqa: PLC0415

        captured["cfg"] = cfg
        captured["spend_probe"] = spend_probe
        r = BotRun()
        r.stop_reason = "max_ticks"
        return r

    monkeypatch.setattr(commands, "_resolve_kg_runners", _fake_kg)
    monkeypatch.setattr("engine.legion.daemon.run_bot", fake_run_bot)
    if llm:
        _FakeAgentClient.made = []
        ns = types.SimpleNamespace(AgentClient=_FakeAgentClient)
        monkeypatch.setattr(commands, "_agent_runtime", lambda: (ns, "fake"))
        monkeypatch.setattr(commands, "_grounding_source", lambda _a: (None, lambda: None))
    return captured


def _run_cli(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


# ------------------------------------------------------------------- 손잡이가 존재하는가


def test_bot_subcommand_exposes_the_guard_flags():
    """플래그 부재 = 가드 도달 불가. parser 가 실제로 받아야 한다."""
    args = build_parser().parse_args(
        [
            "bot",
            "--once",
            "--max-llm-calls",
            "7",
            "--max-total-tokens",
            "500",
            "--max-calls-per-minute",
            "3",
            "--max-tokens-per-minute",
            "1000",
            "--journal",
            "/tmp/j.jsonl",
            "--run-id",
            "r9",
        ]
    )
    assert args.max_llm_calls == 7
    assert args.max_total_tokens == 500
    assert args.max_calls_per_minute == 3.0
    assert args.max_tokens_per_minute == 1000.0
    assert args.journal == "/tmp/j.jsonl"
    assert args.run_id == "r9"


# ------------------------------------------------------- 값이 BotConfig / spend_probe 로 도달


def test_journal_flags_reach_bot_config(monkeypatch, tmp_path):
    cap = _install(monkeypatch)
    jp = tmp_path / "bot.jsonl"
    assert _run_cli(["bot", "--once", "--journal", str(jp), "--run-id", "r1"]) == 0
    assert cap["cfg"].journal_path == str(jp)
    assert cap["cfg"].run_id == "r1"


def test_spend_flags_reach_run_bot_as_a_live_probe(monkeypatch):
    cap = _install(monkeypatch)
    assert _run_cli(["bot", "--once", "--max-llm-calls", "1"]) == 0
    probe = cap["spend_probe"]
    assert probe is not None and probe() is None  # 아직 미사용 → 통과


def test_no_flags_means_no_probe_and_no_journal(monkeypatch):
    """반대 방향: 손잡이를 안 주면 현행 동작 — 상한/저널 없음."""
    cap = _install(monkeypatch)
    assert _run_cli(["bot", "--once"]) == 0
    assert cap["spend_probe"] is None
    assert cap["cfg"].journal_path is None


# --------------------------------------------- 계측이 실제 LLM client 에 붙는가 (핵심 배선)


def test_llm_client_is_instrumented_and_probe_fires_on_real_usage(monkeypatch):
    """--llm + 상한 → AgentClient 가 계측되고, 그 client 사용이 probe 를 발동시킨다.

    이게 '주입 전용이 아니다' 의 증명: cmd_bot 이 만든 *실제* client 를 호출하면
    kill-switch 가 켜진다.
    """
    cap = _install(monkeypatch, llm=True)
    assert _run_cli(["bot", "--once", "--llm", "--max-total-tokens", "150"]) == 0

    client = _FakeAgentClient.made[-1]
    probe = cap["spend_probe"]
    assert probe() is None
    client.complete(system="s", user="u", model="m")  # 100 토큰
    assert probe() is None
    client.complete(system="s", user="u", model="m")  # 누적 200 > 150
    assert "max_total_tokens" in (probe() or "")


def test_llm_client_not_instrumented_when_no_limits(monkeypatch):
    """반대 방향: 상한 없으면 계측도 없다 (오버헤드 0, 현행 동작)."""
    _install(monkeypatch, llm=True)
    assert _run_cli(["bot", "--once", "--llm"]) == 0
    client = _FakeAgentClient.made[-1]
    assert not getattr(client, "_bhgman_spend_metered", False)


def test_call_ceiling_reaches_probe_through_cli(monkeypatch):
    cap = _install(monkeypatch, llm=True)
    assert _run_cli(["bot", "--once", "--llm", "--max-llm-calls", "2"]) == 0
    client = _FakeAgentClient.made[-1]
    probe = cap["spend_probe"]
    client.complete(system="s", user="u", model="m")
    assert probe() is None
    client.complete(system="s", user="u", model="m")
    assert "max_llm_calls" in (probe() or "")
