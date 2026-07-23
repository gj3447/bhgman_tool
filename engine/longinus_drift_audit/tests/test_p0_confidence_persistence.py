"""P0 — Longinus ReferenceSite.confidence KG round-trip persistence.

Design: SYMPOSIUM/HSWM/DESIGN_HARNESS_DOC_HSWM_LENS_DUALITY_2026-07-21.md §8/§10.
Bug (PROM16 C8, design §8): ``merge_reference_site_state`` never ``SET n.confidence``
and ``list_reference_site_states`` never RETURNed it, so every KG-hydrated
ReferenceSite silently re-defaulted to EXTRACTED — the 3-tier trust lattice, human
gate and Lean no_silent_promotion all evaporated across the KG round-trip.

Fix ORDER (design §10 P0, regression-safe): (1) persist confidence on write,
(2) hydrate a *missing* confidence as UNKNOWN — NOT EXTRACTED. The model field
default stays EXTRACTED for fresh scan-time mint sites (backward compat); UNKNOWN
is a hydration sentinel meaning "confidence was never persisted", which is
explicitly *not* a silent promotion to EXTRACTED.

# KG: ATOM_Skill_longinus
"""

from __future__ import annotations

from engine.longinus_drift_audit.kg_client import Neo4jKgClient
from engine.longinus_drift_audit.models import Confidence, ReferenceSite


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)

    def single(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self, driver):
        self._driver = driver

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, cypher, **params):
        self._driver.calls.append((cypher, params))
        return _FakeResult(list(self._driver.rows))


class _FakeDriver:
    """Captures write params + returns canned rows — no live Neo4j needed."""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def session(self):
        return _FakeSession(self)

    def close(self):
        pass


def _client(rows=None) -> Neo4jKgClient:
    # bypass __init__ (which builds a real neo4j driver); inject the fake.
    c = Neo4jKgClient.__new__(Neo4jKgClient)
    c._driver = _FakeDriver(rows=rows)
    return c


class TestConfidenceWritePersistence:
    def test_write_sets_confidence_property(self):
        c = _client()
        c.merge_reference_site_state(
            ReferenceSite(
                sourceId="lesson-a", sourcePath="src/a.py:1", confidence=Confidence.AMBIGUOUS
            )
        )
        cypher, params = c._driver.calls[-1]
        assert "confidence" in params, "write must pass a confidence param"
        assert params["confidence"] == "AMBIGUOUS"
        assert "n.confidence" in cypher, "Cypher SET must persist n.confidence"


class TestConfidenceReadHydration:
    def test_persisted_confidence_hydrated(self):
        c = _client(
            rows=[{"sourceId": "lesson-a", "sourcePath": "src/a.py:1", "confidence": "AMBIGUOUS"}]
        )
        sites = c.list_reference_site_states()
        assert len(sites) == 1
        assert sites[0].confidence == Confidence.AMBIGUOUS

    def test_missing_confidence_hydrates_UNKNOWN_not_extracted(self):
        # Legacy KG node written before the persistence fix carries no confidence prop.
        c = _client(rows=[{"sourceId": "lesson-a", "sourcePath": "src/a.py:1"}])
        sites = c.list_reference_site_states()
        assert len(sites) == 1
        assert sites[0].confidence == Confidence.UNKNOWN
        # the regression guard — must NOT silently promote to EXTRACTED
        assert sites[0].confidence != Confidence.EXTRACTED

    def test_invalid_confidence_hydrates_UNKNOWN(self):
        c = _client(
            rows=[{"sourceId": "lesson-a", "sourcePath": "src/a.py:1", "confidence": "GARBAGE"}]
        )
        sites = c.list_reference_site_states()
        assert sites[0].confidence == Confidence.UNKNOWN


class TestRoundTrip:
    def test_write_then_read_preserves_confidence(self):
        c = _client()
        c.merge_reference_site_state(
            ReferenceSite(
                sourceId="lesson-rt", sourcePath="src/rt.py:9", confidence=Confidence.AMBIGUOUS
            )
        )
        _, params = c._driver.calls[-1]
        # simulate the KG returning exactly what we just wrote
        c._driver.rows = [
            {
                "sourceId": params["sourceId"],
                "sourcePath": params["sourcePath"],
                "confidence": params["confidence"],
            }
        ]
        got = c.list_reference_site_states()[0]
        assert got.confidence == Confidence.AMBIGUOUS  # survived the full round-trip


class TestForwardBindingPersistence:
    """The primary materialization path (# KG: comment -> bound ReferenceSite)
    must also persist confidence — else every forward-bound site reads back as
    UNKNOWN (safe but lossy), nullifying the scan-time tier signal."""

    def test_forward_binding_sets_confidence(self):
        c = _client(rows=[{"bound": 1}])
        ok = c.merge_forward_binding(
            ReferenceSite(
                sourceId="lesson-fb",
                sourcePath="src/fb.py:3",
                kg_anchor="lesson-fb",
                confidence=Confidence.INFERRED,
            ),
            line_count=10,
        )
        assert ok is True
        cypher, params = c._driver.calls[-1]
        assert params.get("confidence") == "INFERRED"
        assert "rs.confidence" in cypher
