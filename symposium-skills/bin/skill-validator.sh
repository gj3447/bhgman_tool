#!/usr/bin/env bash
# skill-validator.sh — SKILL.md frontmatter schema + MANIFEST.json drift 검증
# 사용:
#   skill-validator.sh <SKILL.md path>
#   skill-validator.sh --all                # 모든 SKILL.md frontmatter 검증
#   skill-validator.sh --manifest-check     # MANIFEST.json ↔ frontmatter ↔ git tree 정합 (Plan-5 phase 2 gate)
# 종료코드: 0 OK, 1 schema violation / drift, 2 file/path error
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CANONICAL_SKILLS_ROOT="$(dirname "$_SCRIPT_DIR")"
SCAN_ROOTS=(
  "$CANONICAL_SKILLS_ROOT"
  "$CANONICAL_SKILLS_ROOT/../ICE_ORCA_DRAGON/.claude/skills"
)
MANIFEST_PATH="$CANONICAL_SKILLS_ROOT/MANIFEST.json"
EXPECTED_SKILL_COUNT=27

validate_one() {
  local f="$1"
  [[ -f "$f" ]] || { echo "ERR  $f: not a file" >&2; return 2; }

  local fm
  fm="$(awk '/^---$/{c++; next} c==1{print} c==2{exit}' "$f")"
  [[ -n "$fm" ]] || { echo "ERR  $f: no frontmatter (--- ... ---)" >&2; return 1; }

  local name desc
  name="$(printf '%s\n' "$fm" | awk '/^name:/{sub(/^name:[[:space:]]*/,""); print; exit}')"
  desc="$(printf '%s\n' "$fm" | awk '/^description:/{sub(/^description:[[:space:]]*/,""); print; exit}')"

  [[ -n "$name" ]] || { echo "ERR  $f: missing 'name:' field" >&2; return 1; }
  [[ -n "$desc" ]] || { echo "ERR  $f: missing 'description:' field" >&2; return 1; }

  local dir_name
  dir_name="$(basename "$(dirname "$f")")"
  if [[ "$name" != "$dir_name" ]]; then
    echo "WARN $f: name='$name' != dir='$dir_name'" >&2
  fi

  echo "OK   $name"
  return 0
}

manifest_check() {
  local rc=0
  [[ -f "$MANIFEST_PATH" ]] || { echo "ERR  MANIFEST.json missing: $MANIFEST_PATH" >&2; return 2; }

  local manifest_count
  manifest_count="$(jq '.skills_count' "$MANIFEST_PATH")"
  if [[ "$manifest_count" != "$EXPECTED_SKILL_COUNT" ]]; then
    echo "FAIL MANIFEST.skills_count=$manifest_count (expected $EXPECTED_SKILL_COUNT)" >&2
    rc=1
  fi

  local actual_count
  actual_count="$(find "$CANONICAL_SKILLS_ROOT" -mindepth 2 -maxdepth 2 -name SKILL.md -type f -not -path '*/.git/*' -not -path '*/_backup_*/*' | wc -l | tr -d ' ')"
  if [[ "$actual_count" != "$EXPECTED_SKILL_COUNT" ]]; then
    echo "FAIL filesystem skill count=$actual_count (expected $EXPECTED_SKILL_COUNT)" >&2
    rc=1
  fi

  local manifest_head
  manifest_head="$(jq -r '.git_head_commit' "$MANIFEST_PATH")"
  local current_head
  current_head="$(git -C "$CANONICAL_SKILLS_ROOT" rev-parse HEAD)"
  if [[ "$manifest_head" != "$current_head" ]]; then
    echo "WARN MANIFEST.git_head_commit=$manifest_head vs current HEAD=$current_head (rebuild manifest)" >&2
  fi

  while IFS= read -r entry; do
    local name path version_m kg_ref_m sha_m
    name="$(echo "$entry" | jq -r '.name')"
    path="$(echo "$entry" | jq -r '.path')"
    version_m="$(echo "$entry" | jq -r '.version')"
    kg_ref_m="$(echo "$entry" | jq -r '.kg_ref')"
    sha_m="$(echo "$entry" | jq -r '.git_tree_sha')"

    local skill_md="$CANONICAL_SKILLS_ROOT/$path/SKILL.md"
    if [[ ! -f "$skill_md" ]]; then
      echo "FAIL $name: SKILL.md missing at $skill_md" >&2
      rc=1
      continue
    fi

    local fm
    fm="$(awk '/^---$/{c++; next} c==1{print} c==2{exit}' "$skill_md")"
    local version_f kg_ref_f
    version_f="$(printf '%s\n' "$fm" | awk '/^version:/{sub(/^version:[[:space:]]*/,""); print; exit}')"
    kg_ref_f="$(printf '%s\n' "$fm" | awk '/^kg_ref:/{sub(/^kg_ref:[[:space:]]*/,""); print; exit}')"

    if [[ "$version_f" != "$version_m" ]]; then
      echo "FAIL $name: version frontmatter=$version_f vs MANIFEST=$version_m" >&2
      rc=1
    fi
    if [[ "$kg_ref_f" != "$kg_ref_m" ]]; then
      echo "FAIL $name: kg_ref frontmatter=$kg_ref_f vs MANIFEST=$kg_ref_m" >&2
      rc=1
    fi

    local sha_now
    sha_now="$(git -C "$CANONICAL_SKILLS_ROOT" rev-parse "HEAD:$path" 2>/dev/null || echo '')"
    if [[ -n "$sha_now" && "$sha_now" != "$sha_m" ]]; then
      echo "DRIFT $name: git_tree_sha MANIFEST=$sha_m vs git=$sha_now (rebuild manifest)" >&2
      rc=1
    fi
  done < <(jq -c '.skills[]' "$MANIFEST_PATH")

  local manifest_merkle expected_merkle
  manifest_merkle="$(jq -r '.merkle_root' "$MANIFEST_PATH")"
  expected_merkle="$(python3 -c "
import json, hashlib
m = json.load(open('$MANIFEST_PATH'))
skills = sorted(m['skills'], key=lambda s: s['path'])
print(hashlib.sha256('\n'.join(f\"{s['path']}:{s['git_tree_sha']}\" for s in skills).encode()).hexdigest())
")"
  if [[ "$manifest_merkle" != "$expected_merkle" ]]; then
    echo "FAIL merkle_root: MANIFEST=$manifest_merkle vs computed=$expected_merkle" >&2
    rc=1
  fi

  if [[ $rc -eq 0 ]]; then
    echo "OK   manifest-check: $EXPECTED_SKILL_COUNT skills consistent (frontmatter ↔ MANIFEST ↔ git ↔ merkle:${manifest_merkle:0:12}...)"
  fi
  return $rc
}

if [[ "${1:-}" == "--all" ]]; then
  rc=0
  for root in "${SCAN_ROOTS[@]}"; do
    [[ -d "$root" ]] || continue
    while IFS= read -r f; do
      validate_one "$f" || rc=1
    done < <(find "$root" -maxdepth 3 -name 'SKILL.md' -type f -not -path '*/_backup_*/*' -not -path '*/.git/*' 2>/dev/null)
  done
  exit "$rc"
elif [[ "${1:-}" == "--manifest-check" ]]; then
  manifest_check
elif [[ -n "${1:-}" ]]; then
  validate_one "$1"
else
  echo "usage: $(basename "$0") {<SKILL.md>|--all|--manifest-check}" >&2
  exit 2
fi
