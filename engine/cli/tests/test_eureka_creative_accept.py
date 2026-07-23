"""CLI acceptance fails closed until external verdict ingress exists."""

from __future__ import annotations

from engine.cli.main import cli


class _WriteTrackingRunner:
    def __init__(self) -> None:
        self.writes: list[dict] = []

    def __call__(self, query, params=None):
        params = params or {}
        if "MERGE (a:AbstractClass {name: $name})" in query:
            self.writes.append(dict(params))
            return [{"name": params["name"]}]
        return []


def test_creative_accept_never_enters_pipeline_or_writes(monkeypatch, capsys):
    runner = _WriteTrackingRunner()
    monkeypatch.setattr(
        "engine.cli.runtime.make_kg_runners", lambda: (runner, runner, lambda: None)
    )

    rc = cli(["eureka", "--creative", "--apply", "--accept", "--json"])
    captured = capsys.readouterr()

    assert rc == 2
    assert runner.writes == []
    assert captured.out == ""
    assert "external human/Naesengmoon verdict ingress not implemented" in captured.err
