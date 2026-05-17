# Skill 변천사·Versioning·Provenance 학문 grounding — PROM 16 v1

> **Cycle:** `prom16-skill-versioning-2026-04-29`
> **Lesson KG:** `lesson-prom16-skill-versioning-academic-2026-04-29`
> **16/16 ResearchFinding** (verified=true, gate_passed=true; subagent=haiku general-purpose)
> **10 SubagentTaskSpec 씨앗** (6 consensus HIGH + 2 conflict EXPLORATION + 2 verify VERIFY)
> **Hyperedge:** `hyperedge-prom16-skill-versioning-2026-04-29` (cardinality=16)
>
> **주제:** SYMPOSIUM/SKILLS 의 변천사 관리 (CHANGELOG / SKILL.md ## History / KG :SkillVersion / cross-ref) 의 *학문적 grounding*. Software Configuration Management + Versioning Schemes + Release Engineering + Provenance/SBOM/SLSA 4 정전 영역 추적.
>
> **현 상태**: 별도 git repo (16 commits, tags v26.0.0~v26.0.2), MANIFEST.json (merkle_root) + SBOM.json (CycloneDX 1.5) + in-toto attestation + .well-known/skills/index.json + CHANNELS.md. **Anthropic 공식 (anthropics/skills) 보다 *훨씬 엄격* — 0/17 official skills 가 SBOM/MANIFEST/attestation 부재 (SLSA L0 baseline).**

---

## 0. Axis × Sub-axis 매트릭스 (4 × 4 = 16 cells)

### 4 Axes

| 축 | 라벨 | 핵심 정전 |
|---|---|---|
| **A1** | Software Configuration Management | Lehman 8 laws / Tichy RCS 1985 / Rochkind SCCS 1975 / Estublier 2005 / Git internals |
| **A2** | Versioning Schemes | SemVer 2.0.0 / CalVer / EffVer 2024 / Hyrum's Law / Bertrand Meyer OCP |
| **A3** | Release Engineering & Channels | Adams-McIntosh SANER 2016 / Humble-Farley CD 2010 / Google SRE / Chrome 5채널 / MS 2026-04 통합 |
| **A4** | Provenance & Supply Chain | SLSA v1.0 / in-toto / sigstore / CycloneDX 1.6 / SPDX 3.0.1 / NTIA SBOM Min Elements |

### 4 Sub-axes

```
S1  정전 이론 (Theoretical canon)         — 50+년 학문/책/paper
S2  산업 표준 (Industry standard / RFC)   — IEEE/ISO/spec/RFC
S3  함정 (Anti-pattern / pitfalls)        — 실패 사례, 위반 risk
S4  2026 trends + AI agent context       — Claude Code / Anthropic / marketplace
```

---

## 1. 합의 (Consensus, 2+ axis 동의)

### C1. **CHANGELOG.md 신규 — Keep a Changelog 1.1.0 + git-cliff 자동** (HIGH, A1+A2)

- A1 S2: IEEE 828/ISO 10007/SemVer/CC/in-toto/SLSA stack 5/6 충족 → **last-mile = CHANGELOG.md**
- A2 S3: history 부재 = ZeroVer 함정과 동치 (사용자 모든 observable 의존 가능)
- 권장: deterministic git-cliff baseline + LLM 보강 hybrid (RUBBER_STAMP 방지)

→ Conventional Commits 100% 이미 준수 → 자동 파이프라인 즉시 가능.

### C2. **각 SKILL.md `## History` section 표준화** (HIGH, A1+A2)

- A1 S1: **Lehman V (Conservation of Familiarity) 위반 위험** — per-skill history 부재
- A2 S3: ZeroVer 함정 동치 — frontmatter integer 1개로 변경 이유 표현 불가
- 표준 형식:
```markdown
## History
- v26 (2026-04-26) — A6 resolve-only, MIC slot 3개 추가 (lesson-...)
- v25 (2026-04-17) — error_variants extension
- ...
```
- 우선: 5대 무기 6개 (apt/harness/longinus/taliban/jaebaeman/prometheus) → 27 backfill

### C3. **frontmatter `version: <int>` → SemVer string 마이그레이션** (HIGH, A2)

- A2 S1: integer 26은 SemVer 위반 — PATCH/MINOR 분리 표현 불능
- A2 S3: MANIFEST.json 27 skills version *type 혼재* (int 26, string '3.1', '1.0') → JSON Schema 검증 깨짐 risk
- A2 S4: Anthropic 공식 0/17 official skills 가 version 필드 부재 — **GH issue #37 'unexpected key version' reject risk**
- 옵션 (a) `metadata.version` nesting (공식 키 안), (b) 별도 VERSION 파일, (c) git tag SemVer + frontmatter SemVer string 병기 — **권장 (c)**

### C4. **KG `:SkillVersion` + `:EVOLVED_FROM` edge — Longinus binding** (HIGH, A1+A4)

- A1 S1: Lehman VIII (Feedback System) 정합 — `agent-feedback-loop-canonical-2026-04-27` 정의 합치
- A4 S4: SBOM properties.kg:ref → Neo4j ATOM binding *산업 novel* (in-toto subject.digest 확장)
- 노드 schema:
```cypher
:SkillVersion {
  name, version, kg_ref, frontmatter_hash,
  released_at, channel, attestation_uri,
  git_tree_sha, merkle_local
}
[:EVOLVED_FROM {via_commit, lesson_ids}]
```
- ReferenceSite L7-CodeBinding 으로 SKILL.md 의 git commit hash 와 binding

### C5. **cosign keyless 서명 + SLSA L2 달성** (HIGH, A4)

- 현 `_signature.status = "UNSIGNED"` (in-toto attestation 만, 서명 없음)
- GH Actions OIDC → Fulcio (CA) → Rekor (transparency log) keyless flow
- reproducible build (`SOURCE_DATE_EPOCH`) 추가
- SLSA L0 → L2 진입 (현 Anthropic 공식 = L0 baseline)

### C6. **per-skill progressive rollout + per-skill kill switch** (HIGH, A3)

- A3 S2: Chrome 5채널 1-5%→100% gradual 패턴 (직접 인용)
- A3 S2: **MS 2026-04-24 (이번 달) Insider Experimental+Beta 통합** — "channel coarse + flag fine" 분리 트렌드 evidence
- A3 S3: Anthropic kill switch 6+ env vars (`CLAUDE_CODE_DISABLE_*`) — SYMPOSIUM 1개만 채택
- 권장: per-skill `SYMPOSIUM_DISABLE_<NAME>` env var 확장. drift 자동 강등 (merkle mismatch → stable→beta)

---

## 2. 분기/대립 (Divergence)

### D1. **SemVer (industry) vs EffVer (SYMPOSIUM 의미적)** (A2 S1)

- SemVer = spec dependency-hell 회피 정전. SYMPOSIUM은 spec 아닌 *agent prompt* — 'breaking' 의미 변형
- EffVer (Tomlinson 2024) = MACRO.MESO.MICRO effort 기반 → 더 의미적
- **하이브리드**: SemVer 표면 + EffVer 주석 보조 — apt 시범 추적

### D2. **Channel coarse vs Feature flag fine** (A3 S4 NEW trend)

- MS 2026-04-24 Insider Experimental+Beta 통합 = channel 축소 + flag 확장 evidence
- SYMPOSIUM 현재 channels (experimental/beta/stable, 3개) — 유지 vs 고도화?
- A3 worker: per-skill flag 확장 권장. evidence-based decision

---

## 3. Open Questions

| ID | 질문 | 출처 | 우선 |
|---|---|---|---|
| Q1 | Anthropic 공식 frontmatter spec — version 필드 reject risk 정확 검증 | A2 S4 (GH #37) | HIGH |
| Q2 | SBOM properties.kg:ref → in-toto extension *논문화* 가능성 | A4 S4 | MEDIUM |
| Q3 | collection version (v26.0.x) vs per-skill version mapping 룰 | A1 Q1 | HIGH |
| Q4 | MIC slot 추가 (apt 7→10) = SemVer MAJOR vs EffVer MESO? | A2 OQ | MEDIUM |
| Q5 | KG ATOM_Skill_* vs SKILL.md frontmatter drift 시 ground truth? | A2 OQ | HIGH |
| Q6 | tpa-* '1.0' string의 PATCH 표현 방법 | A2 OQ | LOW |
| Q7 | Conventional Commits 한국어 처리 (영문 type + 한국어 desc?) | A2 OQ | LOW |
| Q8 | Channel Drift 학문 paper 부재 — industry folklore 수준 | A3 S3 | MEDIUM |
| Q9 | LLM-generated SBOM hallucination risk 정량화 | A4 S4 | MEDIUM |

---

## 4. 권장 후속 작업 (Follow-ups, 차근차근)

### F1 (즉시, 30분) — `CHANGELOG.md` 신규 + git-cliff 설정

```bash
# git-cliff 설치 + 16 commit 자동 추출
brew install git-cliff
git-cliff -o CHANGELOG.md
```

Conventional Commits 이미 100% → 자동 생성 잘 됨.

### F2 (단계적, 우선 5대 무기 6개) — 각 SKILL.md `## History` section

apt/harness/longinus/taliban/jaebaeman/prometheus 6개 SKILL.md 끝에 표준 history section 추가. KG Lesson과 cross-ref.

### F3 (1일 작업) — frontmatter `version` SemVer string migration + MANIFEST type 통일

27 skills frontmatter `version: 26` → `version: "26.0.1"`. MANIFEST.json type 통일 (int+string 혼재 해소). validator 갱신.

### F4 (1주 작업) — KG `:SkillVersion` + `:EVOLVED_FROM` 결정화

```cypher
UNWIND $skills AS s
MERGE (sv:SkillVersion {name: s.name + '-v' + s.version})
SET sv.kg_ref = s.kg_ref, sv.frontmatter_hash = s.hash,
    sv.released_at = s.date, sv.channel = s.channel,
    sv.git_tree_sha = s.git_tree_sha
WITH sv, s
OPTIONAL MATCH (prev:SkillVersion {name: s.name + '-v' + s.prev_version})
FOREACH (_ IN CASE WHEN prev IS NOT NULL THEN [1] ELSE [] END |
  MERGE (sv)-[:EVOLVED_FROM]->(prev)
)
```

Longinus binding: ReferenceSite L7-CodeBinding (`git_commit_hash`).

### F5 (2주 작업) — cosign keyless + SLSA L2

GH Actions workflow 추가:
```yaml
- uses: sigstore/cosign-installer@v3
- name: Sign attestation (keyless OIDC)
  run: cosign sign-blob --yes .well-known/skills/attestation.json
```

Rekor transparency log 등록. SLSA L2 달성.

### F6 (R&D) — per-skill progressive rollout + kill switch 자동화

`bin/skill-rollout.sh` — % 단계별 release. `SYMPOSIUM_DISABLE_<NAME>` env var. drift 자동 강등 (merkle mismatch → stable→beta).

---

## 5. 사용자 핵심 답 (직접)

### "git 레포 따로 파서 관리하는게 best?"
**→ 정답. 너 *이미* 별도 repo 운영 중. Anthropic 공식보다 더 엄격.**

### "변천사 로그 어떻게?"
**4 layer 통합**:

| Layer | 도구 | 누가 보나 | 자동화 |
|---|---|---|---|
| **L1 git** | `git log`, tag (v26.0.0~v26.0.2) | git 사용자 | Conventional Commits |
| **L2 CHANGELOG.md** | Keep a Changelog 1.1.0 | 사용자 / 외부 consumer | git-cliff 자동 |
| **L3 SKILL.md `## History`** | per-skill section | skill 사용자 | apt-meta-review hook |
| **L4 KG `:SkillVersion`** | Neo4j + Longinus binding | KG-aware tools | post-commit hook |

→ 4 layer 다 채우면 *완전한 변천사* 확보. 현재 L1 만 충족, L2-L4 부족.

---

## 6. 학문 정전 cite (실제 1차 소스)

### A1 SCM
- Lehman M.M. (1980) "Programs, life cycles, and laws of software evolution" — *Proc IEEE* 68:9
- Tichy W.F. (1985) "RCS — A System for Version Control" — *Software: Practice & Experience* 15:7
- Rochkind M.J. (1975) "The Source Code Control System" — *IEEE TSE* SE-1:4
- Estublier J., Leblang D., van der Hoek A., et al. (2005) "Impact of SCM on Software Evolution: A Survey" — *ACM TOSEM*
- IEEE 828-2012 SCM Plans
- ISO 10007:2017 — Quality management — Configuration management

### A2 Versioning
- Preston-Werner T. (2013) **SemVer 2.0.0** — semver.org
- CalVer.org — Calendar Versioning
- Tomlinson J. (2024) **EffVer** — jacobtomlinson.dev/effver
- Hyrum's Law — hyrumslaw.com (Hyrum Wright, Google)
- Meyer B. (1988) *Object-Oriented Software Construction* — Open-Closed Principle
- PEP 440 (Python), npm node-semver, Cargo, Go modules SIV
- Conventional Commits 1.0.0 — conventionalcommits.org
- IETF httpbis BCP56bis API versioning

### A3 Release Engineering
- Adams B., McIntosh S. (2016) "Modern Release Engineering in a Nutshell" — *SANER 2016* (IEEE)
- Humble J., Farley D. (2010) *Continuous Delivery* — Addison-Wesley
- Beyer B., Jones C., Petoff J., Murphy N.R. (2016) *Site Reliability Engineering* — O'Reilly (ch on Release Engineering by Dinah McNutt)
- Kim G., Humble J., Debois P., Willis J. (2016) *The DevOps Handbook*
- SAFe Agile Release Train
- Fowler M. *Feature Toggles* — martinfowler.com/articles/feature-toggles.html

### A4 Provenance / Supply Chain
- SLSA v1.0 — slsa.dev
- in-toto specification — in-toto.io
- sigstore — sigstore.dev
- NTIA (2021) "Software Bill of Materials Minimum Elements" — EO 14028
- CycloneDX 1.5/1.6 (ECMA-424 ratified June 2024)
- SPDX 3.0.1 = ISO/IEC 5962:2021
- Reproducible Builds — reproducible-builds.org
- TUF — theupdateframework.io
- NIST SP 800-218 SSDF
- Merkle R. (1979) "A Certified Digital Signature"

---

## 7. KG Bindings

```
Lesson:           lesson-prom16-skill-versioning-academic-2026-04-29
Cycle:            prom16-skill-versioning-2026-04-29
ResearchFinding:  finding_prom16_skillver_a{1..4}_s{1..4} (16 nodes)
PromBatchWrite:   verified=true, written=16, expected=16
Hyperedge:        hyperedge-prom16-skill-versioning-2026-04-29 (cardinality=16)
SubagentTaskSpec: 6 consensus + 2 conflict + 2 verify = 10 seeds (status=READY)
```

### MinIO archive (Longinus binding)

```
bhgman/apt-papers/skills-versioning/
├── PROM_16_SKILL_VERSIONING_REPORT.md   ← L1-Document
└── axis/                                 ← L2-AxisFinding
    ├── A1_SCM.md (+ .json)
    ├── A2_Versioning.md (+ .json)
    ├── A3_ReleaseEngineering.md (+ .json)
    └── A4_Provenance.md (+ .json)
```

---

## 8. 한 줄 정리

> **별도 repo 정답 — 너 이미 잘 깎아놨음. Anthropic 공식보다 더 엄격. 부족한 건 *변천사 4 layer* — git 위에 (L2) CHANGELOG.md + (L3) SKILL.md ## History + (L4) KG :SkillVersion. 학문 정전: SCM 50+년 (Lehman/Tichy/Estublier) + SemVer/EffVer + Adams-McIntosh release eng + SLSA/in-toto provenance. 현 가장 큰 *novel*: SBOM properties.kg:ref → Neo4j ATOM binding 은 산업에 없는 패턴.**

---

# KG: ATOM_PROM16_skill_versioning_2026-04-29
# Lesson: lesson-prom16-skill-versioning-academic-2026-04-29
# Hyperedge: hyperedge-prom16-skill-versioning-2026-04-29 (cardinality=16)
