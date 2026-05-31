"""LonginusAudit — orchestrator + CLI.

E2E: scan code → list KG refs → detect 5 drifts → GED → reverse orphan → layer coverage.

# KG: longinus-parallel-fanout-2026-05-18 (L2 parallel fan-out PRELIMINARY)
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from engine.longinus_drift_audit import code_scanner
from engine.longinus_drift_audit import drift_detector
from engine.longinus_drift_audit import forward_orphan_scan
from engine.longinus_drift_audit import ged_metric
from engine.longinus_drift_audit import reference_layers
from engine.longinus_drift_audit import reverse_orphan_scan
from engine.longinus_drift_audit import sha256_baseline
from engine.longinus_drift_audit.bx_lens import make_dict_lens
from engine.longinus_drift_audit.kg_client import KgClient, MockKgClient, Neo4jKgClient
from engine.longinus_drift_audit.models import AuditReport


def _forward_orphan_phase(kg: KgClient):
    hubs = kg.list_knowledge_hubs()
    return forward_orphan_scan.scan_forward_orphans(hubs)


def _dedup_drift_events_by_file(events: list) -> list:
    """Collapse per-node drift events to one event per (path, kind).

    sha256 drift is a property of the FILE, not the KG node. The live KG keys
    ReferenceSites by ``name`` while ``sourceId`` is a shared corpus label, so a
    single drifted file (e.g. one source cited by 277 concept-nodes) otherwise
    emits 277 identical events — inflating the report. Dedup restores the honest
    "how many files drifted" count.

    # KG: lesson-longinus-audit-sourceid-vs-name-pk-drift-inflation-2026-05-26
    """
    seen: set = set()
    out: list = []
    for e in events:
        key = (e.path, e.kind)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def _sha256_phase(kg: KgClient, verify_sha256: bool, repo_tag: str | None = None):
    sites = kg.list_reference_site_states(repo_tag)
    baseline_count = sum(1 for s in sites if s.sha256_baseline)
    events: list = []
    if verify_sha256 and sites:
        result = sha256_baseline.verify_baseline(kg=kg, sites=sites)
        events = _dedup_drift_events_by_file(result.drift_events)
    return events, baseline_count


class LonginusAudit:
    def __init__(
        self,
        *,
        kg: KgClient | None = None,
        code_root: Path | str,
        audit_id: str | None = None,
        parallel: bool = False,
        repo_tag: str | None = None,
    ):
        """parallel default False — empirical bench (2026-05-18) shows L2
        ThreadPool fan-out is parity-or-slower for Mock KG + regex-only scanner.
        Flip to True for real Neo4j (network-IO bound) or after swapping the
        scanner to AST/tree-sitter (per-file CPU > IPC overhead). See
        ``bench/bench_parallel.py`` and KG lesson-longinus-parallel-breakeven-2026-05-18.
        """
        self.kg = kg or MockKgClient()
        self.code_root = Path(code_root).resolve()
        self.audit_id = audit_id or self._make_audit_id()
        self.parallel = parallel
        self.repo_tag = repo_tag

    @staticmethod
    def _make_audit_id() -> str:
        h = hashlib.sha256(dt.datetime.now(dt.timezone.utc).isoformat().encode()).hexdigest()[:12]
        return f"longinus-audit-{h}"

    def run_full(self, *, verify_sha256: bool = True) -> AuditReport:
        """Full Longinus audit cycle.

        Wave 6 additions (2026-05-14):
            - sha256 baseline verify (BX PutGet roundtrip on disk hash)
            - forward orphan scan (KG :KnowledgeHub → package_path materialization)

        Parallel (L2, 2026-05-18): with ``self.parallel`` true, post-barrier 5
        independent phases (drift_detect / reverse_orphan / forward_orphan /
        sha256_verify / GED) fan out via ThreadPoolExecutor. Output is
        byte-identical to sequential — all phases consume immutable snapshots.
        """
        # Barrier 1: scan + KG ref fetch (independent, can parallelize)
        if self.parallel:
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_scan = ex.submit(code_scanner.scan_root, self.code_root)
                f_kg_refs = ex.submit(self.kg.list_reference_sites, self.repo_tag)
                symbols, _flat_refs = f_scan.result()
                kg_refs_list = f_kg_refs.result()
        else:
            symbols, _flat_refs = code_scanner.scan_root(self.code_root, parallel=False)
            kg_refs_list = self.kg.list_reference_sites(self.repo_tag)
        kg_refs = {r.sourceId: r for r in kg_refs_list}

        # Barrier 2: 5 independent phases (drift / reverse / forward / sha256 / GED)
        if self.parallel:
            with ThreadPoolExecutor(max_workers=5) as ex:
                f_drift = ex.submit(
                    drift_detector.detect_all,
                    symbols=symbols,
                    kg_refs=kg_refs,
                    ref_exists=self.kg.has_node,
                )
                f_reverse = ex.submit(reverse_orphan_scan.scan_reverse_orphans, symbols=symbols)
                f_forward = ex.submit(_forward_orphan_phase, self.kg)
                f_sha = ex.submit(_sha256_phase, self.kg, verify_sha256, self.repo_tag)
                f_ged = ex.submit(ged_metric.compute_ged, kg_refs=kg_refs, code_symbols=symbols)
                drift_records = f_drift.result()
                orphans = f_reverse.result()
                forward_orphans = f_forward.result()
                sha256_drift_events, sha256_baseline_count = f_sha.result()
                ged_report = f_ged.result()
        else:
            drift_records = drift_detector.detect_all(
                symbols=symbols, kg_refs=kg_refs, ref_exists=self.kg.has_node
            )
            orphans = reverse_orphan_scan.scan_reverse_orphans(symbols=symbols)
            forward_orphans = _forward_orphan_phase(self.kg)
            sha256_drift_events, sha256_baseline_count = _sha256_phase(
                self.kg, verify_sha256, self.repo_tag
            )
            ged_report = ged_metric.compute_ged(kg_refs=kg_refs, code_symbols=symbols)

        drift_summary = drift_detector.summarize_drifts(drift_records)

        # 6. Layer coverage
        total_kg_refs_in_code = sum(len(s.kg_refs) for s in symbols)
        pierce_rate = reference_layers.make_pierce_rate(
            total_code_symbols=len(symbols),
            total_kg_refs=total_kg_refs_in_code,
        )
        # build ReferenceSite list for layer summary
        sites = []
        for s in symbols:
            for ref in s.kg_refs:
                if ref in kg_refs:
                    from engine.longinus_drift_audit.models import ReferenceSite

                    sites.append(
                        ReferenceSite(
                            sourceId=ref,
                            sourcePath=s.sourcePath,
                        )
                    )
        layer_cov = reference_layers.layer_coverage(
            sites=sites,
            total_kg_refs=total_kg_refs_in_code,
            pierce_rate=pierce_rate,
        )

        # 7. BX Lens — sanity check on simple state lens
        lens = make_dict_lens("ref")
        lens_verif = lens.verify_all(s={"ref": "x"}, v1="y", v2="z")

        return AuditReport(
            audit_id=self.audit_id,
            drifts_by_type=drift_summary,
            drift_records=drift_records,
            reverse_orphans=orphans,
            forward_orphans=forward_orphans,
            sha256_drift_events=sha256_drift_events,
            sha256_baseline_count=sha256_baseline_count,
            layer_coverage=layer_cov,
            lens_verification=lens_verif,
            ged_report=ged_report,
        )


def build_kg(args: argparse.Namespace) -> KgClient:
    """Construct the KG backend from parsed args.

    ``--kg mock`` (default) is a self-test fixture with empty refs — NOT a real
    audit. ``--kg neo4j`` wires the live Neo4jKgClient so the audit runs against
    ground truth (uri/creds via --uri/--user/--password or NEO4J_* env).

    Raises ValueError when --kg neo4j is requested without uri+password.
    """
    if args.kg == "mock":
        return MockKgClient()
    if args.kg == "local":
        from engine.longinus_drift_audit.kg_client import JsonFileKgClient

        return JsonFileKgClient(args.kg_path)
    if not args.uri or not args.password:
        raise ValueError("--kg neo4j requires --uri/--password (or NEO4J_URI / NEO4J_PASSWORD env)")
    return Neo4jKgClient(args.uri, (args.user, args.password))


def main() -> int:
    parser = argparse.ArgumentParser(prog="longinus-audit")
    parser.add_argument("--code-root", required=True)
    parser.add_argument(
        "--kg",
        choices=["mock", "neo4j", "local"],
        default="mock",
        help="mock = empty-ref self-test fixture (verifies nothing); "
        "neo4j = live audit against ground truth; "
        "local = neo4j-free JSON backend (~/.bhgman/longinus_kg.json or --kg-path).",
    )
    parser.add_argument(
        "--kg-path",
        default=None,
        help="JSON file for --kg local (default: ~/.bhgman/longinus_kg.json).",
    )
    parser.add_argument(
        "--uri", default=os.environ.get("NEO4J_URI"), help="Neo4j bolt URI (or NEO4J_URI env)."
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("NEO4J_USER", "neo4j"),
        help="Neo4j user (or NEO4J_USER env, default 'neo4j').",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("NEO4J_PASSWORD"),
        help="Neo4j password (or NEO4J_PASSWORD env).",
    )
    parser.add_argument(
        "--record-signatures",
        action="store_true",
        help="Record current symbol signatures as ReferenceSite baselines (enables "
        "SigMismatch drift on later audits), then exit. Mirrors sha256 baseline init.",
    )
    parser.add_argument(
        "--repo-tag",
        default=None,
        help="Scope audit/materialize to ReferenceSites carrying this repo_tag (e.g. 'bhgman'). "
        "The dgx Neo4j is shared across repos; without this, a single code-root audit "
        "false-flags other repos' sites. None = unscoped (all sites).",
    )
    parser.add_argument(
        "--materialize",
        action="store_true",
        help="Forward-binding mode: scan `# KG:` comments in --code-root and MERGE a "
        "ReferenceSite (+ SourceCodeNode + BINDS_TO) per module/public-API symbol, then exit. "
        "Tags new sites with --repo-tag. This is the missing forward materializer "
        "(audit alone never creates bindings).",
    )
    args = parser.parse_args()

    try:
        kg = build_kg(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        if args.materialize:
            return _materialize_mode(kg, args.code_root, args.repo_tag)
        if args.record_signatures:
            return _record_signatures_mode(kg, args.code_root, args.repo_tag)
        audit = LonginusAudit(kg=kg, code_root=args.code_root, repo_tag=args.repo_tag)
        report = audit.run_full()
    finally:
        close = getattr(kg, "close", None)
        if callable(close):
            close()
    print(json.dumps(report.model_dump(), indent=2, default=str))
    return 0 if report.is_clean else 2


def _record_signatures_mode(kg: KgClient, code_root: str, repo_tag: str | None = None) -> int:
    """Scan code-root and freeze symbol signatures onto ReferenceSite baselines."""
    from engine.longinus_drift_audit.signature_baseline import record_signature_baselines

    symbols, _ = code_scanner.scan_root(Path(code_root))
    n = record_signature_baselines(kg, symbols, repo_tag=repo_tag)
    print(f"[longinus] recorded signature baselines on {n} ReferenceSite(s) from {code_root}")
    return 0


def _materialize_mode(kg: KgClient, code_root: str, repo_tag: str | None) -> int:
    """Forward-binding: scan `# KG:` comments → MERGE ReferenceSite per module/public symbol."""
    from engine.longinus_drift_audit import forward_binding_materialize as fbm

    result = fbm.materialize(kg, Path(code_root), repo_tag=repo_tag or "bhgman")
    print(
        f"[longinus] materialized {result.bound} ReferenceSite(s) "
        f"({result.modules} module + {result.public_api} public-API) "
        f"from {code_root} [repo_tag={repo_tag or 'bhgman'}]"
    )
    if result.orphan_refs:
        print(
            f"[longinus] WARNING {len(result.orphan_refs)} `# KG:` comment(s) cite a "
            f"KG node that does not exist (skipped, not created):",
            file=sys.stderr,
        )
        for ref, where in result.orphan_refs[:20]:
            print(f"  - {ref}  ({where})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
