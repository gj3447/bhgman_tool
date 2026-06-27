"""hades_realize MCP 도구 — fail-closed verdict-provenance gate 테스트.

verdict gate(engine/legion/verdict_gate.py)를 우회하는 oracle-gate 위조/replay/
cross-artifact/weak-key 를 전부 거부하고, 유효 서명 verdict 만 dry-run realize 로
진행하는지 검증. 외부 인프라(neo4j/API-key) 0 — LocalKgStore 시드만 사용.

# KG: adr-legion-runtime-shape-review-2026-06-20,
#     oq-hades-verdict-provenance-standalone-realize-2026-06-20
"""

from __future__ import annotations

from engine.kg_local.store import LocalKgStore
from engine.legion.verdict_gate import (
    VERDICT_SECRET_ENV,
    VerdictGate,
    compute_artifact_id,
)
from engine.mcp_server.registry import catalog_is_consistent_with_security
from engine.mcp_server.server import list_registered_tool_names
from engine.mcp_server.tools.hades import hades_realize_impl

_STRONG_KEY = "x" * 40  # ≥32B, non-empty, != _DEV_DEFAULT


def _seed_store(tmp_path, concept: str, members: list[str]) -> str:
    """ACCEPTED·non-CANONICAL AbstractClass 하나를 가진 LocalKgStore JSON 파일."""
    kg_file = tmp_path / "kg.json"
    store = LocalKgStore(str(kg_file))
    store.merge_node(
        "AbstractClass",
        "name",
        concept,
        {"verdictStatus": "ACCEPTED", "extent": members},
    )
    store.save()
    return str(kg_file)


def _signed_verdict(key: str, cycle_id: str, artifact_id: str) -> dict:
    """gate 통과 정상 서명 verdict (oracle=PASS, ensemble clean)."""
    gate = VerdictGate(key.encode("utf-8"))
    content = {"oracle": "PASS", "ensemble": "ACCEPT", "judgment": "ok", "mode": "live"}
    return gate.sign(content, cycle_id, artifact_id)


# ── (a) 위조/미서명/빈 verdict 거부 ───────────────────────────────────────────
def test_forged_verdict_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(VERDICT_SECRET_ENV, _STRONG_KEY)
    kg = _seed_store(tmp_path, "alpha", ["m1", "m2"])
    res = hades_realize_impl(
        cycle_id="cyc-1",
        verdict={"oracle": "PASS", "ensemble": "ACCEPT"},
        concept="alpha",
        apply=False,
        kg_path=kg,
    )
    assert res["ok"] is False and res["realized"] is False
    assert res["gate_reason"] == "untrusted/absent verdict source"


def test_unsigned_verdict_with_source_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(VERDICT_SECRET_ENV, _STRONG_KEY)
    kg = _seed_store(tmp_path, "alpha", ["m1"])
    half = {"oracle": "PASS", "ensemble": "ACCEPT", "verdict_source": "naesengmoon-verify"}
    res = hades_realize_impl(
        cycle_id="cyc-1", verdict=half, concept="alpha", apply=False, kg_path=kg
    )
    assert res["ok"] is False and res["realized"] is False
    assert res["gate_reason"] == "verdict unsigned"


def test_empty_verdict_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(VERDICT_SECRET_ENV, _STRONG_KEY)
    kg = _seed_store(tmp_path, "alpha", ["m1"])
    res = hades_realize_impl(cycle_id="cyc-1", verdict={}, concept="alpha", apply=False, kg_path=kg)
    assert res["ok"] is False and res["realized"] is False
    assert res["gate_reason"] == "no verdict"


# ── (b) 약/무 키 거부 (from_env weak-key hard-refuse) ─────────────────────────
def test_weak_key_refused_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setenv(VERDICT_SECRET_ENV, "short")  # <32B → 약키
    kg = _seed_store(tmp_path, "alpha", ["m1"])
    verdict = {
        "oracle": "PASS",
        "ensemble": "ACCEPT",
        "verdict_source": "naesengmoon-verify",
        "cycle_id": "cyc-1",
        "artifact_id": compute_artifact_id("alpha", ["m1"]),
        "hmac_signature": "deadbeef",
    }
    res = hades_realize_impl(
        cycle_id="cyc-1", verdict=verdict, concept="alpha", apply=False, kg_path=kg
    )
    assert res["ok"] is False and res["realized"] is False
    assert res["reason"] == "verdict gate misconfigured (weak/absent key)"


def test_absent_key_refused_fail_closed(tmp_path, monkeypatch):
    monkeypatch.delenv(VERDICT_SECRET_ENV, raising=False)
    kg = _seed_store(tmp_path, "alpha", ["m1"])
    res = hades_realize_impl(
        cycle_id="cyc-1", verdict={"oracle": "PASS"}, concept="alpha", apply=False, kg_path=kg
    )
    assert res["ok"] is False and res["realized"] is False
    assert res["reason"] == "verdict gate misconfigured (weak/absent key)"


