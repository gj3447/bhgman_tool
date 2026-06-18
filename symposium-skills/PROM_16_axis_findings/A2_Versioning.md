# PROM 16 — Axis A2: Versioning Schemes (학문 grounding)

> **Worker**: `prom16-a2-haiku-2026-04-29`
> **Topic**: SYMPOSIUM/SKILLS git-repo versioning — 현 `version: 26` (integer) frontmatter 패턴의 학문적 정당성 검토 + 변천사 history section 부재 처방.
> **Method**: WebSearch 1차 spec, 비교군은 Anthropic official skills mirror (`_external/anthropics/`) 17개.

---

## 0. 컨텍스트 사진

| 측정 | 값 |
|---|---|
| 현 SYMPOSIUM/SKILLS 스킬 수 | 27 |
| `version: <int>` 패턴 (예: `apt: 26`) | 다수 (apt, apt-sa, apt-sp, apt-st, apt-scw 모두 26) |
| `version: "<str>"` 패턴 (string quoted) | longinus("3.1"), tpa/tpa-* ("1.0") |
| Anthropic official skills `version:` 필드 | **0/17** (없음) |
| MANIFEST.json `version` field type | mixed: int + string (예: `"3.1"`, `"1.0"`) |
| git tag | `v26.0.0`, `v26.0.1` (SemVer-shaped) |
| frontmatter history section | **없음** — 1개 integer만 |

→ **핵심 모순**: git tag는 `v26.0.1` (SemVer 3-tier) 인데 frontmatter는 `version: 26` (integer). MANIFEST 안에서도 int/string 혼재. Anthropic 공식은 아예 version 필드 부재.

---

## S1 — 정전 이론 (Versioning Schools)

### S1.1 SemVer 2.0.0 (Tom Preston-Werner, 2013)

**Spec**: `https://semver.org/`

핵심 규칙 (12 rules 중 발췌):
- §2: `MAJOR.MINOR.PATCH` — 비음수 정수, leading zero 금지.
- §3: 한번 publish된 version은 **immutable** ("MUST NOT be modified"). 수정 = 새 version.
- §4: **`0.y.z` = 초기 개발. anything MAY change at any time. public API SHOULD NOT be considered stable.** ← SYMPOSIUM 의 `version: 26` integer 가 SemVer 의 MAJOR 위치라면 "이미 25번 breaking 발생" 의미. ZeroVer 함정 회피한 셈이지만 의도적이지는 않음.
- §5: `1.0.0` = public API 정의. 이후 bump 규칙은 "API 가 무엇이냐" 에 종속.
- §6: PATCH bump = backward-compatible bug fix only.
- §7: MINOR bump = backward-compatible 신기능 / deprecation 마킹.
- §8: MAJOR bump = backward-incompatible.
- §9-10: pre-release / build metadata syntax (`-alpha.1`, `+build.123`).

**철학**: dependency hell 회피. 라이브러리 author 가 consumer 와의 **contract** 를 숫자로 약속.

### S1.2 CalVer (calver.org)

**Spec**: `https://calver.org/`

채택 사례:
- **Ubuntu**: `YY.MM` → 24.04, 26.04 (LTS). 출시 *날짜* 자체가 product identity.
- **pip**: `YY.MINOR.MICRO` → 24.0, 24.1.
- **PyCharm/JetBrains**: `YYYY.MAJOR.PATCH`.
- **PEP 2026 (Python language CalVer 제안)**: 진행 중 (Steering Council 검토).

장점: 출시 시점 즉시 인지. 마케팅 친화. "지원 종료 시점" 자명.
단점: Hyrum's Law 와 충돌 — 날짜만으로는 breaking 여부 무지각.

### S1.3 ZeroVer (0ver.org, Mahmoud Hashemi 2018-04-01 satire)

**Spec**: `https://0ver.org/` — **풍자(April Fools) spec**.

요지: "MAJOR 가 절대 0 을 넘지 않는 versioning. 영원히 불안정 보장."

실제 ZeroVer 운영 프로젝트 (의도/비의도 무관):
- Apache Kafka, OpenSSL (전엔), TOML, ...

