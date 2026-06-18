# PROM 16 — Axis A3: Release Engineering & Channel Management 학문 grounding

> agentId: `prom16-a3-haiku-2026-04-29`
> SYMPOSIUM/SKILLS CHANNELS.md grounding sweep — 학문/산업/함정/2026 trends 4 sub-axis.
> 1차 소스 = paper / 공식 docs (Chrome / Firefox / Microsoft / CNCF / Anthropic / SLSA / in-toto).
> 검증 토대: 현 SKILLS CHANNELS.md (3 channel + kill-switch, 27/27 stable, progressive rollout 부재).

---

## S1 — 정전 이론 (Release Engineering Canon)

### S1.1 Adams & McIntosh, "Modern Release Engineering in a Nutshell — Why Researchers Should Care" (SANER 2016)

- 정확한 출처: **2016 IEEE 23rd International Conference on Software Analysis, Evolution, and Reengineering (SANER)**, *not* IEEE Software (현 CHANNELS 인용 보정 필요).
- 핵심 주장: release engineering = **"the process that brings high quality code changes from a developer's workspace to the end user"** — 6 major phases:
  1. Branching / merging (integration)
  2. Continuous integration
  3. Build system & dependencies
  4. Deployment / infrastructure-as-code
  5. Release (channel/cadence)
  6. Post-release monitoring / hot-fix
- 연구 사각지대 경고: 연구자가 release engineering 파이프라인을 모르면 software engineering empirical study 결과가 무효화될 수 있음 (예: build flakiness가 측정 변수가 됨).

> 인용 (Adams & Bram, SANER 2016): *"Recent practices of continuous delivery, which bring new content to the end user in days or hours rather than months or years, have generated a surge of industry-driven interest in the release engineering pipeline."*

### S1.2 Humble & Farley, *Continuous Delivery* (Addison-Wesley, 2010)

- 정전 표어: **"if it hurts, do it more often"** — 빌드/배포는 자동화 + 빈도 ↑ → 위험 ↓.
- **Deployment Pipeline** 정의 (이 책의 가장 큰 기여): "an automated process for managing all changes, from check-in to release."
- 4가지 핵심 원칙:
  1. Build binaries once (한 번만 빌드, 환경별 재빌드 금지)
  2. Deploy the same way to every environment (dev=staging=prod)
  3. Smoke-test deployments
  4. If anything fails, **stop the line** (Andon cord)
- DevOps 운동의 직접 선행 — Phoenix Project / DevOps Handbook이 이를 서사화.

### S1.3 Beyer (ed.) *Site Reliability Engineering* — "Release Engineering" chapter (Dinah McNutt, 2016)

> Online: https://sre.google/sre-book/release-engineering/

- 4 SRE release engineering principles:
  1. **Self-Service Model** — 팀이 release tooling을 직접 사용
  2. **High Velocity** — 자주 release (Google = daily push, deployment ≠ release)
  3. **Hermetic Builds** — *"insensitive to the libraries and other software installed on the build machine"* — known versions of build tools/deps, no external services.
  4. **Enforcement of Policies and Procedures** — RBAC + audit trail
- **Rapid** (Google internal release system): cherry-pick onto release branch + rebuild config package + redeploy.
- **Release branches**: git-flow + cherry-pick approval. 각 cherry-pick은 RM(Release Manager) approve.

### S1.4 Kim et al. — *The Phoenix Project* / *DevOps Handbook* (IT Revolution Press)

- **Three Ways**: (1) Flow (좌→우), (2) Feedback (우→좌), (3) Continuous experimentation/learning.
- The First Way가 release engineering의 직접 motivation: dev → ops → customer 흐름 매끄럽게.
- "Release readiness"는 직접 정의되지 않지만 *DevOps Handbook* 사례연구에서 **definition-of-done = production-ready** 라는 normative 주장.

### S1.5 Release Train 메타포 (SAFe / scaled agile)

