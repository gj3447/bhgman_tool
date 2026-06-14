"""7군단장 → CommanderStage 어댑터 (통일 배선).

`Legion` + `CommanderStage`(legion_models)는 7군단장 공통 인터페이스로 *존재했지만* 실엔진이
한 번도 등록되지 않은 죽은 추상이었다(production `CommanderStage(` = 0). 이 모듈이 그 빚을 갚는다:
6 능동 군단장(획득/연결/창조/정리/검증/실현)을 동일한 `run(substrate dict) -> provides dict`
모양으로 감싸 Legion 닫힌 루프에 실제 배선한다. (재배맨=출격은 stage가 아니라 dispatch
substrate — Legion.run() 루프 자체가 그 in-process instantiation, CANONICAL_ORDER 제외.)

통일 규율 (사용자 verdict 2026-06-01 "통일해줘"): **결정론 코어가 엔진의 정체성·바닥**
(키 없이 KG만으로 동작·테스트 가능), LLM은 *선택적 enrichment*로 강등 — gate 아님, 필수 아님.
근거: bhgman A/B falsifier (LLM 인지기여 0, 증명된 가치=운영뿐) → 결정론화가 그 유일하게
증명된 가치를 극대화. 프로메테우스(획득)·나생문(검증)은 client 있으면 LLM enrich,
없으면 KG 결정론 코어(gap 노드 read / oracle 정합 게이트).

Contract 체인 (requires ⊆ accumulated provides, 재배맨 dual):
  획득→연결→창조→정리 = 각자 run_cypher만 requires, 산출 1키 provides.
  검증(나생문) requires 그 4 산출 전부 → 산출 없인 못 돈다(oracle gate 의미화).
  실현(하데스) requires 검증 → 검증 통과 후에만 추상→구체 내려보냄(하데스 종착, 나생문 gate 후).

# KG: adr-seven-commander-legion-architecture-2026-05-27 (§4 닫힌 루프),
#     bihaenggiman-legioncommanders-2026-05-26, hades-canonical-2026-05-27 (실현 종착),
#     naesengmoon-wired-ensemble-upgrade-2026-05-27 (oracle 렌즈=결정론 floor),
#     apt-contract-root-axiom-2026-05-27 (handoff = interface 계약)
"""

from __future__ import annotations

from typing import Any

from engine.legion.legion import CANONICAL_ORDER, Legion
from engine.legion.legion_models import CommanderStage
from engine.naesengmoon.decorrelation import CriticKind, CriticVerdict, aggregate, flag_echo


def _degraded(key: str, reason: str) -> dict:
    """엔진 호출 실패/백엔드 미지원 시 결정론 graceful-degrade (loop는 항상 provides 반환)."""
    return {key: {"mode": "degraded", "reason": reason, "summary": f"{key}: degraded — {reason}"}}


# ── 획득 (프로메테우스) ─────────────────────────────────────────────────────
def _run_acquire(ctx: dict) -> dict:
    """외부→KG ingest. client 있으면 LLM 리서치 enrich, 없으면 KG gap 노드 결정론 read."""
    rc = ctx["run_cypher"]
    client = ctx.get("client")
    agents = ctx.get("agents")
    if client is not None and agents is not None:
        try:
            topic = ctx.get("topic") or "open questions in the knowledge graph"
            report = agents.research(
                topic,
                int(ctx.get("n", 4)),
                client,
                web_search=bool(ctx.get("web", False)),
                grounding=ctx.get("grounding"),
            )
            return {
                "acquired": {
                    "mode": "llm",
                    "summary": report.summary,
                    "grounded_facts": getattr(report, "grounded_facts", 0),
                }
            }
        except Exception as e:  # noqa: BLE001 — graceful degrade (engine covenant)
            return _degraded("acquired", f"llm research failed: {e}")
    # 결정론 코어: 경계축 ingest 엔진 (gap→query→fetch→parse→ingest). LLM 불필요.
    try:
        from engine.prometheus import run_acquire  # noqa: PLC0415

        report = run_acquire(
            rc,
            fetcher=ctx.get("fetcher"),
            write_cypher=ctx.get("write_cypher"),
            cycle_id=str(ctx.get("cycle_id", "legion-run")),
            apply=bool(ctx.get("apply", False)),
            researched_at=str(ctx.get("researched_at", "")),
        )
        return {
            "acquired": {
                "mode": "kg-deterministic",
                "gap_nodes": len(report.gaps),
                "findings": len(report.findings),
                "ingested": report.ingested,
                "dry_run": report.dry_run,
                "summary": report.summary,
            }
        }
    except Exception as e:  # noqa: BLE001
        return _degraded("acquired", f"acquire pipeline failed: {e}")