→ 시사점: **0.x.y 는 SemVer §4 에 의해 "anything may change" 라서 사실상 contract 부재.** 많은 OSS 가 1.0.0 jump 를 기피 (책임 회피). SYMPOSIUM/SKILLS 의 일부 `version: 1` 스킬 (db-query, deploy, kafka-manage, server-status, backup, skill-creator) 은 ZeroVer 함정에서는 벗어났지만, *선언만 1* 이고 **history section 부재** 라서 실질 contract 모호.

### S1.4 EffVer (Jacob Tomlinson 2024-01)

**Spec**: `https://jacobtomlinson.dev/effver/`

format: `MACRO.MESO.MICRO` (3-tier, SemVer 와 동형이지만 의미 상이)
- **MICRO**: 사용자 effort 0 — drop-in.
- **MESO**: small effort — 일부 수정 가능.
- **MACRO**: significant effort — 대규모 마이그레이션.

채택: JupyterHub, Matplotlib, JAX (JEP 25516).

**SemVer 와 결정적 차이**: SemVer 는 "API 호환성" (객관적 형식 차이) 을 quantify. EffVer 는 **"사용자가 마이그레이션에 들이는 시간"** 을 quantify. → "기술적으로는 breaking 이지만 99% 사용자는 영향 없음" 케이스를 MACRO 가 아닌 MESO 로 표현 가능.

→ **SYMPOSIUM/SKILLS 적용 가능성 ★**: 스킬은 라이브러리가 아니라 "AI agent 가 읽는 프롬프트". 호환성 = "기존 invocation 패턴이 여전히 작동하느냐" = effort 기반 측정에 더 가까움. Slot/MIC 추가는 SemVer 로는 MAJOR 일 수 있지만 EffVer 로는 MESO (호출자 스킬은 코드 수정 불요).

### S1.5 Hyrum's Law (Hyrum Wright, Google ~2012, term coined by Titus Winters)

**Spec**: `https://www.hyrumslaw.com/`

> *"With a sufficient number of users of an API, it does not matter what you promise in the contract: all observable behaviors of your system will be depended on by somebody."*

Implication: SemVer/EffVer 의 명시적 contract 와는 별개로, 사용자는 **모든 observable 행동에 의존**. → "implementation detail" 변경도 사실상 breaking.

XKCD 1172 ("Workflow") 가 정전 만화: 스페이스바 누름 → CPU 과열 버그 fix → 사용자가 "겨울에 아이들이 얼어죽는다" 항의.

**SYMPOSIUM 시사점**: 스킬 description 의 미세한 워딩, slash command 동작, frontmatter 필드 순서까지 — Claude (소비자) 는 모든 것에 의존 가능. 따라서 history section 은 *겉으로 사소해 보이는* 변경도 추적해야 함.

### S1.6 ImpVer / "Impact-based" (검색 시 비공식)

별도 정전 spec 부재. EffVer 에 흡수된 것으로 보임 (jacobtomlinson 본인이 EffVer 발표 시 "기존 ImpVer 아이디어를 effort 로 구체화" 입장). **추정 — Comment 처리.**

### S1.7 Bertrand Meyer — Open-Closed Principle (1988, OOSC)

**Spec**: Meyer, *Object-Oriented Software Construction*, 1988.

> *"Software entities should be open for extension, but closed for modification."*

OCP 와 versioning 의 다리:
- **closed for modification** = 1 회 publish 하면 그 version 은 immutable (≡ SemVer §3).
- **open for extension** = MINOR bump 로 새 기능 추가 가능 (≡ SemVer §7).
- → **SemVer 는 OCP 의 시간-축 구현**. version 번호 자체가 OCP enforcement 도구.

SYMPOSIUM/SKILLS 의 `apt` 스킬이 v22→v25→v26 으로 진화하면서 **MIC slots 7→10 추가**한 것은 OCP-conformant (extension). 하지만 *기존 slot 의 의미를 변경* 하면 OCP 위반 → MAJOR bump 정당화.

---

## S2 — 산업 표준 / RFC

### S2.1 PEP 440 (Python)

**Spec**: `https://peps.python.org/pep-0440/`

