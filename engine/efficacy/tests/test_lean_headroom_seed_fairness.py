"""seed/temperature fairness of the lean_headroom_run frontier path (step 3, pierce direction).

The openai-compat/frontier branch of `_make_complete` MUST thread `seed` and pass an explicit
`temperature` into `AgentClient.complete`. If it does not (the pre-2026-07-12 bug: the inner
`complete(messages, _seed)` dropped `_seed` and never set temperature → server default greedy),
best-of-N's K "independent" draws collapse to ONE greedy proof — the 2026-06-03 confound — making
the whole repair-vs-bestN A/B unfair on exactly the reachable dgx-LAN/cloud path.

The local ollama path already threads seed; this test pins the frontier path to the same contract.
Deterministic, no network, no LLM — a spy AgentClient records the kwargs.

# KG: prom16-bhgman-pierce-direction-2026-07-12 (step 3), LEAN_HEADROOM_FAIRTEST_2026-06-05
"""

from __future__ import annotations

import engine.cli.runtime as _rt
from engine.efficacy import lean_headroom_run as lhr


class _SpyCompletion:
    text = "by rfl"
    input_tokens = 3
    output_tokens = 5


class _SpyClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def complete(self, **kwargs):  # noqa: ANN003
        self.calls.append(kwargs)
        return _SpyCompletion()


_SPY = _SpyClient()


class _FakeAgents:
    AgentClient = staticmethod(lambda: _SPY)


def _install_frontier(monkeypatch, *, temp="0.8", model="qwen2.5:32b-instruct"):
    _SPY.calls.clear()
    monkeypatch.setattr(_rt, "_agent_runtime", lambda: (_FakeAgents, "test-frontier"))
    monkeypatch.setenv("P1_TEMP", temp)
    monkeypatch.setenv("BHGMAN_LLM_MODEL", model)
    monkeypatch.delenv("LEAN_TEMP", raising=False)


def test_frontier_threads_seed_per_attempt(monkeypatch):
    """Each call passes its own seed → bestN's K draws are genuinely independent (no collapse)."""
    _install_frontier(monkeypatch)
    complete, reason = lhr._make_complete()
    assert reason == "frontier:qwen2.5:32b-instruct"
    msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]
    complete(msgs, 42)
    complete(msgs, 43)
    assert [c["seed"] for c in _SPY.calls] == [42, 43], (
        f"seed must be threaded per attempt (else bestN collapses); got {_SPY.calls}"
    )


def test_frontier_passes_nonzero_temperature(monkeypatch):
    """temperature must be an explicit non-zero value; temp=0.0 is greedy and ignores seed
    (client.complete only injects temperature when truthy), which silently re-collapses bestN."""
    _install_frontier(monkeypatch, temp="0.8")
    complete, _ = lhr._make_complete()
    complete([{"role": "system", "content": "S"}, {"role": "user", "content": "U"}], 7)
    assert _SPY.calls[0]["temperature"] == 0.8, f"temperature must be threaded; got {_SPY.calls[0]}"
    assert _SPY.calls[0]["temperature"] > 0.0, (
        "temp=0.0 is greedy → seed is ignored → bestN collapse"
    )


def test_frontier_forwards_prompt_and_model(monkeypatch):
    """The system/user split and model still route correctly through the threaded call."""
    _install_frontier(monkeypatch, model="qwen3.6-27b")
    complete, reason = lhr._make_complete()
    assert reason == "frontier:qwen3.6-27b"
    complete([{"role": "system", "content": "SYS"}, {"role": "user", "content": "USR"}], 1)
    call = _SPY.calls[0]
    assert call["system"] == "SYS" and call["user"] == "USR" and call["model"] == "qwen3.6-27b"


def test_lean_temp_overrides_p1_temp(monkeypatch):
    """LEAN_TEMP takes precedence over P1_TEMP for the headroom fair-test."""
    _install_frontier(monkeypatch, temp="0.8")
    monkeypatch.setenv("LEAN_TEMP", "0.5")
    complete, _ = lhr._make_complete()
    complete([{"role": "system", "content": "S"}, {"role": "user", "content": "U"}], 1)
    assert _SPY.calls[0]["temperature"] == 0.5


class _ProvenV:
    compiles = True
    proven = True
    graded_score = 1.0
    error_tail = ""
    sorry_tainted = False


def test_attempt_records_token_usage_from_complete(monkeypatch):
    """per-attempt input_tokens/output_tokens are recorded from complete.last_usage (prereg P4)."""
    from engine.efficacy.lean_tasks import TASKS

    _install_frontier(monkeypatch)  # spy Completion carries input_tokens=3, output_tokens=5
    complete, _ = lhr._make_complete()
    logged: list[dict] = []
    monkeypatch.setattr(lhr, "_log_record", lambda log, rec: logged.append(rec))
    monkeypatch.setattr(lhr, "evaluate", lambda *a, **k: _ProvenV())

    lhr._arm_single(TASKS[0], complete, 0)
    att = next(r for r in logged if r.get("record_type") == "attempt")
    assert att["input_tokens"] == 3 and att["output_tokens"] == 5
    assert att["model_calls"] == 1
