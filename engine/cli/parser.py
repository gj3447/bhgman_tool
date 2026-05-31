"""bhgman_tool CLI — argparse construction. Split out of main.py 2026-06-01."""

from __future__ import annotations

import argparse

from engine.cli import commands


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bhgman-tool",
        description=(
            "bhgman_tool umbrella CLI — Airplane Man (#4) Harness toolkit. "
            "Tool layer only; essence/ontology layer in separate repos."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_inst = sub.add_parser(
        "install-skills",
        help="Copy skills/* into ~/.claude/skills/ (replaces README step 4 manual cp).",
    )
    p_inst.add_argument(
        "--target",
        default="~/.claude/skills",
        help="Target dir (default: ~/.claude/skills)",
    )
    p_inst.add_argument(
        "--dry-run", action="store_true", help="Show what would happen, don't write."
    )
    p_inst.add_argument("--force", action="store_true", help="Overwrite existing skill dirs.")
    p_inst.set_defaults(func=commands.cmd_install_skills)

    p_ver = sub.add_parser("verify", help="Smoke-run pytest (and optionally lean) for the repo.")
    p_ver.add_argument(
        "--scope",
        choices=["engine", "lean", "all"],
        default="engine",
        help="What to verify (default: engine).",
    )
    p_ver.set_defaults(func=commands.cmd_verify)

    p_v = sub.add_parser("version", help="Print version + repo layout summary.")
    p_v.set_defaults(func=commands.cmd_version)

    p_d = sub.add_parser(
        "daemon",
        help="Delegate to engine.longinus_drift_audit.daemon_cli (add / start / stop / status / logs).",
    )
    p_d.add_argument("passthrough", nargs=argparse.REMAINDER, help="Args forwarded to daemon_cli.")
    p_d.set_defaults(func=commands.cmd_daemon)

    # ─── SYMPOSIUM-absorbed verbs (Wave 7 P2-A, 2026-05-14) ────────────────
    p_apt = sub.add_parser("apt", help="APT cycle dispatch (SA → SP → ST → SCW).")
    p_apt.add_argument("task", nargs="+", help="Task description forwarded to /apt.")
    p_apt.set_defaults(func=commands.cmd_apt)

    p_tpa = sub.add_parser("tpa", help="TPA reverse cycle (TCW → ST → SP → TA).")
    p_tpa.add_argument("path", nargs="+", help="Codebase path to reverse-engineer.")
    p_tpa.set_defaults(func=commands.cmd_tpa)

    p_prom = sub.add_parser("prom", help="프로메테우스 리서치 (런타임 실행 / 없으면 skill route).")
    p_prom.add_argument("N", type=int, help="Sub-question 수 (병렬 서브에이전트).")
    p_prom.add_argument("topic", nargs="+", help="Research topic.")
    p_prom.add_argument("--no-web", action="store_true", help="web_search 끄기 (LLM 지식만).")
    p_prom.add_argument("--route", action="store_true", help="실행 대신 SKILL.md 경로만 출력.")
    p_prom.add_argument(
        "--local",
        action="store_true",
        help="KG 접지에 로컬 KG(~/.bhgman/kg.json) 사용 (neo4j 불필요).",
    )
    p_prom.add_argument(
        "--no-ground",
        action="store_true",
        help="KG 사전지식 접지 끄기 (무접지 LLM, 기본은 접지 ON).",
    )
    p_prom.set_defaults(func=commands.cmd_prom)

    p_tlb = sub.add_parser("tlb", help="나생문 ensemble critic (런타임 실행 / 없으면 skill route).")
    p_tlb.add_argument("target", nargs="+", help="검증 대상 식별자 (SPAN/CONTRACT/claim 이름).")
    p_tlb.add_argument(
        "--lens", help="단일 lens (constitutional / mathematical / solid). 생략=3중."
    )
    p_tlb.add_argument("--claim", help="검증할 주장/산출물 텍스트 (생략 시 target을 사용).")
    p_tlb.add_argument("--route", action="store_true", help="실행 대신 SKILL.md 경로만 출력.")
    p_tlb.add_argument(
        "--local",
        action="store_true",
        help="KG 접지에 로컬 KG(~/.bhgman/kg.json) 사용 (neo4j 불필요).",
    )
    p_tlb.add_argument(
        "--no-ground",
        action="store_true",
        help="KG 사전지식 접지 끄기 (무접지 LLM, 기본은 접지 ON).",
    )
    p_tlb.set_defaults(func=commands.cmd_tlb)

    p_long = sub.add_parser(
        "longinus", help="Longinus reference binding (sha256/ged/reverse-scan)."
    )
    p_long.add_argument(
        "op", nargs="+", help="Operation: sha256 / ged / reverse-scan / <freeform>."
    )
    p_long.set_defaults(func=commands.cmd_longinus)

    p_lfloat = sub.add_parser(
        "longinus-floating",
        help="Floating concept-node scan — concept nodes with no binding to source (local KG).",
    )
    p_lfloat.set_defaults(func=commands.cmd_longinus_floating)

    p_hns = sub.add_parser("harness", help="하네스 3계층/4축 진단 (결정론 엔진). --route=skill.")
    p_hns.add_argument("action", nargs="+", help="진단 대상 (프레임워크명 또는 설명 텍스트).")
    p_hns.add_argument("--route", action="store_true", help="진단 대신 SKILL.md 경로만 출력.")
    p_hns.add_argument(
        "--apply", action="store_true", help="진단을 KG(:HarnessDiagnosis)에 persist."
    )
    p_hns.add_argument("--no-disk-scan", action="store_true", help=argparse.SUPPRESS)
    p_hns.add_argument(
        "--local", action="store_true", help="KG persist에 로컬 KG 사용 (--apply과 함께)."
    )
    p_hns.set_defaults(func=commands.cmd_harness)

    p_st = sub.add_parser("status", help="KG audit (ssh dgx → cypher-shell).")
    p_st.set_defaults(func=commands.cmd_status)

    p_oc = sub.add_parser(
        "occam",
        help="오캄 KG dedup — superseded/dup SourceCodeNode archive (dry-run default, --apply to write).",
    )
    p_oc.add_argument(
        "--scope", help="Restrict to nodes whose sourcePath CONTAINS this (label/path)."
    )
    p_oc.add_argument(
        "--apply",
        action="store_true",
        help="Write SUPERSEDED (reversible). Omit = dry-run (covenant: archive-only).",
    )
    p_oc.add_argument(
        "--no-disk-scan",
        action="store_true",
        help="KG-only (mode-1 same-path dedup). Default scans disk for moved-node/orphan detection.",
    )
    p_oc.add_argument(
        "--local",
        action="store_true",
        help="Use the bundled neo4j-free local KG (~/.bhgman/kg.json) instead of Neo4j.",
    )
    p_oc.set_defaults(func=commands.cmd_occam)

    p_hd = sub.add_parser(
        "hades",
        help="하데스 — ACCEPTED 추상을 KG에 실현 (CANONICAL+INSTANCE_OF). dry-run default, --apply to write.",
    )
    p_hd.add_argument(
        "--concept", help="Realize only this AbstractClass name (default: all ACCEPTED)."
    )
    p_hd.add_argument(
        "--apply",
        action="store_true",
        help="Materialize (reversible via undo). Omit = dry-run (c6 danger guard).",
    )
    p_hd.add_argument(
        "--local",
        action="store_true",
        help="Use the bundled neo4j-free local KG (~/.bhgman/kg.json) instead of Neo4j.",
    )
    p_hd.add_argument(
        "--extract-superclass",
        metavar="PATH",
        help="Code mode (no neo4j): scan a dir/file for classes sharing an identical "
        "method and generate an Extract-Superclass patch (PLAN only).",
    )
    p_hd.add_argument(
        "--preserve-format",
        action="store_true",
        help="Use the libcst backend ([hades-cst]) so comments/layout survive in the patch.",
    )
    p_hd.add_argument(
        "--show-patch",
        action="store_true",
        help="Print the full generated unified diff for each candidate.",
    )
    p_hd.add_argument(
        "--test-cmd",
        metavar="CMD",
        help="With --apply: the characterization-test command (e.g. 'pytest engine/x'). "
        "The refactor is kept only if it still passes, else reverted byte-for-byte.",
    )
    p_hd.set_defaults(func=commands.cmd_hades)

    p_eu = sub.add_parser(
        "eureka",
        help="유레카 — KG 패턴→추상 개념 induce (PROPOSE only, no write; materialize via hades).",
    )
    p_eu.add_argument(
        "--local",
        action="store_true",
        help="Use the bundled neo4j-free local KG (~/.bhgman/kg.json) instead of Neo4j.",
    )
    p_eu.set_defaults(func=commands.cmd_eureka)

    p_ks = sub.add_parser(
        "kg-schema",
        help="Print the in-code KG schema (node/edge defs) or emit Neo4j bootstrap DDL.",
    )
    p_ks.add_argument(
        "--emit",
        choices=["summary", "neo4j"],
        default="summary",
        help="summary = human view; neo4j = CREATE CONSTRAINT DDL to bootstrap a fresh Neo4j.",
    )
    p_ks.set_defaults(func=commands.cmd_kg_schema)

    p_xp = sub.add_parser(
        "export-prov",
        help="W3C PROV-O export — a research cycle's findings → prov:Entity Turtle/nanopub.",
    )
    p_xp.add_argument(
        "passthrough",
        nargs=argparse.REMAINDER,
        help="cycle_id [--format turtle|jsonld|trig] [--findings-json PATH] [--out FILE]",
    )
    p_xp.set_defaults(func=commands.cmd_export_prov)

    # ─── SYMPOSIUM resolver/gate verbs (Wave 7 P3-H, 2026-05-14) ──────────
    p_rs = sub.add_parser(
        "resolver",
        help="APT v27 A6 pre-prompt resolver (render | validate). 9 pytest absorbed.",
    )
    p_rs.add_argument(
        "passthrough",
        nargs=argparse.REMAINDER,
        help="Args forwarded to engine.resolver.resolver (render --input X --output Y | validate <path>).",
    )
    p_rs.set_defaults(func=commands.cmd_resolver)

    p_gt = sub.add_parser(
        "gate",
        help="APT v27 A7 fail-closed gate endpoint (serve | check). 6 pytest absorbed.",
    )
    p_gt.add_argument(
        "passthrough",
        nargs=argparse.REMAINDER,
        help="serve | check --gate NAME --cycle ID --actor NAME [--expected N --actual N]",
    )
    p_gt.set_defaults(func=commands.cmd_gate)

    return p
