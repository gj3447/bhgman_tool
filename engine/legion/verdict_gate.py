"""Verdict-provenance gate — 하데스 realize 경계의 oracle-gate 우회 차단.

OQ1 / ADR `adr-legion-runtime-shape-review-2026-06-20` §design-oq1-hades-verdict-gate.

오늘 `_run_realize`(`commanders.py:255-260`)는 `ctx["verdict"]` 의 bare `oracle`/`ensemble` 문자열만
무결성 검사 없이 신뢰한다(negative check) → 빈 `{}`·위조 `{"oracle":"PASS"}` 가 비가역 realize 를
통과한다. 이 모듈은 verdict 를 (source ⊕ cycle_id ⊕ artifact_id ⊕ content) 에 대한 HMAC-SHA256 으로
self-authenticating 하게 만들고, 소비측(하데스)이 일방 검증한다. 닫는 위협:

  F (forge)            → HMAC 재계산 + positive PASS 요구 (step 5-7, 8)
  O (fail-open/omission)→ 빈/비-dict 거부 + 서명 강제 (step 1-3, 8)
  R (replay)           → cycle_id freshness (step 4)
  R (cross-artifact)   → artifact_id 바인딩 + 1회용 ledger (step 5, 9)
  K (keyless/weak key) → 약/무/공개-default 키 construction-time HARD-REFUSE

대칭 HMAC 구조적 천장 (OQ1c, residual): env(`BHGMAN_VERDICT_HMAC_SECRET`) 를 읽는 fully-in-process
forger 는 키를 mint 할 수 있다 — 같은 프로세스가 sign+verify. 완전 봉쇄는 비대칭 서명(나생문=private,
하데스=public-only) 또는 process isolation 이 필요하며 `oq-hades-verdict-asymmetric-key-2026-06-20`
으로 트래킹한다. 본 모듈은 키-분리·약키-refuse·artifact-binding·ledger 로 명시 적대자(ctx-writer /
standalone caller)에 대한 잔여를 최소화한다.

# KG: adr-legion-runtime-shape-review-2026-06-20, oq-hades-verdict-provenance-standalone-realize-2026-06-20,
#     oq-hades-verdict-asymmetric-key-2026-06-20
"""

from __future__ import annotations

import hashlib
import hmac
import os
import threading
import uuid
from collections.abc import Callable, Iterable
from typing import Any, Final, NamedTuple

#: 유일하게 허용되는 verdict producer 태그 (서명 payload 에 baked → source 바인딩).
VERDICT_SOURCE: Final[str] = "naesengmoon-verify"

#: 환경변수 키 — dispatch HMAC 키(`measurement.py` 의 공개 dev-default)와 **분리**. in-repo default 없음.
VERDICT_SECRET_ENV: Final[str] = "BHGMAN_VERDICT_HMAC_SECRET"

#: OQ1c 비대칭 게이트 키 (Ed25519, hex-encoded raw 32B). producer=private, consumer=public-only.
ED25519_PRIVATE_ENV: Final[str] = "BHGMAN_VERDICT_ED25519_PRIVATE"
ED25519_PUBLIC_ENV: Final[str] = "BHGMAN_VERDICT_ED25519_PUBLIC"

#: 공개되어 무결성을 못 주는 dev 키 — verdict 게이트에서 명시 거부 (measurement.py:35 와 동일 문자열).
_DEV_DEFAULT: Final[bytes] = b"bhgman-dev-secret-2026-05-30"

#: 최소 키 길이 (bytes). 32 미만은 약키로 거부.
_MIN_KEY_BYTES: Final[int] = 32


class WeakVerdictKeyError(RuntimeError):
    """verdict HMAC 키가 빈/공백/공개-default/<32B → fail-closed (게이트 live 금지)."""


class GateResult(NamedTuple):
    ok: bool
    reason: str


def _key_is_strong(secret: bytes) -> bool:
    """약키 정책: 비어있지 않고, 공백만 아니고, 공개 dev-default 아니고, ≥32 bytes."""
    return (
        bool(secret)
        and secret.strip() != b""
        and secret != _DEV_DEFAULT
        and len(secret) >= _MIN_KEY_BYTES
    )


