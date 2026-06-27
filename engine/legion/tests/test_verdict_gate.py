"""Tests — verdict-provenance gate (OQ1, ADR adr-legion-runtime-shape-review-2026-06-20).

red-team 3렌즈(forge / replay / keyless)가 닫혀야 함. 대칭 HMAC 천장(OQ1c)은 범위 밖.
TDD: 이 파일이 먼저(RED), engine/legion/verdict_gate.py 가 GREEN.
"""

from __future__ import annotations

import pytest

from engine.kg_local.store import LocalKgStore
from engine.legion.commanders import _run_realize, _run_verify
from engine.legion.verdict_gate import (
    VERDICT_SOURCE,
    AsymmetricVerdictGate,
    KgVerdictLedger,
    VerdictGate,
    VerdictLedger,
    WeakVerdictKeyError,
    build_gate_from_env,
    compute_artifact_id,
    mint_cycle_id,
    selection_payload,
    verdict_payload,
)


def _stub_rc(query: str, params: dict | None = None) -> list:
    """run_cypher stub — fetch 0 artifacts (realize 는 빈 dry-run plan)."""
    return []


STRONG_KEY = b"k" * 40  # ≥ 32 bytes, not the public dev-default
DEV_DEFAULT = b"bhgman-dev-secret-2026-05-30"
CYC = "cyc-1"
ART = "art-1"


def _clean_verdict(oracle: str = "PASS", ensemble: str = "PASS") -> dict:
    """A naesengmoon verdict shaped like _run_verify out (advisory fields included)."""
    return {
        "oracle": oracle,
        "degraded_upstream": [],
        "mode": "oracle-deterministic",
        "ensemble": ensemble,
        "n_eff": 1.0,  # advisory — NOT signed
        "rho": 0.0,  # advisory
        "summary": "naesengmoon: ...",  # advisory
    }


def _gate() -> VerdictGate:
    return VerdictGate(STRONG_KEY, ledger=VerdictLedger())


# ── key precondition (렌즈 3: keyless / weak / public-default) ────────────────
class TestKeyPrecondition:
    @pytest.mark.parametrize("bad", [b"", b"   ", DEV_DEFAULT, b"short", b"x" * 31])
    def test_weak_key_refused_at_construction(self, bad: bytes) -> None:
        with pytest.raises(WeakVerdictKeyError):
            VerdictGate(bad)

    def test_strong_key_constructs(self) -> None:
        assert VerdictGate(STRONG_KEY) is not None

    def test_from_env_absent_refused(self, monkeypatch) -> None:
        monkeypatch.delenv("BHGMAN_VERDICT_HMAC_SECRET", raising=False)
        with pytest.raises(WeakVerdictKeyError):
            VerdictGate.from_env()

    def test_from_env_empty_refused(self, monkeypatch) -> None:
        monkeypatch.setenv("BHGMAN_VERDICT_HMAC_SECRET", "")
        with pytest.raises(WeakVerdictKeyError):
            VerdictGate.from_env()

    def test_from_env_dev_default_refused(self, monkeypatch) -> None:
        monkeypatch.setenv("BHGMAN_VERDICT_HMAC_SECRET", DEV_DEFAULT.decode())
        with pytest.raises(WeakVerdictKeyError):
            VerdictGate.from_env()

    def test_from_env_strong_ok(self, monkeypatch) -> None:
        monkeypatch.setenv("BHGMAN_VERDICT_HMAC_SECRET", "K" * 40)
        assert VerdictGate.from_env() is not None


# ── happy path ───────────────────────────────────────────────────────────────
class TestRoundtrip:
    def test_sign_then_verify_passes(self) -> None:
        g = _gate()
        signed = g.sign(_clean_verdict(), CYC, ART)
        assert signed["verdict_source"] == VERDICT_SOURCE
        assert signed["cycle_id"] == CYC and signed["artifact_id"] == ART
        assert isinstance(signed["hmac_signature"], str) and signed["hmac_signature"]
        ok, reason = g.verify(signed, CYC, ART)
        assert ok, reason

    def test_advisory_field_tamper_does_not_invalidate(self) -> None:
        # n_eff/rho/summary 는 서명 payload 밖 — 변조해도 sig 유효 (게이트가 안 읽음).
        g = _gate()
        signed = g.sign(_clean_verdict(), CYC, ART)
        signed["n_eff"] = 999.0
        signed["summary"] = "tampered advisory"
        ok, _ = g.verify(signed, CYC, ART)
        assert ok


