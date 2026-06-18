# PROM_16 — Axis A1: Software Configuration Management 학문 grounding

> SYMPOSIUM/SKILLS skill 변천사(versioning/changelog) 관리의 학문적 뿌리 정리.
> 50+ 년 SCM 정전 → 산업 표준 → 함정 → 2026 AI agent context.

- **agentId**: prom16-a1-haiku-2026-04-29
- **researchedAt**: 2026-04-29
- **target repo**: `/Users/lagyeongjun/CD/SYMPOSIUM/SKILLS` (16 commits, 3 tags v26.0.0~v26.0.2, 27 stable skills)
- **현 자산**: MANIFEST.json (merkle_root) + SBOM.json + in-toto attestation + .well-known/skills/index.json + CHANNELS.md + AGENTS.md
- **부족 식별 (사용자 지정)**: ① CHANGELOG.md ② 각 SKILL.md `## History` ③ KG `:SkillVersion` 노드 ④ `_external/` 8 collection cross-ref

---

## 0. 현 SYMPOSIUM/SKILLS 실태 분석 (실 데이터 기반)

### 0.1 git history (16 commits)

```
ce92391 chore: initialize skill repo (rollback infra for ActionPlan)
6da81af feat(skills): add kg_ref frontmatter field to all 27 SKILL.md (Phase C2)
6d4f6cf chore(skills): add MANIFEST.json v1 (metadata + git_tree_sha per skill)
065b2ac fix(manifest): rebuild after pre-commit hook test cleanup
c2ce74e fix(manifest): deterministic generatedAt = HEAD commit time
f655c2d fix(manifest): correct git_tree_sha via rev-parse HEAD:<path>
697fdae feat(manifest+discovery): merkle_root + .well-known/skills/index.json
606bfad chore(governance): add CODEOWNERS placeholder (Plan-3 phase 1)
224d379 feat(channel): introduce channel field + CHANNELS.md policy (Plan-6 phase 1)
4b9a3f7 chore(manifest): rebuild after kg_ref drift (Plan-5 phase 2)
9376bc9 feat(supply-chain): SBOM + in-toto attestation + OCI skeleton
bba9283 feat(supply-chain+marketplace): GH Actions skill-supply-chain.yml + marketplace.json
2ca6d68 feat(discovery): AGENTS.md cross-tool index + .agents/skills/ symlink shim (Phase D)
c528c97 chore(artifacts): refresh MANIFEST/SBOM/attestation/index for HEAD=2ca6d68
d053308 fix(ci): add bin/ to git + workflow path injection (CI activation pre-fix)
dccafc1 refactor(helpers): path-agnostic via __file__/SCRIPT_DIR (Q7) + remove workflow sudo ln hack
```

→ **Conventional Commits 준수율 = 16/16 (100%)** (`feat`, `fix`, `chore`, `refactor` types).
→ tags: `v26.0.0` (init/baseline), `v26.0.1` (HEAD=d053308 MANIFEST 시점), `v26.0.2` (latest).
→ MANIFEST.json: `git_head_short=d053308`, `git_latest_tag=v26.0.1` — **2 commits drift** (dccafc1 미반영).

### 0.2 부족 항목 — A1 axis 진단

| 항목 | 현재 | SCM 정전 요구사항 | gap |
|------|------|-------------------|-----|
| CHANGELOG.md | 부재 | Keep a Changelog 1.1.0 (Added/Changed/Deprecated/Removed/Fixed/Security) | **CRITICAL** — 외부 consumer 가 보는 변천사 1차 surface 누락 |
| 각 SKILL.md `## History` | 부재 | 각 component의 evolution history (Lehman law I "Continuing Change" 가시화) | **HIGH** — per-skill drift 추적 불가능 |
| KG `:SkillVersion` 노드 | 부재 | Configuration Item identification (IEEE 828 §5.2.1.1) | **HIGH** — KG ↔ git tag binding 무. SymposiumKG 가 단순 commit hash만 추적 |
| `_external/` 8 collection cross-ref | `INDEX.md` 만 존재 | 외부 정전 referent traceability (Longinus 7-layer) | **MEDIUM** — referent 로 underrate 금지 (memory) |