format: `[N!]N(.N)*[{a|b|c|rc}N][.postN][.devN][+local]`
- Epoch (`N!`) — schema 자체 변경 시 (드물게).
- Release segment — 메인 (`1.2.3`).
- Pre-release: `a1`, `b1`, `rc1`.
- Post-release: `.post1` (배포 후 메타데이터 fix).
- Dev: `.dev1`.
- Local: `+ubuntu1` (downstream patch 식별).

**SemVer 와 호환성 부분**: 메이저-마이너-패치 골격은 같으나 *pre/post/dev/local* 4 종 추가 segment 가 PEP 440 에만 있음 — Python eco 의 "원본 vs distro patch" 구분 필요성 반영.

### S2.2 Conventional Commits 1.0.0

**Spec**: `https://www.conventionalcommits.org/en/v1.0.0/`

format: `<type>[scope]: <description>` + optional `BREAKING CHANGE:` footer or `!` after scope.

타입 → SemVer bump 매핑:
- `fix:` → PATCH
- `feat:` → MINOR
- `feat!:` 또는 `BREAKING CHANGE:` footer → MAJOR

→ **commit message → version bump 자동화의 ground truth**. semantic-release / release-please 등 도구가 이걸 파싱해서 자동 bump.

### S2.3 npm semver-range syntax

**Spec**: `https://github.com/npm/node-semver`

operators:
- `^1.2.3` (caret) — left-most non-zero 고정. `1.2.3 ≤ x < 2.0.0`. 단 `^0.2.3` → `0.2.3 ≤ x < 0.3.0` (0.x 는 MINOR 가 breaking 으로 간주).
- `~1.2.3` (tilde) — patch 만 허용. `1.2.3 ≤ x < 1.3.0`.
- `>=`, `<`, `=`, `||`, ` - ` (range), `*` (wildcard).

→ SemVer §4 의 "0.x = unstable" 원칙을 caret 의 동작으로 *기계적* 으로 enforce.

### S2.4 Cargo (Rust)

**Spec**: `https://doc.rust-lang.org/cargo/reference/semver.html`

Default behavior: `"1.2.3"` ≡ `"^1.2.3"` (caret 암묵).
Pre-1.0 정책 — npm/Cargo 차이:
- npm: `^0.2.3` → `>=0.2.3 <0.3.0` (0.x 의 MINOR 가 breaking).
- Cargo: 동일하게 `^0.2.3` → `>=0.2.3 <0.3.0`. *그러나* `^0.0.3` → `>=0.0.3 <0.0.4` (0.0.x 에서는 PATCH 도 breaking).
- 추가: Cargo 는 0.x.y ↔ 0.x.z (y≥z, x>0) 를 호환으로 간주.

→ Pre-1.0 의미가 ecosystem 마다 다르다 는 함정.

### S2.5 Go modules — Semantic Import Versioning

**Spec**: `https://go.dev/ref/mod`, `https://research.swtch.com/vgo-import` (Russ Cox)

**Import Compatibility Rule**: *"If an old package and a new package have the same import path, the new package must be backwards compatible with the old package."*

→ MAJOR bump 마다 import path 가 바뀜:
- v0/v1: `example.com/mod`
- v2: `example.com/mod/v2`
- v3: `example.com/mod/v3`

귀결: 한 binary 에 v1+v2+v3 가 동시 링크 가능 (별개 package 로 취급). diamond dependency 회피.

### S2.6 IETF httpbis BCP56bis — API versioning

**Spec**: `https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-bcp56bis-12`

3 가지 backward-incompatible change 메커니즘:
1. **Distinct link relation** — 새 URL 로 새 기능 노출.
2. **Distinct media type** — `application/vnd.example.v2+json` (Accept negotiation).
3. **Distinct HTTP header** — `API-Version: 2` 등.

→ URL path versioning (`/v1/`, `/v2/`) 은 Go modules 와 같은 "import path = version" 패턴의 HTTP 등가물.

### S2.7 Google Cloud / AWS / Azure deprecation policies

- **Google Cloud Enterprise APIs**: 1-year deprecation notice. *"No feature may be removed (or changed in a way that is not backwards compatible) for as long as customers are actively using it"*.
- AWS: API stable + 12-month deprecation notice typical.
- Azure: 12 months 또는 product LTS 종료까지.