- 출처: SAFe (Scaled Agile Framework), `framework.scaledagile.com/agile-release-train`.
- **Agile Release Train (ART)**: *"a long-lived, self-organizing team of Agile teams... like a train on its tracks, moves along a predetermined path and schedule."*
- 핵심: 고정 cadence (e.g. quarterly) + standard velocity + predictable releases.
- 트레이드오프: 한 train 놓치면 다음 train 까지 대기 ("if a feature doesn't make it aboard this quarter's train, it has to catch the next one") — flexibility ↓, predictability ↑.

### S1.6 SYMPOSIUM/SKILLS와의 비교

현 `CHANNELS.md` (3 channel + kill-switch + frontmatter `channel:` + validator) 는:
- ✓ Adams & McIntosh의 phase 5 (release) 충실
- ✓ Hermetic Build에 가까움 (skill = self-contained `SKILL.md` + KG ref)
- ✗ Release Train metaphor 부재 — SYMPOSIUM은 *event-driven* (skill-creator 호출 시), *cadence-driven* 아님
- ✗ Phase 6 (post-release monitoring) 없음 — channel 강등은 manual

---

## S2 — 산업 표준 / RFC (Industry Standards)

### S2.1 Chrome Release Channels (가장 영향력 큰 reference)

> Source: `developer.chrome.com/docs/web-platform/chrome-release-channels`, `chromium.googlesource.com/chromium/src/+/master/docs/process/release_cycle.md`

| Channel | Cadence | Purpose | Rollout % |
|---|---|---|---|
| **Canary** | Daily | 실험, 최소 testing | 1-5% start |
| **Dev** | 1-2× / week | 활동 중인 작업 | gradual |
| **Beta** | Weekly minor + 4-week major | 4-6 week preview of stable | 1-5% → 100% |
| **Stable** | 2-3주 minor / 4주 major | end-user default | 1-5% → 100% (incremental) |
| **Extended Stable** | 8주 | enterprise | slow |

> 인용 (Chrome docs): *"Initially, only a small number of users for each release channel get an update — maybe only 1–5% to start, gradually building up to 100%."*

**Pause-and-fix 원칙**: rollout 중 metrics/feedback 이상 시 *paused*, fix 후 재개. Anthropic "kill switch"의 직접 ancestor.

### S2.2 Mozilla Firefox Release Channels

> Source: `firefox-source-docs.mozilla.org/contributing/pocket-guide-shipping-firefox.html`, `firefox-admin-docs.mozilla.org/guides/firefox-channels/`

| Channel | Cadence | Branch |
|---|---|---|
| **Nightly** | every 12 hours | `firefox-main` |
| **Beta** | 4 weeks merge | `firefox-beta` |
| **Release** | 4 weeks | `firefox-release` |
| **ESR (Extended Support)** | 52 weeks major | enterprise track |

- 3 primary code branches (firefox-main / -beta / -release) + ESR 분리.
- "Uplift" workflow: 새 코드는 무조건 firefox-main 먼저, 그 다음 firefox-beta로 cherry-pick.

### S2.3 Microsoft Windows Insider Program

> Source: `learn.microsoft.com/en-us/windows-insider/flighting`, `blogs.windows.com/windows-insider/2026/04/24/`

- 2023년 3월: 기존 Dev → Canary로 rename + 새 Dev 채널 신설.
- **2026년 4월 (이번 달)**: Dev + Canary 통합 → **Experimental** 채널 + **Beta** 2개 채널로 단순화.
- Release Preview 채널은 enterprise / near-final용으로 잔존.
- Microsoft 변경 이유 (`ghacks.net/2026/04/13/`): *"clearer channels, feature flags, and calendar pause"* — gradual rollout in Beta 종료, feature flag로 대체.

→ **insight**: 2026 trend = 채널 수 줄이고 feature flag로 fine-grained 제어 이동.

### S2.4 Anthropic Claude Code (현 SKILLS의 직접 referent)

> Source: `code.claude.com/docs/en/model-config`, `claudelog.com/configuration/`

확인된 disable 환경변수 (실제 존재):
- `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` — experimental Beta header 끄기 (현 CHANNELS.md 채택)
- `CLAUDE_CODE_DISABLE_1M_CONTEXT` — 1M context 끄기
- `CLAUDE_CODE_DISABLE_CRON` — cron job 끄기
- `CLAUDE_CODE_DISABLE_AUTO_MEMORY` — memory/telemetry 쓰기 끄기
- 6+ remote killswitches (e.g. `tengu_penguins_off`)