---

## S1. 정전 이론 (Theoretical Canon, 1972~2005)

### S1.1 Rochkind SCCS (1975) — 모든 VCS 의 조상

Marc J. Rochkind, "The Source Code Control System", IEEE Transactions on Software Engineering, **Vol. 1, No. 1, pp. 364-370** (March 1975). Bell Labs.

> *"facilities for storing, updating, and retrieving all versions of modules, for controlling updating privileges, for identifying load modules by version number, and for recording who made each software change, when and where it was made, and why."*

핵심 5 질문 ("the five W's of SCM"):
1. **Who** changed it
2. **What** was changed (delta)
3. **When** was it changed
4. **Where** in the codebase
5. **Why** it was changed (commit message)

→ SYMPOSIUM/SKILLS 의 git log 는 5 W 모두 captures (author/diff/timestamp/path/message).
→ 그러나 **per-skill granular 5 W** (이 skill 의 v22→v23 이 *왜* changed?) 는 currently invisible — `## History` section 부재가 직접적 원인.

### S1.2 Tichy RCS (1985) — Delta storage + branching

Walter F. Tichy, "RCS — A System for Version Control", **Software: Practice and Experience, Vol. 15, No. 7, pp. 637-654** (1985). Purdue University.

> *"For conserving space, RCS stores deltas, i.e. differences between successive revisions. Usage statistics show that RCS's delta method is space and time efficient."*

기여:
- **Reverse delta** — 최신 revision 은 full text, 과거는 reverse-applied diff.
- **Symbolic names** (tag의 조상).
- **Locking** for concurrent edit prevention.

→ git 의 content-addressable storage 는 Tichy 의 *snapshot* 방식 (delta가 아닌 SHA-1 indexed blob) 으로 진화한 후손. 그러나 *왜* delta vs snapshot 이 의미있는가는 Tichy 가 정초.

### S1.3 Lehman's Laws (1974/1980/1996) — 8 laws of software evolution

Meir M. Lehman (Imperial College London), 1974 IBM OS/360 study → 1980 ICSE paper "Programs, Life Cycles, and Laws of Software Evolution" → 1996 "Laws of Software Evolution Revisited".

8 법칙 (E-type 시스템 = real-world에 묶여 환경 적응 강제):

| # | 법칙 | 연도 | SYMPOSIUM/SKILLS 함의 |
|---|------|------|----------------------|
| I | Continuing Change | 1974 | 27 skill 모두 계속 진화. v26 정지 가정 = 위반 |
| II | Increasing Complexity | 1974 | 16 commit → 27 skill → KG node + Longinus + Naesengmoon LensSet ... 복잡도 증가. 명시적 refactor 없으면 entropy↑ |
| III | Self Regulation | 1974 | commit/release 빈도 분포 normal — measurable |
| IV | Conservation of Organisational Stability | 1978 | activity rate invariant — single dev (사용자) repo 라 N/A |
| V | Conservation of Familiarity | 1978 | 사용자 mastery 유지 필요 — `## History` 부재 = 이 법칙 위반 |
| VI | Continuing Growth | 1991 | functional content 계속 증가 (5대 무기 → APT/TPA → 인프라) |
| VII | Declining Quality | 1996 | 환경 변화에 적응 안 하면 품질 *체감* 하락 — Anthropic skill spec 변하면 따라가야 |
| VIII | Feedback System | 1996 | "다단계, 다루프, 다행위자 피드백 시스템" — APT/TPA + agent-feedback-loop-canonical-2026-04-27 가 정확히 이것 |

→ **법칙 II + V + VIII** 이 가장 직접적. CHANGELOG/History/SkillVersion 부재 = entropy 누적 + familiarity 유실 + feedback loop 정전화 미흡.