def compute_artifact_id(concept: str | None, members: Iterable[str]) -> str:
    """검증 stage 가 실제로 검사한 artifact 의 content hash = sha256(concept ⊕ sorted(members)).

    realize 시 hades_runner fetch rows(`a.name` + `a.extent`)에서 동일하게 재계산 →
    'artifact Y 에 대한 verdict' 를 artifact Z 에 복사 불가(같은 cycle_id 내에서도)."""
    canon = "|".join([concept or ""] + sorted(str(m) for m in members))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def verdict_payload(verdict: dict, cycle_id: str | None, artifact_id: str | None) -> str:
    """canonical HMAC payload — (verdict content + cycle_id + artifact_id) 의 순수 함수.

    게이트-관련 결정적 필드만 (advisory `n_eff`/`rho`/`summary` 는 의도적 제외 — 게이트 미사용).
    `DispatchDecision._signed_payload`(measurement.py:58-71) 미러. 고정 순서·고정 구분자.
    """
    degraded = ",".join(sorted(str(d) for d in (verdict.get("degraded_upstream") or [])))
    return "|".join(
        [
            VERDICT_SOURCE,
            cycle_id or "",
            artifact_id or "",
            str(verdict.get("oracle") or ""),
            str(verdict.get("ensemble") or ""),
            degraded,
            str(verdict.get("judgment") or ""),
            str(verdict.get("mode") or ""),
        ]
    )


def selection_payload(
    concept: str | None,
    verdict_status: str | None,
    cycle_id: str | None,
    members: Iterable[str],
) -> str:
    """OQ1b canonical payload — AbstractClass selection 노드의 서명 대상.

    하데스는 ``verdictStatus='ACCEPTED'`` 인 노드만 실현 대상으로 고른다(``hades_runner``).
    그 ``verdictStatus`` 는 writable property 라 직접 위조 가능(두 번째 신뢰 지점). 이 payload
    에 대한 HMAC 으로 노드 자체를 서명 → eureka 가 정당하게 ACCEPTED 한 노드만 통과.
    """
    mem = ",".join(sorted(str(m) for m in (members or [])))
    return "|".join(["selection", concept or "", verdict_status or "", cycle_id or "", mem])


def _verify_provenance_steps(
    verdict: object,
    expected_cycle_id: str | None,
    expected_artifact_id: str | None,
    ledger: object,
    sig_valid: "Callable[[str, str], bool]",
) -> GateResult:
    """공유 10단계 게이트. 서명 알고리즘만 ``sig_valid(payload, sig)->bool`` 로 추상화 →
    HMAC(대칭, :class:`VerdictGate`)·Ed25519(비대칭, :class:`AsymmetricVerdictGate`)가 같은
    단계·같은 거부 사유를 쓴다(canonical payload drift 방지). 성공 시에만 ledger 소비."""
    if not isinstance(verdict, dict) or not verdict:
        return GateResult(False, "no verdict")
    if verdict.get("verdict_source") != VERDICT_SOURCE:
        return GateResult(False, "untrusted/absent verdict source")
    sig = verdict.get("hmac_signature")
    if not isinstance(sig, str) or not sig:
        return GateResult(False, "verdict unsigned")
    vcyc = verdict.get("cycle_id")
    if not vcyc or vcyc != expected_cycle_id:
        return GateResult(False, "verdict cycle mismatch (stale/replayed)")
    vart = verdict.get("artifact_id")
    if not vart or vart != expected_artifact_id:
        return GateResult(False, "verdict artifact mismatch (cross-artifact replay)")
    if not sig_valid(verdict_payload(verdict, vcyc, vart), sig):
        return GateResult(False, "verdict signature invalid")
    if ledger.seen(vcyc, vart):  # type: ignore[attr-defined]
        return GateResult(False, "verdict already consumed (replay)")
    if verdict.get("oracle") != "PASS":
        return GateResult(False, "oracle not PASS")
    if verdict.get("ensemble") in {"REJECT", "FAIL"}:
        return GateResult(False, "verification gate not clean")
    if not ledger.claim(vcyc, vart):  # type: ignore[attr-defined]
        return GateResult(False, "verdict already consumed (replay)")
    return GateResult(True, "verdict provenance + content verified")


