"""Gate KG→Rego input materializer (Phase B, the one real deterministic gap).

The gate's `_call_kg_with_retry` was a count-compare STUB (it never queried Neo4j; it
just checked context.expected_count == actual_count). That made the OPA-off path
"grade its own homework" — determinism theater. This module closes it:

  materialize_gate_input(gate, cycle_id, run_cypher) -> input doc the Rego reads
  evaluate_gate(gate, input doc)                     -> (allow, reason)  [pure mirror of the .rego]
  decide_gate(gate, cycle_id, run_cypher)            -> (allow, reason)  [materialize ∘ evaluate]

Pure functions over an injected `run_cypher` (CypherRunner) — fully testable with a fake
runner, no FastAPI / live Neo4j. The Cypher projects the structured booleans/counts each
gate's Rego already expects (sa_to_sp / sp_to_st / st_to_scw / fulfillment_gate); the
evaluator mirrors the Rego decision rule so the gate is a real engine even with OPA off.

This is the VERIFICATION spine only (engine the verbs). It never produces the SA anchor,
SP decomposition, ST contract content, or SCW code — those stay SKILL.md orchestration
(apt-tpa-engine-substrate-scope-2026-06-14: Rice-bound, do not fake as deterministic).

# KG: adr-apt-tpa-engine-substrate-scope-2026-06-14, plan-apt-tpa-engine-substrate-2026-06-14,
#     lesson-apt-tpa-engine-feasibility-2026-06-14
"""

from __future__ import annotations

from collections.abc import Callable

CypherRunner = Callable[[str, dict], "list[dict]"]

# C(S) 5-predicate fields a leaf Span must carry non-null to be ATOMIC (apt-sp).
_C_S_FIELDS = ("objective", "definition", "keyAssertion", "verification", "c_s_predicate")

# ── per-gate Cypher (projection only — reads structured facts, never writes) ──────────

_CYPHER_SA_TO_SP = (
    "MATCH (sa:SemanticAnchor {cycle_id: $cycle_id}) "
    "OPTIONAL MATCH (sa)-[:HAS_ROOT]->(root:Span) "
    "OPTIONAL MATCH (dup:SemanticAnchor {cycle_id: $cycle_id}) WHERE dup <> sa "
    "RETURN sa.name AS name, sa.status AS status, sa.contextBudget AS context_budget, "
    "sa.workKind AS work_kind, sa.phaseActivationMode AS phase_activation_mode, "
    "sa.gitCommitted AS git_committed, root.name AS root_span_name, "
    "root.status AS root_span_status, count(DISTINCT dup) AS duplicate_anchor_count "
    "LIMIT 1"
)

_CYPHER_SP_LEAVES = (
    "MATCH (sa:SemanticAnchor {cycle_id: $cycle_id})-[:HAS_ROOT]->(:Span) "
    "MATCH (leaf:Span {cycle_id: $cycle_id}) "
    "WHERE NOT (leaf)-[:DECOMPOSES_TO|HAS_CHILD]->(:Span) "  # leaves = no children
    "RETURN leaf.name AS name, coalesce(leaf.isAtomic, false) AS is_atomic, "
    "leaf.objective AS objective, leaf.definition AS definition, "
    "leaf.keyAssertion AS keyAssertion, leaf.verification AS verification, "
    "leaf.c_s_predicate AS c_s_predicate"
)

# lens verdict (taliban/naesengmoon constitutional 9-lens) for sp_to_st lensset_complete.
_CYPHER_SP_LENS = (
    "MATCH (sa:SemanticAnchor {cycle_id: $cycle_id}) "
    "OPTIONAL MATCH (sa)-[:HAS_LENS_VERDICT|VALIDATED_BY]->(v) "
    "RETURN v.verdict AS taliban_verdict, coalesce(v.lensCount, 0) AS taliban_lens_count LIMIT 1"
)

_CYPHER_ST = (
    "MATCH (a:AtomicSpan {cycle_id: $cycle_id}) "
    "OPTIONAL MATCH (a)-[:HAS_TWIN]->(tw:Twin) "
    "OPTIONAL MATCH (a)-[:HAS_CONTRACT]->(c:Contract) "
    "OPTIONAL MATCH (a)-[:HAS_TASK]->(t:Task) "
    "RETURN a.name AS atom, (tw IS NOT NULL) AS has_twin, "
    "(c IS NOT NULL) AS has_contract, (t IS NOT NULL) AS has_task, "
    "c.status AS contract_status, coalesce(c.tauCheckPass, false) AS tau_check_pass, "
    "coalesce(c.fieldCount, 0) AS field_count, coalesce(t.impactTests, []) AS impact_tests, "
    "coalesce(a.decisionAreasCompleted, []) AS decision_areas_completed"
)