### S1.4 Estublier et al. (2005) — SCM impact survey

Jacky Estublier, David Leblang, André van der Hoek, Reidar Conradi, Geoffrey Clemm, Walter Tichy, Darcy Wiborg-Weber, "Impact of Software Engineering Research on the Practice of Software Configuration Management", **ACM Transactions on Software Engineering and Methodology (TOSEM), Vol. 14, No. 4, pp. 383-430** (October 2005).

5 dimensions of SCM impact:
1. **Versioning model** (RCS delta → CVS optimistic → SVN atomic → Git DAG)
2. **System model** (file-level → component → product line)
3. **Workspace model** (checkout/checkin → DVCS clone)
4. **Process support** (workflow enforcement)
5. **Components** (dependency, build, configuration)

→ SYMPOSIUM/SKILLS 의 MANIFEST.json + SBOM = **System model + Components** dimension 우수. 그러나 **Process support** (channel 전환 절차 자동화) 와 **Workspace model** (`_external/` 8 collection 의 vendoring/submodule 정책) 이 약함.

### S1.5 Git internals (Pro Git, Chacon & Straub, 2014~)

Scott Chacon, Ben Straub. *Pro Git*, 2nd ed., Apress, 2014. (free at git-scm.com/book)

핵심:
- **Content-addressable filesystem**: SHA-1(content) = address.
- **Object types**: blob (file content) | tree (directory) | commit (snapshot+metadata+parent ptr) | tag (named reference + signature).
- **DAG**: commits 가 parent ptr 로 연결된 directed acyclic graph. branch = pointer-to-commit. merge = commit with N parents.

→ MANIFEST.json 의 `merkle_root` 는 git 의 content-addressable principle 을 skill-collection layer 로 lift 한 것 — *aggregate hash of (skill name, version, kg_ref, channel, git_tree_sha)*. 이것은 이미 SCM canonical pattern 의 정확한 application.

---

## S2. 산업 표준 / RFC

### S2.1 IEEE 828-2012 — SCM Plan standard

"IEEE Standard for Configuration Management in Systems and Software Engineering", IEEE Std 828-2012. https://standards.ieee.org/standard/828-2012.html (predecessor: IEEE 828-1998).

요구 활동:
1. **Configuration Identification** — CI 식별 + 명명 + 베이스라인.
2. **Configuration Change Control** — 변경 요청 → 평가 → 승인 → 적용.
3. **Configuration Status Accounting** — 변경 이력 reporting.
4. **Configuration Audit** — 기능/물리 일치 감사.
5. **Build & Release Engineering** (2012 추가).

→ SYMPOSIUM/SKILLS mapping:
- (1) Identification: `MANIFEST.json` skills[] 의 (name, version, kg_ref, git_tree_sha) — **충족**
- (2) Change Control: git PR + CODEOWNERS — **부분 충족** (placeholder만)
- (3) Status Accounting: **CHANGELOG.md 부재로 미충족** ← critical gap
- (4) Audit: `skill-validator.sh --manifest-check` (CHANNELS.md §47) — 충족
- (5) Build/Release: GH Actions `skill-supply-chain.yml` — 충족

### S2.2 ISO 10007:2017 — Quality management 가이드라인

"Quality management — Guidelines for configuration management", ISO 10007:2017 (3rd ed., 1995/2003/2017). https://www.iso.org/standard/70400.html

5 process components: planning, identification, change control, status accounting, audit. (IEEE 828 과 95% overlap, 보다 process-quality 지향)

→ 산업/항공/방위/SW 등 분야 무관 적용. SYMPOSIUM/SKILLS 같은 skill 라이브러리도 *configuration item* 으로 취급 가능.

### S2.3 SemVer 2.0.0 — semantic versioning

Tom Preston-Werner. "Semantic Versioning 2.0.0". https://semver.org/

