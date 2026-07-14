"""나생문 합의 프로토콜 NCP-1 — 결정론 verdict-aggregation 코어.

N개 렌즈(판단렌즈 LLM + oracle렌즈 결정론)의 개별 verdict 를 *정전 정책 대수*로
집계한다. LLM 은 vote 를 만들어 넣는 호출자일 뿐 — 이 모듈은 순수·결정론·stdlib.

정전 근거 (모두 기존 canon, 발명 아님):
  • UNANIMOUS_PASS default, MAJORITY/WEIGHTED 는 user-explicit alternative — taliban SKILL.md
  • 2 lens-class: 판단렌즈 vs oracle렌즈 = HARD GATE — project-naesengmoon-two-lens-class-2026-05-27
  • D20: executor != reviewer 강제 — apt FulfillmentGate
  • HR11: APPROVED verdict 는 구체 evidence 인용 필수 (RUBBER_STAMP 금지) — apt v26
  • formal-cathedral: 판단렌즈 논증만으로 PASS 불가 → escalate-to-oracle (가장 싼 falsifier)
  • N중 = N 독립 lens (cardinality 1:1) → 중복 lens vote 는 1표 — naesengmoon-cardinality lesson
  • steelman-opposite 재실행 = 독립성 회복 수단 — rf-prom16-contract-dual-steelman-opposite-2026-05-27
  • 상관오류 보정: Kish n_eff + prompt-echo 제외 — engine/naesengmoon/decorrelation.py 재사용
  • n_eff < 1.5 & oracle 0 → clean PASS 금지 (W3-D) — decorrelation._verdict_label 전례 승계
  • BFT quorum: 판단렌즈 f개 임의-오류(drift) 가정 시 N_j ≥ 3f+1, PASS ≥ 2f+1
    (quorum intersection ⇒ 임의의 2f+1 quorum 에 정직 렌즈 ≥ f+1) — transfer333 Byzantine 교훈

# KG: naesengmoon-consensus-protocol-ncp1-2026-07-13, naesengmoon-canonical-2026-05-19
# KG: consensus-prom8-naesengmoon-decorrelation-2026-05-31
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from engine.naesengmoon.decorrelation import DEFAULT_RHO, CriticKind, CriticVerdict, effective_n

# clean PASS 에 필요한 최소 유효독립 (W3-D 전례: 단독/상관 판단렌즈만으로 PASS 금지)
MIN_EFF_FOR_CLEAN_PASS = 1.5


class LensClass(str, Enum):
    # KG: naesengmoon-canonical-2026-05-19
    ORACLE = "oracle"      # 결정론 checker — substrate-disjoint, HARD GATE
    JUDGMENT = "judgment"  # LLM 판단렌즈 — 상관 common-mode 오류 대상


class VoteValue(str, Enum):
    # KG: naesengmoon-consensus-protocol-ncp1-2026-07-13
    PASS = "PASS"
    FAIL = "FAIL"
    CONDITIONAL = "CONDITIONAL"  # pass-with-obligations (obligations 필수)
    ABSTAIN = "ABSTAIN"          # 해당 렌즈 비적용/판단불가 — 분모에서 제외


class PolicyKind(str, Enum):
    # KG: naesengmoon-consensus-protocol-ncp1-2026-07-13
    UNANIMOUS = "UNANIMOUS"      # 정전 default
    MAJORITY = "MAJORITY"        # user-explicit
    WEIGHTED = "WEIGHTED"        # user-explicit
    BFT_QUORUM = "BFT_QUORUM"    # user-explicit: 판단렌즈 N_j ≥ 3f+1, PASS ≥ 2f+1


@dataclass(frozen=True)
class Policy:
    # KG: naesengmoon-consensus-protocol-ncp1-2026-07-13
    kind: PolicyKind = PolicyKind.UNANIMOUS
    f: int = 1            # BFT_QUORUM: 동시-drift 가정 최대 렌즈 수
    theta: float = 0.9    # WEIGHTED: pass-측 가중합 임계 (비-abstain 총가중 대비)


DEFAULT_POLICY = Policy()  # UNANIMOUS_PASS — 정전 default


class Disposition(str, Enum):
    # KG: naesengmoon-consensus-protocol-ncp1-2026-07-13
    ADMITTED = "ADMITTED"
    DROPPED_D20 = "DROPPED_D20"                        # executor == reviewer
    DROPPED_DUP_LENS = "DROPPED_DUP_LENS"              # cardinality 1:1 위반 (2번째 이후)
    DROPPED_ECHO = "DROPPED_ECHO"                      # prompt-echo suspect (판단렌즈)
    DOWNGRADED_NO_EVIDENCE = "DOWNGRADED_NO_EVIDENCE"  # HR11: evidence 없는 PASS/COND → ABSTAIN
    DOWNGRADED_NO_OBLIGATIONS = "DOWNGRADED_NO_OBLIGATIONS"  # 공허한 CONDITIONAL → ABSTAIN


class Escalation(str, Enum):
    # KG: naesengmoon-consensus-protocol-ncp1-2026-07-13
    NONE = "NONE"
    ADD_LENSES = "ADD_LENSES"                # quorum 평가 불능 (표 부족 / BFT N<3f+1)
    STEELMAN_OPPOSITE = "STEELMAN_OPPOSITE"  # 독립성 의심 — 반대 thesis 재실행
    TO_ORACLE = "TO_ORACLE"                  # 가장 싼 oracle falsifier (formal-cathedral)
    TO_USER = "TO_USER"                      # sigma_oracle (인간 verdict)


@dataclass(frozen=True)
class Vote:
    # KG: naesengmoon-consensus-protocol-ncp1-2026-07-13
    lens: str
    lens_class: LensClass
    value: VoteValue
    evidence: tuple[str, ...] = ()
    executor: str = ""
    reviewer: str = ""
    weight: float = 1.0
    obligations: tuple[str, ...] = ()
    model_family: str = "unknown"
    echo_suspect: bool = False


def vote_from_critic(cv: CriticVerdict, *, evidence: tuple[str, ...] = ()) -> Vote:
    # KG: naesengmoon-consensus-protocol-ncp1-2026-07-13
    """기존 decorrelation.CriticVerdict → NCP Vote 승격 (interop)."""
    return Vote(
        lens=cv.lens,
        lens_class=LensClass.ORACLE if cv.kind is CriticKind.ORACLE else LensClass.JUDGMENT,
        value=VoteValue.PASS if cv.passed else VoteValue.FAIL,
        evidence=evidence,
        model_family=cv.model_family,
        echo_suspect=cv.echo_suspect,
    )


@dataclass(frozen=True)
class Admission:
    # KG: naesengmoon-consensus-protocol-ncp1-2026-07-13
    vote: Vote
    disposition: Disposition
    effective_value: VoteValue  # downgrade 반영 후 실제 집계에 쓰인 값


@dataclass(frozen=True)
class ConsensusResult:
    # KG: naesengmoon-consensus-protocol-ncp1-2026-07-13
    verdict: str                 # PASS | CONDITIONAL_PASS | FAIL | ESCALATE
    policy: str
    oracle_veto: bool
    escalation: Escalation
    n_eff: float
    rho: float
    obligations: tuple[str, ...]
    flags: tuple[str, ...]
    admissions: tuple[Admission, ...]
    summary: str

    def to_kg_shape(self, name: str, target: str) -> dict:
        """ValidationResult 노드 + USED_LENS 엣지용 dict (secretary/UNWIND 소비)."""
        return {
            "name": name,
            "labels": ["ValidationResult"],
            "props": {
                "target": target,
                "verdict": self.verdict,
                "policy": self.policy,
                "oracle_veto": self.oracle_veto,
                "escalation": self.escalation.value,
                "n_eff": round(self.n_eff, 4),
                "rho": round(self.rho, 4),
                "flags": list(self.flags),
                "obligations": list(self.obligations),
                "protocol": "NCP-1",
            },
            "used_lens": [a.vote.lens for a in self.admissions
                          if a.disposition is Disposition.ADMITTED],
        }


# ---- 1단계: admissibility (D20 / cardinality / HR11 / echo) ----------------------


def admit(votes: list[Vote]) -> list[Admission]:
    # KG: naesengmoon-consensus-protocol-ncp1-2026-07-13
    """표별 자격 심사. drop 은 기록으로 남긴다 (Eilu va-Eilu — 지우지 않음)."""
    out: list[Admission] = []
    seen_lens: set[str] = set()
    for v in votes:
        if v.executor and v.reviewer and v.executor == v.reviewer:
            out.append(Admission(v, Disposition.DROPPED_D20, VoteValue.ABSTAIN))
            continue
        if v.lens in seen_lens:  # N중 = N *독립* lens — 같은 lens 2표 = 1표
            out.append(Admission(v, Disposition.DROPPED_DUP_LENS, VoteValue.ABSTAIN))
            continue
        seen_lens.add(v.lens)
        if v.echo_suspect and v.lens_class is LensClass.JUDGMENT:
            out.append(Admission(v, Disposition.DROPPED_ECHO, VoteValue.ABSTAIN))
            continue
        if v.value in (VoteValue.PASS, VoteValue.CONDITIONAL) and not v.evidence:
            # HR11: evidence 없는 승인 = RUBBER_STAMP → 기권 강등
            out.append(Admission(v, Disposition.DOWNGRADED_NO_EVIDENCE, VoteValue.ABSTAIN))
            continue
        if v.value is VoteValue.CONDITIONAL and not v.obligations:
            out.append(Admission(v, Disposition.DOWNGRADED_NO_OBLIGATIONS, VoteValue.ABSTAIN))
            continue
        out.append(Admission(v, Disposition.ADMITTED, v.value))
    return out


# ---- 2단계: 상관 붕괴 (identical-evidence collapse) ------------------------------


def _collapse_correlated(pass_side: list[Admission]) -> tuple[list[Admission], bool]:
    """동일 evidence 집합을 공유하는 판단렌즈 pass-측 표들 = 1 유효표로 붕괴.

    반환 (유효 pass-측 표, all_collapsed_to_one). 후자가 True 면 독립성 의심 —
    N표가 사실상 한 관측의 복제 (steelman-opposite 재실행 필요)."""
    groups: dict[frozenset[str], list[Admission]] = {}
    singles: list[Admission] = []
    for a in pass_side:
        if a.vote.lens_class is LensClass.JUDGMENT and a.vote.evidence:
            groups.setdefault(frozenset(a.vote.evidence), []).append(a)
        else:
            singles.append(a)
    effective = singles + [g[0] for g in groups.values()]
    collapsed_any = any(len(g) > 1 for g in groups.values())
    judgment_pass = [a for a in pass_side if a.vote.lens_class is LensClass.JUDGMENT]
    all_one = (
        collapsed_any
        and len(groups) == 1
        and len(singles) == 0
        and len(judgment_pass) >= 2
    )
    return effective, all_one if collapsed_any else False


# ---- 3단계: 정책 quorum + 판정 ----------------------------------------------------


def decide(
    votes: list[Vote],
    policy: Policy = DEFAULT_POLICY,
    *,
    rho: float | None = None,
    min_eff: float = MIN_EFF_FOR_CLEAN_PASS,
) -> ConsensusResult:
    # KG: naesengmoon-consensus-protocol-ncp1-2026-07-13
    """NCP-1 판정. 순서 고정: admit → oracle veto → collapse → quorum → n_eff cap.

    verdict 규칙 (v1):
      1. oracle FAIL → FAIL (HARD GATE, 판단렌즈로 override 불가)
      2. 유효표 0 / BFT N_j < 3f+1 → ESCALATE(ADD_LENSES)
      3. pass-측 quorum 인데 전원 동일-evidence 붕괴 → ESCALATE(STEELMAN_OPPOSITE)
      4. quorum 충족 → PASS / CONDITIONAL_PASS (obligations 합집합; n_eff<min_eff &
         oracle 0 이면 clean PASS 금지 → CONDITIONAL_PASS cap)
      5. quorum 미충족 → evidence 있는 FAIL 존재 시 FAIL; 아니면 ESCALATE
         (oracle 미참여면 TO_ORACLE — 가장 싼 falsifier; 참여면 TO_USER)
    """
    admissions = admit(votes)
    flags: list[str] = []

    admitted = [a for a in admissions if a.disposition is Disposition.ADMITTED]
    dropped = len(admissions) - len(admitted)
    if dropped:
        flags.append(f"DROPPED_{dropped}")

    oracles = [a for a in admitted if a.vote.lens_class is LensClass.ORACLE]
    judgments = [a for a in admitted if a.vote.lens_class is LensClass.JUDGMENT]

    rho_used = DEFAULT_RHO if rho is None else min(max(rho, 0.0), 1.0)
    n_eff = effective_n(len(oracles), len(judgments), rho_used)

    def _result(verdict: str, esc: Escalation, obligations: tuple[str, ...] = ()) -> ConsensusResult:
        summary = (
            f"NCP-1 {policy.kind.value}: {len(votes)} vote → {len(admitted)} admitted "
            f"({len(oracles)} oracle + {len(judgments)} judgment), "
            f"ρ={rho_used:.2f}, n_eff≈{n_eff:.2f} → {verdict}"
            + (f" [{esc.value}]" if esc is not Escalation.NONE else "")
        )
        return ConsensusResult(
            verdict=verdict, policy=policy.kind.value,
            oracle_veto=any(a.effective_value is VoteValue.FAIL for a in oracles),
            escalation=esc, n_eff=n_eff, rho=rho_used,
            obligations=obligations, flags=tuple(flags),
            admissions=tuple(admissions), summary=summary,
        )

    # 1. oracle HARD GATE
    if any(a.effective_value is VoteValue.FAIL for a in oracles):
        flags.append("ORACLE_VETO")
        return _result("FAIL", Escalation.NONE)

    counted = [a for a in admitted if a.effective_value is not VoteValue.ABSTAIN]
    if not counted:
        flags.append("NO_EFFECTIVE_VOTES")
        return _result("ESCALATE", Escalation.ADD_LENSES)

    pass_side = [a for a in counted
                 if a.effective_value in (VoteValue.PASS, VoteValue.CONDITIONAL)]
    fail_side = [a for a in counted if a.effective_value is VoteValue.FAIL]

    # 2. identical-evidence collapse (판단렌즈 pass-측)
    eff_pass, all_one = _collapse_correlated(pass_side)
    if len(eff_pass) < len(pass_side):
        flags.append("CORRELATED_EVIDENCE_COLLAPSED")

    # 3. 정책 quorum
    if policy.kind is PolicyKind.BFT_QUORUM:
        n_j = len([a for a in counted if a.vote.lens_class is LensClass.JUDGMENT])
        pass_j = len([a for a in eff_pass if a.vote.lens_class is LensClass.JUDGMENT])
        if n_j < 3 * policy.f + 1:
            flags.append(f"BFT_INFEASIBLE_NJ_{n_j}_LT_{3 * policy.f + 1}")
            return _result("ESCALATE", Escalation.ADD_LENSES)
        quorum_ok = pass_j >= 2 * policy.f + 1
    elif policy.kind is PolicyKind.MAJORITY:
        quorum_ok = len(eff_pass) * 2 > len(eff_pass) + len(fail_side)
    elif policy.kind is PolicyKind.WEIGHTED:
        w_pass = sum(a.vote.weight for a in eff_pass)
        w_all = w_pass + sum(a.vote.weight for a in fail_side)
        quorum_ok = w_all > 0 and (w_pass / w_all) >= policy.theta
    else:  # UNANIMOUS — 정전 default
        quorum_ok = not fail_side and bool(eff_pass)

    if quorum_ok:
        if all_one:
            flags.append("INDEPENDENCE_SUSPECT")
            return _result("ESCALATE", Escalation.STEELMAN_OPPOSITE)
        obligations = tuple(
            ob for a in eff_pass if a.effective_value is VoteValue.CONDITIONAL
            for ob in a.vote.obligations
        )
        if obligations:
            return _result("CONDITIONAL_PASS", Escalation.NONE, obligations)
        if n_eff < min_eff and not oracles:
            flags.append("N_EFF_BELOW_CLEAN_PASS")  # W3-D 전례 승계
            return _result("CONDITIONAL_PASS", Escalation.NONE)
        return _result("PASS", Escalation.NONE)

    # 4. quorum 미충족
    evidenced_fail = any(a.vote.evidence for a in fail_side)
    if evidenced_fail:
        return _result("FAIL", Escalation.NONE)
    esc = Escalation.TO_ORACLE if not oracles else Escalation.TO_USER
    flags.append("DISSENT_UNEVIDENCED" if fail_side else "QUORUM_SHORT")
    return _result("ESCALATE", esc)


__all__ = [
    "MIN_EFF_FOR_CLEAN_PASS",
    "Admission",
    "ConsensusResult",
    "Disposition",
    "Escalation",
    "LensClass",
    "Policy",
    "PolicyKind",
    "Vote",
    "VoteValue",
    "admit",
    "decide",
    "vote_from_critic",
    "DEFAULT_POLICY",
]