_CYPHER_FULFILLMENT = (
    "MATCH (scw:SourceCodeNode {cycle_id: $cycle_id}) "
    "RETURN coalesce(scw.testsPassed, 0) AS passed, coalesce(scw.testsTotal, 0) AS total_tests, "
    "coalesce(scw.testsFailed, 0) AS failed, coalesce(scw.testsSkipped, 0) AS skipped, "
    "scw.outputType AS actual_output_type, scw.contractOutputType AS contract_output_type, "
    "coalesce(scw.kgRefsInSource, '') AS kg_refs_in_source, "
    "coalesce(scw.lines, 0) AS lines, coalesce(scw.testAssertionCount, 0) AS test_assertion_count, "
    "coalesce(scw.postconditionVerified, false) AS postcondition_verified, "
    "coalesce(scw.preconditionCheckPresent, false) AS precondition_check_present, "
    "coalesce(scw.postconditionCheckPresent, false) AS postcondition_check_present, "
    "scw.latencyP99Ms AS latency_p99_ms, scw.nfrLatencyP99Ms AS nfr_latency_p99_ms, "
    "scw.nfrMemoryMb AS nfr_memory_mb "
    "LIMIT 1"
)

# default thresholds (mirror MethodologyConfig; overridable by config rows on the input).
_DEFAULT_CONTRACT_FIELDS = 7
_DEFAULT_ST_TIER1 = 5
_DEFAULT_COMPLEXITY = 500


def _one(rows: list[dict]) -> dict:
    return rows[0] if rows else {}


def materialize_gate_input(gate_name: str, cycle_id: str, run_cypher: CypherRunner) -> dict:
    """Project the KG into the OPA `input` document a gate's Rego reads. Pure (run_cypher injected)."""
    g = _normalize_gate(gate_name)
    if g == "sa_to_sp":
        row = _one(run_cypher(_CYPHER_SA_TO_SP, {"cycle_id": cycle_id}))
        return {
            "gate_name": gate_name,
            "cycle_id": cycle_id,
            "sa": {
                "name": row.get("name"),
                "status": row.get("status"),
                "root_span_name": row.get("root_span_name"),
                "root_span_status": row.get("root_span_status"),
                "context_budget_total": row.get("context_budget"),
                "duplicate_anchor_count": int(row.get("duplicate_anchor_count") or 0),
                "work_kind": row.get("work_kind"),
                "phase_activation_mode": row.get("phase_activation_mode"),
            },
            "apt_progress": {
                "git_committed": bool(row.get("git_committed")),
                "l1_span_count": 1 if row.get("root_span_name") else 0,
            },
        }
    if g == "sp_to_st":
        leaves = run_cypher(_CYPHER_SP_LEAVES, {"cycle_id": cycle_id})
        lens = _one(run_cypher(_CYPHER_SP_LENS, {"cycle_id": cycle_id}))
        return {
            "gate_name": gate_name,
            "cycle_id": cycle_id,
            "sp": {
                "leaves": [{k: leaf.get(k) for k in ("is_atomic", *_C_S_FIELDS)} for leaf in leaves]
            },
            "taliban_verdict": lens.get("taliban_verdict"),
            "taliban_lens_count": int(lens.get("taliban_lens_count") or 0),
        }
    if g == "st_to_scw":
        rows = run_cypher(_CYPHER_ST, {"cycle_id": cycle_id})
        return {
            "gate_name": gate_name,
            "cycle_id": cycle_id,
            "st": {
                "atoms": [{"has_twin": bool(r.get("has_twin"))} for r in rows],
                "twins": [
                    {
                        "has_contract": bool(r.get("has_contract")),
                        "has_task": bool(r.get("has_task")),
                    }
                    for r in rows
                ],
                "contracts": [
                    {
                        "status": r.get("contract_status"),
                        "tau_check_pass": bool(r.get("tau_check_pass")),
                        "field_count": int(r.get("field_count") or 0),
                    }
                    for r in rows
                    if r.get("has_contract")
                ],
                "tasks": [
                    {"impact_tests": list(r.get("impact_tests") or [])}
                    for r in rows
                    if r.get("has_task")
                ],
                "decision_areas_completed": max(
                    (list(r.get("decision_areas_completed") or []) for r in rows),
                    key=len,
                    default=[],
                ),
            },
            "config": {
                "contract_default_fields": _DEFAULT_CONTRACT_FIELDS,
                "st_tier1_count": _DEFAULT_ST_TIER1,
            },
        }
    if g == "fulfillment":
        row = _one(run_cypher(_CYPHER_FULFILLMENT, {"cycle_id": cycle_id}))
        return {
            "gate_name": gate_name,
            "cycle_id": cycle_id,
            "test_run": {
                "passed": int(row.get("passed") or 0),
                "total_tests": int(row.get("total_tests") or 0),
                "failed": int(row.get("failed") or 0),
                "skipped": int(row.get("skipped") or 0),
            },
            "actual": {
                "output_type": row.get("actual_output_type"),
                "kg_refs_in_source": row.get("kg_refs_in_source") or "",
                "lines": int(row.get("lines") or 0),
                "test_assertion_count": int(row.get("test_assertion_count") or 0),
                "postcondition_verified": bool(row.get("postcondition_verified")),
                "precondition_check_present": bool(row.get("precondition_check_present")),
                "postcondition_check_present": bool(row.get("postcondition_check_present")),
                "latency_p99_ms": row.get("latency_p99_ms"),
            },
            "contract": {
                "output_type": row.get("contract_output_type"),
                "nfr_latency_p99_ms": row.get("nfr_latency_p99_ms"),
                "nfr_memory_mb": row.get("nfr_memory_mb"),
            },
            "config": {"complexity_threshold": _DEFAULT_COMPLEXITY},
        }
    raise ValueError(
        f"unknown gate {gate_name!r} (expected sa_to_sp|sp_to_st|st_to_scw|fulfillment)"
    )