```
X.Y.Z   X = major (incompatible API change)
        Y = minor (backward-compatible feature)
        Z = patch (backward-compatible fix)
```

→ 현 tag `v26.0.0~v26.0.2` 는 SemVer 형식 준수. 그러나 *26* 의 의미가 불명확 — APT methodology version (v26)? 아니면 release year? `THEORY/INDEX.md` 와 `apt SKILL.md` 가 "v26 = APT methodology revision" 으로 사용중이라 **collection version ≠ component version** 분리 필요.

### S2.4 Conventional Commits 1.0.0 — commit message → SemVer 자동매핑

"Conventional Commits 1.0.0". https://www.conventionalcommits.org/en/v1.0.0/

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

매핑:
- `fix:` → PATCH
- `feat:` → MINOR
- `BREAKING CHANGE:` footer 또는 `feat!:`/`fix!:` → MAJOR

→ SYMPOSIUM/SKILLS 16 commit 모두 형식 준수. 하지만 `BREAKING CHANGE:` 로 표시된 commit 은 **0건** — v26.0.0→v26.0.2 PATCH bump 만 발생, 즉 breaking 없음 (consistent).

### S2.5 Keep a Changelog 1.1.0

Olivier Lacan. "Keep a Changelog 1.1.0". https://keepachangelog.com/en/1.1.0/

6 카테고리:
- **Added** — 새 기능
- **Changed** — 기존 기능 변경
- **Deprecated** — 곧 제거될 기능
- **Removed** — 제거된 기능
- **Fixed** — 버그 수정
- **Security** — 보안 관련

원칙:
- Changelogs are *for humans*, not machines.
- Every version에 entry.
- 같은 종류는 그룹.
- 최신이 위.
- Release date in ISO 8601.
- SemVer 준수 명시.

→ **SYMPOSIUM/SKILLS 에 부재**. 권장: `CHANGELOG.md` 생성, Conventional Commits 자동 변환 도구 (e.g., `conventional-changelog-cli`, `git-cliff`) 사용.

### S2.6 in-toto + SLSA — supply chain provenance

- in-toto Attestation Framework: https://github.com/in-toto/attestation
- SLSA spec v1.1: https://slsa.dev/spec/v1.1/

> SLSA defines the predicate type `https://slsa.dev/provenance/v0.1` within the in-toto attestation framework.

→ SYMPOSIUM/SKILLS 는 이미 in-toto attestation 보유 (commit 9376bc9). 권장: SLSA Build Level 명시 (현재 L1 또는 L2 추정).

---

## S3. 함정 / Anti-pattern

### S3.1 Software entropy / code rot — Lehman III 자기조절 위반

> *"The natural state of complex systems is disorder. Order exists only because energy is continually spent to maintain it."* — Software Entropy 정전 인용.

Lehman 이 원래 *entropy* 단어를 사용. 변경이 disorder 도입 → 명시적 refactoring (push back) 없으면 구조 붕괴.

**SYMPOSIUM/SKILLS 적용**:
- 27 skill 의 alias (prom/prometheus, tlb/taliban, 88-taliban) cross-reference 가 깨지지 않게 *MANIFEST drift detection* 이 필수 — 이미 `kg_ref drift` rebuild commit (4b9a3f7) 으로 발견된 패턴. **잠재적 entropy source**.

### S3.2 Big-bang merge / merge hell

장기 long-lived branch → 트렁크와 divergence → merge 시 conflict 폭발.

→ trunk-based development (TBD) 권장. SYMPOSIUM/SKILLS 는 single-dev/single-main 이라 자동 회피, 그러나 *외부 contributor* 영입 시 즉시 위협.

### S3.3 Diverging branches without rebase

→ 본 repo 는 main only, branch 부재. 향후 channel 별 branch (experimental/beta/stable) 도입 시 적용.

### S3.4 "Continuous broken master" syndrome

feature flag 없이 미완성 코드 main 직진 → main 항상 broken.