def _verify_selection_steps(
    node_props: object,
    expected_cycle_id: str | None,
    sig_valid: "Callable[[str, str], bool]",
) -> GateResult:
    """OQ1b 공유 — AbstractClass selection 노드의 자기-인증. 서명 알고리즘은 sig_valid 로 추상화
    (HMAC/Ed25519 동일). 노드 props: name / verdictStatus / cycleId / extent / node_signature."""
    if not isinstance(node_props, dict):
        return GateResult(False, "no selection node")
    if node_props.get("verdictStatus") != "ACCEPTED":
        return GateResult(False, "selection not ACCEPTED")
    sig = node_props.get("node_signature")
    if not isinstance(sig, str) or not sig:
        return GateResult(False, "selection unsigned")
    cyc = node_props.get("cycleId")
    if not cyc or cyc != expected_cycle_id:
        return GateResult(False, "selection cycle mismatch (stale/forged)")
    payload = selection_payload(
        node_props.get("name"), node_props.get("verdictStatus"), cyc, node_props.get("extent") or []
    )
    if not sig_valid(payload, sig):
        return GateResult(False, "selection signature invalid")
    return GateResult(True, "selection verified")


def _signature_only_valid(verdict: object, sig_valid: "Callable[[str, str], bool]") -> bool:
    """서명만 검증 (ledger/freshness/content 무관, 부수효과 없음) — 런-레벨 G2 의 위조-탐지용
    read-only 체크. verdict 자신의 cycle_id/artifact_id 로 payload 재구성 → 서명 진위만 본다."""
    if not isinstance(verdict, dict):
        return False
    sig = verdict.get("hmac_signature")
    if not isinstance(sig, str) or not sig:
        return False
    return sig_valid(
        verdict_payload(verdict, verdict.get("cycle_id"), verdict.get("artifact_id")), sig
    )


class VerdictLedger:
    """(cycle_id, artifact_id) 1회용 집합 — 같은 verdict 의 2회 realize 차단 (thread-safe)."""

    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def seen(self, cycle_id: str, artifact_id: str) -> bool:
        with self._lock:
            return (cycle_id, artifact_id) in self._seen

    def claim(self, cycle_id: str, artifact_id: str) -> bool:
        """원자적 check-and-record. 처음이면 기록 후 True, 이미 있으면 False."""
        key = (cycle_id, artifact_id)
        with self._lock:
            if key in self._seen:
                return False
            self._seen.add(key)
            return True


class KgVerdictLedger:
    """영속 1회용 ledger — 소비한 (cycle_id, artifact_id) 를 KG :RealizedVerdict 노드로 기록.

    in-memory :class:`VerdictLedger` 는 프로세스 재시작 시 비어 replay 구멍이 생긴다. 이
    backend 는 KG store 에 기록하므로 재시작·다중-프로세스 후에도 1회성이 유지된다(로컬
    파일 store 기준; 실 neo4j 는 unique constraint 로 진짜 원자성). ``store`` 는 duck-typed —
    ``find_one(prop, value, label)`` / ``merge_node(label, key, val, props)`` / ``save()`` 만 요구
    (kg_local.LocalKgStore 충족). 그래서 이 모듈은 kg_local 에 하드-의존하지 않는다.
    """

    _LABEL: Final[str] = "RealizedVerdict"

    def __init__(self, store: object) -> None:
        self._store = store

    @staticmethod
    def _key(cycle_id: str, artifact_id: str) -> str:
        return f"{cycle_id}::{artifact_id}"

    def seen(self, cycle_id: str, artifact_id: str) -> bool:
        return (
            self._store.find_one("name", self._key(cycle_id, artifact_id), self._LABEL)  # type: ignore[attr-defined]
            is not None
        )

    def claim(self, cycle_id: str, artifact_id: str) -> bool:
        """KG 에 기록(이미 있으면 False). 로컬 단일-프로세스 기준 check-then-write 원자성."""
        if self.seen(cycle_id, artifact_id):
            return False
        self._store.merge_node(  # type: ignore[attr-defined]
            self._LABEL,
            "name",
            self._key(cycle_id, artifact_id),
            {"cycle_id": cycle_id, "artifact_id": artifact_id},
        )
        self._store.save()  # type: ignore[attr-defined]
        return True