→ Anthropic 패턴 = **per-feature env-var kill switch** (per-channel 아님). SYMPOSIUM은 channel 단위로 묶었지만 더 fine-grained 가능.

### S2.5 Plugin Marketplace (`.claude-plugin/marketplace.json`)

> Source: `code.claude.com/docs/en/discover-plugins`, `github.com/anthropics/claude-plugins-official`

- `marketplace.json`: name + owner + plugins[] schema.
- Plugin 구조: `.claude-plugin/` 디렉터리 + `plugin.json` + `skills/` + `SKILL.md`.
- 명령: `claude plugin marketplace add <url>/marketplace.json`.
- 2026년 3월 기준 official marketplace = **101 plugins**, ecosystem 전체 = 507+ extensions.

→ SYMPOSIUM/SKILLS = 41 skill, 자체 marketplace 가능 단계 (CHANNELS.md를 marketplace metadata로 lift 가능).

### S2.6 AGENTS.md cross-tool 표준 (2025 mid 등장)

> Source: `agents.md/`, `github.com/agentsmd/agents.md`

- Linux Foundation의 Agentic AI Foundation이 stewarding.
- Codex CLI / GitHub Copilot / Cursor / Windsurf / Amp / Devin 모두 native 지원.
- 파일명 대문자 강제 (AGENTS.md ≠ agents.md).
- monorepo: nested AGENTS.md → "nearest file wins" rule.
- 권장 항목: tech stack / code quality / testing / safety guardrails / git conventions / project gotchas.

→ 현 SYMPOSIUM/SKILLS/AGENTS.md 존재 (✓), CHANNELS.md와 cross-link 가능.

### S2.7 Progressive Rollout (Argo Rollouts / Cloud Deploy)

> Source: `argo-rollouts.readthedocs.io`, `docs.cloud.google.com/deploy/docs/deployment-strategies/canary`

표준 step weights:
```
1% → 5% → 20% → 50% → 100%   (Argo Rollouts default sample)
또는
5-10% → 25% → 50% → 100%      (Google Cloud Deploy)
```
각 step 사이 `pause` (manual or auto-analysis).

`Argo Rollouts`: Kubernetes CRD `Rollout`. `setWeight` + `pause` 필드. AnalysisRun (Prometheus / Datadog / NewRelic 메트릭) 자동 promotion/rollback.

### S2.8 OpenFeature (CNCF feature flag spec)

> Source: `cncf.io/projects/openfeature/`, `openfeature.dev/`

- CNCF Sandbox 2022-06 → Incubating 2023-11.
- Spec v0.8.0 (2026 기준): evaluation context, hooks, events, **tracking for A/B tests**, transaction context propagation, **multi-provider support**.
- 목적: vendor lock-in 방지 (LaunchDarkly / Flagsmith / Statsig / DevCycle 모두 OpenFeature provider 구현).

### S2.9 LaunchDarkly Release Patterns

> Source: `launchdarkly.com/docs/home/releases/progressive-rollouts`, `launchdarkly.com/docs/guides/flags/technical-debt`

- Progressive rollout = 시간 기반 incremental flag enable.
- "Code References" 기능: repo 스캔 → flag key를 file/line에 매핑 → cleanup precision.
- Flag lifecycle states: `Inactive` (평가 안 됨) → `Launched` (모두에게 동일 variation) → archive 대상.

---

## S3 — 함정 / Anti-pattern

### S3.1 Big Bang Release / Big Bang Integration

> Source: `aws.amazon.com/wellarchitected/latest/devops-guidance/anti-patterns-for-continuous-delivery.html`, `minware.com/guide/anti-patterns/big-bang-release`

- 정의: 장기 branch / 미통합 누적 → 한 번에 거대 release.
- 문제:
  - Defect risk 폭증 (test ≠ prod)
  - Coordination 인적 실수 다발
  - Downtime 커짐
  - 공유 환경 dependencies 미발견
- 회피: trunk-based dev + feature flag + canary/blue-green.

