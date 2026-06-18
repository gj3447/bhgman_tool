#!/usr/bin/env bash
# skill-build-oci.sh — SYMPOSIUM/SKILLS를 OCI artifact로 패키징/푸시 (ORAS 사용).
#
# Plan-4 phase 1 lite (consensus seed cg-skillver-oci-artifact).
# 실제 push는 GHCR/Harbor remote 설정 후. 기본 모드는 dry-run.
#
# 사용:
#   skill-build-oci.sh                  # dry-run (oras 미설치 시 강제 dry-run)
#   skill-build-oci.sh --push           # 실제 push (env: SKILLVER_OCI_REGISTRY required)
#   SKILLVER_OCI_REGISTRY=ghcr.io/<org>/symposium-skills SKILLVER_OCI_TAG=v26.0.0 \
#     skill-build-oci.sh --push
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SKILLS_DIR="$(dirname "$_SCRIPT_DIR")"
REGISTRY="${SKILLVER_OCI_REGISTRY:-ghcr.io/TBD-org/symposium-skills}"
TAG="${SKILLVER_OCI_TAG:-$(git -C "$SKILLS_DIR" describe --tags --abbrev=0 2>/dev/null || echo 'untagged')}"
ARTIFACT_TYPE="application/vnd.symposium.claude-skills.v1+json"

MODE="${1:---dry-run}"

if ! command -v oras >/dev/null 2>&1; then
  echo "WARN: oras CLI not installed — forcing dry-run"
  MODE="--dry-run"
fi

# Collect artifacts (relative to SKILLS_DIR)
files=("MANIFEST.json")
[[ -f "$SKILLS_DIR/SBOM.json" ]] && files+=("SBOM.json")
[[ -f "$SKILLS_DIR/.well-known/skills/index.json" ]] && files+=(".well-known/skills/index.json")
[[ -f "$SKILLS_DIR/.well-known/skills/attestation.json" ]] && files+=(".well-known/skills/attestation.json")
[[ -f "$SKILLS_DIR/CHANNELS.md" ]] && files+=("CHANNELS.md")
[[ -f "$SKILLS_DIR/CODEOWNERS" ]] && files+=("CODEOWNERS")
while IFS= read -r f; do
  rel="${f#$SKILLS_DIR/}"
  files+=("$rel")
done < <(find "$SKILLS_DIR" -mindepth 2 -maxdepth 2 -name SKILL.md -not -path '*/.git/*' -not -path '*/_backup_*/*' | sort)

cat <<EOF
OCI artifact:    $REGISTRY:$TAG
artifact-type:   $ARTIFACT_TYPE
files (${#files[@]}):
EOF
printf '  %s\n' "${files[@]}"

if [[ "$MODE" == "--push" ]]; then
  cd "$SKILLS_DIR"
  echo "[push] oras push $REGISTRY:$TAG ..."
  oras push "$REGISTRY:$TAG" \
    --artifact-type "$ARTIFACT_TYPE" \
    "${files[@]}"
  echo "OK: pushed to $REGISTRY:$TAG"
else
  echo
  echo "[dry-run] would execute:"
  echo "  oras push $REGISTRY:$TAG --artifact-type $ARTIFACT_TYPE ${files[*]}"
fi
