"""eureka --code: the anti_unification (Plotkin LGG) code-template path must be reachable.

anti_unify.propose_template (implemented + unit-tested) lifts a shared template from N
near-identical code snippets, but it had NO CLI/MCP entry — the module self-documented
"awaiting eureka --code". The KG-induction path (cmd_eureka) required neo4j and never
reached anti_unify. This wires the dep-free, neo4j-free code-template branch.

# KG: finding-eureka-anti-unify-no-cli-entry-2026-06-26
"""

from __future__ import annotations

from engine.cli.main import cli

_SNIPPETS = [
    "def get_x(self): return self.x",
    "def get_y(self): return self.y",
    "def get_z(self): return self.z",
]


def test_eureka_code_proposes_template_from_snippets(capsys):
    rc = cli(["eureka", "--code", *sum((["--snippet", s] for s in _SNIPPETS), [])])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PROPOSED" in out
    assert "·0" in out  # the LGG hole marker for the differing token


def test_eureka_code_rule_of_three_guard(capsys):
    # fewer than min_instances → INSUFFICIENT (premature-abstraction guard), still rc==0
    rc = cli(["eureka", "--code", "--snippet", _SNIPPETS[0], "--snippet", _SNIPPETS[1]])
    out = capsys.readouterr().out
    assert rc == 0
    assert "INSUFFICIENT" in out


def test_eureka_code_from_file(tmp_path, capsys):
    f = tmp_path / "snips.txt"
    f.write_text("\n\n".join(_SNIPPETS), encoding="utf-8")  # blank-line separated
    rc = cli(["eureka", "--code", "--code-file", str(f)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PROPOSED" in out