→ **enterprise contract 의 표준은 "12 month sunset"**. SYMPOSIUM 같은 내부 repo 에는 과도하지만, 무기-사도 SKILL.md 가 다른 스킬에서 참조되는 형국이라면 (apt → harness/prometheus/longinus/taliban/jaebaeman MIC slot) breaking 시 사전 lesson + sunset 권장.

---

## S3 — 함정 / Anti-pattern

### S3.1 ZeroVer 함정 (SemVer §4 명시)

> *"Major version zero (0.y.z) is for initial development. Anything MAY change at any time."*

→ 0.x 에 머무르는 한 SemVer 약속은 **공허**. consumer 는 caret/tilde 어느 쪽도 안전하지 않음. 그럼에도 OSS 는 1.0.0 jump 의 *책임 부담* 때문에 멈춤. Apache Kafka, OpenSSL (이전), Terraform (이전) 등 거대 프로젝트가 ZeroVer 에 머물렀음.

**SYMPOSIUM 적용**: `version: 1` 스킬들 (db-query 등) 이 명시적으로 "1.0 contract 안정" 인지, 아니면 "최초 작성 후 손 안 댐" 인지 frontmatter 만으로는 불명. **history section 필수.**

### S3.2 Major Version Bump Fatigue

대표 사례:
- **Python 2 → 3** (2008 announce, 2020 EOL — 12년 transition). Unicode 모델 전면 개편이 핵심 breaking. 2019-09 시점에도 download 의 40% 가 2.7. 
- **Java 8 → 9** (2017) — module system (JPMS) 강제 → 거대 ecosystem 이 9 점프 거부, 11 LTS 까지 지연.
- **Angular 1 → 2** (사실상 다른 프레임워크) — 사용자 분열.

→ MAJOR bump 는 단순 숫자가 아닌 **마이그레이션 비용 책임**. SemVer 만 따르면 "기술적으로 정당한" major bump 가 ecosystem 전체를 reject 하는 사례.

→ **EffVer 의 등장 동기**: "MAJOR" 가 너무 무거우니 effort 로 분해.

### S3.3 Library Author vs Consumer 갈등

- Author 관점: SemVer 정당하게 MAJOR bump.
- Consumer 관점: dependency tree 의 모든 transitive 가 동시 bump 안 하면 혼돈 (peer dep / diamond).
- → npm/Cargo 의 lockfile 은 이 갈등의 *런타임 합의 기록*.

### S3.4 Hyrum's Law violation (XKCD 1172)

위 S1.5. Implication: "patch bump 인데 사용자가 깨졌다" 는 보고 자주 발생 — Author 가 약속한 contract 와 사용자 의존하는 observable 의 미스매치.

### S3.5 Calendar-based Illusion

CalVer 는 "출시 *날짜* 가 정해지면 그 날 release" → **deadline pressure**. 기능이 안 익었어도 release. Ubuntu 의 "interim release vs LTS" 분리는 이 함정 완화 도구. 일반 CalVer 는 이 안전판 없음.

### S3.6 Mixed Type 함정 (SYMPOSIUM/SKILLS 자체)

MANIFEST.json 안:
```json
{"name": "apt",      "version": 26}     // int
{"name": "longinus", "version": "3.1"}  // string
{"name": "tpa",      "version": "1.0"}  // string
```

→ JSON Schema 검증/UNWIND 배치/sort comparator 가 모두 깨질 수 있음. *type 일관성* = "the version field 가 SemVer string 인가 sequence integer 인가" 의 *식별성* 결정. 둘 다 OK 하지만 **mixing 은 anti-pattern**. 권장: 전 스킬 SemVer string 으로 통일 (`"26.0.0"`, `"3.1.0"`, `"1.0.0"`).

---

## S4 — 2026 trends + AI agent context

### S4.1 Claude Code skills `version` 필드 — 공식 입장

