"""Forward binding materializer tests — granularity, orphan handling, 7-tuple, idempotence.

# KG: lesson-concept-nodes-created-without-longinus-binding-float-2026-05-29
"""

from __future__ import annotations

from pathlib import Path

from engine.longinus_drift_audit import forward_binding_materialize as fbm
from engine.longinus_drift_audit.kg_client import MockKgClient
from engine.longinus_drift_audit.models import ReferenceLayer


def _write(root: Path, rel: str, body: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _kg(*nodes: str) -> MockKgClient:
    kg = MockKgClient()
    kg.other_nodes.update(nodes)
    return kg


def test_public_symbol_bound_private_skipped(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "engine/occam/cut.py",
        "# KG: occam-kam-canonical-2026-05-26\n"
        "\n"
        "def public_cut(x):  # KG: occam-public-api\n"
        "    return x\n"
        "\n"
        "def _private_helper(y):  # KG: occam-private-internal\n"
        "    return y\n",
    )
    kg = _kg("occam-kam-canonical-2026-05-26", "occam-public-api", "occam-private-internal")
    res = fbm.materialize(kg, tmp_path, repo_tag="bhgman")

    bound_refs = {s.kg_anchor for s in kg.list_reference_site_states("bhgman")}
    assert "occam-public-api" in bound_refs  # public symbol bound
    assert "occam-kam-canonical-2026-05-26" in bound_refs  # module-level bound
    assert "occam-private-internal" not in bound_refs  # private helper skipped
    assert res.skipped_private >= 1
    assert res.public_api >= 1 and res.modules >= 1


def test_orphan_ref_skipped_and_reported(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "engine/eureka/build.py",
        "def builder():  # KG: eureka-canonical-2026-05-26\n    return 1\n"
        "def other():  # KG: does-not-exist-node\n    return 2\n",
    )
    kg = _kg("eureka-canonical-2026-05-26")  # the second node is absent
    res = fbm.materialize(kg, tmp_path, repo_tag="bhgman")

    bound = {s.kg_anchor for s in kg.list_reference_site_states("bhgman")}
    assert "eureka-canonical-2026-05-26" in bound
    assert "does-not-exist-node" not in bound
    assert any(ref == "does-not-exist-node" for ref, _ in res.orphan_refs)


def test_seven_tuple_fields_complete(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "engine/hades/realize.py",
        "def realize(spec):  # KG: hades-canonical-2026-05-27\n    return spec\n",
    )
    kg = _kg("hades-canonical-2026-05-27")
    fbm.materialize(kg, tmp_path, repo_tag="bhgman")

    site = next(s for s in kg.list_reference_site_states("bhgman"))
    assert site.sourceId == "hades-canonical-2026-05-27"
    assert site.kg_anchor == "hades-canonical-2026-05-27"
    assert site.sha256 and site.sha256_baseline == site.sha256  # baseline frozen
    assert site.layer == ReferenceLayer.L4_SEMIOTIC
    assert site.repo_tag == "bhgman"
    assert site.signature_baseline == "spec"  # public symbol signature captured
    assert site.last_validated is not None


def test_repo_tag_scopes_listing(tmp_path: Path) -> None:
    _write(tmp_path, "engine/x.py", "def f():  # KG: node-a\n    return 1\n")
    kg = _kg("node-a")
    fbm.materialize(kg, tmp_path, repo_tag="bhgman")
    assert len(kg.list_reference_site_states("bhgman")) == 1
    assert len(kg.list_reference_site_states("other-repo")) == 0  # scoped out


def test_idempotent_rerun(tmp_path: Path) -> None:
    _write(tmp_path, "engine/y.py", "def g():  # KG: node-b\n    return 1\n")
    kg = _kg("node-b")
    r1 = fbm.materialize(kg, tmp_path, repo_tag="bhgman")
    n1 = len(kg.list_reference_site_states("bhgman"))
    r2 = fbm.materialize(kg, tmp_path, repo_tag="bhgman")
    n2 = len(kg.list_reference_site_states("bhgman"))
    assert r1.bound == r2.bound  # same count
    assert n1 == n2 == 1  # no duplicate site