class VerdictGate:
    """나생문 verdict 의 HMAC 서명/검증. secret 은 DI(생성자 주입) — 테스트 친화 + 키 강제.

    생성 자체가 키-게이트다: 약/무/공개-default 키로는 인스턴스가 만들어지지 않는다(`from_env`
    포함). 따라서 게이트 객체가 존재한다 = 신뢰 가능한 키가 해석됐다.
    """

    def __init__(self, secret: bytes, *, ledger: VerdictLedger | None = None) -> None:
        if not _key_is_strong(secret):
            raise WeakVerdictKeyError(
                f"verdict gate misconfigured: weak/absent/default HMAC key "
                f"(set a ≥{_MIN_KEY_BYTES}B, non-default {VERDICT_SECRET_ENV})"
            )
        self._secret = secret
        self._ledger = ledger if ledger is not None else VerdictLedger()

    @classmethod
    def from_env(cls, *, ledger: VerdictLedger | None = None) -> "VerdictGate":
        """프로덕션 배선용 — `BHGMAN_VERDICT_HMAC_SECRET` 해석 + 약키 hard-refuse."""
        raw = os.environ.get(VERDICT_SECRET_ENV, "").strip()
        return cls(raw.encode("utf-8"), ledger=ledger)

    # ── sign (producer / 나생문 stage) ───────────────────────────────────────
    def _sign(self, payload: str) -> str:
        return hmac.new(self._secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def sign(self, verdict: dict, cycle_id: str | None, artifact_id: str | None) -> dict:
        """verdict 에 provenance 필드(cycle_id/artifact_id/verdict_source/hmac_signature) append.

        원본 dict 는 변형하지 않고 새 dict 반환. content 필드는 그대로 두고 서명만 얹는다.
        """
        signed = dict(verdict)
        signed["cycle_id"] = cycle_id
        signed["artifact_id"] = artifact_id
        signed["verdict_source"] = VERDICT_SOURCE
        signed["hmac_signature"] = self._sign(verdict_payload(verdict, cycle_id, artifact_id))
        return signed

    # ── verify (consumer / 하데스 realize 경계) ──────────────────────────────
    def verify(
        self,
        verdict: object,
        expected_cycle_id: str | None,
        expected_artifact_id: str | None,
    ) -> GateResult:
        """§3 10단계 게이트. 통과 시에만 (cycle_id, artifact_id) 를 ledger 에 소비 기록.

        **부수효과**: 성공 검증은 1회용이다 — 동일 (cycle, artifact) 의 재검증은 거부된다
        (realize 가 비가역이므로 verdict 소비도 1회). 실패 검증은 ledger 를 건드리지 않는다.
        대칭 HMAC — recompute 후 constant-time compare. 천장(env-read in-process forger)은
        :class:`AsymmetricVerdictGate` (OQ1c) 가 닫는다.
        """
        return _verify_provenance_steps(
            verdict, expected_cycle_id, expected_artifact_id, self._ledger, self._sig_valid
        )

    def _sig_valid(self, payload: str, sig: str) -> bool:
        """대칭 HMAC: recompute 후 constant-time compare."""
        return hmac.compare_digest(self._sign(payload), sig)

    # ── OQ1b: selection-node 서명 (verdictStatus 직접 위조 차단) ───────────────
    def sign_selection(
        self, concept: str, verdict_status: str, cycle_id: str | None, members: Iterable[str]
    ) -> str:
        """eureka 가 AbstractClass 를 ACCEPTED 로 persist 할 때 노드에 박을 서명."""
        return self._sign(selection_payload(concept, verdict_status, cycle_id, members))

    def verify_selection(self, node_props: object, expected_cycle_id: str | None) -> GateResult:
        """realize 대상 AbstractClass 노드의 자기-인증 검사 (OQ1b, 공유 step-machine)."""
        return _verify_selection_steps(node_props, expected_cycle_id, self._sig_valid)

    def signature_valid(self, verdict: object) -> bool:
        """서명 진위만 (run-level G2 위조-탐지용, read-only, ledger 미소비)."""
        return _signature_only_valid(verdict, self._sig_valid)


def _load_ed25519_private(hex_str: str) -> Any:
    if not hex_str:
        return None
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: PLC0415
        Ed25519PrivateKey,
    )

    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(hex_str))


