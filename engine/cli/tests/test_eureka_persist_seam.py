"""cmd_eureka must wire the stage_6 KG-persist seam (eureka → hades), gated by covenant.

The eureka pipeline already implements stage_6_persist + the PROPOSED→ACCEPTED transition
(verdictStatus='ACCEPTED'), and hades_runner fetches exactly `a.verdictStatus = 'ACCEPTED'`.
But cmd_eureka unpacked `run_cypher, _write, close` and built PipelineConfig WITHOUT
persist_cypher, so the persist stage (gated on `config.persist_cypher is not None`) never
fired — verdictStatus rows were never written and hades fetched empty. The eureka→hades
producer→consumer loop was permanently open from the CLI (the most-used surface).

Covenant (eureka = PROPOSE only, 실현은 하데스):
  - no flag  → read-only, no persist (dry-run, like occam/hades).
  - --apply  → persist candidates as verdictStatus='VERDICT_PENDING' (visible to hades but
               NOT realizable — covenant preserved; hades only realizes ACCEPTED).
  - --accept → always fail-closed until external human/Naesengmoon verdict ingress exists.

These tests pin the wiring at the PipelineConfig seam (independent of whether FCA induces
any concept on the test KG): cmd_eureka may inject pending persistence but never self-accept.

# KG: finding-eureka-stage6-persist-seam-dead-from-cli-2026-06-26
"""

from __future__ import annotations

from engine.cli.main import build_parser, cli


class _FakeRunner:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def __call__(self, cypher, params=None):
        self.calls.append((cypher, params))
        return self.rows


def _patch(monkeypatch):
    """Patch runners + capture the PipelineConfig cmd_eureka hands to run_from_kg."""
    read, write = _FakeRunner(), _FakeRunner()
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: (read, write, lambda: None))
    captured = {}

    class _PR:
        stages = []

    def _fake_run_from_kg(run_cypher, config, *a, **k):
        captured["config"] = config
        return _PR()

    monkeypatch.setattr("engine.eureka.pipeline.run_from_kg", _fake_run_from_kg)
    return read, write, captured


def test_eureka_parser_defaults_dry_run():
    args = build_parser().parse_args(["eureka"])
    assert args.apply is False  # covenant: read-only default
    assert args.accept is False


def test_eureka_default_does_not_wire_persist(monkeypatch):
    _read, write, captured = _patch(monkeypatch)
    rc = cli(["eureka"])
    assert rc == 1  # fake run has no earned proposal: honest NO_CANDIDATE
    # covenant: no persist runner injected → stage_6 stays off, nothing written
    assert captured["config"].persist_cypher is None
    assert write.calls == []


def test_eureka_apply_wires_persist_as_pending(monkeypatch):
    _read, write, captured = _patch(monkeypatch)
    rc = cli(["eureka", "--apply"])
    assert rc == 3  # requested persist has no receipt/stage in this seam fake
    # --apply injects the write runner so stage_6_persist fires...
    assert captured["config"].persist_cypher is write
    # ...but NOT accepted → verdictStatus='VERDICT_PENDING' (hades won't realize it yet)
    assert captured["config"].persist_accept is False


def test_eureka_accept_without_creative_receipt_is_refused(monkeypatch):
    _read, write, _captured = _patch(monkeypatch)
    rc = cli(["eureka", "--apply", "--accept"])
    assert rc == 2
    assert write.calls == []