# ── (c) cross-artifact / (d) cycle 불일치 거부 ────────────────────────────────
def test_artifact_mismatch_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(VERDICT_SECRET_ENV, _STRONG_KEY)
    kg = _seed_store(tmp_path, "alpha", ["m1", "m2"])
    wrong_art = compute_artifact_id("beta", ["x"])  # 다른 artifact 에 서명됨
    verdict = _signed_verdict(_STRONG_KEY, "cyc-1", wrong_art)
    res = hades_realize_impl(
        cycle_id="cyc-1", verdict=verdict, concept="alpha", apply=False, kg_path=kg
    )
    assert res["ok"] is False and res["realized"] is False
    assert res["gate_reason"] == "verdict artifact mismatch (cross-artifact replay)"


def test_cycle_mismatch_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(VERDICT_SECRET_ENV, _STRONG_KEY)
    kg = _seed_store(tmp_path, "alpha", ["m1"])
    art = compute_artifact_id("alpha", ["m1"])
    verdict = _signed_verdict(_STRONG_KEY, "OTHER-cyc", art)  # 다른 cycle 로 서명
    res = hades_realize_impl(
        cycle_id="cyc-1", verdict=verdict, concept="alpha", apply=False, kg_path=kg
    )
    assert res["ok"] is False and res["realized"] is False
    assert res["gate_reason"] == "verdict cycle mismatch (stale/replayed)"


# ── (e) 유효 서명 ⇒ 진행(dry-run) + 1회용 소비 ────────────────────────────────
def test_valid_signed_verdict_proceeds_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv(VERDICT_SECRET_ENV, _STRONG_KEY)
    members = ["m1", "m2"]
    kg = _seed_store(tmp_path, "alpha", members)
    art = compute_artifact_id("alpha", members)  # 서버 재계산과 동일해야 함
    verdict = _signed_verdict(_STRONG_KEY, "cyc-1", art)
    res = hades_realize_impl(
        cycle_id="cyc-1", verdict=verdict, concept="alpha", apply=False, kg_path=kg
    )
    assert res["ok"] is True
    assert res["gate_reason"] == "verdict provenance + content verified"
    assert res["expected_artifact_id"] == art
    assert res["dry_run"] is True
    assert res["applied_count"] == 0
    assert res["candidates"] == 1


def test_valid_verdict_consumed_once_replay_refused(tmp_path, monkeypatch):
    """같은 프로세스 내 동일 (cycle, artifact) 재호출은 ledger 가 거부."""
    monkeypatch.setenv(VERDICT_SECRET_ENV, _STRONG_KEY)
    kg = _seed_store(tmp_path, "gamma", ["only"])
    art = compute_artifact_id("gamma", ["only"])
    verdict = _signed_verdict(_STRONG_KEY, "cyc-replay", art)
    first = hades_realize_impl(
        cycle_id="cyc-replay", verdict=verdict, concept="gamma", apply=False, kg_path=kg
    )
    assert first["ok"] is True
    second = hades_realize_impl(
        cycle_id="cyc-replay", verdict=verdict, concept="gamma", apply=False, kg_path=kg
    )
    assert second["ok"] is False
    assert second["gate_reason"] == "verdict already consumed (replay)"


# ── (f) 알 수 없는 concept (재계산 row 없음) 거부 ────────────────────────────
def test_unknown_concept_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(VERDICT_SECRET_ENV, _STRONG_KEY)
    kg = _seed_store(tmp_path, "alpha", ["m1"])
    verdict = _signed_verdict(_STRONG_KEY, "cyc-1", compute_artifact_id("ghost", []))
    res = hades_realize_impl(
        cycle_id="cyc-1", verdict=verdict, concept="ghost", apply=False, kg_path=kg
    )
    assert res["ok"] is False and res["realized"] is False
    assert res["reason"] == "no ACCEPTED AbstractClass for concept"


# ── 등록/일관성 불변식 ───────────────────────────────────────────────────────
def test_hades_realize_registered():
    assert "hades_realize" in list_registered_tool_names()


def test_catalog_capabilities_match_security():
    assert catalog_is_consistent_with_security() is True


# ── OQ1b: opt-in selection-node 서명 검사 ─────────────────────────────────────
def _seed_signed_store(tmp_path, concept: str, members: list[str], cycle_id: str) -> str:
    """node_signature(+cycleId) 가 박힌 ACCEPTED AbstractClass."""
    kg_file = tmp_path / "kg.json"
    store = LocalKgStore(str(kg_file))
    sig = VerdictGate(_STRONG_KEY.encode("utf-8")).sign_selection(
        concept, "ACCEPTED", cycle_id, members
    )
    store.merge_node(
        "AbstractClass",
        "name",
        concept,
        {
            "verdictStatus": "ACCEPTED",
            "extent": members,
            "cycleId": cycle_id,
            "node_signature": sig,
        },
    )
    store.save()
    return str(kg_file)


