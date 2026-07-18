#!/usr/bin/env python3
"""Produce positive, injected-negative, and restored P4 erratum observations."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Mapping

from engine.efficacy.diagnostic_repair_analysis_errata import (
    ErratumError,
    build_p4_erratum,
)


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "verification" / "diagnostic-repair-v3-32b" / "analysis.json"
GENERATOR = ROOT / "engine" / "efficacy" / "diagnostic_repair_analysis_errata.py"
CID = "pi-diagnostic-repair-v3-p4-erratum-20260718"


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write(path: Path, document: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _build(analysis: dict[str, object], source_bytes: bytes) -> dict[str, object]:
    return build_p4_erratum(
        analysis,
        source_path=SOURCE.relative_to(ROOT).as_posix(),
        source_sha256=_sha(source_bytes),
        generator_path=GENERATOR.relative_to(ROOT).as_posix(),
        generator_sha256=_sha(GENERATOR.read_bytes()),
    )


def main() -> int:
    source_bytes = SOURCE.read_bytes()
    analysis = json.loads(source_bytes)
    if not isinstance(analysis, dict):
        raise TypeError("source analysis must be an object")

    positive = _build(analysis, source_bytes)
    positive_path = HERE / "erratum.json"
    _write(positive_path, positive)
    readback = json.loads(positive_path.read_text(encoding="utf-8"))
    if readback != positive or readback["correction"]["status"] != "FAIL":
        raise RuntimeError("positive erratum readback failed")

    injected = copy.deepcopy(analysis)
    raw_ratios = injected["gates"]["P4"]["raw_ratios"]
    for metrics in raw_ratios.values():
        for metric in metrics:
            metrics[metric] = 1.0
    try:
        _build(injected, source_bytes)
    except ErratumError as exc:
        negative = {
            "schema": "pi-diagnostic-repair-analysis-erratum-negative/v1",
            "cid": CID,
            "injection": "replace every raw P4 ratio with the in-bounds value 1.0",
            "observed": "red",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "source_sha256": _sha(source_bytes),
        }
    else:
        raise RuntimeError("negative injection was incorrectly accepted")
    _write(HERE / "negative.json", negative)

    restored = _build(analysis, source_bytes)
    restored_bytes = (
        json.dumps(restored, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    positive_bytes = positive_path.read_bytes()
    restored_observation = {
        "schema": "pi-diagnostic-repair-analysis-erratum-restore/v1",
        "cid": CID,
        "source_unchanged": SOURCE.read_bytes() == source_bytes,
        "restored_matches_positive": restored_bytes == positive_bytes,
        "erratum_sha256": _sha(positive_bytes),
    }
    if not all(
        restored_observation[key] for key in ("source_unchanged", "restored_matches_positive")
    ):
        raise RuntimeError("restore check failed")
    _write(HERE / "restored.json", restored_observation)
    print(
        json.dumps(
            {
                "cid": CID,
                "positive": "green",
                "negative": "red",
                "restored": "green",
                "erratum_sha256": restored_observation["erratum_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
