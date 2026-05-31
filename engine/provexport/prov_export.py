"""bhgman export-prov — bhgman KG findings → W3C PROV-O (Turtle / JSON / XML).

Maps the per-finding KG provenance loop onto W3C PROV-O so it is FAIR-citable and
not a vendor silo (see ADRs/prov-o-nanopub-export-2026-05-30.md):

    ResearchFinding   -> prov:Entity
    cycle_id          -> prov:Activity
    agentId           -> prov:SoftwareAgent  (PROV-AGENT AIAgent type)
    researchedAt      -> prov:generatedAtTime (on wasGeneratedBy)
    citation_url/refs -> prov:hadPrimarySource
    sourceKgBindings  -> prov:used
    GERMINATED_FROM   -> prov:wasDerivedFrom

Two input paths: live KG (neo4j driver, env-configured) or a pre-fetched findings JSON.
Pure-python, no external services. Validate output via rdflib round-trip + prov constraints.

# KG: consensus-prom6-bhgman-paths-2026-05-30, bhgman-tool-academic-significance-2026-05-30
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prov.model import ProvDocument

BHGMAN_NS = "https://bhgman.ai/kg/"


def _parse_dt(value: Any) -> datetime | None:
    """Best-effort ISO-8601 / neo4j-datetime → python datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            return datetime.fromisoformat(s[:19])
        except ValueError:
            return None


def _src_id(url: str) -> str:
    return "bhgman:src-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


_ATTR_MAP = (
    ("oneLineSummary", "prov:value"),
    ("domain", "bhgman:domain"),
    ("confidence", "bhgman:confidence"),
    ("rootCause", "bhgman:rootCause"),
)


def _finding_attrs(f: dict[str, Any], rf_type: Any) -> dict[str, Any]:
    attrs: dict[str, Any] = {"prov:type": rf_type}
    attrs.update({dst: str(f[src]) for src, dst in _ATTR_MAP if f.get(src)})
    return attrs


def _attach_agent(doc, ent_id: str, aid: Any, seen: set[str]) -> None:
    if not aid:
        return
    agent_id = "bhgman:agent-" + str(aid)
    if agent_id not in seen:
        from prov.model import PROV

        doc.agent(
            agent_id, {"prov:type": PROV["SoftwareAgent"], "bhgman:kind": "prov-agent:AIAgent"}
        )
        seen.add(agent_id)
    doc.wasAttributedTo(ent_id, agent_id)


def _attach_sources(doc, ent_id: str, f: dict[str, Any], src_type: Any, seen: set[str]) -> None:
    urls = list(f.get("references") or [])
    if f.get("citation_url"):
        urls = [f["citation_url"], *urls]
    for url in (u for u in urls if u):
        sid = _src_id(str(url))
        if sid not in seen:
            doc.entity(sid, {"prov:type": src_type, "bhgman:url": str(url)})
            seen.add(sid)
        doc.hadPrimarySource(ent_id, sid)


def _add_finding(doc, f, cycle, rf_type, src_type, seen_agents, seen_src) -> None:
    ent_id = "bhgman:" + f["findingId"]
    doc.entity(ent_id, _finding_attrs(f, rf_type))
    doc.wasGeneratedBy(ent_id, cycle, time=_parse_dt(f.get("researchedAt")))
    _attach_agent(doc, ent_id, f.get("agentId"), seen_agents)
    _attach_sources(doc, ent_id, f, src_type, seen_src)
    for kg in (k for k in (f.get("sourceKgBindings") or []) if k):
        doc.used(cycle, "bhgman:kg-" + str(kg))


def build_prov_document(
    cycle_id: str,
    findings: list[dict[str, Any]],
    derivations: list[tuple[str, str]] | None = None,
) -> ProvDocument:
    """Pure mapping: (cycle_id, findings, GERMINATED_FROM edges) → PROV-O ProvDocument."""
    from prov.model import ProvDocument  # lazy: optional [provexport] extra

    doc = ProvDocument()
    doc.add_namespace("bhgman", BHGMAN_NS)
    doc.add_namespace("prov-agent", "https://provagent.org/ns#")

    rf_type = doc.valid_qualified_name("bhgman:ResearchFinding")
    src_type = doc.valid_qualified_name("bhgman:PrimarySource")
    cycle = doc.activity("bhgman:cycle-" + cycle_id)
    seen_agents: set[str] = set()
    seen_src: set[str] = set()

    for f in findings:
        _add_finding(doc, f, cycle, rf_type, src_type, seen_agents, seen_src)
    for child, parent in derivations or []:
        doc.wasDerivedFrom("bhgman:" + child, "bhgman:" + parent)

    return doc


def serialize(doc: ProvDocument, fmt: str = "turtle") -> str:
    if fmt in ("turtle", "ttl"):
        return doc.serialize(format="rdf", rdf_format="turtle")
    if fmt in ("jsonld", "json-ld"):
        return doc.serialize(format="rdf", rdf_format="json-ld")
    if fmt == "provjson":
        return doc.serialize(format="json")
    if fmt == "xml":
        return doc.serialize(format="xml")
    raise ValueError(f"unknown format: {fmt}")


# ---- live KG path ----------------------------------------------------------

_CYPHER_FINDINGS = """
MATCH (rf:ResearchFinding {cycle_id:$cid})
RETURN rf.name AS findingId, rf.agentId AS agentId, rf.oneLineSummary AS oneLineSummary,
       rf.domain AS domain, rf.confidence AS confidence, rf.rootCause AS rootCause,
       rf.citation_url AS citation_url, rf.references AS references,
       rf.sourceKgBindings AS sourceKgBindings, toString(rf.researchedAt) AS researchedAt
"""
_CYPHER_DERIV = """
MATCH (c:ResearchFinding {cycle_id:$cid})-[:GERMINATED_FROM|GERMINATED_FROM_AXIS|INSTANCE_OF]->(p)
RETURN c.name AS child, p.name AS parent
"""


def fetch_cycle_from_kg(cycle_id: str, uri: str, user: str, password: str):
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as s:
            findings = [dict(r) for r in s.run(_CYPHER_FINDINGS, cid=cycle_id)]
            derivations = [(r["child"], r["parent"]) for r in s.run(_CYPHER_DERIV, cid=cycle_id)]
    finally:
        driver.close()
    return findings, derivations


def export_prov(cycle_id: str, fmt: str = "turtle", findings_json: str | None = None) -> str:
    if findings_json:
        with open(findings_json) as fh:
            payload = json.load(fh)
        findings = payload["findings"]
        derivations = [tuple(x) for x in payload.get("derivations", [])]
    else:
        findings, derivations = fetch_cycle_from_kg(
            cycle_id,
            os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            os.environ.get("NEO4J_USER", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", ""),
        )
    if not findings:
        raise SystemExit(f"no ResearchFinding for cycle_id={cycle_id}")
    doc = build_prov_document(cycle_id, findings, derivations)
    return serialize(doc, fmt)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="bhgman export-prov", description="Export a bhgman KG cycle's findings as W3C PROV-O."
    )
    ap.add_argument("cycle_id")
    ap.add_argument(
        "--format",
        default="turtle",
        choices=["turtle", "ttl", "jsonld", "json-ld", "provjson", "xml"],
    )
    ap.add_argument("--findings-json", help="offline input instead of live KG")
    ap.add_argument("--out", help="output file (default: stdout)")
    args = ap.parse_args(argv)
    out = export_prov(args.cycle_id, args.format, args.findings_json)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(out)
        print(f"wrote {args.out} ({len(out)} bytes)", file=sys.stderr)
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
