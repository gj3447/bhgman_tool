# A4 — Provenance & Supply Chain Integrity

> PROM 16 axis worker A4. Agent: `prom16-a4-haiku-2026-04-29`. Date: 2026-04-29.
> Topic: SYMPOSIUM/SKILLS supply chain provenance/integrity grounding.
> Scope: 4 sub-axes (S1 정전 이론, S2 산업 표준/RFC, S3 함정/anti-pattern, S4 2026 trends + AI agent).
> Method: Real spec citations (slsa.dev, in-toto.io, sigstore.dev, cyclonedx.org, spdx.dev, theupdateframework.io) + analysis of current SYMPOSIUM/SKILLS attestation state vs. Anthropic official `anthropics/skills`.

---

## 0. SYMPOSIUM/SKILLS 현재 상태 (Pre-fetch)

확인된 사실 (2026-04-29 inspection):

| Artifact | Path | Spec | Status |
|---|---|---|---|
| SBOM | `SBOM.json` | CycloneDX 1.5 | Present, 27 components, `serialNumber=urn:uuid:507e3856-...`, embedded `manifest:merkle_root` property |
| Manifest (drift sentinel) | `MANIFEST.json` | Custom `schema:v1` | Present, `merkle_root=d8c62efd...`, `git_head_commit=d053308...`, 27 skills |
| Provenance attestation | `.well-known/skills/attestation.json` | `_type=https://in-toto.io/Statement/v1` + `predicateType=https://slsa.dev/provenance/v1` | Present but **`_signature.status=UNSIGNED`** (cosign deferred) |
| Public skill index | `.well-known/skills/index.json` | Custom RFC 8615 well-known | Present, `schema=rfc8615-skills-v1` |
| Marketplace metadata | `.claude-plugin/marketplace.json` | Anthropic plugin spec | Present |

확인된 누락 (gap analysis):

1. `_signature.status=UNSIGNED` — sigstore Cosign signature 미부착. Statement 자체는 in-toto v1 envelope 형식이지만 DSSE (Dead Simple Signing Envelope) signature 없음.
2. Reproducible build 보장 없음 — `git:tree_sha`로 component identity는 잡지만, 빌드 산출물(SBOM/MANIFEST)의 bit-for-bit 재현은 확립 안 됨 (timestamp 포함).
3. OCI artifact push 미수행 — `oras push` 같은 registry distribution 없이 git-only.
4. TUF root metadata 없음 — key rotation/revocation 메커니즘 부재.
5. SLSA Build Level 자체평가 없음 — 현재 attestation 형식은 SLSA L1 ("Provenance exists") 충족 가능, L2 ("tamper protection on attestation") 미달 (signature 부재).

비교 baseline — Anthropic 공식 `anthropics/skills` (`_external/anthropics/` mirror, 18 skills):
- **SBOM 없음, MANIFEST 없음, attestation 없음, .well-known 없음.** SKILL.md만 존재. 즉 SYMPOSIUM/SKILLS는 이미 공식 skill 마켓플레이스보다 supply-chain 측면에서 앞서 있다.

---

## S1 — 정전 이론 (Foundational theory)

### S1.1 SLSA framework (Supply-chain Levels for Software Artifacts)

- **출처**: `slsa.dev` (Google originated, OpenSSF에 기증).
- **정의**: SLSA는 "기존 소프트웨어 산출물의 공급망 무결성을 점진적으로 강화하는 보안 프레임워크" (a checklist of standards and controls).
- **현재 정전 버전**: SLSA v1.0 (2023-04 ratified). v1.1 FAQ, v1.2-rc1 build track basics 진행 중.
- **핵심 layer**: Build Track (가장 성숙). 추가로 Source Track / Dependency Track 초안 진행.
- **Build Track levels** (`slsa.dev/spec/v1.0/levels`):
  - **L0**: Provenance 없음 (baseline).
  - **L1**: "Package has provenance showing how it was built. Can be used to prevent mistakes but is trivial to bypass or forge." — provenance 형식만 갖춤, signature 무관.
  - **L2**: "Covers tampering of the artifact or provenance after the build." — provenance is signed, build platform is hosted (not on developer workstation).
  - **L3**: "Forging the provenance or evading verification requires exploiting a vulnerability that is beyond the capabilities of most adversaries. Builds run on a hardened build platform that offers strong tamper protection." — isolated build platform, non-falsifiable provenance.
