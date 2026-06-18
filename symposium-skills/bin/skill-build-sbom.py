#!/usr/bin/env python3
"""skill-build-sbom.py — CycloneDX 1.5 SBOM for SYMPOSIUM/SKILLS.

Plan-3 phase 2 lite (consensus seed cg-skillver-slsa-sigstore-attestation).
Reads MANIFEST.json, emits SBOM.json with deterministic serialNumber (uuid5 of merkle_root).
Actual sigstore signing deferred to Plan-3 phase 3-N.
"""
import json
import sys
import uuid
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent
MANIFEST = SKILLS_DIR / "MANIFEST.json"
SBOM_PATH = SKILLS_DIR / "SBOM.json"


def main():
    if not MANIFEST.exists():
        print(f"ERR: {MANIFEST} missing — run skill-build-manifest.py first", file=sys.stderr)
        return 2
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))

    components = []
    for s in m["skills"]:
        components.append({
            "type": "library",
            "bom-ref": f"pkg:claude-skill/{s['name']}@{s['version']}",
            "name": s["name"],
            "version": str(s["version"]),
            "scope": "required",
            "purl": f"pkg:claude-skill/{s['name']}@{s['version']}?channel={s['channel']}",
            "properties": [
                {"name": "kg:ref", "value": s["kg_ref"]},
                {"name": "git:tree_sha", "value": s["git_tree_sha"]},
                {"name": "claude-skill:channel", "value": s["channel"]},
            ],
        })

    serial = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, m["merkle_root"]))

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": serial,
        "version": 1,
        "metadata": {
            "timestamp": m["generatedAt"],
            "tools": [{"vendor": "SYMPOSIUM", "name": "skill-build-sbom.py", "version": "1"}],
            "component": {
                "type": "application",
                "name": "SYMPOSIUM/SKILLS",
                "version": m.get("git_latest_tag") or m["git_head_short"],
                "properties": [
                    {"name": "git:head", "value": m["git_head_commit"]},
                    {"name": "manifest:merkle_root", "value": m["merkle_root"]},
                    {"name": "manifest:skills_count", "value": str(m["skills_count"])},
                ],
            },
        },
        "components": components,
    }
    SBOM_PATH.write_text(json.dumps(sbom, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK: wrote {SBOM_PATH} ({len(components)} components, serial={serial[-12:]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