# ── 렌즈 1: forge / omission ──────────────────────────────────────────────────
class TestForge:
    def test_empty_verdict_refused(self) -> None:
        ok, reason = _gate().verify({}, CYC, ART)
        assert not ok and "no verdict" in reason

    def test_bare_forged_pass_refused(self) -> None:
        # 위협 모델 핵심: {"oracle":"PASS","ensemble":"PASS"} 날조 (source/sig 없음).
        ok, reason = _gate().verify({"oracle": "PASS", "ensemble": "PASS"}, CYC, ART)
        assert not ok and "source" in reason

    def test_source_present_but_unsigned_refused(self) -> None:
        v = {
            "oracle": "PASS",
            "ensemble": "PASS",
            "verdict_source": VERDICT_SOURCE,
            "cycle_id": CYC,
            "artifact_id": ART,
        }
        ok, reason = _gate().verify(v, CYC, ART)
        assert not ok and "unsigned" in reason

    def test_tampered_content_refused(self) -> None:
        g = _gate()
        signed = g.sign(_clean_verdict(oracle="FAIL", ensemble="REJECT"), CYC, ART)
        signed["oracle"] = "PASS"  # flip content after signing
        signed["ensemble"] = "PASS"
        ok, reason = g.verify(signed, CYC, ART)
        assert not ok and "signature invalid" in reason

    def test_foreign_key_signature_refused(self) -> None:
        # 다른 키로 서명된 verdict 는 우리 게이트에서 무효 (키 분리 의의).
        other = VerdictGate(b"z" * 48, ledger=VerdictLedger())
        signed = other.sign(_clean_verdict(), CYC, ART)
        ok, reason = _gate().verify(signed, CYC, ART)
        assert not ok and "signature invalid" in reason


# ── 렌즈 2: replay / cross-artifact ───────────────────────────────────────────
class TestReplay:
    def test_cycle_mismatch_refused(self) -> None:
        g = _gate()
        signed = g.sign(_clean_verdict(), "cyc-OLD", ART)
        ok, reason = g.verify(signed, "cyc-NEW", ART)
        assert not ok and "cycle" in reason

    def test_cross_artifact_replay_refused(self) -> None:
        g = _gate()
        signed = g.sign(_clean_verdict(), CYC, "artifact-Y")
        ok, reason = g.verify(signed, CYC, "artifact-Z")
        assert not ok and "artifact" in reason

    def test_one_time_ledger_blocks_second_realize(self) -> None:
        g = _gate()
        signed = g.sign(_clean_verdict(), CYC, ART)
        ok1, _ = g.verify(signed, CYC, ART)
        ok2, reason2 = g.verify(signed, CYC, ART)
        assert ok1
        assert not ok2 and "consumed" in reason2

    def test_distinct_artifacts_same_cycle_both_pass(self) -> None:
        # ledger 는 (cycle, artifact) 단위 — 다른 artifact 는 잘못 'consumed' 되면 안 됨.
        g = _gate()
        s1 = g.sign(_clean_verdict(), CYC, "art-A")
        s2 = g.sign(_clean_verdict(), CYC, "art-B")
        assert g.verify(s1, CYC, "art-A").ok
        assert g.verify(s2, CYC, "art-B").ok


# ── content gate (positive PASS 요구) ─────────────────────────────────────────
class TestContentGate:
    def test_oracle_not_pass_refused_even_if_signed(self) -> None:
        g = _gate()
        signed = g.sign(_clean_verdict(oracle="FAIL"), CYC, ART)
        ok, reason = g.verify(signed, CYC, ART)
        assert not ok and "oracle" in reason

    def test_ensemble_reject_refused_even_if_signed(self) -> None:
        g = _gate()
        signed = g.sign(_clean_verdict(ensemble="REJECT"), CYC, ART)
        ok, reason = g.verify(signed, CYC, ART)
        assert not ok and "gate not clean" in reason

    def test_oracle_missing_refused(self) -> None:
        # oracle 키 없음(None) → positive PASS 아님 → 거부 (negative-check 회귀 방지).
        g = _gate()
        v = {"ensemble": "PASS", "mode": "x", "degraded_upstream": []}
        signed = g.sign(v, CYC, ART)
        ok, reason = g.verify(signed, CYC, ART)
        assert not ok and "oracle" in reason


