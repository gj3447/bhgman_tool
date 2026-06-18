"""5 Drift Type Detector — Missing / Orphan / SigMismatch / PatternDiv / LabelRot.

각 drift = lens law violation 으로 재정의.
"""

from __future__ import annotations

import ast
from collections import Counter
from functools import lru_cache
from typing import Callable, Iterable

from engine.longinus_drift_audit.models import (
    CodeSymbol,
    DriftRecord,
    DriftType,
    KgRefRecord,
    ReferenceLayer,
)


def detect_missing(
    *,
    symbols: Iterable[CodeSymbol],
    kg_refs: dict[str, KgRefRecord],
    require_kg_ref_kinds: set[str] | None = None,
    ref_exists: Callable[[str], bool] | None = None,
) -> list[DriftRecord]:
    # KG: ATOM_Skill_longinus
    """PutGet violation: code symbol 존재 ∧ KG ref 부재.

    require_kg_ref_kinds: filter only these kinds (default: all).
    ref_exists: anchor-existence predicate. Default checks membership in the
        ``kg_refs`` ReferenceSite snapshot — but a ``# KG:`` comment may anchor
        ANY node kind (:Lesson/:Span/:ATOM…), not only a ReferenceSite, so that
        default false-flags valid non-ReferenceSite anchors as MISSING. Callers
        with a live KG should pass ``kg.has_node`` (matches name OR sourceId
        across all node kinds). Naesengmoon ensemble finding
        ac-bhgman-5f5a905-goodhart-self-audit-mock-zero-drift (deeper refinement).
    """
    if require_kg_ref_kinds is None:
        require_kg_ref_kinds = {"function", "class"}
    if ref_exists is None:
        ref_exists = lambda r: r in kg_refs  # noqa: E731 — backward-compat default

    # Pre-resolve anchor existence once per *unique* ref (ac-bhgman-cd3eeaa-detect_missing-...):
    # the same `# KG:` anchor (esp. hub nodes) recurs across many symbols. Without dedup,
    # kg.has_node (label-less MATCH = full node-store scan) fires per occurrence. This memo
    # → 1 query per unique ref. (Label-less scan itself = KG-index territory, OPEN_TRACKED LOW.)
    symbols = [s for s in symbols if s.kind in require_kg_ref_kinds]
    unique_refs = {ref for s in symbols for ref in (s.kg_refs or [])}
    exists = {ref: ref_exists(ref) for ref in unique_refs}

    out: list[DriftRecord] = []
    for s in symbols:
        # else (no kg_refs): could be Reverse Orphan — separate scan.
        for ref in s.kg_refs or []:
            if not exists[ref]:
                out.append(
                    DriftRecord(
                        drift_type=DriftType.MISSING,
                        sourceId=ref,
                        sourcePath=s.sourcePath,
                        expected="KG node present",
                        actual="missing",
                        layer_violated=ReferenceLayer.L5_DISTRIBUTED,
                        lens_law_violated="PutGet",
                    )
                )
    return out


def detect_orphan(
    *,
    symbols: Iterable[CodeSymbol],
    kg_refs: dict[str, KgRefRecord],
) -> list[DriftRecord]:
    # KG: ATOM_Skill_longinus
    """GetPut violation: KG ref 존재 ∧ 코드 대응 부재.

    Reverse: code 측 모든 `# KG: x` 의 합집합에 없는 KG ref 들.
    """
    code_kg_refs: set[str] = set()
    code_paths_by_id: dict[str, str] = {}
    for s in symbols:
        for ref in s.kg_refs:
            code_kg_refs.add(ref)
            code_paths_by_id.setdefault(ref, s.sourcePath)
    out: list[DriftRecord] = []
    for ref_id, rec in kg_refs.items():
        if ref_id not in code_kg_refs:
            out.append(
                DriftRecord(
                    drift_type=DriftType.ORPHAN,
                    sourceId=ref_id,
                    sourcePath=rec.sourcePath,
                    expected="code symbol cites this KG node",
                    actual="no code references found",
                    layer_violated=ReferenceLayer.L2_LIFETIME,
                    lens_law_violated="GetPut",
                )
            )
    return out


# Memoized: signature strings repeat heavily across a codebase (many symbols
# share a shape, and each KG ref's expected_signature is compared against every
# referencing symbol). Without this, detect_sig_mismatch re-runs ast.parse once
# per (symbol, ref) pair — measured 40k parses for 10 distinct signatures.
# Pure function of its str arg → safe to cache. maxsize caps unbounded growth.
@lru_cache(maxsize=4096)
def _parse_sig(sig: str) -> tuple[tuple[tuple[str, str | None], ...], str | None] | None:
    """Structured form of a signature string: (params, return).

    params = ((name, annotation_or_None), ...); return = annotation_or_None.
    Returns None if the string cannot be parsed as a Python parameter list
    (caller then falls back to normalized string equality). ``*``/``/`` markers
    are dropped — drift is judged on param identity + annotation + return.
    """
    body, _, ret_raw = sig.partition("->")
    ret: str | None = ret_raw.strip() or None
    try:
        tree = ast.parse(f"def _({body.strip()}): pass")
    except SyntaxError:
        return None
    fn = tree.body[0]
    assert isinstance(fn, ast.FunctionDef)
    a = fn.args
    params: list[tuple[str, str | None]] = []
    for arg in a.posonlyargs + a.args + a.kwonlyargs:
        params.append((arg.arg, ast.unparse(arg.annotation) if arg.annotation else None))
    if a.vararg:
        params.append(("*" + a.vararg.arg, None))
    if a.kwarg:
        params.append(("**" + a.kwarg.arg, None))
    return tuple(params), ret


