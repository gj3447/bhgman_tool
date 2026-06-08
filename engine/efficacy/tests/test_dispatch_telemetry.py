"""dispatch_telemetry 순수부 — jsonl Task/Agent 성공률 스캔."""

from __future__ import annotations

import json

from engine.efficacy.dispatch_telemetry import DispatchStats, scan_dispatches


def _use(tid, name="Task"):
    return json.dumps(
        {
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": tid, "name": name, "input": {}}],
            }
        }
    )


def _result(tid, err=False):
    return json.dumps(
        {
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": tid, "is_error": err}],
            }
        }
    )


def test_success_and_error_matched():
    lines = [_use("t1"), _result("t1"), _use("t2"), _result("t2", err=True)]
    s = scan_dispatches(lines)
    assert s.dispatched == 2 and s.succeeded == 1 and s.errored == 1
    assert s.success_rate == 0.5


def test_pending_when_no_result():
    s = scan_dispatches([_use("t1")])
    assert s.dispatched == 1 and s.pending == 1
    assert s.success_rate == 0.0  # done=0


def test_ignores_non_dispatch_tools():
    lines = [
        json.dumps(
            {
                "message": {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "r1", "name": "Read", "input": {}}],
                }
            }
        ),
        _result("r1"),
    ]
    s = scan_dispatches(lines)
    assert s.dispatched == 0


def test_agent_tool_also_counted():
    s = scan_dispatches([_use("a1", name="Agent"), _result("a1")])
    assert s.dispatched == 1 and s.succeeded == 1


def test_result_for_unknown_id_ignored():
    s = scan_dispatches([_result("ghost")])
    assert s.dispatched == 0 and s.succeeded == 0


def test_corrupt_lines_skipped():
    s = scan_dispatches(["{broken", "not json", _use("t1"), _result("t1")])
    assert s.dispatched == 1 and s.succeeded == 1


def test_success_rate_excludes_pending():
    # 성공률은 완료분(성공+실패)만 분모; pending 제외
    s = DispatchStats(dispatched=10, succeeded=6, errored=2, pending=2)
    assert s.success_rate == 0.75
