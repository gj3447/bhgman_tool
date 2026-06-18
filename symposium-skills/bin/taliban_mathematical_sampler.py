#!/usr/bin/env python3
"""
Taliban --lens mathematical sampler v1.0 (production).

Reads MIC_v1.MathematicalSamplingPolicy slot from KG, returns N lens names
from 13-domain × 113-lens taxonomy (stratified random per domain).

Modes (argparse):
  --full                 : all 113 lens
  --sample N             : explicit N lens count (or rate float < 1.0)
  --minimum              : floor 12 (CI smoke gate, 1 per domain)
  --policy               : print active MathematicalSamplingPolicy
  --domain CODE          : restrict to single domain (LL/CT/TT/AL/OL/TG/AN/CD/NT/CC/FV/GD/IC)
  --auto                 : cost-guard aware mode — auto-select between minimum/sample/full based on
                           current $40/$50 cost cap proximity (CLAUDE.md L3 stop hook integration)
  --json                 : machine-readable output

KG: lensset-mathematical (113 lens registry),
    MIC_v1.MathematicalSamplingPolicy slot,
    mathematical-sampling-default-2026-05-06,
    fw-mathematical-113-coverage-2026-05-06,
    taliban-mathematical-sampler-poc-2026-05-06 (v0 PoC),
    iter9-sampler-cli-implementation-2026-05-06 (v1.0 production)

Stratification: 13 mathematical-validation domains
  LL/CT/TT/AL (9 each), OL/TG/AN (8), CD (9), NT (8), CC/FV/GD/IC (9)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys

NEO4J_URL = os.environ.get("NEO4J_URL", "http://neo4j.metahumotonic.com/db/neo4j/tx/commit")
NEO4J_AUTH = os.environ.get("NEO4J_AUTH", "neo4j:neo4jpassword")

# 113-lens taxonomy stratification (from THEORY/TALIBAN/113_LENS_TAXONOMY.md §2).
DOMAINS = {
    "LL": 9, "CT": 9, "TT": 9, "AL": 9,
    "OL": 8, "TG": 8, "AN": 8,
    "CD": 9, "NT": 8,
    "CC": 9, "FV": 9, "GD": 9, "IC": 9,
}
TOTAL = sum(DOMAINS.values())  # = 113


def cypher(stmt, params=None):
    body = {"statement": stmt}
    if params:
        body["parameters"] = params
    payload = json.dumps({"statements": [body]})
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


def fetch_policy():
    res = cypher(
        "MATCH (s:MethodologySlot {name:'MathematicalSamplingPolicy'}) "
        "MATCH (p:MathematicalSamplingPolicy {name:s.currentConcrete}) "
        "RETURN p.default_sample_rate AS rate, p.default_sample_count AS count, "
        "p.minimum_sample_count AS minimum, p.lens_total AS total"
    )
    rows = res.get("results", [{}])[0].get("data", [])
    if not rows:
        return {"rate": 0.30, "count": 34, "minimum": 12, "total": 113}
    r = rows[0]["row"]
    return {"rate": r[0], "count": r[1], "minimum": r[2], "total": r[3]}


def fetch_lens_codes_by_domain():
    """Fetch real :Lens code from KG, group by domain prefix (e.g. 'LL', 'CT')."""
    res = cypher(
        "MATCH (l:Lens) WHERE l.code IS NOT NULL "
        "RETURN l.code AS code, l.name AS name ORDER BY l.code"
    )
    rows = res.get("results", [{}])[0].get("data", [])
    by_domain = {d: [] for d in DOMAINS}
    for r in rows:
        code, name = r["row"]
        domain = code.split(".")[0] if "." in code else code[:2]
        if domain in by_domain:
            by_domain[domain].append({"code": code, "name": name})
    return by_domain


def stratified_sample(target_count):
    """Distribute target_count proportionally across 13 domains using real KG :Lens codes."""
    rng = random.Random(42)  # deterministic for PoC
    rate = target_count / TOTAL
    samples = {}
    by_domain = fetch_lens_codes_by_domain()
    for domain, domain_total in DOMAINS.items():
        domain_target = max(1, round(domain_total * rate))
        kg_lenses = by_domain.get(domain, [])
        # Fallback to synthetic names if KG missing
        if not kg_lenses:
            domain_lens = [{"code": f"{domain}.{i}", "name": f"<unbound-{i}>"} for i in range(1, domain_total + 1)]
        else:
            domain_lens = list(kg_lenses)
        rng.shuffle(domain_lens)
        samples[domain] = domain_lens[:min(domain_target, len(domain_lens))]
    return samples


def fetch_cost_estimate():
    """Fetch current Anthropic API cost from CLAUDE.md L3 stop hook tracking.

    Returns float USD or None if unavailable. Used by --auto mode.
    """
    cost_file = os.path.expanduser("~/.claude/hooks/.cost_running_total")
    if not os.path.exists(cost_file):
        return None
    try:
        with open(cost_file) as f:
            return float(f.read().strip())
    except (ValueError, OSError):
        return None


def cmd_policy(as_json=False):
    p = fetch_policy()
    if as_json:
        print(json.dumps(p, indent=2))
        return 0
    print(f"MathematicalSamplingPolicy:")
    print(f"  default_sample_rate:  {p['rate']}")
    print(f"  default_sample_count: {p['count']}")
    print(f"  minimum_sample_count: {p['minimum']}")
    print(f"  lens_total:           {p['total']}")
    return 0


def _format_lens_list(lenses):
    return ",".join(l["code"] for l in lenses)


def _emit_samples(samples, target_n, as_json):
    total = sum(len(v) for v in samples.values())
    if as_json:
        out = {
            "target_count": target_n,
            "actual_count": total,
            "by_domain": {d: [{"code": l["code"], "name": l["name"]} for l in lenses] for d, lenses in samples.items()},
        }
        print(json.dumps(out, indent=2))
        return 0
    for domain, lenses in samples.items():
        if not lenses and target_n > 0:
            continue
        print(f"  {domain}: {len(lenses)}/{DOMAINS[domain]} — {_format_lens_list(lenses)}")
    suffix = f" (target {target_n})" if target_n != total else ""
    print(f"total: {total}{suffix}")
    return 0


def cmd_full(as_json=False, single_domain=None):
    samples = stratified_sample(TOTAL)
    if single_domain:
        samples = {single_domain: samples.get(single_domain, [])}
    return _emit_samples(samples, TOTAL, as_json)


def cmd_sample(n, as_json=False, single_domain=None):
    samples = stratified_sample(n)
    if single_domain:
        samples = {single_domain: samples.get(single_domain, [])}
    return _emit_samples(samples, n, as_json)


def cmd_minimum(as_json=False, single_domain=None):
    p = fetch_policy()
    return cmd_sample(p["minimum"], as_json=as_json, single_domain=single_domain)


def cmd_auto(as_json=False, single_domain=None):
    """Cost-guard aware: select mode based on current $40/$50 proximity."""
    cost = fetch_cost_estimate()
    p = fetch_policy()
    if cost is None:
        # No tracking — fallback to default sample
        chosen = "sample-default"
        target = p["count"]
    elif cost >= 50.0:
        # Halt threshold — refuse
        msg = {"error": "cost cap $50 reached — sampler halted", "current_cost": cost}
        print(json.dumps(msg) if as_json else f"ERROR: {msg['error']} (current ${cost:.2f})", file=sys.stderr)
        return 3
    elif cost >= 40.0:
        # Warn threshold — minimum mode
        chosen = "minimum"
        target = p["minimum"]
    elif cost >= 20.0:
        # Mid-range — default sample
        chosen = "sample-default"
        target = p["count"]
    else:
        # Low cost — full
        chosen = "full"
        target = TOTAL
    if not as_json:
        print(f"# auto mode: chose '{chosen}' (target={target}, cost=${cost or 0:.2f})", file=sys.stderr)
    return cmd_sample(target, as_json=as_json, single_domain=single_domain)


def build_parser():
    p = argparse.ArgumentParser(
        prog="taliban_mathematical_sampler",
        description="Taliban --lens mathematical sampler v1.0 (production).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--full", action="store_true", help="all 113 lens (stratified)")
    g.add_argument("--sample", metavar="N_OR_RATE", help="N lens count or float rate < 1.0")
    g.add_argument("--minimum", action="store_true", help="12 lens floor (CI smoke gate)")
    g.add_argument("--policy", action="store_true", help="print active MathematicalSamplingPolicy")
    g.add_argument("--auto", action="store_true", help="cost-guard aware auto-select mode")
    p.add_argument("--domain", metavar="CODE", help=f"restrict to single domain ({'/'.join(DOMAINS.keys())})")
    p.add_argument("--json", action="store_true", help="machine-readable JSON output")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    domain = args.domain
    if domain and domain not in DOMAINS:
        print(f"ERROR: --domain must be one of {list(DOMAINS.keys())}", file=sys.stderr)
        return 2
    if args.policy:
        return cmd_policy(as_json=args.json)
    if args.full:
        return cmd_full(as_json=args.json, single_domain=domain)
    if args.minimum:
        return cmd_minimum(as_json=args.json, single_domain=domain)
    if args.auto:
        return cmd_auto(as_json=args.json, single_domain=domain)
    if args.sample is not None:
        v = args.sample
        try:
            if "." in v:
                rate = float(v)
                if rate >= 1.0:
                    print("ERROR: --sample rate must be < 1.0 (use --full for all)", file=sys.stderr)
                    return 2
                target = round(rate * TOTAL)
            else:
                target = int(v)
        except ValueError:
            print(f"ERROR: --sample value '{v}' must be int or float", file=sys.stderr)
            return 2
        return cmd_sample(target, as_json=args.json, single_domain=domain)
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