def test_require_signed_selection_unsigned_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(VERDICT_SECRET_ENV, _STRONG_KEY)
    kg = _seed_store(tmp_path, "alpha", ["m1"])  # node_signature 없음
    verdict = _signed_verdict(_STRONG_KEY, "cyc-1", compute_artifact_id("alpha", ["m1"]))
    res = hades_realize_impl(
        cycle_id="cyc-1",
        verdict=verdict,
        concept="alpha",
        apply=False,
        kg_path=kg,
        require_signed_selection=True,
    )
    assert res["ok"] is False and res["realized"] is False
    assert res["selection_reason"] == "selection unsigned"


def test_require_signed_selection_valid_proceeds(tmp_path, monkeypatch):
    monkeypatch.setenv(VERDICT_SECRET_ENV, _STRONG_KEY)
    members = ["m1", "m2"]
    kg = _seed_signed_store(tmp_path, "alpha", members, "cyc-1")
    verdict = _signed_verdict(_STRONG_KEY, "cyc-1", compute_artifact_id("alpha", members))
    res = hades_realize_impl(
        cycle_id="cyc-1",
        verdict=verdict,
        concept="alpha",
        apply=False,
        kg_path=kg,
        require_signed_selection=True,
    )
    assert res["ok"] is True and res["candidates"] == 1


def test_selection_check_off_by_default(tmp_path, monkeypatch):
    # 기본 require_signed_selection=False → unsigned 노드도 verdict 만 맞으면 통과 (비파괴).
    monkeypatch.setenv(VERDICT_SECRET_ENV, _STRONG_KEY)
    kg = _seed_store(tmp_path, "alpha", ["m1"])
    verdict = _signed_verdict(_STRONG_KEY, "cyc-1", compute_artifact_id("alpha", ["m1"]))
    res = hades_realize_impl(
        cycle_id="cyc-1", verdict=verdict, concept="alpha", apply=False, kg_path=kg
    )
    assert res["ok"] is True


def test_require_signed_selection_does_not_consume_verdict_on_fail(tmp_path, monkeypatch):
    # selection 실패는 verdict ledger 를 소비하면 안 됨 (검사 순서: selection → verdict).
    monkeypatch.setenv(VERDICT_SECRET_ENV, _STRONG_KEY)
    members = ["m1"]
    kg = _seed_store(tmp_path, "alpha", members)  # unsigned → selection fail
    verdict = _signed_verdict(_STRONG_KEY, "cyc-1", compute_artifact_id("alpha", members))
    r1 = hades_realize_impl(
        cycle_id="cyc-1",
        verdict=verdict,
        concept="alpha",
        apply=False,
        kg_path=kg,
        require_signed_selection=True,
    )
    assert r1["ok"] is False and r1["selection_reason"] == "selection unsigned"
    # 같은 verdict 를 (이번엔 selection 끄고) 다시 → ledger 안 소비됐으니 통과해야
    r2 = hades_realize_impl(
        cycle_id="cyc-1", verdict=verdict, concept="alpha", apply=False, kg_path=kg
    )
    assert r2["ok"] is True


# ── OQ1c: hades 도구가 ED25519 키 설정 시 비대칭 게이트 선택 (천장 봉쇄 경로) ──
def _ed_keys():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = Ed25519PrivateKey.generate()
    raw_pub = (
        priv.public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        .hex()
    )
    return priv, raw_pub


def _asym_signed_verdict(priv, cycle_id, artifact_id):
    from engine.legion.verdict_gate import AsymmetricVerdictGate

    content = {"oracle": "PASS", "ensemble": "ACCEPT", "judgment": "ok", "mode": "live"}
    return AsymmetricVerdictGate(private_key=priv).sign(content, cycle_id, artifact_id)


def test_asymmetric_gate_consumer_public_only_proceeds(tmp_path, monkeypatch):
    priv, raw_pub = _ed_keys()
    members = ["m1", "m2"]
    kg = _seed_store(tmp_path, "alpha", members)
    verdict = _asym_signed_verdict(priv, "cyc-1", compute_artifact_id("alpha", members))
    # consumer env: public only (HMAC·private 없음) → 도구가 비대칭 선택, verify-only
    monkeypatch.delenv(VERDICT_SECRET_ENV, raising=False)
    monkeypatch.delenv("BHGMAN_VERDICT_ED25519_PRIVATE", raising=False)
    monkeypatch.setenv("BHGMAN_VERDICT_ED25519_PUBLIC", raw_pub)
    res = hades_realize_impl(
        cycle_id="cyc-1", verdict=verdict, concept="alpha", apply=False, kg_path=kg
    )
    assert res["ok"] is True and res["candidates"] == 1


def test_asymmetric_gate_forged_refused(tmp_path, monkeypatch):
    _, raw_pub = _ed_keys()
    kg = _seed_store(tmp_path, "alpha", ["m1"])
    monkeypatch.delenv(VERDICT_SECRET_ENV, raising=False)
    monkeypatch.setenv("BHGMAN_VERDICT_ED25519_PUBLIC", raw_pub)
    res = hades_realize_impl(
        cycle_id="cyc-1",
        verdict={"oracle": "PASS", "ensemble": "ACCEPT"},
        concept="alpha",
        apply=False,
        kg_path=kg,
    )
    assert res["ok"] is False
    assert res["gate_reason"] == "untrusted/absent verdict source"
