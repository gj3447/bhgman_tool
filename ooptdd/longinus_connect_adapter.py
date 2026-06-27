"""ooptdd-loop in_process target — binds the longinus 연결(connect) CREATE-binding half to
the REAL engine (``forward_binding_materialize.materialize`` + ``symbol_binding.bind_file``).

This is the CREATE half of 연결 — DISTINCT from the existing detect-only slice
(``ooptdd/adapter.py``, which runs ``LonginusAudit.run_full``). The production commander
path never calls materialize/bind_file, so the bindings this earns are novel content the
detect slice never observed.

Honest-count contract (verified before writing, STEP-0 baseline):
    ``materialize`` over a fresh ``MockKgClient`` routes EVERY '# KG:' ref to ``orphan_refs``
    (the cited node does not exist) => ``bound==0`` => a >=1/==N gate is genuinely RED. To
    EARN ``bound>=1`` we write a tmp code-root with a real '# KG: <NODE>' comment AND make
    that exact node pre-exist via ``kg.other_nodes.add('<NODE>')`` (so ``has_node`` is True);
    a SECOND, un-seeded ref stays orphan, so one scan yields ``bound==1`` AND orphan==1
    (orphan_discrimination — drop the seed and the bound ref flips to orphan). ``symbol_bound``
    is earned only from real public top-level symbols lacking a '# KG:' header. Every count is
    RE-DERIVED from the real ``MaterializeResult`` / ``BindResult`` — never hand-typed.

Longinus binding (AST-checked by ``ooptdd_loop.longinus.verify_binding``):
    Each must_emit literal lives VERBATIM inside the ADAPTER symbol that ships it
    (``emit_materialize_phase`` / ``emit_symbol_bind_phase`` / ``run_longinus_connect_pipeline``)
    — NEVER inside ``engine/longinus_drift_audit/`` (the engine functions return pure
    ``MaterializeResult`` / ``BindResult`` and must stay literal-free). Rename => UNBOUND/RED.

# KG: finding-ooptdd-bhgman-longinus-connect-adapter-20260625
# KG: ATOM_Skill_longinus
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from engine.longinus_drift_audit import forward_binding_materialize as _fbm
from engine.longinus_drift_audit import symbol_binding as _sb
from engine.longinus_drift_audit.kg_client import MockKgClient

_KG_ANCHOR = "finding-ooptdd-bhgman-longinus-connect-adapter-20260625"

_BOUND_NODE = "NODE_BOUND_A"      # seeded into the KG => materializes to a bound ReferenceSite
_ORPHAN_NODE = "NODE_ORPHAN_B"    # NOT seeded => stays an orphan '# KG:' ref (discrimination)
_SYMBOL_CONCEPT = "ATOM_Skill_longinus"


def _ev(cid: str, event: str, **attrs) -> dict:
    """Shape one trace event the way the memory backend keys + counts it (cid + event)."""
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "bhgman.longinus.connect",
        "event": event,
        **attrs,
    }


def _materialize_code_root(*, seed_bound: bool) -> tuple[MockKgClient, Path]:
    """Build a tmp code-root with two distinct '# KG:' refs (one to-be-bound, one orphan) and a
    ``MockKgClient`` pre-seeded with the bound node iff ``seed_bound``. The tmp dir uses an
    absolute path so ``materialize`` resolves sourcePath to a real FILE (not a file-missing
    orphan). materialize is read-only on disk."""
    d = Path(tempfile.mkdtemp(prefix="longinus_connect_mat_"))
    (d / "mod.py").write_text(
        f"# KG: {_BOUND_NODE}\n# KG: {_ORPHAN_NODE}\n\ndef public_fn():\n    return 1\n"
    )
    kg = MockKgClient()
    if seed_bound:
        kg.other_nodes.add(_BOUND_NODE)  # the cited node now pre-exists => has_node True
    return kg, d


def _symbol_bind_file() -> Path:
    """A tmp file with public top-level symbols (alpha/beta) that carry NO '# KG:' header, so
    ``bind_file`` earns a real nonzero ``BindResult.bound``. Kept OUTSIDE the materialize
    code-root so its module concept is not scanned as an extra orphan ref."""
    d = Path(tempfile.mkdtemp(prefix="longinus_connect_sym_"))
    f = d / "symfile.py"
    f.write_text(
        f"# KG: {_SYMBOL_CONCEPT}\n\ndef alpha():\n    return 1\n\ndef beta():\n    return 2\n"
    )
    return f


def _orphan_reason(where: str) -> str:
    """Distinguish the two orphan causes the engine collapses into one (ref, where) tuple:
    a missing on-disk file vs a cited node that is simply absent from the KG."""
    return "file_missing" if "(file missing)" in where else "node_absent"


def emit_materialize_phase(backend, cid: str, kg: MockKgClient, code_root: Path) -> tuple[int, int]:
    """Run the REAL ``materialize`` and ship one 'longinus_binding_materialized' per bound
    ReferenceSite + one 'longinus_orphan_ref_skipped' per orphan ref (reason synthesized).
    Both literals live verbatim here — Longinus AST-checks THIS symbol. Counts RE-DERIVED
    from the real ``MaterializeResult``."""
    result = _fbm.materialize(kg, code_root)
    for site in kg.list_reference_site_states():
        backend.ship([
            _ev(cid, "longinus_binding_materialized", ref=site.sourceId,
                source_path=site.sourcePath)
        ])
    for ref, where in result.orphan_refs:
        backend.ship([_ev(cid, "longinus_orphan_ref_skipped", ref=ref, reason=_orphan_reason(where))])
    return result.bound, len(result.orphan_refs)


def emit_symbol_bind_phase(backend, cid: str, path: Path) -> int:
    """Run the REAL ``bind_file`` (PROPOSE / apply=False) and ship one 'longinus_symbol_bound'
    per public symbol it would bind. The literal lives verbatim here. Count RE-DERIVED from
    ``BindResult.bound`` (a fully-bound file earns 0)."""
    result = _sb.bind_file(path)
    for symbol in result.bound:
        backend.ship([_ev(cid, "longinus_symbol_bound", symbol=symbol, concept=result.concept)])
    return len(result.bound)


def run_longinus_connect_pipeline(backend, cid: str, *, seed_bound: bool = True) -> dict:
    """Loop entry point (called as ``run_longinus_connect_pipeline(backend, cid)``). Runs the
    REAL materialize + symbol-bind and ships the full lifecycle under ``cid``. The
    'longinus_connect_started' and 'longinus_connect_complete' literals live verbatim in THIS
    symbol's body — Longinus AST-checks ``run_longinus_connect_pipeline`` for the completion.

    ``seed_bound`` defaults True so the loop's 2-arg call drives the green path; the twin test
    overrides it to False for the drop-the-seed RED proof (the bound ref flips to orphan)."""
    kg, code_root = _materialize_code_root(seed_bound=seed_bound)

    backend.ship([_ev(cid, "longinus_connect_started", phase="scan")])
    n_bound, n_orphan = emit_materialize_phase(backend, cid, kg, code_root)
    n_symbols = emit_symbol_bind_phase(backend, cid, _symbol_bind_file())
    backend.ship([
        _ev(cid, "longinus_connect_complete", bound=n_bound, orphans=n_orphan, symbols=n_symbols)
    ])
    return {"bound": n_bound, "orphans": n_orphan, "symbols": n_symbols}


__all__ = [
    "emit_materialize_phase",
    "emit_symbol_bind_phase",
    "run_longinus_connect_pipeline",
]