def _load_ed25519_public(hex_str: str) -> Any:
    if not hex_str:
        return None
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: PLC0415
        Ed25519PublicKey,
    )

    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(hex_str))


class AsymmetricVerdictGate:
    """OQ1c — Ed25519 비대칭 verdict 게이트. **대칭 HMAC 의 구조적 천장을 닫는다.**

    producer(나생문)는 **private key** 로 서명, consumer(하데스)는 **public key 만** 들고 검증.
    소비측이 서명 키를 갖지 않으므로, env 를 읽을 수 있는 in-process forger 조차 유효 서명을
    mint 할 수 없다 (대칭 HMAC 은 sign==verify 키라 불가능했던 보장). 인터페이스는
    :class:`VerdictGate` 와 동일(sign/verify) — 공유 :func:`_verify_provenance_steps` 로 같은
    10단계·거부 사유. 서명 필드명은 계약 호환 위해 ``hmac_signature`` 재사용(값은 Ed25519 hex).

    ``cryptography`` 는 lazy import (현재 미선언 transitive dep) — 부재 시 ImportError 가 명확히
    난다. 운영 채택 시 opt-in extra(예: ``[verdict-asym]``)로 선언 권장.

    # KG: oq-hades-verdict-asymmetric-key-2026-06-20
    """

    def __init__(
        self,
        *,
        private_key: Any = None,
        public_key: Any = None,
        ledger: Any = None,
    ) -> None:
        if private_key is None and public_key is None:
            raise WeakVerdictKeyError(
                "asymmetric verdict gate needs a private (signer) or public (verifier) Ed25519 key"
            )
        self._priv = private_key
        self._pub = public_key if public_key is not None else private_key.public_key()
        self._ledger = ledger if ledger is not None else VerdictLedger()

    @classmethod
    def from_env(cls, *, ledger: Any = None) -> "AsymmetricVerdictGate":
        """``BHGMAN_VERDICT_ED25519_PRIVATE`` (signer) / ``..._PUBLIC`` (verifier) 해석.
        consumer 는 public 만 설정 → 검증만 가능(sign 시 WeakVerdictKeyError)."""
        priv = _load_ed25519_private(os.environ.get(ED25519_PRIVATE_ENV, "").strip())
        pub = _load_ed25519_public(os.environ.get(ED25519_PUBLIC_ENV, "").strip())
        return cls(private_key=priv, public_key=pub, ledger=ledger)

    def _make_sig(self, payload: str) -> str:
        if self._priv is None:
            raise WeakVerdictKeyError(
                "no private key — consumer-side asymmetric gate can verify but not sign "
                "(this asymmetry is exactly the OQ1c ceiling closure)"
            )
        return self._priv.sign(payload.encode("utf-8")).hex()

    def _sig_valid(self, payload: str, sig: str) -> bool:
        from cryptography.exceptions import InvalidSignature  # noqa: PLC0415

        try:
            self._pub.verify(bytes.fromhex(sig), payload.encode("utf-8"))
            return True
        except (InvalidSignature, ValueError):
            return False

    def sign(self, verdict: dict, cycle_id: str | None, artifact_id: str | None) -> dict:
        signed = dict(verdict)
        signed["cycle_id"] = cycle_id
        signed["artifact_id"] = artifact_id
        signed["verdict_source"] = VERDICT_SOURCE
        signed["hmac_signature"] = self._make_sig(verdict_payload(verdict, cycle_id, artifact_id))
        return signed

    def verify(
        self,
        verdict: object,
        expected_cycle_id: str | None,
        expected_artifact_id: str | None,
    ) -> GateResult:
        return _verify_provenance_steps(
            verdict, expected_cycle_id, expected_artifact_id, self._ledger, self._sig_valid
        )

    def sign_selection(
        self, concept: str, verdict_status: str, cycle_id: str | None, members: Iterable[str]
    ) -> str:
        return self._make_sig(selection_payload(concept, verdict_status, cycle_id, members))

    def verify_selection(self, node_props: object, expected_cycle_id: str | None) -> GateResult:
        return _verify_selection_steps(node_props, expected_cycle_id, self._sig_valid)

    def signature_valid(self, verdict: object) -> bool:
        return _signature_only_valid(verdict, self._sig_valid)


