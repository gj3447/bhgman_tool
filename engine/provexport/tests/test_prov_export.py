"""Tests for PROV-O export — mapping correctness + RDF validity + prov constraints."""

import io

import rdflib
from prov.model import ProvDocument

from engine.provexport.prov_export import build_nanopub_trig, build_prov_document, serialize

SAMPLE = [
    {
        "findingId": "finding-x-A1",
        "agentId": "prom-A1",
        "oneLineSummary": "claim one",
        "domain": "axis-A",
        "confidence": "HIGH",
        "rootCause": "because",
        "citation_url": "https://arxiv.org/abs/0000.00001",
        "references": ["Author 2025 — title (arXiv:0000.00001)"],
        "sourceKgBindings": ["node-1"],
        "researchedAt": "2026-05-30T12:00:00+00:00",
    },
    {
        "findingId": "finding-x-A2",
        "agentId": "prom-A2",
        "oneLineSummary": "claim two",
        "domain": "axis-A",
        "confidence": "MEDIUM",
        "citation_url": "https://example.org/doc",
        "references": [],
        "researchedAt": "2026-05-30T12:01:00+00:00",
    },
]
DERIV = [("finding-x-A2", "finding-x-A1")]


def _doc():
    return build_prov_document("cycle-test-1", SAMPLE, DERIV)


def test_builds_prov_document():
    doc = _doc()
    assert isinstance(doc, ProvDocument)
    ids = {str(r.identifier) for r in doc.get_records()}
    assert any("cycle-test-1" in i for i in ids)
    assert any("finding-x-A1" in i for i in ids)


def test_turtle_serializes_and_roundtrips():
    ttl = serialize(_doc(), "turtle")
    assert "prov:" in ttl or "wasGeneratedBy" in ttl.lower() or "Activity" in ttl
    g = rdflib.Graph()
    g.parse(io.StringIO(ttl), format="turtle")  # raises if invalid RDF
    assert len(g) > 0


def test_derivation_and_attribution_present():
    g = rdflib.Graph()
    g.parse(io.StringIO(serialize(_doc(), "turtle")), format="turtle")
    PROV = rdflib.Namespace("http://www.w3.org/ns/prov#")
    # direct predicates
    assert (None, PROV.wasDerivedFrom, None) in g
    assert (None, PROV.wasAttributedTo, None) in g
    # timed generation + cited source serialize as the canonical qualified forms
    assert (None, PROV.qualifiedGeneration, None) in g
    assert (None, PROV.qualifiedPrimarySource, None) in g
    assert (None, rdflib.RDF.type, PROV.Activity) in g


def test_prov_constraints_hold():
    # prov lib enforces PROV-DM constraints; unification must not raise
    doc = _doc()
    doc.unified()


def test_provjson_serializes():
    js = serialize(_doc(), "provjson")
    assert "entity" in js and "activity" in js


def test_nanopub_trig_has_four_graphs_and_np_structure():
    """nanopub export = valid TriG with the 4 canonical nanopublication graphs."""
    trig = build_nanopub_trig("cycle-test-1", SAMPLE, DERIV)
    ds = rdflib.Dataset()
    ds.parse(io.StringIO(trig), format="trig")  # raises if invalid TriG
    NP = rdflib.Namespace("http://www.nanopub.org/nschema#")
    PROV = rdflib.Namespace("http://www.w3.org/ns/prov#")
    BH = rdflib.Namespace("https://bhgman.ai/kg/")

    # Head graph declares the nanopub + links the 3 sub-graphs.
    np_uri = rdflib.URIRef("https://bhgman.ai/kg/np/cycle-test-1")
    head = ds.graph(rdflib.URIRef(str(np_uri) + "#Head"))
    assertion = rdflib.URIRef(str(np_uri) + "#assertion")
    provenance = rdflib.URIRef(str(np_uri) + "#provenance")
    pubinfo = rdflib.URIRef(str(np_uri) + "#pubinfo")
    assert (np_uri, rdflib.RDF.type, NP.Nanopublication) in head
    assert (np_uri, NP.hasAssertion, assertion) in head
    assert (np_uri, NP.hasProvenance, provenance) in head
    assert (np_uri, NP.hasPublicationInfo, pubinfo) in head

    # All four named graphs exist and are non-empty.
    named = {str(g.identifier) for g in ds.graphs() if len(g) > 0}
    for g_uri in (str(head.identifier), str(assertion), str(provenance), str(pubinfo)):
        assert g_uri in named, f"missing/empty nanopub graph: {g_uri}"

    # Assertion graph carries the claim; provenance graph carries how it was made.
    g_assert = ds.graph(assertion)
    g_prov = ds.graph(provenance)
    assert (BH["finding-x-A1"], rdflib.RDF.type, BH.ResearchFinding) in g_assert
    assert (BH["finding-x-A2"], PROV.wasDerivedFrom, BH["finding-x-A1"]) in g_assert
    assert (BH["finding-x-A1"], PROV.wasGeneratedBy, BH["cycle-cycle-test-1"]) in g_prov
    assert (None, PROV.hadPrimarySource, None) in g_prov


def test_nanopub_trig_is_idempotent():
    """Same inputs → byte-identical TriG (no wall-clock injected)."""
    assert build_nanopub_trig("c", SAMPLE, DERIV) == build_nanopub_trig("c", SAMPLE, DERIV)


def test_export_real_prom6_fixture(tmp_path):
    """End-to-end on the real prom6 cycle fixture → valid PROV-O Turtle."""
    import os

    from engine.provexport.prov_export import export_prov

    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "prom6_findings.json")
    ttl = export_prov("prom6-bhgman-significance-paths-2026-05-30", "turtle", fixture)
    g = rdflib.Graph()
    g.parse(io.StringIO(ttl), format="turtle")
    PROV = rdflib.Namespace("http://www.w3.org/ns/prov#")
    findings = [s for s in g.subjects(rdflib.RDF.type, PROV.Entity) if "finding-prom6" in str(s)]
    assert len(findings) == 6  # all 6 prom6 findings became prov:Entity
    assert (None, rdflib.RDF.type, PROV.Activity) in g  # the cycle