# ── pure helpers ──────────────────────────────────────────────────────────────
class TestPureHelpers:
    def test_compute_artifact_id_deterministic_and_order_independent(self) -> None:
        a = compute_artifact_id("Concept", ["b", "a", "c"])
        b = compute_artifact_id("Concept", ["c", "b", "a"])
        assert a == b
        assert a != compute_artifact_id("Concept", ["a", "b"])  # member set matters
        assert a != compute_artifact_id("Other", ["a", "b", "c"])  # concept matters

    def test_golden_vector_payload_pinned(self) -> None:
        # canonical payload 문자열 drift 방지 (producer/verifier 영구 일치).
        v = {
            "oracle": "PASS",
            "ensemble": "PASS",
            "degraded_upstream": [],
            "mode": "oracle-deterministic",
        }
        # 8 필드: source|cycle|artifact|oracle|ensemble|degraded|judgment|mode
        # degraded="" + judgment="" 둘 다 빈칸 → 파이프 3개 연속.
        assert (
            verdict_payload(v, "cyc-1", "art-1")
            == "naesengmoon-verify|cyc-1|art-1|PASS|PASS|||oracle-deterministic"
        )

    def test_golden_vector_with_degraded_and_judgment(self) -> None:
        v = {
            "oracle": "FAIL",
            "ensemble": "REJECT",
            "degraded_upstream": ["bindings", "acquired"],
            "judgment": "REJECT",
            "mode": "oracle+judgment",
        }
        assert (
            verdict_payload(v, "c", "a")
            == "naesengmoon-verify|c|a|FAIL|REJECT|acquired,bindings|REJECT|oracle+judgment"
        )


# ── 배선: _run_verify (producer) / _run_realize (consumer) ────────────────────
class TestRealizeWiring:
    def test_run_verify_signs_when_gate_injected(self) -> None:
        g = VerdictGate(STRONG_KEY, ledger=VerdictLedger())
        out = _run_verify({"verdict_gate": g, "cycle_id": "cyc-V", "artifact_id": "art-V"})[
            "verdict"
        ]
        assert out["verdict_source"] == VERDICT_SOURCE
        assert isinstance(out.get("hmac_signature"), str) and out["hmac_signature"]
        assert g.verify(out, "cyc-V", "art-V").ok  # self-authenticating round-trip

    def test_run_verify_unchanged_without_gate(self) -> None:
        out = _run_verify({})["verdict"]
        assert "hmac_signature" not in out and "verdict_source" not in out

    def test_realize_refuses_forged_verdict_when_gated(self) -> None:
        g = VerdictGate(STRONG_KEY, ledger=VerdictLedger())
        art = compute_artifact_id("C", [])
        res = _run_realize(
            {
                "verdict": {"oracle": "PASS", "ensemble": "PASS"},  # forged, unsigned
                "verdict_gate": g,
                "cycle_id": "cyc-W",
                "artifact_id": art,
                "run_cypher": _stub_rc,
            }
        )
        assert res["realized"]["mode"] == "skipped"
        assert "provenance not verified" in res["realized"]["summary"]

    def test_realize_proceeds_with_valid_signed_verdict(self) -> None:
        g = VerdictGate(STRONG_KEY, ledger=VerdictLedger())
        art = compute_artifact_id("MyConcept", [])
        signed = g.sign(_clean_verdict(), "cyc-W", art)
        res = _run_realize(
            {
                "verdict": signed,
                "verdict_gate": g,
                "cycle_id": "cyc-W",
                "artifact_id": art,
                "run_cypher": _stub_rc,
                "write_cypher": None,
                "concept": "MyConcept",
                "apply": False,
            }
        )
        assert res["realized"]["mode"] == "hades"  # passed the gate, reached realize

    def test_realize_legacy_floor_without_gate(self) -> None:
        # 게이트 미주입 → 기존 negative-check 동작 보존 (비파괴 회귀 가드).
        res = _run_realize(
            {
                "verdict": {"oracle": "PASS", "ensemble": "PASS"},
                "run_cypher": _stub_rc,
                "write_cypher": None,
                "concept": "X",
                "apply": False,
            }
        )
        assert res["realized"]["mode"] == "hades"

    def test_end_to_end_verify_then_realize_gated(self) -> None:
        g = VerdictGate(STRONG_KEY, ledger=VerdictLedger())
        verdict = _run_verify({"verdict_gate": g, "cycle_id": "cyc-RT", "artifact_id": "art-RT"})[
            "verdict"
        ]
        res = _run_realize(
            {
                "verdict": verdict,
                "verdict_gate": g,
                "cycle_id": "cyc-RT",
                "artifact_id": "art-RT",
                "run_cypher": _stub_rc,
                "write_cypher": None,
                "concept": "C",
                "apply": False,
            }
        )
        assert res["realized"]["mode"] == "hades"


