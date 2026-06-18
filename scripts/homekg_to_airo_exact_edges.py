#!/usr/bin/env python3
"""Copy exact Home KG relationships into the airo Neo4j MCP.

Source access is direct Neo4j Bolt, configured by:
  HOME_NEO4J_URI
  HOME_NEO4J_USERNAME
  HOME_NEO4J_PASSWORD

Target access is the airo MCP streamable HTTP endpoint from
~/.codex/config.toml, or AIRO_MCP_URL.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


KEYWORD_PREDICATE = """
WHERE any(v IN [a.name, a.title, a.path, a.file, a.id, a.key]
          WHERE v IS NOT NULL AND (
            toLower(toString(v)) CONTAINS 'metahumotonic'
            OR toLower(toString(v)) CONTAINS 'bhgman'
            OR toLower(toString(v)) CONTAINS 'longinus'))
   OR any(v IN [b.name, b.title, b.path, b.file, b.id, b.key]
          WHERE v IS NOT NULL AND (
            toLower(toString(v)) CONTAINS 'metahumotonic'
            OR toLower(toString(v)) CONTAINS 'bhgman'
            OR toLower(toString(v)) CONTAINS 'longinus'))
"""


READ_QUERY = """
MATCH (a)-[r]->(b)
{predicate}
RETURN elementId(a) AS s,
       coalesce(a.name, a.title, a.path, a.file, a.id, a.key, elementId(a)) AS sn,
       labels(a) AS sl,
       type(r) AS t,
       elementId(r) AS re,
       properties(r) AS rp,
       elementId(b) AS d,
       coalesce(b.name, b.title, b.path, b.file, b.id, b.key, elementId(b)) AS dn,
       labels(b) AS dl
ORDER BY re
SKIP $skip
LIMIT $limit
"""


COUNT_QUERY = """
MATCH (a)-[r]->(b)
{predicate}
RETURN count(r) AS c
"""


WRITE_QUERY = """
MERGE (b:HomeKgImportBatch {id: $batchId})
SET b.kind = 'exact_edge_chunk',
    b.source = 'homekg',
    b.target = 'airo',
    b.updated_at = datetime()
WITH b
UNWIND $rows AS row
MERGE (src:HomeKgExactNode {homeElementId: row.s})
SET src.name = row.sn,
    src.homeLabels = row.sl,
    src.sourceKg = 'homekg',
    src.updated_at = datetime()
MERGE (dst:HomeKgExactNode {homeElementId: row.d})
SET dst.name = row.dn,
    dst.homeLabels = row.dl,
    dst.sourceKg = 'homekg',
    dst.updated_at = datetime()
MERGE (src)-[e:HOME_KG_EXACT_REL {homeRelElementId: row.re}]->(dst)
SET e.originalType = row.t,
    e.sourceKg = 'homekg',
    e.importBatch = $batchId,
    e.homeRelPropsJson = row.rpj,
    e.updated_at = datetime()
MERGE (b)-[:IMPORTED_EXACT_EDGE]->(src)
MERGE (b)-[:IMPORTED_EXACT_EDGE]->(dst)
RETURN count(e) AS edgesTouched
"""


def load_airo_mcp_url() -> str:
    if os.environ.get("AIRO_MCP_URL"):
        return os.environ["AIRO_MCP_URL"]

    config = Path.home() / ".codex" / "config.toml"
    text = config.read_text(encoding="utf-8")
    match = re.search(
        r"\[mcp_servers\.airo-neo4j\]\s*\nurl\s*=\s*\"([^\"]+)\"",
        text,
    )
    if not match:
        raise RuntimeError("Could not find [mcp_servers.airo-neo4j] url in ~/.codex/config.toml")
    return match.group(1)


def mcp_call(url: str, tool_name: str, arguments: dict[str, Any], timeout: int = 120) -> Any:
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")

    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        message = json.loads(line[6:])
        if "error" in message:
            raise RuntimeError(message["error"])
        return message.get("result")
    raise RuntimeError(f"No MCP data event returned: {body[:300]}")


def source_driver():
    uri = os.environ.get("HOME_NEO4J_URI")
    username = os.environ.get("HOME_NEO4J_USERNAME")
    password = os.environ.get("HOME_NEO4J_PASSWORD")
    missing = [
        name
        for name, value in {
            "HOME_NEO4J_URI": uri,
            "HOME_NEO4J_USERNAME": username,
            "HOME_NEO4J_PASSWORD": password,
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit(f"Missing source env vars: {', '.join(missing)}")
    return GraphDatabase.driver(uri, auth=(username, password), connection_timeout=15)


def sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(row)
    props = cleaned.pop("rp", {}) or {}
    cleaned["rpj"] = json.dumps(props, ensure_ascii=False, sort_keys=True, default=str)
    for key in ("sn", "dn"):
        cleaned[key] = str(cleaned[key])
    return cleaned


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--max-edges", type=int, default=0, help="0 means no limit")
    parser.add_argument("--all-relationships", action="store_true", help="copy all Home KG relationships")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-prefix", default="homekg-exact-edge-keyword")
    args = parser.parse_args()

    predicate = "" if args.all_relationships else KEYWORD_PREDICATE
    read_query = READ_QUERY.format(predicate=predicate)
    count_query = COUNT_QUERY.format(predicate=predicate)
    airo_url = load_airo_mcp_url()

    with source_driver() as driver:
        with driver.session() as session:
            total = session.run(count_query).single()["c"]
            if args.max_edges:
                total = min(total, args.max_edges)
            print(f"source relationships selected: {total}")
            if args.dry_run:
                return 0

            copied = 0
            skip = 0
            while copied < total:
                limit = min(args.batch_size, total - copied)
                rows = [
                    sanitize_row(dict(record))
                    for record in session.run(read_query, skip=skip, limit=limit)
                ]
                if not rows:
                    break
                batch_id = f"{args.batch_prefix}-{skip:09d}-{int(time.time())}"
                result = mcp_call(
                    airo_url,
                    "write_neo4j_cypher",
                    {"query": WRITE_QUERY, "params": {"batchId": batch_id, "rows": rows}},
                )
                copied += len(rows)
                skip += len(rows)
                print(json.dumps({"copied": copied, "batchId": batch_id, "result": result}, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