- **Anthropic 공식 docs** (`https://code.claude.com/docs/en/skills`): SKILL.md frontmatter 필수 = `name`, `description`. Optional = `license`, `allowed-tools`, `metadata`.
- **`version` 필드는 공식 spec 에 없음.** GitHub issue `anthropics/skills#37` (2024-2025) 보고: skill-creator 가 생성한 skill 에 `version:` 추가하면 *"unexpected key in SKILL.md frontmatter"* 검증 실패.
- 실측: `_external/anthropics/` 17 개 official SKILL.md **0/17 에 `version:` 필드**.

→ **현 SYMPOSIUM/SKILLS 의 `version: 26` 은 비공식 확장**. Claude Code marketplace 가 공식 검증을 강화하면 reject 가능.

대응 옵션:
1. **`metadata.version`** 으로 이전 (공식 허용 키 안에 nesting).
2. 별도 `VERSION` 파일 (Anthropic mirror 도 일부 채택).
3. 현 위치 유지하되 **commercial-marketplace registry 진입 시 변환 스크립트 준비**.

### S4.2 semantic-release / release-please / Changesets

3 강 자동화 도구 비교:
| 도구 | 입력 | 출력 |
|---|---|---|
| `semantic-release` | conventional commits | git tag + CHANGELOG + npm publish (one-shot full automation) |
| `release-please` (Google) | conventional commits | release PR (human merge → 자동 bump) |
| `Changesets` (Atlassian) | 수동 changeset 파일 | release PR + 다중 패키지 monorepo 친화 |

→ SYMPOSIUM/SKILLS 가 conventional commits 채택하면 `semantic-release` 로 git tag 자동화 가능. *하지만 SKILL.md frontmatter `version:` 까지 자동 sync 는 별도 plugin 필요* (npm/python eco 에 비해 도구 부재).

### S4.3 AI-generated changelog

GitHub Copilot for PRs / `gh-cli ai` / Anthropic prompt-caching 워크플로 — "PR diff → human-readable changelog entry" 를 LLM 이 작성. SemVer 자동화의 마지막 사람 손길 (commit message 작성) 까지 LLM 으로 흡수되는 추세.

→ SYMPOSIUM 의 KG 정전 패턴과 호환: **commit → KG Lesson 노드 → CHANGELOG 자동 생성** 파이프라인 가능. 단 *과거 lesson 들을 기계가 잘 surface 할 수 있는 schema* 필요 (이미 `agent-feedback-loop-canonical-2026-04-27` 가 그 기반).

### S4.4 Marketplace contract — frontmatter version 강제 정책 (가설)

현재 Anthropic skills marketplace 는 *공식 출시 전*. 추정되는 정책 방향:
- (A) `version` 필드 신설 → SemVer string 강제.
- (B) 현행 유지 → `metadata.version` 권장.
- (C) git tag 만으로 식별 (현 SYMPOSIUM/SKILLS 의 `v26.0.x` 패턴).

→ **SYMPOSIUM 권장**: (C) + frontmatter SemVer string 병기. integer 폐기.

### S4.5 Agent identity tier (SemVer + agent role)

새 패턴 제안 (SYMPOSIUM 자체 발견):
```
<agent-role>:<semver>
e.g., apt-orchestrator:26.0.1
      taliban-critic:3.0.2
```

근거:
- Hyrum's Law 가 LLM agent 에게는 *극단적* 으로 적용. 동일 SKILL.md 라도 invocation 패턴/context window/모델 버전 (Opus 4.7 vs 4.6) 이 다르면 행동이 달라짐.
- SemVer 의 "API contract" 를 agent 에서는 "**invocation contract** (slash command + slot) + **expectation contract** (output 형식)" 2-tier 로 분해.
- → frontmatter: `version: 26.0.1` + `model_compat: ["opus-4.6", "opus-4.7"]` 권장.

---

## 5. 합의 (Consensus) — 4 sub-axis 교차 결론

### C1. SemVer 가 SYMPOSIUM/SKILLS 의 정답이다 (조건부)

- 현 `version: 26` integer 는 SemVer §2 의 `MAJOR.MINOR.PATCH` 위반. integer 1 개만으로는 "MINOR 추가" / "PATCH fix" 표현 불가.
- git tag (`v26.0.1`) 가 이미 SemVer 형. → frontmatter 도 일치시키면 *MANIFEST.json 의 type 혼재* 와 *git tag-frontmatter drift* 를 동시 해결.
- **권장 action**: 모든 스킬 frontmatter 를 `version: "26.0.1"` SemVer string 으로 마이그레이션. integer/quoted 혼재 종식.