# ── 영속 ledger (KG-backed) — 프로세스 재시작 후 replay 봉쇄 ───────────────────
class TestKgVerdictLedger:
    def test_claim_then_seen_persists_across_instances(self, tmp_path) -> None:
        p = str(tmp_path / "kg.json")
        led1 = KgVerdictLedger(LocalKgStore(p))
        assert led1.claim("c", "a") is True
        assert led1.claim("c", "a") is False  # 같은 인스턴스: 이미 소비
        led2 = KgVerdictLedger(LocalKgStore(p))  # 파일 reload = "재시작"
        assert led2.seen("c", "a") is True
        assert led2.claim("c", "a") is False

    def test_distinct_keys_independent(self, tmp_path) -> None:
        led = KgVerdictLedger(LocalKgStore(str(tmp_path / "kg.json")))
        assert led.claim("c", "a1") is True
        assert led.claim("c", "a2") is True  # 다른 artifact 는 독립
        assert led.seen("c", "a1") and led.seen("c", "a2")

    def test_gate_with_kg_ledger_replay_refused_across_restart(self, tmp_path) -> None:
        p = str(tmp_path / "kg.json")
        g1 = VerdictGate(STRONG_KEY, ledger=KgVerdictLedger(LocalKgStore(p)))
        signed = g1.sign(_clean_verdict(), "cyc", "art")
        assert g1.verify(signed, "cyc", "art").ok
        # 새 store(파일 reload) = 프로세스 재시작 시뮬레이션 → in-memory 였다면 통과했을 것
        g2 = VerdictGate(STRONG_KEY, ledger=KgVerdictLedger(LocalKgStore(p)))
        ok, reason = g2.verify(signed, "cyc", "art")
        assert not ok and "consumed" in reason


# ── OQ1b: selection-node 서명 (두 번째 신뢰 지점 = verdictStatus 직접 위조 차단) ─
class TestSelectionSigning:
    def test_sign_then_verify_selection_passes(self) -> None:
        g = _gate()
        sig = g.sign_selection("alpha", "ACCEPTED", "cyc-1", ["m1", "m2"])
        node = {
            "name": "alpha",
            "verdictStatus": "ACCEPTED",
            "cycleId": "cyc-1",
            "extent": ["m1", "m2"],
            "node_signature": sig,
        }
        ok, reason = g.verify_selection(node, "cyc-1")
        assert ok, reason

    def test_forged_acceptedstatus_unsigned_refused(self) -> None:
        # 공격자가 verdictStatus='ACCEPTED' 만 직접 SET (서명 없음) → 거부.
        g = _gate()
        node = {"name": "evil", "verdictStatus": "ACCEPTED", "cycleId": "cyc-1", "extent": []}
        ok, reason = g.verify_selection(node, "cyc-1")
        assert not ok and "unsigned" in reason

    def test_tampered_extent_refused(self) -> None:
        g = _gate()
        sig = g.sign_selection("alpha", "ACCEPTED", "cyc-1", ["m1"])
        node = {
            "name": "alpha",
            "verdictStatus": "ACCEPTED",
            "cycleId": "cyc-1",
            "extent": ["m1", "INJECTED"],
            "node_signature": sig,
        }  # extent 변조
        ok, reason = g.verify_selection(node, "cyc-1")
        assert not ok and "signature invalid" in reason

    def test_selection_cycle_mismatch_refused(self) -> None:
        g = _gate()
        sig = g.sign_selection("alpha", "ACCEPTED", "cyc-OLD", ["m1"])
        node = {
            "name": "alpha",
            "verdictStatus": "ACCEPTED",
            "cycleId": "cyc-OLD",
            "extent": ["m1"],
            "node_signature": sig,
        }
        ok, reason = g.verify_selection(node, "cyc-NEW")
        assert not ok and "cycle" in reason

    def test_non_accepted_status_refused(self) -> None:
        g = _gate()
        sig = g.sign_selection("alpha", "PROPOSED", "cyc-1", ["m1"])
        node = {
            "name": "alpha",
            "verdictStatus": "PROPOSED",
            "cycleId": "cyc-1",
            "extent": ["m1"],
            "node_signature": sig,
        }
        ok, reason = g.verify_selection(node, "cyc-1")
        assert not ok and "ACCEPTED" in reason

    def test_selection_payload_golden_and_order_independent(self) -> None:
        assert (
            selection_payload("alpha", "ACCEPTED", "cyc-1", ["m2", "m1"])
            == "selection|alpha|ACCEPTED|cyc-1|m1,m2"
        )
        # extent 순서 무관
        g = _gate()
        assert g.sign_selection("a", "ACCEPTED", "c", ["b", "a"]) == g.sign_selection(
            "a", "ACCEPTED", "c", ["a", "b"]
        )


