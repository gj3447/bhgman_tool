"""LonginusAudit — orchestrator + CLI.

E2E: scan code → list KG refs → detect 5 drifts → GED → reverse orphan → layer coverage.

# KG: longinus-parallel-fanout-2026-05-18 (L2 parallel fan-out PRELIMINARY)
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import code_scanner
import drift_detector
import forward_orphan_scan
import ged_metric
import reference_layers
import reverse_orphan_scan
import sha256_baseline
from bx_lens import make_dict_lens
from kg_client import KgClient, MockKgClient
from models import AuditReport


def _forward_orphan_phase(kg: KgClient):
    hubs = kg.list_knowledge_hubs()
    return forward_orphan_scan.scan_forward_orphans(hubs)


def _sha256_phase(kg: KgClient, verify_sha256: bool):
    sites = kg.list_reference_site_states()
    baseline_count = sum(1 for s in sites if s.sha256_baseline)
    events: list = []
    if verify_sha256 and sites:
        result = sha256_baseline.verify_baseline(kg=kg, sites=sites)
        events = result.drift_events
    return events, baseline_count


class LonginusAudit:
    def __init__(
        self,
        *,
        kg: KgClient | None = None,
        code_root: Path | str,
        audit_id: str | None = None,
        parallel: bool = False,
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
                f_kg_refs = ex.submit(self.kg.list_reference_sites)
                symbols, _flat_refs = f_scan.result()
                kg_refs_list = f_kg_refs.result()
        else:
            symbols, _flat_refs = code_scanner.scan_root(self.code_root, parallel=False)
            kg_refs_list = self.kg.list_reference_sites()
        kg_refs = {r.sourceId: r for r in kg_refs_list}

        # Barrier 2: 5 independent phases (drift / reverse / forward / sha256 / GED)
        if self.parallel:
            with ThreadPoolExecutor(max_workers=5) as ex:
                f_drift = ex.submit(drift_detector.detect_all, symbols=symbols, kg_refs=kg_refs)
                f_reverse = ex.submit(reverse_orphan_scan.scan_reverse_orphans, symbols=symbols)
                f_forward = ex.submit(_forward_orphan_phase, self.kg)
                f_sha = ex.submit(_sha256_phase, self.kg, verify_sha256)
                f_ged = ex.submit(ged_metric.compute_ged, kg_refs=kg_refs, code_symbols=symbols)
                drift_records = f_drift.result()
                orphans = f_reverse.result()
                forward_orphans = f_forward.result()
                sha256_drift_events, sha256_baseline_count = f_sha.result()
                ged_report = f_ged.result()
        else:
            drift_records = drift_detector.detect_all(symbols=symbols, kg_refs=kg_refs)
            orphans = reverse_orphan_scan.scan_reverse_orphans(symbols=symbols)
            forward_orphans = _forward_orphan_phase(self.kg)
            sha256_drift_events, sha256_baseline_count = _sha256_phase(self.kg, verify_sha256)
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
                    from models import ReferenceSite

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


def main() -> int:
    parser = argparse.ArgumentParser(prog="longinus-audit")
    parser.add_argument("--code-root", required=True)
    parser.add_argument("--kg", choices=["mock", "neo4j"], default="mock")
    args = parser.parse_args()

    kg = MockKgClient() if args.kg == "mock" else None
    if kg is None:
        print("neo4j backend requires --uri/auth args (not wired in stub)", file=sys.stderr)
        return 1

    audit = LonginusAudit(kg=kg, code_root=args.code_root)
    report = audit.run_full()
    print(json.dumps(report.model_dump(), indent=2, default=str))
    return 0 if report.is_clean else 2


if __name__ == "__main__":
    sys.exit(main())