### C2. History section 신설 — frontmatter 에 `history:` 또는 별도 `CHANGELOG.md`

- SemVer §3 (immutability) + Hyrum's Law (모든 변경 추적 필요) → 변천사 기록은 *옵션이 아니라 의무*.
- 형식 옵션:
  - (a) frontmatter 안 `history: [{version, date, summary, breaking}]` 배열.
  - (b) 스킬 폴더 안 `CHANGELOG.md` (Keep a Changelog 형식).
  - (c) git log + conventional commits + `gh release` (machine-only).
- **권장**: (a) + (b) 혼합 — frontmatter 에 최근 3개 + CHANGELOG.md 에 전체.

### C3. Conventional Commits 채택

- semantic-release 자동화의 ground truth. apt-meta-review 의 Lesson 생성과 자연 호환 (lesson type ↔ commit type 매핑).
- 현 SYMPOSIUM 는 KG-first 이지만 commit 에도 동일 의미가 흘러야 자동화 가능.

### C4. EffVer 보조 채택 (선택)

- SYMPOSIUM 스킬은 *agent prompt* 라 EffVer 의 "사용자 effort" 가 SemVer 보다 의미적으로 더 정확.
- 단 ecosystem (npm/cargo/git tag) 는 SemVer 가정. → **SemVer 표면 + EffVer 주석** (예: `# effort: meso` in frontmatter).

### C5. Anthropic 공식 정책과의 정렬 risk

- 0/17 official skills 에 `version:` 필드 없음 → 향후 marketplace 가 reject 할 risk.
- 현재 권장: `metadata.version` nesting 또는 별도 `VERSION` 파일 + frontmatter integer 는 단계적 deprecate.

---

## 6. 분기 / 대립 (Divergence)

### D1. Integer "26" vs SemVer "26.0.1" — 파급 비용

- Integer 유지: 27 스킬 frontmatter 무수정. 다만 PATCH 표현 불능.
- SemVer 마이그레이션: 27 스킬 + MANIFEST.json + 모든 KG 노드 (ATOM_Skill_*) version 참조 동시 갱신. 비용 ↑↑.
- → "incremental: 새 스킬은 SemVer string, 기존은 history section 만 추가" 절충안 가능.

### D2. CalVer 가 SYMPOSIUM 에 더 맞을 가능성

- Anthropic 모델 버전과 강결합 (`opus-4.6`, `opus-4.7`) → 모델 출시 날짜가 사실상 스킬 호환성 cutoff.
- CalVer (`26.04.0` = 2026-04 release) 가 더 직관적일 수 있음.
- 단 SemVer 의 contract 표현력 손실. → **Hybrid CalVer-SemVer** (`YY.MM.PATCH`) 가 PEP 2026 가는 길.

### D3. frontmatter `version` 필드 자체의 정당성

- Anthropic 공식 입장: 미지원.
- SYMPOSIUM 입장: 정전 노드 (KG) 와 SKILL.md 의 *어느 한쪽이* version 을 들고 있어야 drift 검출 가능.
- → **frontmatter 폐기 + KG 단일 정전** 도 옵션 (KG-first 원칙과 일관). MANIFEST.json 이 KG 의 mirror 일 뿐인 형태.

---

## 7. Open Questions

1. SYMPOSIUM/SKILLS marketplace 진입 시점이 결정되면 그 이전에 frontmatter 마이그레이션 강제. 시점 미정 → 어느 시점에 trigger?
2. apt v26 의 MIC slot 추가 (7→10) 가 SemVer MAJOR 인가 MINOR 인가? (slot 은 *open-closed* 의 extension 같지만 기존 slot 사용자는 새 slot resolve 강제될 수 있음.) → EffVer 채택 시 MESO.
3. KG 의 ATOM_Skill_* 노드와 SKILL.md frontmatter 가 drift 났을 때 ground truth 는? (현재 명시 부재.)
4. tpa-* 의 `version: "1.0"` (string, 2자리) 은 SemVer pre-release 인가, "MAJOR.MINOR" patch 생략인가? PATCH 는 어떻게 표현?
5. Conventional Commits 채택 시 SYMPOSIUM 의 *한국어 commit* 는 어떻게 처리? (`feat(apt): ...` 영문 type + 한국어 description?)