# ── 연결 (롱기누스) ─────────────────────────────────────────────────────────
def _run_bind(ctx: dict) -> dict:
    """code↔KG 바인딩. kg+code_root 주면 full audit, 없으면 KG-only float(미바인딩) 결정론 count."""
    rc = ctx["run_cypher"]
    kg = ctx.get("kg")
    code_root = ctx.get("code_root")
    if kg is not None and code_root is not None:
        try:
            from engine.longinus_drift_audit.audit_runner import LonginusAudit  # noqa: PLC0415

            report = LonginusAudit(
                kg=kg, code_root=code_root, repo_tag=ctx.get("repo_tag")
            ).run_full(verify_sha256=bool(ctx.get("verify_sha256", True)))
            return {
                "bindings": {
                    "mode": "full-audit",
                    "drifts_by_type": getattr(report, "drifts_by_type", {}),
                    "summary": f"longinus[audit]: drift={getattr(report, 'drifts_by_type', {})}",
                }
            }
        except Exception as e:  # noqa: BLE001
            return _degraded("bindings", f"full audit failed: {e}")
    # 결정론 코어: ReferenceSite 바인딩 없는 떠다니는 concept 노드 count (float lesson).
    try:
        rows = rc(
            "MATCH (c) WHERE c:Concept OR c:ResearchFinding OR c:Lesson "
            "WITH c WHERE NOT (c)-[:HAS_REFERENCE|BINDS_TO]->() "
            "RETURN count(c) AS n",
            {},
        )
        n = rows[0]["n"] if rows else 0
        return {
            "bindings": {
                "mode": "kg-deterministic",
                "floating_nodes": n,
                "summary": f"longinus[kg]: {n} floating (unbound) concept nodes",
            }
        }
    except Exception as e:  # noqa: BLE001
        return _degraded("bindings", f"float scan failed: {e}")


# ── 창조 (유레카) ───────────────────────────────────────────────────────────
def _run_induce(ctx: dict) -> dict:
    """KG 패턴→추상 개념 induce (FCA, PROPOSE only — 결정론). 하데스가 나중에 실현."""
    rc = ctx["run_cypher"]
    try:
        from engine.eureka import pipeline, stages  # noqa: PLC0415

        cfg = pipeline.PipelineConfig(
            cycle_id=str(ctx.get("cycle_id", "legion-run")),
            **stages.wire_default_stages(rc),
        )
        pr = pipeline.run_from_kg(rc, cfg)
        ok = sum(1 for s in pr.stages if s.ok)
        return {
            "abstractions": {
                "mode": "fca",
                "stages_ok": ok,
                "stages_total": len(pr.stages),
                "summary": f"eureka[fca]: {ok}/{len(pr.stages)} stages ok (PROPOSE only)",
            }
        }
    except Exception as e:  # noqa: BLE001
        return _degraded("abstractions", f"induce failed: {e}")


# ── 정리 (오캄) ─────────────────────────────────────────────────────────────
def _run_hygiene(ctx: dict) -> dict:
    """superseded/dup SourceCodeNode 정리 (dry-run 기본, ctx['apply']로 write)."""
    rc = ctx["run_cypher"]
    try:
        from engine.occam.occam_runner import run_occam  # noqa: PLC0415

        res = run_occam(
            rc,
            write_cypher=ctx.get("write_cypher"),
            scope=ctx.get("scope"),
            apply=bool(ctx.get("apply", False)),
            repo_root=ctx.get("repo_root"),
        )
        return {
            "hygiene": {
                "mode": "occam",
                "applied": res.apply_result.applied_count,
                "dry_run": res.apply_result.dry_run,
                "summary": res.summary,
            }
        }
    except Exception as e:  # noqa: BLE001
        return _degraded("hygiene", f"occam failed: {e}")