### S3.2 Release Freeze Fatigue

> Source: Wikipedia *Freeze (software engineering)*, `agileforall.com/agile-antipattern-code-freezes-during-each-iteration/`, `reliably.com/blog/are-code-freezes-still-needed-sre/`

- Code freeze = 변경 금지 기간. Agile에서는 antipattern 후보:
  - 동결 직전 rush commit → 품질 저하
  - 동결 중 미통합 코드 누적 → 해제 시 폭발
  - QA-only-during-freeze는 "발견된 결함은 다음 iteration에" 라는 안티 feedback loop 만듦
- SRE perspective: CI/CD 성숙도 高이면 code freeze 불필요. 대신 **feature flag로 동결 효과**.

### S3.3 Channel Drift ("Beta가 Stable보다 stable한 경우")

학문 paper 출처는 직접 발견 못함 (여러 검색 시도). 산업 implicit folklore:
- 신호: stable의 hot-fix > beta의 hot-fix. stable user가 beta로 옮겨감.
- 원인:
  - Beta tester ≠ stable user demographics (load profile 다름)
  - Stable channel이 너무 보수적 → critical fix가 안 들어감
  - Channel cadence 불균형 (beta = 빠른 cycle / stable = 느린 cycle인데 stability 역전)
- 회피: stable의 patch lane (Chrome의 "Extended Stable" + "minor" release가 이 역할), regression 시 즉시 강등.

> 현 SYMPOSIUM CHANNELS.md `stable → regression 즉시 → beta 강등`은 이 함정의 인지를 보여줌 (✓).

### S3.4 Skip-Level Upgrade

- 정의: v1 → v2 직행 (v1.5 미경유). breaking change pile-up.
- DBMS / Kubernetes에서 가장 흔함 (e.g. K8s는 "skip 1 minor version maximum" 정책).
- SYMPOSIUM context: skill `version: 3` → `version: 5` 직행 시 마이그레이션 break 가능 → 권장은 staircase (3→4→5).

### S3.5 Kill Switch Failure (DR 시 미작동)

> Source: Netflix Hystrix wiki (`github.com/netflix/hystrix/wiki/how-it-works`).

- Hystrix circuit breaker = 가장 유명한 production kill switch. 현재 maintenance mode (resilience4j 추천).
- Failure mode:
  - Kill switch 자체에 의존성 (e.g. 환경변수가 외부 config에서 옴 → config 서비스 down 시 무력화)
  - Kill switch 후 fallback 없음 → 서비스 ↓
  - Kill switch test 안 됨 (game day 부재)
- 권장: 정기 chaos engineering으로 kill switch 자체 검증.

> 현 CHANNELS.md `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`은 simple env-var → 안정적이지만 fallback 없음 (skill 기능 자체가 disable).

### S3.6 Feature Flag Debt

> Source: `launchdarkly.com/docs/guides/flags/technical-debt`, `launchdarkly.com/blog/how-to-use-feature-flags-without-technical-debt/`

- 정의: 더 이상 evaluate 안 되는 flag가 코드에 남음.
- *"Flag debt compounds faster than technical debt because each stale flag adds two code paths that both need testing and maintenance."*
- 회피:
  - Flag 생성 시 expiration date 설정
  - "Launched" status flag = 자동 cleanup 후보로 표시
  - Code references 자동 스캔 (LaunchDarkly Code References)
  - Owner + ticket 강제 매핑

### S3.7 Trunk-Based Development 미준수 시 발생하는 종합 함정

> Source: `paulhammant.com/2013/04/05/what-is-trunk-based-development/`, SE Radio 564 (2023)

- Long-lived feature branch + integration day → big bang 발생 (S3.1).
- 회피: 일일 trunk merge + feature flag로 incomplete code 숨김 ("dark launch").

---

## S4 — 2026 Trends + AI Agent Context

### S4.1 Claude Code Plugin Marketplace 패턴 (현행)

- `.claude-plugin/marketplace.json` schema 표준.
- 2026 Q1: official marketplace 101 plugin, ecosystem 507+.
- 명령 표면: `claude plugin marketplace add ...`.
- SYMPOSIUM/SKILLS = 41 skill — marketplace.json 추가 시 외부 publish 가능.