---

## 8. 권장 후속 작업 (action items)

| # | action | 우선도 |
|---|---|---|
| A1 | 모든 SKILL.md frontmatter 에 `history:` 배열 추가 (최소 2~3개 entry) | ★★★ |
| A2 | `CHANGELOG.md` 폴더별 신설 (Keep a Changelog 형식) | ★★ |
| A3 | MANIFEST.json `version` 필드 type 통일 (SemVer string) | ★★★ |
| A4 | Conventional Commits adoption 가이드 작성 + PR template | ★★ |
| A5 | `apt-meta-review` 의 Lesson 생성 → 자동 CHANGELOG entry 파이프라인 | ★ |
| A6 | KG 의 ATOM_Skill_* 노드와 frontmatter version drift 검증 Cypher 작성 | ★★ |
| A7 | Anthropic marketplace 정책 모니터링 (issue tracker watch) | ★ |
| A8 | EffVer 주석 (`effort: micro/meso/macro`) 시범 도입 — apt 부터 | ★ |

---

## 9. KG Lesson 후보

- `lesson-prom16-skillver-a2-2026-04-29` — **현 `version: <int>` integer 단독 패턴은 SemVer §2 위반 + Hyrum's Law 약점 + Anthropic 공식 frontmatter 와 불일치. 정정: SemVer string + history section + CHANGELOG.md 3 단 구조.**
- 페어:
  - `wrongAssumption`: "version: 26 integer 만으로 변천사 충분히 표현됨"
  - `truth`: "integer 1 개는 PATCH/MINOR 분리 불가 + breaking 여부 무지각 + Hyrum's Law 의 모든 observable 추적 의무 미충족. SemVer 3-tier + history array + Conventional Commits 가 최소 합의."

---

## Sources

- [Semantic Versioning 2.0.0 — semver.org](https://semver.org/)
- [Calendar Versioning — calver.org](https://calver.org/)
- [PEP 2026 — Calendar versioning for Python](https://peps.python.org/pep-2026/)
- [ZeroVer — 0ver.org](https://0ver.org/)
- [EffVer — Jacob Tomlinson](https://jacobtomlinson.dev/effver/)
- [JEP 25516: Effort-based versioning for JAX](https://docs.jax.dev/en/latest/jep/25516-effver.html)
- [Hyrum's Law — hyrumslaw.com](https://www.hyrumslaw.com/)
- [XKCD 1172 — Workflow](https://m.xkcd.com/1172/)
- [Open–closed principle (Wikipedia)](https://en.wikipedia.org/wiki/Open%E2%80%93closed_principle)
- [PEP 440 — Version Identification and Dependency Specification](https://peps.python.org/pep-0440/)
- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
- [npm node-semver](https://github.com/npm/node-semver)
- [Cargo Book — SemVer Compatibility](https://doc.rust-lang.org/cargo/reference/semver.html)
- [Go Modules Reference](https://go.dev/ref/mod)
- [Russ Cox — Semantic Import Versioning (vgo Part 3)](https://research.swtch.com/vgo-import)
- [draft-ietf-httpbis-bcp56bis-12 — Building Protocols with HTTP](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-bcp56bis-12)
- [Google Cloud — API stability tenets](https://cloud.google.com/blog/topics/inside-google-cloud/new-api-stability-tenets-govern-google-enterprise-apis)
- [semantic-release — npm](https://www.npmjs.com/package/semantic-release)
- [Anthropic Skills — Claude Code Docs](https://code.claude.com/docs/en/skills)
- [anthropics/skills GitHub](https://github.com/anthropics/skills)
- [Issue #37 — version frontmatter unsupported](https://github.com/anthropics/skills/issues/37)
- [Andrew Nesbitt — From ZeroVer to SemVer (versioning schemes survey)](https://nesbitt.io/2024/06/24/from-zerover-to-semver-a-comprehensive-list-of-versioning-schemes-in-open-source.html)