# ── OQ1c: 비대칭 게이트(Ed25519) — 대칭 HMAC 천장(in-process forger) 봉쇄 ──────
def _ed25519_keypair():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = Ed25519PrivateKey.generate()
    return priv, priv.public_key()


class TestAsymmetricVerdictGate:
    def test_sign_private_verify_public_passes(self) -> None:
        priv, pub = _ed25519_keypair()
        signer = AsymmetricVerdictGate(private_key=priv, ledger=VerdictLedger())
        verifier = AsymmetricVerdictGate(public_key=pub, ledger=VerdictLedger())
        signed = signer.sign(_clean_verdict(), "c", "a")
        assert verifier.verify(signed, "c", "a").ok

    def test_public_only_cannot_sign_closes_ceiling(self) -> None:
        # OQ1c 핵심: 소비측(public-only)은 sign 불가 → env 읽는 forger 도 위조 못 함.
        _, pub = _ed25519_keypair()
        verifier = AsymmetricVerdictGate(public_key=pub)
        with pytest.raises(WeakVerdictKeyError):
            verifier.sign(_clean_verdict(), "c", "a")

    def test_tampered_content_refused(self) -> None:
        priv, pub = _ed25519_keypair()
        signed = AsymmetricVerdictGate(private_key=priv).sign(_clean_verdict(), "c", "a")
        signed["ensemble"] = "TAMPERED"  # payload 일부 → 서명 무효
        ok, reason = AsymmetricVerdictGate(public_key=pub).verify(signed, "c", "a")
        assert not ok and "signature invalid" in reason

    def test_foreign_keypair_refused(self) -> None:
        priv1, _ = _ed25519_keypair()
        _, pub2 = _ed25519_keypair()
        signed = AsymmetricVerdictGate(private_key=priv1).sign(_clean_verdict(), "c", "a")
        ok, reason = AsymmetricVerdictGate(public_key=pub2).verify(signed, "c", "a")
        assert not ok and "signature invalid" in reason

    def test_cross_artifact_refused(self) -> None:
        priv, pub = _ed25519_keypair()
        signed = AsymmetricVerdictGate(private_key=priv).sign(_clean_verdict(), "c", "art-Y")
        ok, reason = AsymmetricVerdictGate(public_key=pub).verify(signed, "c", "art-Z")
        assert not ok and "artifact" in reason

    def test_no_key_at_all_refused(self) -> None:
        with pytest.raises(WeakVerdictKeyError):
            AsymmetricVerdictGate()

    def test_from_env_private_signs_public_verifies(self, monkeypatch) -> None:
        from cryptography.hazmat.primitives import serialization

        priv, pub = _ed25519_keypair()
        raw_priv = priv.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        ).hex()
        raw_pub = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
        # producer env: private only
        monkeypatch.setenv("BHGMAN_VERDICT_ED25519_PRIVATE", raw_priv)
        monkeypatch.delenv("BHGMAN_VERDICT_ED25519_PUBLIC", raising=False)
        signed = AsymmetricVerdictGate.from_env(ledger=VerdictLedger()).sign(
            _clean_verdict(), "c", "a"
        )
        # consumer env: public only → verify ok, sign 불가
        monkeypatch.delenv("BHGMAN_VERDICT_ED25519_PRIVATE", raising=False)
        monkeypatch.setenv("BHGMAN_VERDICT_ED25519_PUBLIC", raw_pub)
        verifier = AsymmetricVerdictGate.from_env(ledger=VerdictLedger())
        assert verifier.verify(signed, "c", "a").ok
        with pytest.raises(WeakVerdictKeyError):
            verifier.sign(_clean_verdict(), "c", "a")