### S4.2 AGENTS.md Cross-Tool 표준 채택

- 1 file, every agent. 6+ tool native (Codex / Copilot / Cursor / Windsurf / Amp / Devin).
- Linux Foundation steward → 사실상 표준.
- 현 SYMPOSIUM/SKILLS/AGENTS.md (✓ 존재) → CHANNELS.md를 AGENTS.md 안에 release engineering 절로 cross-ref 권장.

### S4.3 Microsoft 채널 단순화 (2026-04, 같은 달)

- Dev + Canary → Experimental 통합.
- "gradual rollouts in Beta 종료, **feature flags로 대체**".
- 시사점: **채널 = coarse-grained, feature flag = fine-grained**. 두 layer 분리.
- SYMPOSIUM 적용: channel은 stability 의도(experimental/beta/stable) 표시, **per-skill feature flag**가 추가 layer.

### S4.4 LLM-as-Judge → Release Readiness 자동 판정

> Source: `arize.com/llm-as-a-judge/`, `labelyourdata.com/articles/llm-as-a-judge`, `analyticsweek.com/llm-as-a-judge-enterprise-ai-qa/`

- 2026 enterprise: LLM-as-Judge가 CI/CD release gate에 통합.
- 정량 기준:
  - 75-90% match (judge vs human label) = strong alignment
  - Spearman ≥0.80 with human evaluators = production-ready
- 통합 패턴: "three trigger types + progressive canary deployment".
- SYMPOSIUM 적용: skill-validator + Naesengmoon (--lens constitutional)가 이미 LLM-as-Judge 패턴. CHANNELS.md의 channel transition gate에 정량 score 도입 가능.

### S4.5 Skill Drift Detection (merkle_root) → 자동 강등

> Source: SLSA (`slsa.dev`), in-toto (`github.com/in-toto/attestation`)

- SLSA = supply chain attestation 표준. ITE-6 in-toto format.
- Merkle root = content-addressable hash → drift detection (skill 내용 변경 시 hash 변경).
- SYMPOSIUM 직접 적용:
  - 각 SKILL.md → merkle root in MANIFEST.json
  - drift detect → 자동 channel 강등 (stable → beta)
  - SLSA Level 2+ provenance attestation 가능 (signed build).

### S4.6 OpenFeature + 채널의 결합

- 현 `channel: experimental | beta | stable` = 정적.
- OpenFeature evaluation context로 동적화:
  - user.role = "early-adopter" → experimental skill 자동 노출
  - hostname matches CI → kill switch 자동 발동
- multi-provider: 한 skill을 LaunchDarkly + Flagsmith 동시 publish 가능.

### S4.7 Progressive Rollout per Skill (Argo Rollouts pattern)

권장 step weights for SYMPOSIUM/SKILLS:
```
experimental:  100% (작성자만, opt-in)
beta:          1% → 5% → 25% → 100%   (24h pause between steps)
stable:        gradual override 무, 즉시 100%
```

각 step에서 metrics gate (skill invocation success rate / error rate / Lesson `MT_*` 발생률).

---

## SYMPOSIUM/SKILLS CHANNELS.md vs Chrome Release Channels — 상세 비교

| 측면 | Chrome | SYMPOSIUM 현행 | gap |
|---|---|---|---|
| 채널 수 | 5 (Canary/Dev/Beta/Stable/Ext-Stable) | 3 (experimental/beta/stable) | OK (Chrome 5는 매우 큰 user base 전제, 41 skill엔 과함) |
| 일일 cadence | Canary daily | 없음 | skill update 빈도 낮으면 불필요 |
| Rollout % | 1-5% → 100% gradual | 100% all-or-nothing | **부족** — per-skill feature flag로 보강 필요 |
| Pause-and-fix | metrics 이상 시 자동 pause | manual 강등 | **부족** — automation 부재 |
| Hermetic | 빌드 환경 isolation | SKILL.md self-contained | OK |
| Kill switch | per-feature flags + remote | env var (1개) | per-skill kill switch 가능하면 강화 |
| Channel transition gate | 정량 metrics + RM approval | 7일/14일 + manual eval | 정량화 필요 (LLM-as-Judge integration) |
| Drift detection | binary hash | 부재 | merkle root 도입 권장 |