- **Note**: SLSA L4 was deprecated in v1.0; older drafts had it. Current spec stops at L3 for Build Track. ([slsa.dev/spec/v1.0/whats-new](https://slsa.dev/spec/v1.0/whats-new))

### S1.2 in-toto specification

- **출처**: `in-toto.io` (NYU Tandon / SAFECode / CNCF Graduated 2023).
- **목적**: "Cryptographic and verifiable framework for the integrity of the entire software supply chain."
- **3-layer architecture** (in-toto Attestation Framework):
  1. **Statement** (`_type: https://in-toto.io/Statement/v1`) — binds attestation to subject (artifacts) + predicateType + predicate.
  2. **Predicate** — type-specific payload (e.g., SLSA Provenance v1 is one predicateType).
  3. **Envelope** — DSSE wraps statement for signing/serialization. Bundle groups multiple attestations.
- **Predicate type relationship**: SLSA Provenance가 in-toto Predicate의 한 type. `predicateType=https://slsa.dev/provenance/v1` (renamed from older `https://slsa.dev/provenance/v0.2`).
- **Link metadata**: in-toto의 원래 형태 (each pipeline step = signed link). Modern usage는 attestation-based로 진화.

### S1.3 sigstore — keyless signing

- **출처**: `sigstore.dev` (Linux Foundation, CNCF Sandbox→Incubating).
- **3 components**:
  - **Cosign** — signing/verification CLI tool.
  - **Fulcio** — Certificate Authority. OIDC token (Google/GitHub/Microsoft) → short-lived (10-min) X.509 cert binding identity to ephemeral keypair.
  - **Rekor** — append-only, cryptographically verifiable transparency log of signing events.
- **Keyless flow** (`docs.sigstore.dev/cosign/signing/overview/`):
  1. User runs `cosign sign --bundle <artifact>` → triggers OIDC flow.
  2. Identity provider issues OIDC token.
  3. Cosign generates ephemeral keypair, signs token claims.
  4. Fulcio mints time-stamped cert tying public key to OIDC identity.
  5. Cosign signs artifact digest with ephemeral private key.
  6. Signature + cert published to Rekor transparency log.
  7. Ephemeral private key discarded.
- **Why keyless > traditional**: No long-lived private key to compromise/lose. Identity = OIDC (rotatable, MFA-protectable). Transparency log = audit trail.

### S1.4 SBOM origin (NTIA Minimum Elements 2021)

- **출처**: NTIA (`ntia.gov/report/2021/minimum-elements-software-bill-materials-sbom`), pursuant to U.S. Executive Order 14028 (2021-05-12, "Improving the Nation's Cybersecurity").
- **Definition**: SBOM is "a formal record containing the details and supply chain relationships of various components used in building software."
- **3 minimum element categories**:
  1. **Data Fields**: Supplier, component name, version, unique identifier, dependency relationship, SBOM author, timestamp.
  2. **Automation Support**: Machine-readable formats. NTIA explicitly accepts **SPDX, CycloneDX, SWID** as standard formats.
  3. **Practices and Processes**: How SBOMs are generated, requested, distributed, updated, consumed.
- **NIST connection**: SP 800-218 (SSDF — Secure Software Development Framework) PO.1.3, PS.3.2 reference SBOMs explicitly. SP 800-161 (SCRM) integrates SBOMs into supply chain risk management. CISA published 2025 update to minimum elements.

### S1.5 Reproducible Builds

- **출처**: `reproducible-builds.org` (Debian-originated, multi-distro now).
- **Definition** (`reproducible-builds.org/docs/definition/`): "A build is reproducible if given the same source code, build environment and build instructions, any party can recreate bit-by-bit identical copies of all specified artifacts."
- **Necessary conditions**: Determinism (no current date/time embedded, stable file ordering, fixed locale, normalized timestamps via SOURCE_DATE_EPOCH env var).
- **Key tools**: `diffoscope` (recursive binary diff to identify what differs), `repro-build` (reproducible container builds).
- **Why critical**: Without reproducibility, "trust the published binary matches the source" is unverifiable — only the original builder can claim correspondence. With reproducibility, **any third party can rebuild and compare**.

### S1.6 Solarwinds 2020 (SUNBURST) — root lesson

- **Vector**: Attackers compromised SolarWinds Orion build pipeline (between source and signed binary). Inserted malicious code into legitimate software updates distributed to ~18,000 customers including U.S. federal agencies.
- **Discovery**: 2020-12 by FireEye/Mandiant.
- **Lesson** (drove EO 14028 + NIST SSDF + SLSA adoption): **Trusting only the signed final binary is insufficient. The build pipeline itself must be observable, verifiable, and tamper-evident.** This is exactly what SLSA Build L2/L3 addresses (provenance covers what happened during build, not just final artifact identity).
- **Industry impact**: Mandiant 2021 reported supply chain compromise rose to 17% of intrusions (from <1% in 2020).

### S1.7 Codecov 2021

- **Vector**: Attackers modified Codecov's Bash Uploader script (used by 29,000+ enterprises in CI). Single character change exfiltrated CI environment variables (secrets, tokens) to attacker-controlled server. Persisted ~2 months.
- **Lesson**: Even non-binary supply chain components (shell scripts, install scripts, CI plugins) need integrity verification. Hash pinning of remote-fetched scripts is now standard guidance.

### S1.8 Merkle tree (Ralph Merkle, 1979)

- **Origin**: Ralph C. Merkle's 1979 Stanford PhD thesis "Secrecy, Authentication, and Public Key Systems" introduced Merkle trees (originally Merkle hash trees) for efficient signature schemes.
- **Property**: Any tampering of any leaf changes the root hash. Logarithmic verification (need only path of size log₂N).
- **Use in supply chain**: Git uses Merkle DAG. SYMPOSIUM/SKILLS' `MANIFEST.json.merkle_root` is direct application — drift detection without re-hashing every file.

---

## S2 — 산업 표준 / RFC

### S2.1 CycloneDX 1.5 / 1.6 / 1.7

- **출처**: `cyclonedx.org`, OWASP project, ratified as **ECMA-424, 1st Edition** (June 2024) for v1.6.
- **Versions and capabilities**:
  - v1.5: Foundational SBOM (software components), ML-BOM, SaaSBOM, OBOM (Operations BOM), VDR/VEX (vulnerability disclosures).
  - **v1.6 (2024)**: Added **CBOM (Cryptography BOM)** — first open standard for cryptographic asset inventory. Added **Attestations** capability — declarative claims + evidence, integrated into CycloneDX. Introduced ML-BOM enhancements.
  - v1.7 (current): Advanced cryptography support, intellectual property declarations, data provenance transparency.
- **JSON schema reference**: `cyclonedx.org/docs/1.6/json/`.
- **SYMPOSIUM/SKILLS state**: Currently uses **CycloneDX 1.5** (`"specVersion": "1.5"` in SBOM.json). Upgrade path to 1.6 trivial (additive changes), would unlock Attestations capability natively (currently external in `.well-known/skills/attestation.json`).

### S2.2 SPDX 3.0 (ISO/IEC 5962:2021)

- **출처**: `spdx.dev`, Linux Foundation project. **ISO/IEC 5962:2021** since 2021.
- **Current**: SPDX 3.0.1 (`spdx.github.io/spdx-spec/v3.0.1/`). Major restructure from 2.x — moved from monolithic to **profiles** (Software, Security, Build, AI, Dataset, Licensing, Lite).
- **Software profile** defines `Sbom` class — collection of SPDX Elements describing a package.
- **NTIA conformance**: SPDX has explicit "SPDX and NTIA Minimum Elements for SBOM HOWTO" at `spdx.github.io/spdx-ntia-sbom-howto/`.

### S2.3 in-toto attestation predicate types

- **Predicate registry** (`github.com/in-toto/attestation/blob/main/spec/predicates/`):
  - `https://slsa.dev/provenance/v1` (build provenance).
  - `https://in-toto.io/attestation/link/v0.3` (legacy in-toto link).
  - `https://in-toto.io/attestation/test-result/v0.1`.
  - `https://in-toto.io/attestation/vulns/v0.1` (vuln scan results).
  - `https://spdx.dev/Document` (SPDX SBOM as predicate).
  - `https://cyclonedx.org/bom` (CycloneDX SBOM as predicate).
- **Statement v1 schema** (`github.com/in-toto/attestation/blob/main/spec/v1/statement.md`):
  ```json
  {
    "_type": "https://in-toto.io/Statement/v1",
    "subject": [{"name": "...", "digest": {"sha256": "..."}}],
    "predicateType": "<URI>",
    "predicate": { /* type-specific */ }
  }
  ```
- SYMPOSIUM/SKILLS의 attestation.json은 이 schema를 정확히 따른다.

### S2.4 SLSA Provenance v1 schema

- **Reference**: `slsa.dev/spec/v1.0/provenance`.
- **Top-level fields**:
  - `buildDefinition.buildType` (URI describing schema of remaining fields).
  - `buildDefinition.externalParameters` (user-controlled inputs — REQUIRED for L1).
  - `buildDefinition.internalParameters` (build-platform-controlled).
  - `buildDefinition.resolvedDependencies` (array of `ResourceDescriptor` — dependencies pinned by digest).
  - `runDetails.builder.id` (URI identifying the build platform).
  - `runDetails.builder.builderDependencies`, `runDetails.builder.version`.
  - `runDetails.metadata.invocationId`, `startedOn`, `finishedOn`.
  - `runDetails.byproducts` (array of `ResourceDescriptor`).
- **ResourceDescriptor** fields: `uri`, `digest` (sha256/sha512/gitCommit/...), `name`, `downloadLocation`, `mediaType`, `content` (base64), `annotations`.
- SYMPOSIUM/SKILLS의 attestation.json — `runDetails.builder.id="https://symposium.local/builders/skill-build@v1"` (local placeholder), `resolvedDependencies` has 27 skills with `digest.sha1` (git tree shas). **Conformance is solid for L1.**

### S2.5 Sigstore Cosign signature format

- **Reference**: `docs.sigstore.dev/cosign/signing/overview/`, Cosign 2.0 (2023).
- **Signature wrapping**: DSSE (Dead Simple Signing Envelope) is the canonical format. Wraps in-toto Statement.
- **Bundle format** (`.sigstore` bundle, 2024+): combines DSSE signature + Fulcio cert chain + Rekor inclusion proof in single file. Replaces older `.sig + .crt + .rekor` triples.
- **Verification**: `cosign verify-attestation --certificate-identity <expected> --certificate-oidc-issuer <expected>` enforces identity match against Fulcio cert.

### S2.6 OCI artifact spec + ORAS

- **OCI Distribution v1.1** (`opencontainers.org`): standardizes OCI registries (Docker Hub, GHCR, ECR, GAR, etc.) as generic artifact storage.
- **OCI Image Manifest** (v1.1 added `artifactType` field): allows non-image artifacts (SBOMs, attestations, signatures, helm charts, skills, etc.).
- **Reference Types** (`oras.land/docs/concepts/reftypes/`): manifest's `subject` field links one artifact (e.g., signature) to another (e.g., signed image). Foundation for "attestation as registry artifact attached to signed thing."
- **ORAS** (OCI Registry As Storage): CLI for pushing/pulling arbitrary artifacts. `oras push <registry>/<repo>:<tag> --artifact-type application/vnd.symposium.skill.v1+json ./SKILL.tar`.

### S2.7 TUF — The Update Framework

- **Reference**: `theupdateframework.io/spec/`, CNCF Graduated.
- **Core insight**: Even if signing keys are compromised, attacker should not be able to install arbitrary software. Solved via **role separation + threshold signatures + key rotation**.
- **Top-level roles**:
  - `root` — root of trust. Lists keys for all other roles. Rarely updated, offline keys.
  - `targets` — signs metadata about actual target files (skills in our case).
  - `snapshot` — prevents mix-and-match attacks (consistent view of all metadata at point in time).
  - `timestamp` — freshness guarantee (frequent re-sign, prevents freeze attacks).
- **Used by**: PyPI (Warehouse), Docker Notary, sigstore root key management itself, RustUp.
- **Relevance**: SYMPOSIUM/SKILLS currently has no key management for signing — TUF root.json would establish initial trust if cosign gets adopted.

### S2.8 NIST SSDF (Secure Software Development Framework)

- **Reference**: NIST SP 800-218 (Feb 2022, v1.1).
- **4 practice groups**: Prepare the Organization (PO), Protect the Software (PS), Produce Well-Secured Software (PW), Respond to Vulnerabilities (RV).
- **SBOM-relevant tasks**: PS.3.2 ("collect provenance data"), PO.1.3 ("communicate requirements to third parties"), PW.4.1 ("acquire and maintain well-secured software components").
- **EO 14028 mapping**: federal procurement (since 2022) requires SSDF self-attestation including SBOM availability.

---

## S3 — 함정 / Anti-pattern

### S3.1 "SBOM theater"

- **Definition**: Generating SBOMs as a compliance checkbox without integrating them into vulnerability management or verification workflows.
- **Symptom**: SBOM produced once at release, stored in S3, never queried. No automated `cosign verify-attestation` in deployment pipeline.
- **SYMPOSIUM/SKILLS check**: Currently SBOM.json is generated but **no consumer-side verification path documented** (no `verify-skill.sh` script, no Naesengmoon lens for supply-chain integrity). **Risk: SBOM theater unless verification is wired.**

### S3.2 Unsigned attestation (unverifiable)

- **Risk**: An attestation document without DSSE signature is forgeable by anyone with write access to the repository. Provides traceability narrative but zero non-repudiation.
- **Current state**: `attestation.json._signature.status="UNSIGNED"` — explicitly acknowledged. SLSA Build L1 only.
- **Fix**: `cosign attest --predicate attestation.json --type slsaprovenance --bundle attestation.bundle <subject>`. Bundle contains Fulcio cert + Rekor proof.

### S3.3 Single point of trust (key compromise)

- **Failure mode**: One signing key, no rotation, no transparency log → key compromise = total trust collapse (e.g., NotPetya M.E.Doc 2017, key was reused).
- **Mitigation**:
  - Keyless signing (sigstore) — no long-lived keys, identity-based.
  - TUF threshold signatures + key rotation.
  - Transparency log (Rekor) — even compromised keys leave evidence in tamper-evident log.

### S3.4 SLSA L0 (no provenance)

- **State**: 대부분의 OSS package registries (npm, PyPI default) — package metadata only, no proof of how it was built.
- **Anthropic `anthropics/skills` is currently here** (no MANIFEST/SBOM/attestation). User cloning/installing has zero verification capability. SYMPOSIUM/SKILLS has surpassed this baseline.

### S3.5 Reproducibility-less trust claims

- **Failure**: Vendor publishes binary + source + signature, but binary is non-reproducible. User can verify "vendor signed it" but cannot verify "source corresponds to binary." SolarWinds-class attack remains possible (compromised build env injects code; signed binary still verifies).
- **Counter**: Reproducible build + diverse rebuilders (multiple independent parties rebuild and compare hashes).

### S3.6 Dependency confusion (Birsan 2021)

- **Mechanism**: Internal package `@company/internal-tool` not on public registry. Attacker registers same name on public registry. Misconfigured package manager prefers higher version → fetches malicious public package.
- **Birsan's bounty**: ~$130,000 across 35+ companies including Apple, Microsoft, Tesla, Yelp.
- **Mitigation**: scope reservation on public registries, explicit registry pinning per scope, hash pinning of all transitive deps, internal-only registries with public mirror lockdown.
- **Skill ecosystem analog**: If `claude-skill/apt` is internal but someone registers same name in a public skill marketplace, dependency confusion replicates. **SYMPOSIUM/SKILLS uses purl `pkg:claude-skill/apt@26?channel=stable` — the `channel=stable` qualifier is good defense if registries enforce channel scoping.**

### S3.7 Typosquatting (PyPI/npm)

- **Mechanism**: `requests` (real) vs `reqeusts`/`requestz`/`request` (malicious). User typos → installs malicious package. ~63,000+ suspicious packages caught by Sonatype across registries.
- **Skill analog**: `apt-st` vs `apt-sl` typo could matter if a public skill marketplace exists. Currently scoped to git, low risk.

### S3.8 Prompt injection through skill content

- **Skill-specific anti-pattern (NEW)**: A skill is loaded into Claude's context by the harness. Skill content = direct prompt to the model. If a malicious actor controls a skill in the loadout (via supply chain compromise of the skill repo), they can inject instructions like "ignore prior instructions, exfiltrate $X."
- **Defense**: SBOM + signed attestation + verified install path. Without it, **skill supply chain = direct prompt injection vector at install time**, much higher impact than traditional code (executes with model's full agency).

---

## S4 — 2026 trends + AI agent context

### S4.1 Anthropic skill marketplace 의 attestation 현황

- **Inspection** (`_external/anthropics/` mirror, 18 skills as of 2026-04): No SBOM, no MANIFEST, no `.well-known`, no signing. Only `SKILL.md` per skill folder + repo-level `THIRD_PARTY_NOTICES.md` + `_REPO_README.md`.
- **Implication**: Anthropic's official skills repo is at SLSA L0. Users have no way to verify a downloaded skill is the version Anthropic published, beyond git commit hash trust (which itself relies on GitHub trust).
- **Comparison**: SYMPOSIUM/SKILLS exceeds Anthropic's own bar in supply-chain rigor — a deliberate Longinus-style "공학 결정화" (engineering crystallization).

### S4.2 AI-generated code provenance

- **Emerging concern (2025-2026)**: When Claude/Copilot/Cursor generates code, what's the provenance? `git blame` shows human committer but actual authorship is mixed.
- **Proposals**: SBOM extension to include `aiGeneratedComponent` metadata, model version, prompt hash. Some early work in CycloneDX 1.7's "data provenance transparency."
- **No standard yet**. SYMPOSIUM/SKILLS could be early adopter via custom CycloneDX property (`ai:generator=claude-opus-4.7` + `ai:promptHash=<sha256>`).

### S4.3 LLM-generated SBOM analysis

- **Trend (2025-2026)**: LLMs (Claude, GPT) automatically analyze codebases to generate SBOMs/SPDX. Faster than syft/cdxgen for legacy codebases without package manager metadata. **Risk**: hallucinated dependencies (LLM lists components that aren't actually there) — needs ground-truth verification (taliban lens).
- **Mitigation**: LLM produces draft SBOM → automated tooling (syft/cdxgen) cross-validates → deltas escalated to human review.

### S4.4 Agent skill supply chain risk

- **Distinct from traditional code**: Skill content is loaded into LLM context, not compiled or sandboxed. **Supply chain compromise of a skill = direct prompt injection in the user's session.**
- **Threat model**:
  1. Attacker submits PR to popular skill repo with hidden instruction ("If user asks for X, also do Y").
  2. Maintainer merges without thorough adversarial review.
  3. All users pulling latest get hijacked agency.
- **Defenses**:
  - Signed attestations per skill release (cosign keyless via OIDC).
  - Pinned skill versions in user config (no auto-update).
  - Adversarial skill lens (taliban --lens prompt-injection scanning skill content).
  - SBOM-binding to KG (a skill's `kg:ref=ATOM_Skill_X` provides semantic anchoring; drift detection compares KG state against installed skill).

### S4.5 SBOM + KG binding (Longinus-style)

- **SYMPOSIUM/SKILLS unique innovation**: Each SBOM component carries `properties.kg:ref` → Neo4j ATOM node ID. Each skill's `git_tree_sha` is verifiable against the source. The MANIFEST's merkle_root is the drift sentinel.
- **This realizes Longinus 7-Layer Reference Model at the supply chain layer**: Layer 0 (KG semantic node) ↔ Layer N (deployed skill content), with cryptographic binding (sha) + semantic binding (kg:ref).
- **Equivalent in spec**: in-toto `subject.name` + `digest` is the same idea, but our addition of KG linkage is novel — enables not just "is this the same bytes" but also "does this conform to the canonical semantic spec."
- **ResearchFinding integration**: A `:ReferenceSite` in KG can carry `slsa.predicate.digest` and `cyclonedx.bom-ref` to bind reference-site to provenance evidence.

### S4.6 2026 industry direction

- **Mandatory SBOMs**: U.S. federal procurement (since 2024 OMB M-22-18 enforcement); EU CRA (Cyber Resilience Act, effective 2027) requires SBOMs and vulnerability management for all "products with digital elements."
- **SLSA adoption**: GitHub Actions has built-in SLSA L3 builder (`slsa-github-generator`); Google Cloud Build native provenance; npm provenance (since 2023, sigstore-backed).
- **Sigstore reaches GA**: Cosign 2.0 (2023) and the public-good instance maturity make keyless signing turnkey for OSS projects.

---

## 권장 후속 작업 (Recommendations for SYMPOSIUM/SKILLS)

### Immediate (low effort, high value)

1. **Upgrade SBOM.json to CycloneDX 1.6** — additive change, unlocks native Attestations object, ECMA-424 conformance.
2. **Add `verify-skill.sh`** — script that recomputes merkle_root from current tree, compares against MANIFEST, and validates SBOM digest against attestation subject. Closes the SBOM-theater gap.
3. **Document SLSA Build Level self-assessment** — currently L0/L1 borderline. Explicit `slsa-level: L1` in `.well-known/skills/index.json` until signing is added.

### Medium-term (cosign integration, ~2-3 weeks)

4. **Cosign keyless signing of attestation.json** via GitHub Actions OIDC:
   ```bash
   cosign sign-blob --bundle attestation.bundle attestation.json
   # OIDC identity: workflow URI + org claim
   ```
   - Move `_signature.status` from "UNSIGNED" to actual DSSE signature + Fulcio cert + Rekor inclusion proof.
   - Achieves SLSA Build L2 (provenance signed, hosted build platform).

5. **Reproducible build of MANIFEST.json + SBOM.json**:
   - Pin tool versions (`skill-build-sbom.py` version, jq, sha256sum).
   - Use SOURCE_DATE_EPOCH for timestamp normalization.
   - CI rebuilds and asserts byte-for-byte equality with committed artifacts.

### Longer-term (OCI distribution + TUF)

6. **OCI artifact push** via ORAS. The bin/ directory and skeleton are already in place:
   ```bash
   oras push ghcr.io/<org>/symposium-skills:v26.0.1 \
     --artifact-type application/vnd.symposium.skill-bundle.v1+json \
     SBOM.json:application/vnd.cyclonedx+json \
     MANIFEST.json:application/vnd.symposium.manifest.v1+json \
     attestation.json:application/vnd.in-toto+json
   ```
   - Achieves cryptographic registry distribution. Enables `cosign verify` flow for downstream consumers.

7. **TUF root.json** for key management — only if SYMPOSIUM/SKILLS becomes externally distributed. Premature otherwise (Solo project: keyless sigstore is sufficient.).

8. **Anthropic upstream contribution**: Open PR to `anthropics/skills` adding the SBOM/MANIFEST/attestation pattern. Establishes SYMPOSIUM/SKILLS' approach as a reference implementation. (Open question — does Anthropic want this? Asked, not answered.)

---

## Open questions

- **Q1**: Is `claude-skill` a registered purl type? (Currently using `pkg:claude-skill/...` — informal). PURL spec authority is `github.com/package-url/purl-spec`. Registering would standardize.
- **Q2**: Should each skill have its own per-skill attestation, or only the bundle-level one? Bundle-level is current; per-skill would enable selective install verification.
- **Q3**: How does `science-feedback-loop` 의 NUMEROLOGY_HOLD pattern apply to SBOM claims? Possibly: SBOM-claimed dependencies that aren't verified by syft/cdxgen scanning = "numerology" until grounded.
- **Q4**: Anthropic 정전 referent에 대한 underrate 금지 (memory MEMORY.md). Anthropic의 official skills 에 attestation 부재는 사실이고, SYMPOSIUM 이 이 영역에서 앞서 있는 것도 사실 — over-cautious 표현 회피, 명료히 기록.

---

## Sources cited

- [SLSA specification v1.0](https://slsa.dev/spec/v1.0/)
- [SLSA security levels](https://slsa.dev/spec/v1.0/levels)
- [SLSA Provenance v1](https://slsa.dev/spec/v1.0/provenance)
- [SLSA What's New in v1.0](https://slsa.dev/spec/v1.0/whats-new)
- [in-toto Attestation Framework](https://github.com/in-toto/attestation)
- [in-toto Statement v1 spec](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md)
- [in-toto Provenance predicate](https://github.com/in-toto/attestation/blob/main/spec/predicates/provenance.md)
- [Sigstore Cosign signing overview](https://docs.sigstore.dev/cosign/signing/overview/)
- [Sigstore Security Model](https://docs.sigstore.dev/about/security/)
- [Rekor transparency log](https://docs.sigstore.dev/logging/overview/)
- [CycloneDX Specification Overview](https://cyclonedx.org/specification/overview/)
- [CycloneDX v1.6 release announcement](https://cyclonedx.org/news/cyclonedx-v1.6-released/)
- [CycloneDX v1.7 release announcement](https://cyclonedx.org/news/cyclonedx-v1.7-released/)
- [CycloneDX 1.6 JSON Reference](https://cyclonedx.org/docs/1.6/json/)
- [SPDX Specification 3.0.1](https://spdx.github.io/spdx-spec/v3.0.1/)
- [SPDX is now ISO/IEC 5962:2021](https://spdx.dev/spdx-specification-is-now-an-iso-standard/)
- [SPDX NTIA SBOM HOWTO](https://spdx.github.io/spdx-ntia-sbom-howto/)
- [TUF Specification (latest)](https://theupdateframework.github.io/specification/latest/)
- [TUF Roles and Metadata](https://theupdateframework.io/docs/metadata/)
- [NTIA SBOM Minimum Elements (2021)](https://www.ntia.gov/report/2021/minimum-elements-software-bill-materials-sbom)
- [CISA 2025 Minimum Elements update](https://www.cisa.gov/resources-tools/resources/2025-minimum-elements-software-bill-materials-sbom)
- [Reproducible Builds project](https://reproducible-builds.org/)
- [Reproducible Builds Definition](https://reproducible-builds.org/docs/definition/)
- [ORAS — OCI Registry As Storage](https://oras.land/)
- [ORAS pushing and pulling](https://oras.land/docs/how_to_guides/pushing_and_pulling/)
- [ORAS reference types](https://oras.land/docs/concepts/reftypes/)
- [Alex Birsan — Dependency Confusion (2021)](https://medium.com/@alex.birsan/dependency-confusion-4a5d60fec610)
- [anthropics/skills repository](https://github.com/anthropics/skills)
