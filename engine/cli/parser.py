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
    p_apt = sub.add_parser(
        "apt",
        help="APT cycle dispatch (SA → SP → ST → SCW). --gated = run the verified legion runtime (G1/G2/G3).",
    )
    p_apt.add_argument("task", nargs="*", help="Task description forwarded to /apt (skill route).")
    p_apt.add_argument(
        "--gated",
        action="store_true",
        help="Run the gated legion runtime: closed loop + G1 ARTIFACT_EXISTS / G2 ADVERSARY_RAN / "
        "G3 GROUND_TRUTH_GREEN. Fail-closed (verified iff all 3 PASS).",
    )
    p_apt.add_argument(
        "--local", action="store_true", help="(--gated) use the bundled neo4j-free local KG."
    )
    p_apt.add_argument(
        "--ground-truth",
        dest="ground_truth",
        help="(--gated) external oracle command for G3, e.g. 'uv run pytest -q'. "
        "Omit => G3 SKIPPED => not verified.",
    )
    p_apt.add_argument(
        "--status",
        action="store_true",
        help="Phase navigation: detect which APT phase a project (SemanticAnchor) is at + what runs next.",
    )
    p_apt.add_argument(
        "--target", help="(--status / --gated) project SemanticAnchor name to navigate."
    )
    p_apt.set_defaults(func=commands.cmd_apt)

    p_tpa = sub.add_parser(
        "tpa",
        help="TPA reverse cycle (TCW → ST → SP → TA). --gated = run the engine/tpa reverse legion runtime.",
    )
    p_tpa.add_argument(
        "path", nargs="*", help="Codebase path to reverse-engineer (skill route / --gated runtime)."
    )
    p_tpa.add_argument(
        "--gated",
        action="store_true",
        help="Run the engine/tpa reverse legion runtime over <path>: TCW extract → ST/SP recover → "
        "TA 5-drift (deterministic substrate; NOT a cognitive-quality claim).",
    )
    p_tpa.add_argument(
        "--status",
        action="store_true",
        help="Reverse phase navigation: which TPA phase a recovery target is at + what runs next.",
    )
    p_tpa.add_argument("--target", help="(--status) TpaTarget recovery-cycle name to navigate.")
    p_tpa.add_argument(
        "--local", action="store_true", help="(--status) use the bundled neo4j-free local KG."
    )
    p_tpa.set_defaults(func=commands.cmd_tpa)

    p_prom = sub.add_parser("prom", help="프로메테우스 리서치 (런타임 실행 / 없으면 skill route).")
    p_prom.add_argument("N", type=int, help="Sub-question 수 (병렬 서브에이전트).")
    p_prom.add_argument("topic", nargs="+", help="Research topic.")
    p_prom.add_argument("--no-web", action="store_true", help="web_search 끄기 (LLM 지식만).")
    p_prom.add_argument(
        "--k",
        type=int,
        default=None,
        help="축당 self-consistency 샘플 수 (>1=K×N 동시 디코드로 GB10 포화; "
        "기본=BHGMAN_PROM_K 또는 1).",
    )
    p_prom.add_argument(
        "--verify",
        action="store_true",
        help="L5: synth 후 나생문 적대 검증 → FAIL/CONDITIONAL이면 1회 수리(기본 OFF).",
    )
    p_prom.add_argument(
        "--depth",
        type=int,
        default=None,
        help="L6: 재귀 트리 깊이 (1=flat 오늘 경로, 2=map-reduce 트리; 기본=BHGMAN_PROM_DEPTH 또는 1).",
    )
    p_prom.add_argument(
        "--hard-axes",
        type=int,
        default=None,
        dest="hard_axes",
        help="L4: 상위 N개 하드 축(compare/prove/why…)을 tier-1(122B)로 라우팅(기본=BHGMAN_HARD_AXES 또는 0).",
    )
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
        "longinus", help="Longinus reference binding (bind/sha256/ged/reverse-scan)."
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

    p_st = sub.add_parser(
        "status", help="KG audit (local cypher-shell → ssh dgx/kubectl fallback)."
    )
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
    p_oc.add_argument(
        "--semantic",
        action="store_true",
        help="의미론 near-dup mode: embed text nodes, flag cosine≥θ pairs (sha256-blind paraphrase dups).",
    )
    p_oc.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Semantic cosine threshold (model-dependent; all-MiniLM paraphrase ≈ 0.6-0.75).",
    )
    p_oc.add_argument(
        "--label",
        default="ResearchFinding",
        help="Semantic mode target label: ResearchFinding | Lesson.",
    )
    p_oc.add_argument("--limit", type=int, default=200, help="Semantic mode: max nodes to scan.")
    p_oc.add_argument(
        "--allow-hash-embed",
        action="store_true",
        help="Semantic --apply override: permit superseding even when the real embedding "
        "model is absent and the meaningless hash fallback is in use (NOT recommended).",
    )
    p_oc.set_defaults(func=commands.cmd_occam)

    p_orc = sub.add_parser(
        "oracle",
        help="결정론 검증 substrate — artifact 건전성을 4 oracle 중 하나로 (추론기가 호출하는 API/CLI).",
    )
    p_orc.add_argument(
        "--kind",
        required=True,
        choices=["lean-goals", "pytest-ratio", "drift-recount", "occam-twins", "kg-corroborate"],
        help="검증 oracle 종류.",
    )
    p_orc.add_argument(
        "--target",
        help="lean-goals: 자족 .lean 파일 / pytest-ratio: pytest 대상 / kg-corroborate: 검증할 주장(claim).",
    )
    p_orc.add_argument("--lean-dir", default="lean", help="lean-goals: .lean 파일 디렉터리.")
    p_orc.add_argument("--code-root", default=".", help="drift-recount: 코드 루트.")
    p_orc.add_argument("--scope", help="occam-twins: sourcePath CONTAINS 필터.")
    p_orc.add_argument("--local", action="store_true", help="drift/occam: 로컬 neo4j-free KG.")
    p_orc.add_argument(
        "--no-disk-scan",
        action="store_true",
        help="occam-twins: KG-only (skip disk sha scan → same-path dups only, mode-1).",
    )
    p_orc.add_argument("--json", action="store_true", help="JSON verdict 출력.")
    p_orc.set_defaults(func=commands.cmd_oracle)

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

    p_jb = sub.add_parser(
        "jaebaeman",
        help="재배맨 — 계획→씨앗 결정화. 목표를 계획 트리로 unfold + SubagentTaskSpec 씨앗 MERGE "
        "(dry-run default, --apply to plant). 씨앗 심기 = 계획 짜기.",
    )
    p_jb.add_argument("goal", nargs="+", help="목표 텍스트 (계획의 루트).")
    p_jb.add_argument("--name", help="목표 노드 name(PK). 생략 시 goal 텍스트 앞 60자.")
    p_jb.add_argument(
        "--anchor",
        help="KG 발아 원천 노드 name. 주면 그 밑 분해 구조를 연쇄 unfold (없으면 단일 루트).",
    )
    p_jb.add_argument("--skill", help="씨앗 소속 스킬 (default: jaebaeman).")
    p_jb.add_argument("--domain", help="targetDomain.")
    p_jb.add_argument("--task-type", dest="task_type", help="taskType (research/validation/...).")
    p_jb.add_argument("--cycle-id", dest="cycle_id", help="provenance cycleId.")
    p_jb.add_argument(
        "--depth", type=int, default=3, help="최대 분해 세대 [0,3] (SKILL v2.4 fractal hard limit)."
    )
    p_jb.add_argument(
        "--coinductive",
        action="store_true",
        help="ν 모드 — lazy BFS unfold를 --fuel 개 노드까지만 심는다 (depth cap도 함께 작동, P3 병존).",
    )
    p_jb.add_argument(
        "--fuel",
        type=int,
        default=None,
        help="--coinductive와 함께: productive 전개할 최대 노드 수 (observation budget). 생략=depth까지 전부.",
    )
    p_jb.add_argument(
        "--method",
        choices=["auto", "kg", "kg-htn", "llm"],
        default="auto",
        help="분해 방법 (jbm-s6 G6 배선): auto=기존 규칙(anchor+KG면 kg, 아니면 단일 루트) / "
        "kg=kg_decompose 강제 / kg-htn=HTN method 계층(KG HAS_METHOD→DECOMPOSES_TO, "
        "htn.kg_method_decompose) / llm=LLM generate-and-check(결정론 gate, C5; runtime 없으면 "
        "결정론 fallback으로 정직 강등).",
    )
    p_jb.add_argument(
        "--apply",
        action="store_true",
        help="씨앗 MERGE write (멱등/reversible). 생략 = dry-run (planned only).",
    )
    p_jb.add_argument("--local", action="store_true", help="Use the bundled neo4j-free local KG.")
    p_jb.add_argument(
        "--record",
        action="store_true",
        help="production 표면: 실행을 :JaebaemanRun KG 감사노드 + OTel attrs + PROV-O로 기록.",
    )
    p_jb.add_argument(
        "--germinate",
        action="store_true",
        help="발아: 심긴 READY 씨앗을 KG에서 읽어 LLM subagent로 출격(동작)시킨다 "
        "(씨앗→발아→동작 핸드오프). LLM 백엔드 필요; status 전이는 --apply와 함께 write.",
    )
    p_jb.add_argument(
        "--germinate-limit",
        dest="germinate_limit",
        type=int,
        default=None,
        help="--germinate 시 한 번에 발아할 READY 씨앗 최대 수 (생략=전부).",
    )
    p_jb.set_defaults(func=commands.cmd_jaebaeman)

    p_eu = sub.add_parser(
        "eureka",
        help="유레카 — KG 패턴→추상 개념 induce (PROPOSE only, no write; materialize via hades).",
    )
    p_eu.add_argument(
        "--local",
        action="store_true",
        help="Use the bundled neo4j-free local KG (~/.bhgman/kg.json) instead of Neo4j.",
    )
    p_eu.add_argument(
        "--apply",
        action="store_true",
        help="Persist gated concepts to the KG as verdictStatus='VERDICT_PENDING' so hades "
        "can see them (visible, NOT yet realizable). 생략 = dry-run (PROPOSE only, no write).",
    )
    p_eu.add_argument(
        "--accept",
        action="store_true",
        help="명시적 PROPOSED→ACCEPTED: persist as verdictStatus='ACCEPTED' (the row hades "
        "realizes). Implies --apply. covenant: 실현 게이트는 명시적 accept 신호에서만.",
    )
    p_eu.add_argument(
        "--code",
        action="store_true",
        help="code-template path (Plotkin LGG anti-unification over snippets) — neo4j-free, "
        "PROPOSE-only. Feed snippets via repeated --snippet or --code-file.",
    )
    p_eu.add_argument(
        "--snippet",
        action="append",
        help="--code: one code snippet (repeat for N). Rule of Three: ≥3 to propose.",
    )
    p_eu.add_argument(
        "--code-file", help="--code: file of snippets separated by blank lines (or one per line)."
    )
    p_eu.add_argument(
        "--min-instances", type=int, default=3, help="--code: Rule-of-Three minimum (default 3)."
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

    p_lg = sub.add_parser(
        "legion",
        help="레기온 — 6 군단장 통일 닫힌 루프 (획득→연결→창조→정리→검증→실현). 결정론 floor + --llm enrich.",
    )
    p_lg.add_argument(
        "verb",
        nargs="?",
        choices=["run"],
        default="run",
        help="Optional 'run' verb (ergonomic; `legion` and `legion run` are equivalent).",
    )
    p_lg.add_argument("--local", action="store_true", help="Use the bundled neo4j-free local KG.")
    p_lg.add_argument(
        "--apply",
        action="store_true",
        help="Write (occam supersede + hades realize). Omit = dry-run.",
    )
    p_lg.add_argument("--scope", help="occam scope filter (sourcePath CONTAINS).")
    p_lg.add_argument("--concept", help="hades: realize only this AbstractClass name.")
    p_lg.add_argument("--topic", nargs="*", help="prometheus 획득 topic (LLM mode only).")
    p_lg.add_argument(
        "--no-disk-scan", action="store_true", help="occam KG-only (skip disk sha scan)."
    )
    p_lg.add_argument(
        "--llm",
        action="store_true",
        help="Optional LLM enrichment (획득/검증). Default = deterministic core only.",
    )
    p_lg.add_argument(
        "--no-ground", action="store_true", help="Skip KG grounding for LLM enrichment."
    )
    p_lg.add_argument(
        "--web",
        action="store_true",
        help="획득(prometheus) 결정론 코어에 실제 웹 fetcher 주입 (DDG → fetch → ingest). "
        "없으면 gap+query PROPOSE만 (no network).",
    )
    p_lg.add_argument(
        "--consume-dispatch",
        action="store_true",
        help="G5-C5 post-run 소비 (opt-in): 발화된 DispatchDecision 중 allowlist 엣지"
        "(occam janitor)만 depth-cap 안에서 실행, 나머지는 provenance-only skip. "
        "--apply 병용은 경로 정규화 selftest 통과 체크아웃에서만 (R2\u2032 속성 게이트 — "
        "bhgman_tool[-wt-*] 규약 밖 클론이면 공유 KG apply 소비 거부).",
    )
    p_lg.set_defaults(func=commands.cmd_legion)

    p_bot = sub.add_parser(
        "bot",
        help="bhgman 봇 — legion 닫힌루프 백그라운드 자율 데몬 (vLLM 추론 + KG + SearXNG + 하네스).",
    )
    p_bot.add_argument(
        "--interval", type=float, default=300, help="tick 간 sleep 초 (default 300)."
    )
    p_bot.add_argument("--once", action="store_true", help="1 tick 만 실행하고 종료 (검증용).")
    p_bot.add_argument("--max-ticks", type=int, default=None, help="N tick 후 종료 (default 무한).")
    p_bot.add_argument(
        "--topics", nargs="*", help="tick rotation topic 큐 (없으면 KG 에서 일감 pull)."
    )
    p_bot.add_argument("--local", action="store_true", help="번들 neo4j-free local KG 사용.")
    p_bot.add_argument(
        "--apply", action="store_true", help="KG write (occam supersede + hades). 생략=dry-run."
    )
    p_bot.add_argument("--scope", help="occam scope filter (sourcePath CONTAINS).")
    p_bot.add_argument("--no-disk-scan", action="store_true", help="occam KG-only.")
    p_bot.add_argument(
        "--llm", action="store_true", help="vLLM enrichment (획득/검증). 생략=결정론 코어."
    )
    p_bot.add_argument("--no-ground", action="store_true", help="LLM grounding skip.")
    p_bot.add_argument(
        "--web",
        action="store_true",
        help="실제 웹 fetcher 주입 (SearXNG self-host 우선, 없으면 DDG).",
    )
    p_bot.set_defaults(func=commands.cmd_bot)

    p_na = sub.add_parser(
        "naesengmoon-audit",
        help="나생문 truth-렌즈 (결정론): axiom-audit(일관성 vs 참 간극) + falsifiability routing.",
    )
    p_na.add_argument("--lean", help="Lean dir to audit (default: <repo>/lean).")
    p_na.add_argument(
        "--claimed", type=int, help="Check a 'N theorems rest on the axiom' claim vs actual."
    )
    p_na.add_argument("--classify", help="Route a claim string: truth-apt? which external oracle?")
    p_na.set_defaults(func=commands.cmd_naesengmoon_audit)

    p_acq = sub.add_parser(
        "acquire",
        help="프로메테우스 결정론 엔진 — 경계축 ingest (gap→query→fetch→parse→ingest). LLM 불필요(=prom).",
    )
    p_acq.add_argument("--local", action="store_true", help="Use the bundled neo4j-free local KG.")
    p_acq.add_argument(
        "--apply",
        action="store_true",
        help="Write :ResearchFinding (needs fetcher). Omit = PROPOSE/dry-run.",
    )
    p_acq.add_argument(
        "--gap-limit", type=int, default=50, help="Max gap nodes to scan (default 50)."
    )
    p_acq.add_argument("--cycle-id", help="cycleId for provenance (default: acquire-cli).")
    p_acq.add_argument(
        "--web",
        action="store_true",
        help="Inject the real web fetcher (DDG search → fetch → ingest). Omit = gap+query "
        "PROPOSE only (no network). Required for --apply to actually ingest findings.",
    )
    p_acq.set_defaults(func=commands.cmd_acquire)

    return p