def mint_cycle_id(prefix: str = "cyc") -> str:
    """서버-mint cycle_id (uuid4 hex). caller free-text 대신 각 run 이 고유 cycle 을 갖게 해
    서로 다른 run 의 같은 artifact 가 ledger 에서 잘못 'consumed' 로 충돌하지 않게 한다."""
    return f"{prefix}-{uuid.uuid4().hex}"


def build_gate_from_env(ledger: Any = None) -> Any:
    """게이트 팩토리 — ED25519 키(``BHGMAN_VERDICT_ED25519_*``) 설정 시 비대칭(OQ1c, 천장 봉쇄),
    아니면 대칭 HMAC. 약/무키면 ``WeakVerdictKeyError`` → caller fail-closed. hades/legion 공용."""
    if os.environ.get(ED25519_PRIVATE_ENV) or os.environ.get(ED25519_PUBLIC_ENV):
        return AsymmetricVerdictGate.from_env(ledger=ledger)
    return VerdictGate.from_env(ledger=ledger)


def prepare_forward_ctx(
    ctx: dict,
    *,
    cycle_id: str | None = None,
    store: object | None = None,
    artifact_id: str | None = None,
) -> dict:
    """정방향 legion-run ctx 를 mint 된 cycle_id + (store 있을 때) verdict_gate 로 채운다 (in-place).

    MCP legion 툴과 CLI cmd_legion 이 *동일* 경로로 ctx 를 준비하게 하는 공유 헬퍼 (jbm-s3 패리티,
    T0-3). cycle_id 는 항상 스탬프 — :DispatchEvent.cycle_id 가 null 이 되지 않는다(정방향 provenance
    결손 봉합). verdict_gate + artifact_id leg 는 KG store(duck-typed find_one/merge_node/save)가
    주어지고 verdict 키가 강할 때만 주입한다: store 부재/약키면 legacy(비게이트·비파괴) 경로 유지 —
    가짜 게이트로 fail-open 하지 않는다. (neo4j runner 경로의 store-less ledger 는 별개 follow-up:
    q-legion-cli-verdict-ledger.)
    """
    cid = ctx.get("cycle_id") or cycle_id or mint_cycle_id()
    ctx["cycle_id"] = cid
    if store is not None:
        try:
            ctx["verdict_gate"] = build_gate_from_env(ledger=KgVerdictLedger(store))
            ctx["artifact_id"] = artifact_id or cid
        except WeakVerdictKeyError:
            pass  # 약/무키 → legacy negative-check 경로 (비파괴), fail-open 아님
    return ctx


__all__ = [
    "VERDICT_SOURCE",
    "VERDICT_SECRET_ENV",
    "ED25519_PRIVATE_ENV",
    "ED25519_PUBLIC_ENV",
    "mint_cycle_id",
    "build_gate_from_env",
    "prepare_forward_ctx",
    "WeakVerdictKeyError",
    "GateResult",
    "VerdictLedger",
    "KgVerdictLedger",
    "VerdictGate",
    "AsymmetricVerdictGate",
    "compute_artifact_id",
    "verdict_payload",
    "selection_payload",
]