해법 (Martin Fowler, "Feature Toggles", 2017): https://martinfowler.com/articles/feature-toggles.html
> Wrap new changes in inactive code path, activate later. CHANNELS.md `experimental` channel + `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` kill-switch 가 정확히 이 패턴.

→ SYMPOSIUM/SKILLS 가 이미 채택. 평가: 매우 우수.

### S3.5 Lock-step monolithic versioning — 모든 skill 동일 version 강제 시 churn

monorepo 에서 모든 component 를 같은 version 으로 bump 하면:
- 변경 안 한 skill 도 신규 version 발급 → false signal.
- consumer 가 version mismatch 추적 불가.

해법: **independent versioning per skill** (changesets, Nx, Lerna 등 독립 bump 도구).

→ SYMPOSIUM/SKILLS 는 이미 per-skill `version` field (MANIFEST.json) 보유 — 88-taliban=3, apt=26, backup=1 등 이질적 version. 우수. 그러나 collection-level tag (v26.0.0) 와의 관계 미명시.

### S3.6 RUBBER_STAMP CHANGELOG (사용자 lesson 적용)

> "외부 verdict (compiler/사용자/critic) → root cause → KG symmetric pair Lesson" (memory)

CHANGELOG 도 *고무도장* 위험: "v1.2.0: improvements" 같은 무의미 entry. 해법: Conventional Commits → CHANGELOG 자동 생성 + `BREAKING CHANGE:` footer 강제.

---

## S4. 2026 Trends + AI Agent Context

### S4.1 Claude Code skills marketplace (Anthropic 공식)

- 공식 repo: https://github.com/anthropics/skills
- 공식 docs: https://code.claude.com/docs/en/skills
- 출시: 2025-12-18 (Agent Skills open standard).
- 2026-03 기준 **32 tools 채택** (Claude Code, OpenAI Codex/ChatGPT, Cursor, VS Code, Gemini CLI, Kiro, Goose, JetBrains Junie 등).

핵심 요구:
- `SKILL.md` with YAML frontmatter (name, description, etc.) + Markdown 본문.
- `kg_ref` (SYMPOSIUM 자체 확장), `version`, `channel` 은 *non-standard extension* — 이식성 보전 위해 standard fields 우선.

### S4.2 AGENTS.md cross-tool standard

- 공식: https://agents.md/ (Google + OpenAI + Factory + Sourcegraph + Cursor 공동 출시)
- spec repo: https://github.com/agentsmd/agents.md

차이:
- **AGENTS.md** = README for agents (cross-tool, 비-Anthropic).
- **CLAUDE.md** = Anthropic 고유 (Claude Code 가 native 로 읽음).
- **SKILL.md** = Agent Skills open standard (32 tools 채택, AGENTS.md 와 별개 stack).

→ SYMPOSIUM/SKILLS 는 이미 AGENTS.md (commit 2ca6d68) + SKILL.md (모든 27 skill) 동시 보유. **이중 호환** 우수.

### S4.3 Generative changelog (LLM 자동 분류)

LLM 이 commit messages → CHANGELOG 자동 생성 + 카테고리 (Added/Changed/Fixed) 분류. 도구:
- `git-cliff` (Conventional Commits 기반 deterministic)
- `release-please` (Google, GitHub Action)
- LLM 직접: prompt 로 PR 단위 generative summary

→ SYMPOSIUM 권장: deterministic (`git-cliff`) 우선 + LLM 보강 (사용자 lesson "사후 fitting 금지" 준수 위해 deterministic baseline 필수).

### S4.4 Agent-driven git workflow

Claude Code / Cursor 가 자동:
- commit message 생성 (Conventional Commits 형식)
- branch 생성 / PR 작성 (gh CLI)
- skill version bump (changesets-style)

→ SYMPOSIUM 의 `apt-meta-review` skill 이 부분적으로 이 역할 (Lesson → SKILL.md patch). 이를 *changelog auto-generation* 으로 확장 가능.

