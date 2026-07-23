"""Tests — Occam infra-config supersession lens (ghost-reference detection).

Replays the cp-migration 2026-06 failure: dead IP / node / relay refs across live configs must be
flagged (grouped by root cause), while the SAME refs in historical records are preserved.

# KG: impl-occam-infra-config-supersession-2026-07-13, cycle-prom16-occam-infra-config-supersession-2026-07-13
"""
from __future__ import annotations

import pytest

from engine.occam.occam_models import Confidence
from engine.occam.infra_supersession import (
    FLAG_ONLY,
    SUPERSEDE,
    VERIFY,
    InfraSupersessionFact,
    LiveInventory,
    RefKind,
    SourceClass,
    SourceRef,
    build_infra_escalation_plan,
    build_supersede_cypher,
    classify_source,
    is_confident_supersede,
    make_ref,
    scan,
)


# --- the cp-migration supersession facts (old -> new) ---
def _facts():
    ep = lambda s: make_ref(RefKind.ENDPOINT, s)
    return [
        InfraSupersessionFact(ep("192.168.2.2:6443"), ep("192.168.0.23:6443"), "endpoint",
                              "migration_decommission_event:cp-migration-2026-06",
                              fact_source_last_validated="2026-06-18"),
        InfraSupersessionFact(ep("100.64.0.2:6443"), ep("192.168.0.23:6443"), "endpoint",
                              "migration_decommission_event:cp-migration-2026-06",
                              fact_source_last_validated="2026-06-23"),
        InfraSupersessionFact(make_ref(RefKind.RELAY, "192.168.0.101:8443"), None, "relay",
                              "migration_decommission_event:cp-migration-2026-06",
                              fact_source_last_validated="2026-06-18"),
        InfraSupersessionFact(make_ref(RefKind.NODE_NAME, "k8s-cp"),
                              make_ref(RefKind.NODE_NAME, "dgx-worker"), "node_name",
                              "migration_decommission_event:cp-migration-2026-06",
                              fact_source_last_validated="2026-06-18"),
    ]


def test_make_ref_canonicalizes_endpoint_host():
    r = make_ref(RefKind.ENDPOINT, "192.168.2.2:6443")
    assert r.canonical == "192.168.2.2:6443"
    assert r.host == "192.168.2.2"


def test_dead_ip_in_live_configmap_is_high_supersede():
    src = ("apiVersion: v1\nkind: ConfigMap\ndata:\n  controlPlaneEndpoint: 192.168.2.2:6443\n",
           SourceRef("/etc/kubernetes/kubeadm-config.yaml", source_kind="configmap"))
    rep = scan([src], _facts())
    ghosts = [c for c in rep.candidates if c.stale.canonical == "192.168.2.2:6443"]
    assert len(ghosts) == 1
    g = ghosts[0]
    assert g.confidence is Confidence.HIGH
    assert g.verdict == SUPERSEDE
    assert g.proposed_fix == "192.168.0.23:6443"
    assert g.evidence == "fact_map"


def test_boundary_no_false_match_on_longer_ip():
    # 192.168.2.20 must NOT match the fact for 192.168.2.2
    src = ("server: https://192.168.2.20:6443\n", SourceRef("/etc/kubernetes/live.conf"))
    rep = scan([src], _facts())
    assert not any(c.stale.canonical == "192.168.2.2:6443" for c in rep.candidates)


def test_same_dead_ip_across_live_configs_groups_as_one_root_cause():
    # C4 reverse blast-radius: one dead IP in 3 live sources = one group, blast_radius=3
    facts = _facts()
    srcs = [
        ("controlPlaneEndpoint: 192.168.2.2:6443\n", SourceRef("/etc/kubernetes/kubeadm-config.yaml")),
        ("server: https://192.168.2.2:6443\n", SourceRef("/etc/kubernetes/cluster-info.yaml")),
        ("upstream 192.168.2.2:6443;\n", SourceRef("/etc/kube-proxy/config")),
    ]
    rep = scan(srcs, facts)
    groups = dict(rep.blast_radius_groups)
    assert "192.168.2.2:6443" in groups
    grp = groups["192.168.2.2:6443"]
    assert len(grp) == 3
    assert all(c.blast_radius == 3 for c in grp)


def test_historical_record_with_same_dead_ip_is_preserved():
    # C6 Eilu-va-Eilu: the identical dead IP inside a backup / lesson record is NOT flagged
    srcs = [
        ("controlPlaneEndpoint: 192.168.2.2:6443\n", SourceRef("/etc/kubernetes/kubeadm-config.yaml")),
        ("controlPlaneEndpoint: 192.168.2.2:6443\n", SourceRef("/backups/cp-migration-2026-06-16/kubeadm-config.yaml")),
        ("the old endpoint was 192.168.2.2:6443\n", SourceRef("/CD/SYMPOSIUM/PI/_pidna_receipts/lesson.md")),
    ]
    rep = scan(srcs, _facts())
    assert rep.historical_sources_skipped == 2
    assert rep.live_sources == 1
    # only the live CM produced a ghost
    assert all("/backups/" not in c.source_ref.file_path for c in rep.candidates)
    assert all("_pidna_receipts" not in c.source_ref.file_path for c in rep.candidates)
    assert len([c for c in rep.candidates if c.stale.canonical == "192.168.2.2:6443"]) == 1


def test_tombstoned_source_is_historical():
    src = ("controlPlaneEndpoint: 192.168.2.2:6443\n", SourceRef("/etc/kubernetes/x.yaml"))
    rep = scan([src], _facts(), source_flags={"/etc/kubernetes/x.yaml": {"tombstoned": True}})
    assert rep.historical_sources_skipped == 1
    assert rep.candidates == ()


