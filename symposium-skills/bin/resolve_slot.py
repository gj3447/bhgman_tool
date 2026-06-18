#!/usr/bin/env python3
"""
A6 SKILL.md Resolve-Only Pattern — runtime resolver PoC.

Reads a SKILL.md file, finds ${MIC_v1.SLOT_NAME} placeholders,
fetches MIC_v1 slot.currentConcrete from Neo4j KG, prints a
resolved markdown to stdout (placeholders replaced with concrete
slot values).

Limitation (documented blocker fw-a6-resolver-runtime-2026-05-06):
  Anthropic Skills runtime injects SKILL.md as system prompt — there
  is no in-process hook that rewrites SKILL.md body before delivery.
  This script is a pre-flight resolver: a developer or PreToolUse
  hook runs it manually OR a build step regenerates SKILL.md from
  SKILL.md.tmpl into SKILL.md prior to skill packaging. Real-time
  per-invocation resolution requires Skills runtime contract change
  upstream (tracked as :FutureWork).

Usage:
  resolve_slot.py path/to/SKILL.md         # print resolved md
  resolve_slot.py --check path/to/SKILL.md # report unresolved placeholders only
  resolve_slot.py --slots                  # list all MIC_v1 slots + currentConcrete

KG: APT_v26_A6_2026-04-21, MIC_v1, fw-a6-resolver-runtime-2026-05-06
"""

import json
import os
import re
import subprocess
import sys

NEO4J_URL = os.environ.get("NEO4J_URL", "http://neo4j.metahumotonic.com/db/neo4j/tx/commit")
NEO4J_AUTH = os.environ.get("NEO4J_AUTH", "neo4j:neo4jpassword")
PLACEHOLDER_RE = re.compile(r"\$\{MIC_v1\.([A-Za-z][A-Za-z0-9_]*)\}")


def cypher(stmt: str) -> dict:
    payload = json.dumps({"statements": [{"statement": stmt}]})
    out = subprocess.check_output(
        [
            "curl", "-s", "-m", "5",
            "-u", NEO4J_AUTH,
            "-H", "Content-Type: application/json",
            "-d", payload,
            NEO4J_URL,
        ],
        timeout=10,
    )
    return json.loads(out.decode())


def list_slots() -> dict:
    res = cypher(
        "MATCH (m:MIC {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot) "
        "RETURN s.name AS name, s.currentConcrete AS current, s.invocation AS inv "
        "ORDER BY s.name"
    )
    rows = res.get("results", [{}])[0].get("data", [])
    return {r["row"][0]: {"current": r["row"][1], "invocation": r["row"][2]} for r in rows}


def resolve_body(body: str, slots: dict) -> tuple[str, list[str]]:
    unresolved: list[str] = []

    def repl(m):
        name = m.group(1)
        slot = slots.get(name)
        if slot and slot.get("current"):
            return slot["current"]
        unresolved.append(name)
        return m.group(0)

    return PLACEHOLDER_RE.sub(repl, body), unresolved


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--slots":
        slots = list_slots()
        for name, meta in slots.items():
            print(f"{name}\t{meta['current']}")
        return 0

    check_only = False
    args = sys.argv[1:]
    if args and args[0] == "--check":
        check_only = True
        args = args[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    path = args[0]
    if not os.path.exists(path):
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 2

    with open(path, encoding="utf-8") as f:
        body = f.read()

    slots = list_slots()
    resolved, unresolved = resolve_body(body, slots)

    if check_only:
        if unresolved:
            print(f"UNRESOLVED ({len(unresolved)}): {sorted(set(unresolved))}", file=sys.stderr)
            return 1
        placeholders_found = len(PLACEHOLDER_RE.findall(body))
        print(f"OK: {placeholders_found} placeholders, all resolvable", file=sys.stderr)
        return 0

    sys.stdout.write(resolved)
    if unresolved:
        print(f"\nWARN: {len(unresolved)} unresolved placeholders: {sorted(set(unresolved))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
