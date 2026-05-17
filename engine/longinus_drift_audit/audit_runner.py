"""LonginusAudit — orchestrator + CLI.

E2E: scan code → list KG refs → detect 5 drifts → GED → reverse orphan → layer coverage.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
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


class LonginusAudit:
    def __init__(
        self,
        *,
        kg: KgClient | None = None,
        code_root: Path | str,
        audit_id: str | None = None,
    ):
        self.kg = kg or MockKgClient()
        self.code_root = Path(code_root).resolve()
        self.audit_id = audit_id or self._make_audit_id()

    @staticmethod
    def _make_audit_id() -> str:
        h = hashlib.sha256(dt.datetime.now(dt.timezone.utc).isoformat().encode()).hexdigest()[:12]
        return f"longinus-audit-{h}"

    def run_full(self, *, verify_sha256: bool = True) -> AuditReport:
        """Full Longinus audit cycle.

        Wave 6 additions (2026-05-14):
            - sha256 baseline verify (BX PutGet roundtrip on disk hash)
            - forward orphan scan (KG :KnowledgeHub → package_path materialization)
        """
        # 1. Scan code
        symbols, _flat_refs = code_scanner.scan_root(self.code_root)

        # 2. List KG refs
        kg_refs_list = self.kg.list_reference_sites()
        kg_refs = {r.sourceId: r for r in kg_refs_list}

        # 3. Detect 5 drifts
        drift_records = drift_detector.detect_all(symbols=symbols, kg_refs=kg_refs)
        drift_summary = drift_detector.summarize_drifts(drift_records)

        # 4. Reverse Orphan (Code → KG)
        orphans = reverse_orphan_scan.scan_reverse_orphans(symbols=symbols)

        # 4b. Forward Orphan (KG hub → disk) — Wave 6
        hubs = self.kg.list_knowledge_hubs()
        forward_orphans = forward_orphan_scan.scan_forward_orphans(hubs)

        # 4c. sha256 baseline verify — Wave 6
        sha256_sites = self.kg.list_reference_site_states()
        sha256_baseline_count = sum(1 for s in sha256_sites if s.sha256_baseline)
        sha256_drift_events: list = []
        if verify_sha256 and sha256_sites:
            verify_result = sha256_baseline.verify_baseline(kg=self.kg, sites=sha256_sites)
            sha256_drift_events = verify_result.drift_events

        # 5. GED
        ged_report = ged_metric.compute_ged(kg_refs=kg_refs, code_symbols=symbols)

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
