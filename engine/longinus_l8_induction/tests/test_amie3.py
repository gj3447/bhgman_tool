"""Smoke test for AMIE3 wrapper. Requires java + amie3.5.1.jar present.

Tiny synthetic triple store with one obvious rule:
  livesIn(x, y) ∧ locatedIn(y, z) => livesIn(x, z)  (transitive closure)
"""

import subprocess
from pathlib import Path

import pytest


JAR = Path(__file__).resolve().parent.parent / "vendor" / "amie3.5.1.jar"
JAVA = "/opt/homebrew/opt/openjdk@21/bin/java"


def _java_available() -> bool:
    if not Path(JAVA).exists():
        return False
    try:
        subprocess.run([JAVA, "-version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (JAR.exists() and _java_available()),
    reason="AMIE jar or Java 21 not available",
)


def test_amie3_runs_on_synthetic_triples():
    from induction_operators.amie3 import induce_amie3

    triples = []
    for i in range(120):
        triples.append((f"person_{i}", "livesIn", f"city_{i % 10}"))
        triples.append((f"city_{i % 10}", "locatedIn", f"country_{i % 3}"))
    for i in range(120):
        triples.append((f"person_{i}", "livesIn", f"country_{i % 3}"))

    result = induce_amie3(
        triples,
        min_pca_confidence=0.1,
        min_head_coverage=0.05,
        min_support=10,
        timeout_sec=120,
    )

    assert result.triples_input == 360
    assert isinstance(result.rules, tuple)
    assert result.elapsed_sec < 120
