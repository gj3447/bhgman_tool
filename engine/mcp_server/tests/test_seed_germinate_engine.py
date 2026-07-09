"""seed_germinate MCP tool — REAL engine path (jbm-s2, gap G3 of audit wf_376c327b-8f3).

RED-first: written against the sha256 shim (symposium.py:296) — the shim hashes
{spec, payload} into a seed_id string and never imports ``engine.jaebaeman``, so every
test below starts RED. The promotion contract it pins:

  1. PLANNED wing: a valid seed spec returns planned MERGE-only cyphers RE-DERIVED from
     the real ``plant_seeds(dry_run=True)`` — parity-checked against a direct engine
     recomputation over the SAME parsed SeedRecords (MCP == engine, never hand-typed).
  2. BLOCKED wing (fail-closed): a violating spec (dup-PK / depth-range / dangling
     parent) is refused by the real ``validate_seed_invariants`` gate BEFORE any plan is
     computed — status BLOCKED, exact ViolationCode surfaced, planned_cyphers empty.
  3. Discrimination (the NOVEL axis, judge P2): valid vs violating spec pairs split
     PLANNED/BLOCKED — accuracy of the fail-closed branch, independent of any count.
  4. Honest label: registry category for seed_germinate is 'read' (a dry-run planner
     that writes nothing), no longer 'write'.
  5. Shim-compat: seed_id / spec_name / payload_keys survive the promotion.
  6. Longinus binding: the PLANNED/BLOCKED status vocabulary literals live verbatim in
     ``_seed_germinate_impl`` (AST-checked; renamed literal goes UNBOUND).

# KG: LakatosTree_BhgmanJaebaeman_20260702/jbm_s2_seed_germinate_engine
# KG: 재배맨-v2-subagent-runtime-protocol
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.jaebaeman.jaebaeman_models import ViolationCode
from engine.jaebaeman.kg_adapter import plant_seeds
from engine.mcp_server.registry import _CATALOG_SEED
from engine.mcp_server.tools.symposium import (
    SeedGerminateRequest,
    _seed_germinate_impl,
    seeds_from_payload,
)

_ROOT = str(Path(__file__).resolve().parents[3])
_SRC = "engine/mcp_server/tools/symposium.py"
_KG_ANCHOR = "finding-ooptdd-bhgman-jaebaeman-germinate-20260702"

# A valid 2-seed plan tree: self-anchored root + one child anchored/parented to it.
_VALID_PAYLOAD = {
    "seeds": [
        {"name": "sg-root", "expected_outcome": "루트 계획 심기", "depth": 0},
        {
            "name": "sg-leaf",
            "anchor": "sg-root",
            "parent": "sg-root",
            "depth": 1,
            "expected_outcome": "잎 수행",
        },
    ]
}

_DUP_PK_PAYLOAD = {"seeds": [{"name": "sg-dup"}, {"name": "sg-dup"}]}
_DEPTH_PAYLOAD = {"seeds": [{"name": "sg-deep", "depth": 99}]}
_DANGLING_PAYLOAD = {"seeds": [{"name": "sg-orphan", "parent": "sg-nowhere"}]}


def _call(payload: dict, spec_name: str = "jbm-s2") -> dict:
    return _seed_germinate_impl(
        SeedGerminateRequest(spec_name=spec_name, payload=payload, parent_cycle_id="jbm-s2-test")
    )


def test_planned_cyphers_derive_from_real_engine():
    """PLANNED wing: the response's planned_cyphers must be EXACTLY what the real
    plant_seeds(dry_run=True) plans for the same parsed SeedRecords — engine parity,
    not a hand-typed or hashed artifact. Every plan is MERGE-only (covenant)."""
    resp = _call(_VALID_PAYLOAD)

    assert resp["status"] == "PLANNED", resp
    got = resp["planned_cyphers"]
    assert got, "a valid spec must yield engine-derived planned cyphers"

    # independent engine recomputation over the same parsed records (shared parser,
    # independent plan): MCP == engine, byte-for-byte.
    seeds = seeds_from_payload("jbm-s2", _VALID_PAYLOAD)
    expected = plant_seeds(
        seeds, write_cypher=None, cycle_id=resp["engine"]["cycle_id"], dry_run=True
    ).planned_cyphers
    assert [(p["cypher"], p["params"]) for p in got] == [(c, params) for c, params in expected]

    # covenant: seeds are planted, never uprooted — and only via MERGE.
    for p in got:
        up = p["cypher"].upper()
        assert "MERGE" in up
        assert not any(tok in up for tok in ("DELETE", "DETACH", "REMOVE"))

    assert resp["engine"]["seeds_planned"] == 2
    assert resp["engine"]["dry_run"] is True
    assert resp["violations"] == []


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (_DUP_PK_PAYLOAD, ViolationCode.DUP_SEED_NAME),
        (_DEPTH_PAYLOAD, ViolationCode.E4_DEPTH_RANGE),
        (_DANGLING_PAYLOAD, ViolationCode.DANGLING_PARENT),
    ],
    ids=["dup-pk", "depth-range", "dangling-parent"],
)
def test_invariant_gate_fail_closed(payload, code):
    """BLOCKED wing: the real validate_seed_invariants gate refuses the batch BEFORE any
    plan exists — fail-closed, exact code surfaced, zero planned cyphers."""
    resp = _call(payload)

    assert resp["status"] == "BLOCKED", resp
    assert resp["planned_cyphers"] == [], "fail-closed: a blocked batch plans NOTHING"
    codes = {v["code"] for v in resp["violations"]}
    assert code.value in codes, f"expected {code.value} in {codes}"


def test_discrimination_valid_vs_violating():
    """NOVEL axis (judge P2, independent of cypher counts): valid vs violating spec
    pairs must split PLANNED/BLOCKED with full accuracy — the invariant gate
    *discriminates* at the MCP boundary, it is not a constant status."""
    cases = [
        (_VALID_PAYLOAD, "PLANNED"),
        (_DUP_PK_PAYLOAD, "BLOCKED"),
        (_DEPTH_PAYLOAD, "BLOCKED"),
        (_DANGLING_PAYLOAD, "BLOCKED"),
    ]
    hits = sum(1 for payload, want in cases if _call(payload)["status"] == want)
    assert hits == len(cases), f"discrimination {hits}/{len(cases)} — gate must split all pairs"


def test_registry_label_is_honest():
    """The catalog category must match reality: a dry-run planner that writes nothing is
    'read' (like prometheus_research), not 'write'."""
    entry = next(t for t in _CATALOG_SEED if t[0] == "seed_germinate")
    assert entry[3] == "read", f"seed_germinate advertises '{entry[3]}' but never writes"


def test_shim_compat_fields_preserved():
    """The promotion keeps the original surface: deterministic seed_id, spec echo,
    payload key listing (parents that consumed the shim keep working)."""
    resp = _call(_VALID_PAYLOAD)
    assert resp["seed_id"].startswith("seed_jbm-s2_")
    assert resp["spec_name"] == "jbm-s2"
    assert resp["payload_keys"] == ["seeds"]
    assert "next_action" in resp


def test_longinus_binding_status_literals():
    """Longinus binding proof: the load-bearing status vocabulary (PLANNED / BLOCKED)
    lives verbatim inside _seed_germinate_impl's body — AST-checked, and a renamed
    literal goes UNBOUND (the binding discriminates)."""
    pytest.importorskip("ooptdd_loop")
    from ooptdd_loop.engine.longinus import verify_binding
    from ooptdd_loop.domain.spec import Longinus

    for literal in ("PLANNED", "BLOCKED"):
        bound = verify_binding(_ROOT, Longinus(_KG_ANCHOR, _SRC, "_seed_germinate_impl", literal))
        assert bound.bound is True, f"_seed_germinate_impl should carry '{literal}': {bound.reason}"
        miss = verify_binding(
            _ROOT, Longinus(_KG_ANCHOR, _SRC, "_seed_germinate_impl", literal + "_RENAMED")
        )
        assert miss.bound is False, "a renamed status literal must NOT bind"