# ── evaluators — pure Python mirror of the .rego decision rule ───────────────────────


_A15_WORK_KINDS = frozenset({"NEW", "EXTEND", "MAINTENANCE"})
_A15_MODES = frozenset({"FULL", "SHORT_CIRCUIT", "SKIP_TO_ST_DRIFT"})


def _evaluate_sa_to_sp(inp: dict) -> tuple[bool, str]:
    sa = inp.get("sa") or {}
    prog = inp.get("apt_progress") or {}
    root_ok = bool(sa.get("root_span_name")) and sa.get("root_span_status") == "open"
    checks = [
        (not sa.get("name"), "no SemanticAnchor"),
        (sa.get("status") != "active", f"sa.status={sa.get('status')} != active"),
        (not root_ok, "no open Root Span (HAS_ROOT)"),
        (not sa.get("context_budget_total"), "context budget not allocated"),
        (int(sa.get("duplicate_anchor_count") or 0) != 0, "duplicate anchors"),
        (int(prog.get("l1_span_count") or 0) <= 0, "no L1 span (Progressive Disclosure)"),
        # v27 A15: work_kind + phase_activation_mode must be classified (sa_to_sp.rego)
        (
            sa.get("work_kind") not in _A15_WORK_KINDS,
            f"A15 work_kind {sa.get('work_kind')} invalid",
        ),
        (sa.get("phase_activation_mode") not in _A15_MODES, "A15 phase_activation_mode not set"),
        (not prog.get("git_committed"), "not git-committed"),
    ]
    fails = [msg for cond, msg in checks if cond]
    return (not fails, "SA→SP gate: " + ("PASS" if not fails else "; ".join(fails)))


def _evaluate_sp_to_st(inp: dict) -> tuple[bool, str]:
    leaves = ((inp.get("sp") or {}).get("leaves")) or []
    if not leaves:
        return False, "SP→ST gate: no leaf spans (crystallization frontier empty)"
    non_atomic = [i for i, lf in enumerate(leaves) if not lf.get("is_atomic")]
    if non_atomic:
        return False, f"SP→ST gate: {len(non_atomic)} non-atomic leaf (frontier not reached)"
    incomplete = [
        i for i, lf in enumerate(leaves) if any(lf.get(f) in (None, "") for f in _C_S_FIELDS)
    ]
    if incomplete:
        return False, f"SP→ST gate: {len(incomplete)} leaf missing C(S) 5-predicate field(s)"
    # lensset_complete (sp_to_st.rego): constitutional 9-lens unanimous, no 3-lens shortcut.
    if inp.get("taliban_verdict") != "APPROVED" or int(inp.get("taliban_lens_count") or 0) != 9:
        return False, (
            f"SP→ST gate: LensSet incomplete (taliban={inp.get('taliban_verdict')}, "
            f"lens={inp.get('taliban_lens_count')}/9 — 3-lens shortcut?)"
        )
    return True, f"SP→ST gate: PASS ({len(leaves)} atomic leaves, C(S) + 9-lens complete)"


def _contract_fails(contracts: list, field_min: int) -> list[str]:
    out: list[str] = []
    for c in contracts:
        if c.get("status") != "Active":
            out.append(f"contract.status={c.get('status')} != Active")
        if not c.get("tau_check_pass"):
            out.append("contract tau_check not pass")
        if int(c.get("field_count") or 0) < field_min:
            out.append(f"contract field_count {c.get('field_count')} < {field_min}")
    return out