def test_node_name_ghost_detected_in_nodeselector():
    src = ("  nodeSelector:\n    kubernetes.io/hostname: k8s-cp\n", SourceRef("/manifests/deploy.yaml"))
    rep = scan([src], _facts())
    ghosts = [c for c in rep.candidates if c.stale.canonical == "k8s-cp"]
    assert len(ghosts) == 1
    assert ghosts[0].proposed_fix == "dgx-worker"
    assert ghosts[0].verdict == SUPERSEDE


def test_removed_relay_with_no_successor_is_flag_only():
    src = ("relay = 192.168.0.101:8443\n", SourceRef("/etc/coturn/turnserver.conf"))
    rep = scan([src], _facts())
    ghosts = [c for c in rep.candidates if c.stale.canonical == "192.168.0.101:8443"]
    assert len(ghosts) == 1
    assert ghosts[0].verdict == FLAG_ONLY
    assert ghosts[0].proposed_fix is None
    assert ghosts[0].current is None


def test_setdiff_orphan_when_endpoint_unmapped_and_not_live():
    live = LiveInventory(endpoints=frozenset({"192.168.0.23:6443"}))
    src = ("backend: 10.0.0.5:9999\n", SourceRef("/etc/app/config"))
    rep = scan([src], _facts(), live_inventory=live)
    assert any(o.canonical == "10.0.0.5:9999" for o in rep.orphans)


def test_allowlist_endpoint_not_orphaned():
    live = LiveInventory(endpoints=frozenset())
    src = ("bind: 127.0.0.1:8080\n", SourceRef("/etc/app/config"))
    rep = scan([src], _facts(), live_inventory=live)
    assert not any("127.0.0.1" in o.canonical for o in rep.orphans)


def test_ambiguous_source_downgrades_to_verify():
    src = ("controlPlaneEndpoint: 192.168.2.2:6443\n", SourceRef("/gitops/templates/cm.yaml"))
    rep = scan([src], _facts(), source_flags={"/gitops/templates/cm.yaml": {"ambiguous": True}})
    ghosts = [c for c in rep.candidates if c.stale.canonical == "192.168.2.2:6443"]
    assert ghosts and all(c.confidence is Confidence.MEDIUM and c.verdict == VERIFY for c in ghosts)


def test_covenant_supersede_cypher_is_archive_only():
    facts = _facts()
    src = ("controlPlaneEndpoint: 192.168.2.2:6443\n", SourceRef("/etc/kubernetes/kubeadm-config.yaml",
                                                                 field_path="data.controlPlaneEndpoint"))
    rep = scan([src], facts)
    c = rep.candidates[0]
    cypher, params = build_supersede_cypher(c)  # would raise AssertionError on a destructive token
    up = cypher.upper()
    assert "DELETE" not in up and "DETACH" not in up and "REMOVE" not in up
    assert "SUPERSEDED_BY" in cypher
    assert params["stale"] == "192.168.2.2:6443"
    assert params["current"] == "192.168.0.23:6443"


def test_is_confident_supersede_only_high_with_current():
    src = ("controlPlaneEndpoint: 192.168.2.2:6443\n", SourceRef("/etc/kubernetes/kubeadm-config.yaml"))
    high = scan([src], _facts()).candidates[0]
    assert is_confident_supersede(high) is True

    relay = ("relay = 192.168.0.101:8443\n", SourceRef("/etc/coturn/turnserver.conf"))
    flag_only = [c for c in scan([relay], _facts()).candidates if c.verdict == FLAG_ONLY][0]
    assert is_confident_supersede(flag_only) is False


def test_escalation_routes_uncertain_and_orphans():
    live = LiveInventory(endpoints=frozenset({"192.168.0.23:6443"}))
    srcs = [
        ("controlPlaneEndpoint: 192.168.2.2:6443\n", SourceRef("/etc/kubernetes/kubeadm-config.yaml")),  # HIGH -> no escalation
        ("relay = 192.168.0.101:8443\n", SourceRef("/etc/coturn/turnserver.conf")),                      # FLAG_ONLY -> naesengmoon
        ("backend: 10.0.0.5:9999\n", SourceRef("/etc/app/config")),                                       # orphan -> longinus
    ]
    rep = scan(srcs, _facts(), live_inventory=live)
    plan = build_infra_escalation_plan(rep)
    assert any("192.168.0.101:8443" in s for s in plan["naesengmoon"])   # FLAG_ONLY escalates
    assert not any("192.168.2.2:6443" in s for s in plan["naesengmoon"])  # confident supersede does not
    assert any("10.0.0.5:9999" in s for s in plan["longinus"])


def test_fact_table_self_staleness_warning():
    # C9: a fact with no fact_source_last_validated is flagged
    ep = lambda s: make_ref(RefKind.ENDPOINT, s)
    facts = [InfraSupersessionFact(ep("1.2.3.4:80"), ep("1.2.3.5:80"), "endpoint", "user_verdict")]
    rep = scan([("x: 1.2.3.4:80\n", SourceRef("/etc/live"))], facts)
    assert any("1.2.3.4:80" in w for w in rep.fact_table_staleness_warnings)


def test_classify_source_gates():
    assert classify_source(SourceRef("/etc/kubernetes/kubeadm-config.yaml")) is SourceClass.LIVE
    assert classify_source(SourceRef("/backups/x.yaml")) is SourceClass.HISTORICAL
    assert classify_source(SourceRef("/x.yaml"), tombstoned=True) is SourceClass.HISTORICAL
    assert classify_source(SourceRef("/x.yaml"), ambiguous=True) is SourceClass.AMBIGUOUS
    assert classify_source(SourceRef("/CD/SYMPOSIUM/_archive/x")) is SourceClass.HISTORICAL


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1; print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
