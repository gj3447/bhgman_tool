"""5 Drift Type Detector — Missing / Orphan / SigMismatch / PatternDiv / LabelRot.

각 drift = lens law violation 으로 재정의.

# KG: finding-prom16-parallelism-bhgman-dep-A1 (Bernstein-trivially parallel, W=∅)
# KG: finding-prom16-parallelism-bhgman-dep-A4 (5-phase fan-out, immutable snapshot)
"""

from __future__ import annotations

import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

from models import (
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
) -> list[DriftRecord]:
    """PutGet violation: code symbol 존재 ∧ KG ref 부재.

    require_kg_ref_kinds: filter only these kinds (default: all).
    """
    if require_kg_ref_kinds is None:
        require_kg_ref_kinds = {"function", "class"}
    out: list[DriftRecord] = []
    for s in symbols:
        if s.kind not in require_kg_ref_kinds:
            continue
        if s.kg_refs:
            # symbol declares some KG refs; ensure each exists in KG
            for ref in s.kg_refs:
                if ref not in kg_refs:
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
        # else: no kg_refs declared by code — could be Reverse Orphan (separate scan).
    return out


def detect_orphan(
    *,
    symbols: Iterable[CodeSymbol],
    kg_refs: dict[str, KgRefRecord],
) -> list[DriftRecord]:
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


def detect_sig_mismatch(
    *,
    symbols: Iterable[CodeSymbol],
    kg_refs: dict[str, KgRefRecord],
) -> list[DriftRecord]:
    """PutGet violation (signature 변): KG ref 와 코드 시그니처 비일치.

    Mock check — KG ref 의 label 이 symbol.signature 와 substring 일치 여부.
    실 production 은 AST semantic diff (GumTree) 위임.
    """
    out: list[DriftRecord] = []
    for s in symbols:
        for ref in s.kg_refs:
            if ref not in kg_refs:
                continue  # MISSING 측 처리
            rec = kg_refs[ref]
            if rec.label and s.signature and rec.label not in s.signature:
                out.append(
                    DriftRecord(
                        drift_type=DriftType.SIG_MISMATCH,
                        sourceId=ref,
                        sourcePath=s.sourcePath,
                        expected=rec.label,
                        actual=s.signature,
                        layer_violated=ReferenceLayer.L3_TYPE,
                        lens_law_violated="PutGet",
                    )
                )
    return out


def detect_pattern_div(*, symbols: Iterable[CodeSymbol]) -> list[DriftRecord]:
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
    return dict(Counter(r.drift_type.value for r in records))


def detect_all(
    *,
    symbols: Iterable[CodeSymbol],
    kg_refs: dict[str, KgRefRecord],
    parallel: bool | None = None,
) -> list[DriftRecord]:
    """모든 5 drift 검출 — Bernstein-trivially parallel (W=∅).

    All 5 detect_* are pure functions over immutable Iterable[CodeSymbol] +
    frozen kg_refs dict. R∩W=∅, W∩W=∅, W∩R=∅ (Bernstein 1966) → safely
    fan-out via ThreadPool. Each returns a disjoint list[DriftRecord] (no
    shared mutable state).

    Args:
        parallel: True → ThreadPool fan-out (5 worker). False → sequential.
            None (default) → env var ``LONGINUS_DRIFT_DETECT_PARALLEL=1``
            opt-in; sequential otherwise (matches longinus_drift_audit
            audit_runner default-OFF policy until neo4j-backend bench flip).

    # KG: finding-prom16-parallelism-bhgman-dep-A1 (Bernstein conditions)
    """
    syms = list(symbols)
    if parallel is None:
        parallel = os.environ.get("LONGINUS_DRIFT_DETECT_PARALLEL", "0") == "1"

    if not parallel:
        out: list[DriftRecord] = []
        out.extend(detect_missing(symbols=syms, kg_refs=kg_refs))
        out.extend(detect_orphan(symbols=syms, kg_refs=kg_refs))
        out.extend(detect_sig_mismatch(symbols=syms, kg_refs=kg_refs))
        out.extend(detect_pattern_div(symbols=syms))
        out.extend(detect_label_rot(symbols=syms, kg_refs=kg_refs))
        return out

    # ThreadPool fan-out — 5 detectors, immutable input, disjoint output.
    tasks = (
        ("missing", lambda: detect_missing(symbols=syms, kg_refs=kg_refs)),
        ("orphan", lambda: detect_orphan(symbols=syms, kg_refs=kg_refs)),
        ("sig_mismatch", lambda: detect_sig_mismatch(symbols=syms, kg_refs=kg_refs)),
        ("pattern_div", lambda: detect_pattern_div(symbols=syms)),
        ("label_rot", lambda: detect_label_rot(symbols=syms, kg_refs=kg_refs)),
    )
    with ThreadPoolExecutor(max_workers=5) as pool:
        # Submit in stable order so the result list ordering matches sequential
        # mode (drift consumers may depend on detect order; explicit guard).
        futures = [pool.submit(fn) for _name, fn in tasks]
        merged: list[DriftRecord] = []
        for fut in futures:
            merged.extend(fut.result())
        return merged