def _evaluate_st_to_scw(inp: dict) -> tuple[bool, str]:
    st = inp.get("st") or {}
    cfg = inp.get("config") or {}
    field_min = int(cfg.get("contract_default_fields") or _DEFAULT_CONTRACT_FIELDS)
    tier1 = int(cfg.get("st_tier1_count") or _DEFAULT_ST_TIER1)
    atoms = st.get("atoms") or []
    if not atoms:
        return False, "ST→SCW gate: no atoms"
    checks = [
        (not all(a.get("has_twin") for a in atoms), "atom without Twin"),
        (
            not all(t.get("has_contract") and t.get("has_task") for t in (st.get("twins") or [])),
            "twin without Contract/Task",
        ),
        (
            any(len(t.get("impact_tests") or []) == 0 for t in (st.get("tasks") or [])),
            "task without impact_tests (TDAD)",
        ),
        (
            len(st.get("decision_areas_completed") or []) < tier1,
            f"decision_areas {len(st.get('decision_areas_completed') or [])} < tier1 {tier1}",
        ),
    ]
    fails = [msg for cond, msg in checks if cond]
    fails += _contract_fails(st.get("contracts") or [], field_min)
    return (not fails, "ST→SCW gate: " + ("PASS" if not fails else "; ".join(fails)))


def _nfr_ok(con: dict, act: dict) -> bool:
    """check_7 mirror: pass if no NFR set, else latency_p99 <= threshold (memory-only NFR can't pass)."""
    nfr_lat = con.get("nfr_latency_p99_ms")
    nfr_mem = con.get("nfr_memory_mb")
    if nfr_lat is None and nfr_mem is None:
        return True
    if nfr_lat is None:  # only memory NFR set → rego check_7 has no passing branch
        return False
    lat = act.get("latency_p99_ms")
    actual_lat = float(lat) if lat is not None else float("inf")
    return actual_lat <= float(nfr_lat)


def _evaluate_fulfillment(inp: dict) -> tuple[bool, str]:
    tr = inp.get("test_run") or {}
    act = inp.get("actual") or {}
    con = inp.get("contract") or {}
    cfg = inp.get("config") or {}
    total = int(tr.get("total_tests") or 0)
    refs = act.get("kg_refs_in_source") or ""
    complexity_max = int(cfg.get("complexity_threshold") or _DEFAULT_COMPLEXITY)
    green = total > 0 and int(tr.get("passed") or 0) == total and int(tr.get("failed") or 0) == 0
    checks = [
        (total <= 0, "no tests"),
        (total > 0 and not green, "tests not all green"),
        (int(tr.get("skipped") or 0) != 0, "tests skipped (check_1 skipped!=0)"),
        (
            bool(con.get("output_type")) and act.get("output_type") != con.get("output_type"),
            f"output_type {act.get('output_type')} != contract {con.get('output_type')}",
        ),
        (not act.get("precondition_check_present"), "precondition check absent (check_3)"),
        (not act.get("postcondition_check_present"), "postcondition check absent (check_3)"),
        ("TASK_" not in refs or "CONTRACT_" not in refs, "source missing TASK_/CONTRACT_ KG refs"),
        (int(act.get("lines") or 0) > complexity_max, f"lines {act.get('lines')} > threshold"),
        (int(act.get("test_assertion_count") or 0) <= 0, "no test assertions (check_6)"),
        (not act.get("postcondition_verified"), "postcondition not verified (check_6)"),
        (not _nfr_ok(con, act), "NFR latency_p99 over threshold (check_7)"),
    ]
    fails = [msg for cond, msg in checks if cond]
    return (not fails, "Fulfillment gate: " + ("PASS" if not fails else "; ".join(fails)))


_EVALUATORS = {
    "sa_to_sp": _evaluate_sa_to_sp,
    "sp_to_st": _evaluate_sp_to_st,
    "st_to_scw": _evaluate_st_to_scw,
    "fulfillment": _evaluate_fulfillment,
}

_GATE_ALIASES = {
    "sa_to_sp": "sa_to_sp",
    "sp_to_st": "sp_to_st",
    "st_to_scw": "st_to_scw",
    "fulfillment": "fulfillment",
    "fulfillment_gate": "fulfillment",
}


def _normalize_gate(gate_name: str) -> str:
    key = _GATE_ALIASES.get(gate_name)
    if key is None:
        raise ValueError(f"unknown gate {gate_name!r}")
    return key


def evaluate_gate(gate_name: str, input_doc: dict) -> tuple[bool, str]:
    """Pure Python mirror of the gate's Rego decision rule → (allow, reason)."""
    return _EVALUATORS[_normalize_gate(gate_name)](input_doc)


def decide_gate(gate_name: str, cycle_id: str, run_cypher: CypherRunner) -> tuple[bool, str]:
    """materialize ∘ evaluate — the real KG-backed gate verdict (no OPA sidecar needed)."""
    return evaluate_gate(gate_name, materialize_gate_input(gate_name, cycle_id, run_cypher))


__all__ = [
    "CypherRunner",
    "decide_gate",
    "evaluate_gate",
    "materialize_gate_input",
]