# ── 검증 (나생문) ───────────────────────────────────────────────────────────
def _run_verify(ctx: dict) -> dict:
    """나생문 검증 = oracle floor + 판단렌즈를 *하나의 honest verdict* 로 합성.

    생성-검증 비대칭(naesengmoon-generate-verify-asymmetry-2026-06-01): 렌즈는 무수히 적층할
    수 있지만 같은-family LLM critic 은 ρ 상관으로 n_eff 가 붕괴한다. 그래서 oracle
    (substrate-disjoint, 완전성 floor) + 판단렌즈를 decorrelation.aggregate 로 한 번에 합쳐
    Kish n_eff 를 정직하게 carry 한다. (이전엔 oracle floor 와 판단렌즈가 합산 없이 따로
    놀고, aggregate() 는 production 호출부 0 의 orphan 이었다 — 비대칭 원리의 핵심 합성 미배선.)
    """
    upstream = ("acquired", "bindings", "abstractions", "hygiene")
    degraded = [
        k for k in upstream if isinstance(ctx.get(k), dict) and ctx[k].get("mode") == "degraded"
    ]
    oracle_pass = not degraded
    critics: list[CriticVerdict] = [
        CriticVerdict(lens="upstream-completeness", kind=CriticKind.ORACLE, passed=oracle_pass)
    ]
    out: dict[str, Any] = {
        "oracle": "PASS" if oracle_pass else "FAIL",
        "degraded_upstream": degraded,
        "mode": "oracle-deterministic",
    }
    client = ctx.get("client")
    agents = ctx.get("agents")
    echo_hint = ""
    reasonings: dict[str, str] = {}
    if client is not None and agents is not None:
        try:
            target = ctx.get("topic") or "legion run"
            echo_hint = str(ctx.get("claim") or target)
            verdict = agents.critique(
                target,
                echo_hint,
                client,
                lenses=ctx.get("lenses") or agents.DEFAULT_LENSES,
                grounding=ctx.get("grounding"),
            )
            out["judgment"] = verdict.verdict
            out["mode"] = "oracle+judgment"
            critics.extend(
                CriticVerdict(
                    lens=lv.lens,
                    kind=CriticKind.JUDGMENT,
                    passed=(lv.verdict == "PASS"),
                    model_family="anthropic",
                )
                for lv in verdict.lens_verdicts
            )
            reasonings = {lv.lens: lv.findings for lv in verdict.lens_verdicts}
        except Exception as e:  # noqa: BLE001
            out["judgment_error"] = str(e)
    # prompt-echo 배제: executor framing 을 그대로 받아쓴 판단렌즈는 독립표 아님 → n_eff 에서 제외.
    # (flag_echo 도 production 호출부 0 orphan 이었음 — aggregate 의 echo-배제 분기 dead.)
    if reasonings:
        flag_echo(critics, echo_hint, reasonings)
    # 합성: oracle + 판단렌즈 → 하나의 honest EnsembleResult (n_eff carry). orphan 배선 closure.
    ens = aggregate(critics)
    out["ensemble"] = ens.verdict
    out["n_eff"] = round(ens.n_eff, 2)
    out["rho"] = ens.rho
    out["n_echo_excluded"] = ens.n_echo_excluded
    out["summary"] = (
        f"naesengmoon: oracle={out['oracle']} ensemble={ens.verdict} n_eff≈{ens.n_eff:.2f}"
        + (f" echo_excluded={ens.n_echo_excluded}" if ens.n_echo_excluded else "")
    )
    return {"verdict": out}


# ── 실현 (하데스) ───────────────────────────────────────────────────────────
def _run_realize(ctx: dict) -> dict:
    """검증 통과한 ACCEPTED 추상을 KG에 실현 (CANONICAL+INSTANCE_OF). 나생문 oracle FAIL
    또는 ensemble REJECT/FAIL이면 skip (적대 검증이 거부한 산물은 실현하지 않는다)."""
    verdict = ctx.get("verdict") or {}
    oracle = verdict.get("oracle")
    ensemble = verdict.get("ensemble")
    if oracle == "FAIL" or ensemble in {"REJECT", "FAIL"}:
        return {
            "realized": {
                "mode": "skipped",
                "reason": f"verification gate not clean (oracle={oracle}, ensemble={ensemble})",
                "summary": "hades: skipped — verification gate did not pass",
            }
        }
    rc = ctx["run_cypher"]
    try:
        from engine.hades.hades_runner import run_hades  # noqa: PLC0415

        res = run_hades(
            rc,
            apply_cypher=ctx.get("write_cypher"),
            concept=ctx.get("concept"),
            apply=bool(ctx.get("apply", False)),
        )
        return {
            "realized": {
                "mode": "hades",
                "applied": res.applied_count,
                "dry_run": res.dry_run,
                "summary": res.summary,
            }
        }
    except Exception as e:  # noqa: BLE001
        return _degraded("realized", f"hades failed: {e}")


# ── stage 빌더 + 기본 합성 ──────────────────────────────────────────────────
_STAGES: tuple[CommanderStage, ...] = (
    CommanderStage("prometheus", "획득", ("run_cypher",), ("acquired",), _run_acquire),
    CommanderStage("longinus", "연결", ("run_cypher",), ("bindings",), _run_bind),
    CommanderStage("eureka", "창조", ("run_cypher",), ("abstractions",), _run_induce),
    CommanderStage("occam", "정리", ("run_cypher",), ("hygiene",), _run_hygiene),
    CommanderStage(
        "naesengmoon",
        "검증",
        ("acquired", "bindings", "abstractions", "hygiene"),
        ("verdict",),
        _run_verify,
    ),
    CommanderStage("hades", "실현", ("verdict",), ("realized",), _run_realize),
)


def default_stages() -> tuple[CommanderStage, ...]:
    """CANONICAL_ORDER(획득→연결→창조→정리→검증→실현)대로 정렬된 6 군단장 stage."""
    by_verb = {s.verb: s for s in _STAGES}
    return tuple(by_verb[v] for v in CANONICAL_ORDER)


def build_default_legion() -> Legion:
    """6 능동 군단장을 CANONICAL_ORDER로 등록한 Legion (닫힌 루프 1회 = run())."""
    legion = Legion()
    for stage in default_stages():
        legion.register(stage)
    return legion


__all__ = ["build_default_legion", "default_stages"]