### S4.5 Skill drift detection (merkle_root signal)

`merkle_root` change 가 *유일한 trustworthy signal* for "something changed". MANIFEST drift 발생 시:
1. merkle_root mismatch 감지
2. 어떤 skill 의 `git_tree_sha` 가 바뀌었는지 diff
3. 해당 skill `version` bump 또는 *suspicious change* 경고

→ 현 4b9a3f7 ("rebuild after kg_ref drift") commit 이 정확히 이 메커니즘 작동 증거.

### S4.6 SkillVersion KG 노드 — 권장 schema

```cypher
(:SkillVersion {
  id: 'sv_apt_v26_2026-04-21',
  skill_name: 'apt',
  version: 26,
  channel: 'stable',
  git_tree_sha: '8b8a4bf...',
  released_at: '2026-04-21T...',
  changelog_entries: ['feat: A1 MIC slot expansion', 'feat: A4 MethodologyConfig slot', ...],
  breaking_changes: [],
  predecessor: 'sv_apt_v25_2026-04-17',
  manifest_merkle_root: 'd8c62efd...'
})
-[:SUPERSEDES]->(:SkillVersion {id: 'sv_apt_v25_...'})
-[:DEFINED_BY]->(:Skill {kg_ref: 'ATOM_Skill_apt_orchestrator'})
-[:RELEASED_IN]->(:Release {tag: 'v26.0.1'})
```

→ 이 schema 가 IEEE 828 §5.2 Configuration Identification + Status Accounting 을 KG 형태로 만족.

---

## 권장사항 (Action items)

### P1 (즉시) — CHANGELOG.md 생성

1. `git-cliff` 또는 `conventional-changelog-cli` 도입.
2. `CHANGELOG.md` (Keep a Changelog 1.1.0 형식) 생성 — 16 commit → v26.0.0/v26.0.1/v26.0.2 entries.
3. CI 에서 `CHANGELOG.md` 자동 갱신 (GH Actions).

### P2 (이번 sprint) — 각 SKILL.md `## History` section

표준 template:
```markdown
## History

| Version | Date       | Changes                                 | KG Lesson         |
|---------|------------|-----------------------------------------|-------------------|
| v26     | 2026-04-21 | A1-A6 MIC slot expansion (10 slots)     | lesson-...-2026-04-21 |
| v25     | 2026-04-17 | error_variants extension, SharedType    | lesson-...-2026-04-17 |
| v22     | 2026-04-16 | Gate Check Hook enforcement             | lesson-...-2026-04-16 |
```

→ 27 skill 모두 적용 시 Lehman V (Conservation of Familiarity) 보장.

### P3 (이번 quarter) — KG `:SkillVersion` 노드 도입

§S4.6 schema 채택. 기존 `ATOM_Skill_*` 와 N:1 (Skill : SkillVersion). MANIFEST.json 갱신 시 KG 동기 write.

### P4 — `_external/` 8 collection cross-ref

각 external collection (anthropics, davepoon-collection, hesreallyhim-agents, iannuttall-agents, obra-superpowers, VoltAgent-categories, wshobson-agents) → SYMPOSIUM skill 와의 mapping 표 (`_external/INDEX.md` 확장).

→ **외부 정전 referent underrate 금지** (memory) 원칙 적용.

### P5 (long-term) — SLSA Build Level 명시

현 in-toto attestation → SLSA L2 (signed provenance) 또는 L3 (hardened build platform) 명시.

---

## Open Questions