class TestAsymmetricSelectionParity:
    def test_selection_sign_verify_parity(self) -> None:
        priv, pub = _ed25519_keypair()
        sig = AsymmetricVerdictGate(private_key=priv).sign_selection(
            "alpha", "ACCEPTED", "c", ["m1", "m2"]
        )
        node = {
            "name": "alpha",
            "verdictStatus": "ACCEPTED",
            "cycleId": "c",
            "extent": ["m1", "m2"],
            "node_signature": sig,
        }
        assert AsymmetricVerdictGate(public_key=pub).verify_selection(node, "c").ok

    def test_selection_tampered_refused(self) -> None:
        priv, pub = _ed25519_keypair()
        sig = AsymmetricVerdictGate(private_key=priv).sign_selection(
            "alpha", "ACCEPTED", "c", ["m1"]
        )
        node = {
            "name": "alpha",
            "verdictStatus": "ACCEPTED",
            "cycleId": "c",
            "extent": ["m1", "X"],
            "node_signature": sig,
        }  # extent 변조
        ok, reason = AsymmetricVerdictGate(public_key=pub).verify_selection(node, "c")
        assert not ok and "signature invalid" in reason

    def test_selection_public_only_cannot_sign(self) -> None:
        _, pub = _ed25519_keypair()
        with pytest.raises(WeakVerdictKeyError):
            AsymmetricVerdictGate(public_key=pub).sign_selection("a", "ACCEPTED", "c", [])


# ── R6: cycle_id 서버-mint + 게이트 팩토리 ────────────────────────────────────
class TestServerMintAndFactory:
    def test_mint_cycle_id_unique_prefixed(self) -> None:
        a, b = mint_cycle_id(), mint_cycle_id()
        assert a != b and a.startswith("cyc-") and len(a) >= 36
        assert mint_cycle_id("run").startswith("run-")

    def test_factory_symmetric(self, monkeypatch) -> None:
        monkeypatch.delenv("BHGMAN_VERDICT_ED25519_PRIVATE", raising=False)
        monkeypatch.delenv("BHGMAN_VERDICT_ED25519_PUBLIC", raising=False)
        monkeypatch.setenv("BHGMAN_VERDICT_HMAC_SECRET", "K" * 40)
        assert isinstance(build_gate_from_env(), VerdictGate)

    def test_factory_asymmetric_when_ed25519_set(self, monkeypatch) -> None:
        from cryptography.hazmat.primitives import serialization

        _, pub = _ed25519_keypair()
        raw_pub = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
        monkeypatch.setenv("BHGMAN_VERDICT_ED25519_PUBLIC", raw_pub)
        assert isinstance(build_gate_from_env(), AsymmetricVerdictGate)

    def test_factory_no_key_raises(self, monkeypatch) -> None:
        for k in (
            "BHGMAN_VERDICT_HMAC_SECRET",
            "BHGMAN_VERDICT_ED25519_PRIVATE",
            "BHGMAN_VERDICT_ED25519_PUBLIC",
        ):
            monkeypatch.delenv(k, raising=False)
        with pytest.raises(WeakVerdictKeyError):
            build_gate_from_env()


def test_signature_valid_primitive() -> None:
    g = _gate()
    signed = g.sign(_clean_verdict(), "c", "a")
    assert g.signature_valid(signed) is True
    assert g.signature_valid({**signed, "hmac_signature": "deadbeef"}) is False
    assert g.signature_valid({}) is False
    assert g.signature_valid({"hmac_signature": ""}) is False
