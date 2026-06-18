#!/usr/bin/env python3
"""skill-build-attestation.py — in-toto SLSA Provenance v1 attestation skeleton.

Plan-3 phase 2 lite. Unsigned envelope (sigstore Cosign signing deferred to phase 3-N).
Subjects: MANIFEST.json, SBOM.json, .well-known/skills/index.json (each by SHA256).
"""
import hashlib
import json
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent
MANIFEST = SKILLS_DIR / "MANIFEST.json"
ATTESTATION_PATH = SKILLS_DIR / ".well-known" / "skills" / "attestation.json"


def sha256_of(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if not MANIFEST.exists():
        print(f"ERR: {MANIFEST} missing — run skill-build-manifest.py first", file=sys.stderr)
        return 2
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))

    targets = []
    for rel in ["MANIFEST.json", "SBOM.json", ".well-known/skills/index.json"]:
        p = SKILLS_DIR / rel
        if p.exists():
            targets.append({"name": rel, "digest": {"sha256": sha256_of(p)}})

    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": targets,
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://symposium.local/skill-build/v1",
                "externalParameters": {
                    "git_head_commit": m["git_head_commit"],
                    "git_latest_tag": m.get("git_latest_tag"),
                    "canonical_path": m["canonical_path"],
                },
                "internalParameters": {
                    "merkle_root": m["merkle_root"],
                    "skills_count": m["skills_count"],
                },
                "resolvedDependencies": [
                    {"uri": f"pkg:claude-skill/{s['name']}@{s['version']}",
                     "digest": {"sha1": s["git_tree_sha"]}}
                    for s in m["skills"]
                ],
            },
            "runDetails": {
                "builder": {"id": "https://symposium.local/builders/skill-build@v1"},
                "metadata": {
                    "invocationId": m["merkle_root"],
                    "startedOn": m["generatedAt"],
                    "finishedOn": m["generatedAt"],
                },
                "byproducts": [
                    {"name": "MANIFEST.json", "uri": "MANIFEST.json"},
                    {"name": "SBOM.json", "uri": "SBOM.json"},
                ],
            },
        },
        "_signature": {
            "status": "UNSIGNED",
            "reason": "Plan-3 phase 2 lite — sigstore Cosign integration deferred to phase 3-N (5-6주 effort, GitHub remote + OIDC required)",
        },
    }
    ATTESTATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    ATTESTATION_PATH.write_text(json.dumps(statement, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK: wrote {ATTESTATION_PATH} (UNSIGNED skeleton, {len(targets)} subjects, {len(m['skills'])} resolvedDependencies)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