1. **collection version vs skill version 관계 정식화** — `v26.0.0` (collection tag) 는 어떤 skill version aggregate? merkle_root 만 binding 하나, 각 skill `version` bump 와의 mapping 룰 부재.
2. **CHANGELOG vs `## History` 중복 위험** — 둘 다 도입 시 single source of truth?
3. **SkillVersion KG 노드 + git tag 의 단일화** — KG 가 정전 vs git 이 정전?
4. **Anthropic SKILL.md spec 변화 대응** — frontmatter 추가 필드 (e.g., `kg_ref`, `channel`) 가 future spec 과 충돌 시?
5. **RUBBER_STAMP 방지** — generative changelog 가 무의미 entry 생성하는 risk vs deterministic git-cliff 의 entry 빈약 risk 사이 balance?

---

## References (1차 소스 URL)

### S1 Theoretical Canon
- Rochkind 1975: https://dl.acm.org/doi/10.1109/TSE.1975.6312866
- Tichy 1985: https://onlinelibrary.wiley.com/doi/abs/10.1002/spe.4380150703
- Tichy 1985 PDF: https://www.gnu.org/software/rcs/tichy-paper.pdf
- Lehman 1980 PDF: https://users.ece.utexas.edu/~perry/education/SE-Intro/lehman.pdf
- Lehman 1996 revised: https://gwern.net/doc/cs/1996-lehman.pdf
- Lehman's Laws Wikipedia: https://en.wikipedia.org/wiki/Lehman%27s_laws_of_software_evolution
- Estublier et al. 2005 ACM TOSEM: https://dl.acm.org/doi/10.1145/1101815.1101817
- Estublier roadmap PDF: http://www0.cs.ucl.ac.uk/staff/a.finkelstein/fose/finalestublier.pdf
- Pro Git book: https://git-scm.com/book/en/v2
- Pro Git Internals chapter: https://git-scm.com/book/en/v2/Git-Internals-Git-Objects

### S2 Standards / RFCs
- IEEE 828-2012: https://standards.ieee.org/standard/828-2012.html
- IEEE 828-2012 IEEE Xplore: https://ieeexplore.ieee.org/document/6170935
- ISO 10007:2017: https://www.iso.org/standard/70400.html
- SemVer 2.0.0: https://semver.org/
- Conventional Commits 1.0.0: https://www.conventionalcommits.org/en/v1.0.0/
- Keep a Changelog 1.1.0: https://keepachangelog.com/en/1.1.0/
- in-toto attestation: https://github.com/in-toto/attestation
- SLSA v1.1: https://slsa.dev/spec/v1.1/
- SLSA Provenance v0.1: https://slsa.dev/spec/v0.1/provenance

### S3 Anti-patterns
- Software Entropy Wikipedia: https://en.wikipedia.org/wiki/Software_entropy
- Technical Debt Wikipedia: https://en.wikipedia.org/wiki/Technical_debt
- Trunk-based development: https://trunkbaseddevelopment.com/
- Atlassian TBD: https://www.atlassian.com/continuous-delivery/continuous-integration/trunk-based-development
- Martin Fowler "Feature Toggles": https://martinfowler.com/articles/feature-toggles.html

### S4 2026 AI Agent Context
- Anthropic skills repo: https://github.com/anthropics/skills
- Claude Code skills docs: https://code.claude.com/docs/en/skills
- Anthropic engineering blog (Agent Skills): https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Anthropic Skills launch blog: https://claude.com/blog/skills
- AGENTS.md spec: https://agents.md/
- AGENTS.md GitHub: https://github.com/agentsmd/agents.md
- Agent Skills open standard explainer: https://www.agensi.io/learn/agent-skills-open-standard
- git-cliff (Conventional Commits → CHANGELOG): https://git-cliff.org/

---

## A1 Axis 한 줄 정리

**SYMPOSIUM/SKILLS 는 SCM 정전 (IEEE 828 / ISO 10007 / SemVer / Conventional Commits / SLSA / in-toto) 의 ~70% 를 이미 채택함. CHANGELOG.md + `## History` + `:SkillVersion` KG 3종 도입으로 Lehman V/VIII 법칙(Familiarity 보존 + Feedback System) 까지 충족하면 *agent-driven SCM 의 reference implementation* 이 된다.**
