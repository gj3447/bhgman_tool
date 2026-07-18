"""Content-addressed errata for frozen diagnostic-repair analyses.

The v3 analyzer is itself part of the frozen experiment manifest, so changing
that module in place would destroy replayability.  This module applies narrow,
explicit overlays to an immutable analysis artifact instead.

P4 is a conjunction.  Once a raw compute-parity ratio is known to be outside
its preregistered interval, the conjunction is false even if a different
matched-token conjunct is underpowered.  The frozen v3 analyzer ordered those
checks incorrectly and emitted ``ABSENT``.  This overlay records the decisive
``FAIL`` without rewriting the historical artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence


ERRATUM_SCHEMA = "pi-diagnostic-repair-analysis-erratum/v1"
ERRATUM_ID = "p4-known-false-dominates-unknown-v1"
SOURCE_SCHEMA = "pi-diagnostic-repair-harness/v2"


class ErratumError(ValueError):
    """Raised when an analysis cannot safely receive this erratum."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _finite_ratio(value: object, *, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ErratumError(f"{label} must be a finite number or null")
    number = float(value)
    if not math.isfinite(number):
        raise ErratumError(f"{label} must be finite")
    return number


def _ratio_failures(
    raw_ratios: Mapping[str, object], *, low: float, high: float
) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    for baseline in sorted(raw_ratios):
        metrics = raw_ratios[baseline]
        if not isinstance(metrics, Mapping):
            raise ErratumError(f"gates.P4.raw_ratios.{baseline} must be an object")
        for metric in sorted(metrics):
            value = _finite_ratio(metrics[metric], label=f"gates.P4.raw_ratios.{baseline}.{metric}")
            if value is not None and not low <= value <= high:
                failures.append({"baseline": baseline, "metric": metric, "value": value})
    return failures


def build_p4_erratum(
    analysis: Mapping[str, Any],
    *,
    source_path: str,
    source_sha256: str,
    generator_path: str,
    generator_sha256: str,
) -> dict[str, Any]:
    """Return a deterministic overlay for the frozen P4 ordering defect.

    The function refuses to reinterpret a passing or already-failed P4 gate.
    It is intentionally narrow: only a historical ``ABSENT`` with at least one
    known raw-ratio violation is eligible.
    """

    if analysis.get("schema") != SOURCE_SCHEMA:
        raise ErratumError(f"source schema must be {SOURCE_SCHEMA!r}")
    thresholds = analysis.get("thresholds")
    gates = analysis.get("gates")
    if not isinstance(thresholds, Mapping) or not isinstance(gates, Mapping):
        raise ErratumError("source analysis must contain thresholds and gates objects")
    p4 = gates.get("P4")
    if not isinstance(p4, Mapping):
        raise ErratumError("source analysis must contain gates.P4")
    original_status = p4.get("status")
    if original_status != "ABSENT":
        raise ErratumError(f"erratum requires historical P4=ABSENT, observed {original_status!r}")

    low = _finite_ratio(thresholds.get("parity_low"), label="thresholds.parity_low")
    high = _finite_ratio(thresholds.get("parity_high"), label="thresholds.parity_high")
    if low is None or high is None or not 0 < low <= 1 <= high:
        raise ErratumError("parity bounds must satisfy 0 < low <= 1 <= high")
    raw_ratios = p4.get("raw_ratios")
    if not isinstance(raw_ratios, Mapping):
        raise ErratumError("historical P4 must contain raw_ratios")
    failures = _ratio_failures(raw_ratios, low=low, high=high)
    if not failures:
        raise ErratumError("no known raw-ratio violation exists; P4 cannot be corrected to FAIL")

    if len(source_sha256) != 64 or len(generator_sha256) != 64:
        raise ErratumError("source and generator hashes must be SHA-256 hex digests")
    try:
        int(source_sha256, 16)
        int(generator_sha256, 16)
    except ValueError as exc:
        raise ErratumError("source and generator hashes must be SHA-256 hex digests") from exc

    formatted = ", ".join(
        f"{item['baseline']}.{item['metric']}={item['value']}" for item in failures
    )
    old_confirm = analysis.get("confirm")
    corrected_confirm = False
    return {
        "schema": ERRATUM_SCHEMA,
        "erratum_id": ERRATUM_ID,
        "source": {
            "path": source_path,
            "sha256": source_sha256.lower(),
            "schema": SOURCE_SCHEMA,
        },
        "generator": {
            "path": generator_path,
            "sha256": generator_sha256.lower(),
        },
        "rule": {
            "gate": "P4",
            "operator": "AND",
            "semantics": "KNOWN_FALSE_DOMINATES_UNKNOWN",
            "preregistered_requirement": "all raw ratios must remain within bounds",
        },
        "observation": {
            "bounds": {"low": low, "high": high},
            "ratio_failures": failures,
            "original_status": original_status,
            "original_reasons": list(p4.get("reasons", [])),
        },
        "correction": {
            "status": "FAIL",
            "reasons": [
                f"known live-task usage ratios outside [{low}, {high}]: {formatted}",
                "matched-token underpower cannot mask an already false required conjunct",
            ],
            "original_confirm": old_confirm,
            "corrected_confirm": corrected_confirm,
            "final_claim_changed": old_confirm != corrected_confirm,
        },
        "immutability": {
            "source_rewritten": False,
            "raw_measurement_reinterpreted": False,
            "scope": "gate-status correction only; raw data and historical analysis remain frozen",
        },
    }


def _atomic_write_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    analysis_path = args.analysis.resolve()
    generator = Path(__file__).resolve()
    for label, path in (("analysis", analysis_path), ("generator", generator)):
        if path != root and root not in path.parents:
            parser.error(f"{label} path escapes --root")
        if not path.is_file():
            parser.error(f"{label} path is not a file: {path}")

    source_bytes = analysis_path.read_bytes()
    try:
        analysis = json.loads(source_bytes)
    except json.JSONDecodeError as exc:
        parser.error(f"analysis is invalid JSON: {exc.msg}")
    if not isinstance(analysis, dict):
        parser.error("analysis must be a JSON object")

    try:
        document = build_p4_erratum(
            analysis,
            source_path=analysis_path.relative_to(root).as_posix(),
            source_sha256=_sha256_bytes(source_bytes),
            generator_path=generator.relative_to(root).as_posix(),
            generator_sha256=_sha256_bytes(generator.read_bytes()),
        )
    except ErratumError as exc:
        parser.error(str(exc))
    _atomic_write_json(args.output.resolve(), document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