def _signatures_match(expected: str, actual: str) -> bool:
    """True iff two signatures are structurally equal (param names + annotations +
    return). Falls back to whitespace-normalized string equality if either side
    is not parseable."""
    pe, pa = _parse_sig(expected), _parse_sig(actual)
    if pe is None or pa is None:
        return " ".join(expected.split()) == " ".join(actual.split())
    return pe == pa


def detect_sig_mismatch(
    *,
    symbols: Iterable[CodeSymbol],
    kg_refs: dict[str, KgRefRecord],
) -> list[DriftRecord]:
    # KG: ATOM_Skill_longinus
    """PutGet violation (signature drift): KG ref vs live code signature.

    Two modes per ref:
      * ``expected_signature`` set on the KG ref → **structural ast comparison**
        (real param/annotation/return diff; the production path).
      * else → label-substring heuristic (legacy fallback, kept for refs that
        only carry a label and no recorded baseline signature).
    """
    out: list[DriftRecord] = []
    for s in symbols:
        for ref in s.kg_refs:
            rec = kg_refs.get(ref)
            if rec is None:
                continue  # MISSING 측 처리
            drift = _sig_drift_record(s, ref, rec)
            if drift is not None:
                out.append(drift)
    return out


def _sig_drift_record(s: CodeSymbol, ref: str, rec: KgRefRecord) -> DriftRecord | None:
    """One ref's SigMismatch verdict: structural (expected_signature) or label heuristic."""
    if rec.expected_signature is not None:
        if s.signature is None or _signatures_match(rec.expected_signature, s.signature):
            return None
        expected = rec.expected_signature
    elif rec.label and s.signature and rec.label not in s.signature:
        expected = rec.label
    else:
        return None
    return DriftRecord(
        drift_type=DriftType.SIG_MISMATCH,
        sourceId=ref,
        sourcePath=s.sourcePath,
        expected=expected,
        actual=s.signature,
        layer_violated=ReferenceLayer.L3_TYPE,
        lens_law_violated="PutGet",
    )


def detect_pattern_div(*, symbols: Iterable[CodeSymbol]) -> list[DriftRecord]:
    # KG: ATOM_Skill_longinus
    """PutPut violation: 동일 KG ref 가 다중 sourcePath 에 분산 — 의도된 multi-ref
    인지 drift 인지 caller 판단 필요. *경고*만.
    """
    by_ref: dict[str, list[str]] = {}
    for s in symbols:
        for ref in s.kg_refs:
            by_ref.setdefault(ref, []).append(s.sourcePath)
    out: list[DriftRecord] = []
    for ref, paths in by_ref.items():
        if len(paths) > 3:  # 임계값 — caller 가 override 가능
            out.append(
                DriftRecord(
                    drift_type=DriftType.PATTERN_DIV,
                    sourceId=ref,
                    sourcePath=paths[0],
                    expected="≤ 3 references",
                    actual=f"{len(paths)} references at {', '.join(paths[:3])} ...",
                    layer_violated=ReferenceLayer.L6_COMPRESSION,
                    lens_law_violated="PutPut",
                )
            )
    return out


def detect_label_rot(
    *,
    symbols: Iterable[CodeSymbol],
    kg_refs: dict[str, KgRefRecord],
) -> list[DriftRecord]:
    # KG: ATOM_Skill_longinus
    """PutPut violation: KG ref 라벨이 코드 심볼 이름과 모두 다름.

    e.g., `# KG: lesson-foo-2026` 코멘트가 함수 `bar_baz()` 에 붙어있는데
    KG label 도 "qux" 로 다른 경우 — rename 사고.
    """
    out: list[DriftRecord] = []
    for s in symbols:
        for ref in s.kg_refs:
            if ref not in kg_refs:
                continue
            rec = kg_refs[ref]
            if rec.label and s.name and rec.label != s.name and s.name not in rec.sourcePath:
                # not a strict drift unless multiple mismatches. heuristic.
                if not _label_substring(s.name, rec.label):
                    out.append(
                        DriftRecord(
                            drift_type=DriftType.LABEL_ROT,
                            sourceId=ref,
                            sourcePath=s.sourcePath,
                            expected=rec.label,
                            actual=s.name,
                            layer_violated=ReferenceLayer.L4_SEMIOTIC,
                            lens_law_violated="PutPut",
                        )
                    )
    return out


def _label_substring(a: str, b: str) -> bool:
    al, bl = a.lower(), b.lower()
    return al in bl or bl in al


def summarize_drifts(records: Iterable[DriftRecord]) -> dict[str, int]:
    # KG: ATOM_Skill_longinus
    return dict(Counter(r.drift_type.value for r in records))


def detect_all(
    *,
    symbols: Iterable[CodeSymbol],
    kg_refs: dict[str, KgRefRecord],
    ref_exists: Callable[[str], bool] | None = None,
) -> list[DriftRecord]:
    # KG: ATOM_Skill_longinus
    """모든 5 drift 검출 — single dispatch.

    ref_exists threads to detect_missing only (the other 4 drifts compare
    against the ReferenceSite registry by design). See detect_missing.
    """
    syms = list(symbols)
    out: list[DriftRecord] = []
    out.extend(detect_missing(symbols=syms, kg_refs=kg_refs, ref_exists=ref_exists))
    out.extend(detect_orphan(symbols=syms, kg_refs=kg_refs))
    out.extend(detect_sig_mismatch(symbols=syms, kg_refs=kg_refs))
    out.extend(detect_pattern_div(symbols=syms))
    out.extend(detect_label_rot(symbols=syms, kg_refs=kg_refs))
    return out
