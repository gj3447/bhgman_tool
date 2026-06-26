"""AMIE 3.5.1 Horn rule mining via Java subprocess.

Lajus-Galárraga-Suchanek 2020. Typed Horn rule induction with PCA (Partial Completeness
Assumption) confidence over typed-edge triples.

JAR: vendor/amie3.5.1.jar (downloaded 2026-05-20).
Java: /opt/homebrew/opt/openjdk@21/bin/java (brew openjdk@21 keg-only).

Input format: TSV with 3 columns (subject, predicate, object), no header.
Output format: parsed table of Horn rules with PCA confidence + head coverage.
"""
# KG: eureka-canonical-2026-05-26

from __future__ import annotations

import csv
import dataclasses as dc
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, Optional


_DEFAULT_JAVA_CANDIDATES = (
    "/opt/homebrew/opt/openjdk@21/bin/java",
    "/opt/homebrew/opt/openjdk/bin/java",
    "java",
)
_DEFAULT_JAR = Path(__file__).resolve().parent.parent / "vendor" / "amie3.5.1.jar"


def _find_java() -> str:
    # Honor the JAVA / JAVA_HOME env vars the error message advertises — BEFORE the
    # macOS-Homebrew defaults — so the operator is usable on Linux/CI with a non-default JDK.
    env_candidates: list[str] = []
    if os.environ.get("JAVA"):
        env_candidates.append(os.environ["JAVA"])
    if os.environ.get("JAVA_HOME"):
        env_candidates.append(str(Path(os.environ["JAVA_HOME"]) / "bin" / "java"))
    for candidate in (*env_candidates, *_DEFAULT_JAVA_CANDIDATES):
        path = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if path:
            return path
    raise RuntimeError(
        "java executable not found. Install via `brew install openjdk@21` or set JAVA env var."
    )


@dc.dataclass(frozen=True)
class HornRule:
    # KG: eureka-canonical-2026-05-26
    """A single Horn rule emitted by AMIE.

    body and head are stored as raw AMIE atom strings (e.g. "?a livesIn ?b").
    """

    body: str
    head: str
    head_coverage: float
    std_confidence: float
    pca_confidence: float
    positive_examples: int
    body_size: int
    pca_body_size: int


@dc.dataclass(frozen=True)
class Amie3Result:
    # KG: eureka-canonical-2026-05-26
    rules: tuple[HornRule, ...]
    triples_input: int
    raw_stdout_lines: tuple[str, ...]
    elapsed_sec: float


def _triples_to_tsv(triples: Iterable[tuple[str, str, str]], dst: Path) -> int:
    count = 0
    with dst.open("w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        for s, p, o in triples:
            writer.writerow([str(s), str(p), str(o)])
            count += 1
    return count


def _parse_rules(stdout: str) -> list[HornRule]:
    """Parse AMIE stdout table.

    AMIE prints rules after a header line with tab-separated columns:
        Rule  HeadCov  StdConf  PCAConf  PositiveExamples  BodySize  PCABodySize ...
    """
    rules: list[HornRule] = []
    lines = stdout.splitlines()
    started = False
    for line in lines:
        if not started:
            if "Head Coverage" in line and "PCA Confidence" in line:
                started = True
            continue
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        try:
            rule_str = parts[0].strip()
            if " => " not in rule_str:
                continue
            body, head = rule_str.split(" => ", 1)
            rules.append(
                HornRule(
                    body=body.strip(),
                    head=head.strip(),
                    head_coverage=float(parts[1]),
                    std_confidence=float(parts[2]),
                    pca_confidence=float(parts[3]),
                    positive_examples=int(parts[4]),
                    body_size=int(parts[5]),
                    pca_body_size=int(parts[6]),
                )
            )
        except (ValueError, IndexError):
            continue
    return rules


def induce_amie3(
    triples: Iterable[tuple[str, str, str]],
    *,
    min_pca_confidence: float = 0.1,
    min_head_coverage: float = 0.01,
    min_support: int = 100,
    java: Optional[str] = None,
    jar: Optional[Path] = None,
    timeout_sec: float = 300.0,
    extra_args: Optional[list[str]] = None,
) -> Amie3Result:
    # KG: eureka-canonical-2026-05-26
    """Run AMIE 3.5.1 over typed triples. Returns parsed Horn rules.

    Parameters
    ----------
    triples : iterable of (s, p, o)
    min_pca_confidence, min_head_coverage, min_support : AMIE thresholds
    java : path to java executable; auto-detected if None
    jar : path to amie3.5.1.jar; defaults to vendor/amie3.5.1.jar
    timeout_sec : subprocess timeout
    extra_args : passed through to AMIE CLI
    """
    import time

    java_exe = java or _find_java()
    jar_path = (jar or _DEFAULT_JAR).resolve()
    if not jar_path.exists():
        raise FileNotFoundError(
            f"AMIE jar not found at {jar_path}. "
            "Download with: curl -L -o vendor/amie3.5.1.jar "
            "https://github.com/dig-team/AMIE/releases/download/v3.5.1/amie3.5.1.jar"
        )

    with tempfile.TemporaryDirectory(prefix="amie3_") as tmp:
        tsv = Path(tmp) / "triples.tsv"
        triple_count = _triples_to_tsv(triples, tsv)

        cmd = [
            java_exe,
            "-jar",
            str(jar_path),
            "-minc",
            str(min_pca_confidence),
            "-minhc",
            str(min_head_coverage),
            "-mins",
            str(min_support),
            str(tsv),
        ]
        if extra_args:
            cmd.extend(extra_args)

        t0 = time.monotonic()
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env={**os.environ, "JAVA_TOOL_OPTIONS": "-Xss10m"},
        )
        elapsed = time.monotonic() - t0

        if proc.returncode != 0:
            raise RuntimeError(f"AMIE exit {proc.returncode}: stderr={proc.stderr[:500]}")

        rules = _parse_rules(proc.stdout)

    return Amie3Result(
        rules=tuple(rules),
        triples_input=triple_count,
        raw_stdout_lines=tuple(proc.stdout.splitlines()),
        elapsed_sec=elapsed,
    )


__all__ = [
    "Amie3Result",
    "HornRule",
    "induce_amie3",
]
