"""evolve_loop 실 어댑터 테스트 — 실 oracle 파서 / LLM 생성기(주입 transport) / 학습셋 환류."""

from __future__ import annotations

import random

from engine.agents.client import AgentClient
from engine.legion.evolve_adapters import (
    LlmGenerator,
    default_llm_render,
    export_training_set,
    lean_cleanliness,
    lean_oracle,
    pytest_oracle,
    pytest_pass_ratio,
    write_training_jsonl,
)
from engine.legion.evolve_loop import Candidate, ScoredCandidate
from engine.naesengmoon.oracle_lens import OracleVerdict


def _v(passed: bool, detail: str) -> OracleVerdict:
    return OracleVerdict(lens="x", kind="test", passed=passed, detail=detail)


def test_pytest_pass_ratio_parses_counts():
    assert pytest_pass_ratio(_v(False, "3 passed, 1 failed in 0.1s")) == 0.75
    assert pytest_pass_ratio(_v(True, "5 passed in 0.2s")) == 1.0
    # 카운트 없으면 boolean fallback
    assert pytest_pass_ratio(_v(True, "PASS")) == 1.0
    assert pytest_pass_ratio(_v(False, "boom")) == 0.0


def test_lean_cleanliness():
    assert lean_cleanliness(_v(True, "PASS")) == 1.0  # clean
    assert lean_cleanliness(_v(False, "error: foo\nerror: bar")) == 1.0 / 3.0  # 2 errors
    assert lean_cleanliness(_v(False, "declaration uses 'sorry'")) == 0.5  # 1 sorry


def test_pytest_oracle_builds_command_and_scores():
    captured = {}

    def fake_runner(cmd):
        captured["cmd"] = tuple(cmd)
        return 0, "2 passed in 0.0s"

    oracle = pytest_oracle(lambda task, c: f"/tmp/{c.payload}.py", runner=fake_runner)
    scored = oracle.score("t", Candidate("mycand"))
    assert captured["cmd"] == ("pytest", "-q", "/tmp/mycand.py")
    assert scored.passed and scored.score == 1.0


def test_lean_oracle_scores_sorry():
    oracle = lean_oracle(
        lambda task, c: "Mod.Sub", runner=lambda cmd: (1, "declaration uses 'sorry'")
    )
    scored = oracle.score("t", Candidate("p"))
    assert not scored.passed
    assert scored.score == 0.5  # 1 sorry → 1/(1+1)


def test_llm_generator_uses_injected_transport():
    # 백엔드 불요: openai-compat transport 주입 → propose가 completion text를 후보로.
    import os

    os.environ["BHGMAN_LLM_MODEL"] = "fake-model"

    def fake_post(url, payload, headers, timeout):
        return {
            "model": "fake-model",
            "choices": [{"message": {"content": "candidate-XYZ"}, "finish_reason": "stop"}],
            "usage": {"completion_tokens": 7},
        }

    client = AgentClient(http_post=fake_post)
    gen = LlmGenerator(client=client)
    cand = gen.propose("task", (), random.Random(0))
    assert cand.payload == "candidate-XYZ"
    assert gen.output_tokens == 7  # 토큰 회계


def test_llm_render_injects_best_k():
    best = (ScoredCandidate(Candidate("sol-A"), 9.0, True),)
    rendered = default_llm_render("maximize", best)
    assert "sol-A" in rendered and "score=9.000" in rendered
    assert "No prior" in default_llm_render("maximize", ())  # cold start


def test_export_training_set_only_verified(tmp_path):
    pairs = [
        ScoredCandidate(Candidate("good"), 9.0, True),
        ScoredCandidate(Candidate("bad"), 1.0, False),  # unverified → 제외
        ScoredCandidate(Candidate("weak"), 3.0, True),
    ]
    records = export_training_set(pairs, task="maximize", min_score=5.0)
    assert len(records) == 1  # good만 (verified ∧ score≥5)
    assert records[0]["solution"] == "good"
    n = write_training_jsonl(records, tmp_path / "train.jsonl")
    assert n == 1
    assert (tmp_path / "train.jsonl").read_text().strip().startswith("{")