---

## 권장 강화 (가이드라인)

### Tier 1 (즉시)

1. **per-skill kill switch**: 환경변수 `SYMPOSIUM_DISABLE_<SKILL_NAME>=1` 추가 (Anthropic 패턴 직접 모방).
2. **merkle_root in MANIFEST.json**: SLSA-style content hash → drift 자동 감지 → drift 시 자동 강등.
3. **AGENTS.md cross-ref**: CHANNELS.md를 AGENTS.md "Release Engineering" 절로 link.

### Tier 2 (중기)

4. **OpenFeature provider integration**: `channel:` frontmatter를 OpenFeature evaluation context로 lift.
5. **Channel transition LLM-as-Judge gate**: experimental → beta 전환 시 Naesengmoon --lens constitutional 정량 score ≥0.8 강제.
6. **Progressive rollout per skill** (Argo Rollouts pattern): beta → stable 시 1% → 5% → 25% → 100% step + metric gate.

### Tier 3 (장기)

7. **`.claude-plugin/marketplace.json` publish**: SYMPOSIUM = 외부 marketplace로 export.
8. **Feature flag debt automation**: "Launched" status flag 자동 archive (LaunchDarkly Code References 모방).
9. **Chaos engineering for kill switch**: 정기 game day로 kill switch 자체 검증.

---

## 참고 (1차 소스 URL)

- Adams & McIntosh SANER 2016: https://rebels.cs.uwaterloo.ca/papers/saner2016_adams.pdf
- Humble & Farley *Continuous Delivery*: https://martinfowler.com/books/continuousDelivery.html
- Google SRE book — Release Engineering: https://sre.google/sre-book/release-engineering/
- Chrome Release Channels: https://developer.chrome.com/docs/web-platform/chrome-release-channels
- Chromium release_cycle docs: https://chromium.googlesource.com/chromium/src/+/master/docs/process/release_cycle.md
- Firefox Pocket Guide: https://firefox-source-docs.mozilla.org/contributing/pocket-guide-shipping-firefox.html
- Microsoft Insider 2026-04 Experimental+Beta: https://blogs.windows.com/windows-insider/2026/04/24/were-moving-to-experimental-and-beta-announcing-new-builds/
- Anthropic Claude Code env vars: https://code.claude.com/docs/en/model-config
- Anthropic plugin marketplace: https://code.claude.com/docs/en/discover-plugins
- AGENTS.md spec: https://agents.md/
- Argo Rollouts canary: https://argo-rollouts.readthedocs.io/en/stable/features/canary/
- OpenFeature: https://openfeature.dev/
- LaunchDarkly tech debt: https://launchdarkly.com/docs/guides/flags/technical-debt
- SAFe Agile Release Train: https://framework.scaledagile.com/agile-release-train
- Hystrix circuit breaker wiki: https://github.com/netflix/hystrix/wiki/how-it-works
- Trunk-Based Dev (Hammant): https://paulhammant.com/2013/04/05/what-is-trunk-based-development/
- SLSA framework: https://slsa.dev/
- in-toto attestation: https://github.com/in-toto/attestation
- Facebook Chat dark launch (2008): https://engineering.fb.com/2008/05/13/web/facebook-chat/
- AWS DevOps anti-patterns: https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/anti-patterns-for-continuous-delivery.html

---

# KG seeds

- `finding_prom16_skillver_a3_s1` — Release Engineering canon (Adams/Humble/SRE/Phoenix/SAFe)
- `finding_prom16_skillver_a3_s2` — Industry standards (Chrome/Firefox/MS/Anthropic/AGENTS.md/Argo/OpenFeature)
- `finding_prom16_skillver_a3_s3` — Anti-patterns (BigBang/Freeze/ChannelDrift/SkipLevel/KillSwitchFailure/FlagDebt)
- `finding_prom16_skillver_a3_s4` — 2026 trends (marketplace/AGENTS.md/MS-2026-04/LLM-judge/SLSA/OpenFeature/per-skill rollout)
