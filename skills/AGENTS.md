# AGENTS.md — SYMPOSIUM Skills (cross-tool agent index)

> Cross-tool agent skill catalog following the emerging `AGENTS.md` convention.
> Discoverable from `.agents/skills/` (symlink farm) and `.well-known/skills/index.json` (RFC 8615).

## Identity

| Field | Value |
|---|---|
| Publisher | SYMPOSIUM |
| Canonical path | `/Users/lagyeongjun/CD/SYMPOSIUM/SKILLS` |
| Release | `v26.0.0` |
| Schema | `claude-skill v1` (frontmatter: `name`, `version`, `description`, `kg_ref`, `channel`) |
| Manifest | `MANIFEST.json` (merkle-rooted, drift-gated) |
| Discovery | `.well-known/skills/index.json` (public-safe subset) |
| Attestation | `.well-known/skills/attestation.json` (in-toto SLSA Provenance v1) |
| SBOM | `SBOM.json` (CycloneDX 1.5) |
| Marketplace | `.claude-plugin/marketplace.json` |
| OCI artifact-type | `application/vnd.symposium.claude-skills.v1+json` |
| KG namespace | `ATOM_Skill_*` (Neo4j) |

## Skill tiers

| Tier | Skills | Role |
|---|---|---|
| **essence** | apt, harness, longinus, taliban, jaebaeman, prometheus | 5대 무기 + APT orchestrator. Constitutional governance via CODEOWNERS. |
| **alias** | 88-taliban, tlb, prom | Thin aliases of essence (drift-sensitive). |
| **phase** | apt-sa, apt-sp, apt-st, apt-scw, apt-meta-review | APT 5-phase cycle. |
| **tpa** | tpa, tpa-tcw, tpa-tt, tpa-tp, tpa-ta | Reverse cycle (code → spec). |
| **meta** | solve, skill-creator | Meta-tooling. |
| **ops** | db-query, docker-logs, kafka-manage, server-status, deploy, backup | Infrastructure operations. |

## Discovery for non-Claude agents

Agents that don't know about Claude's `.claude/skills/` convention can:

1. Read `AGENTS.md` (this file) for top-level orientation.
2. Walk `.agents/skills/<name>/SKILL.md` (cross-tool symlink farm).
3. Fetch `.well-known/skills/index.json` for machine-readable catalog with merkle integrity.
4. Verify `MANIFEST.json` against `.well-known/skills/attestation.json` + cosign signature (when remote is wired).

## Drift detection

```bash
python3 bin/skill-merkle-check.py            # one-shot
launchctl list | grep symposium-merkle       # 12-min cron
```

`MANIFEST.merkle_root` is `SHA256(sorted(path:git_tree_sha))`. Mismatch with live state → DRIFT exit 1.

## Supply-chain hardening

- **CODEOWNERS**: 5대 무기 + aliases + critical metadata require owner review.
- **Pre-commit hook**: rebuilds MANIFEST.json on any `SKILL.md` staged change.
- **GH Actions** (dormant until remote): drift gate → validator → SBOM/attestation rebuild → cosign keyless (Fulcio + Rekor via OIDC) → npm-style provenance → ORAS push to GHCR on tag.

## Channel policy

`channel: stable | beta | experimental` in frontmatter. See `CHANNELS.md` for promotion rules.

## Reproducibility

Every artifact includes:
- `git_head_commit` — exact source commit
- `git_tree_sha` per skill — content-addressed
- `merkle_root` — bundle integrity gate
- `kg_ref` — KG `ATOM_Skill_<x>` node (W3C PROV-O Entity)

Re-running `bin/skill-build-manifest.py` at the same `git_head_commit` produces byte-identical output (deterministic `generatedAt` = HEAD commit time).
