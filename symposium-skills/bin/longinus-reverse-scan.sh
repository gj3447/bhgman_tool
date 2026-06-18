#!/usr/bin/env bash
# longinus-reverse-scan.sh — KG ↔ SKILL.md 양방향 orphan 검사
# (Longinus 7-Layer Reference Model 의 Reverse Orphan Scan, 수동 실행 — cron 미설정)
#
# 출력:
#   FILE_ORPHAN  <path>         : SKILL.md 에 kg_ref 없거나 존재 안 하는 ATOM 노드 가리킴
#   KG_ORPHAN    <atomName>     : KG 의 ATOM_Skill_* 인데 absolutePath 의 SKILL.md 없음
#   OK           <name>          : 양방향 일치
#
# 사용:
#   longinus-reverse-scan.sh [--quiet]   # quiet 면 OK 줄 생략, 문제만 출력
set -euo pipefail

QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SKILLS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"

# Build expected mapping from skill-add-kgref.py source
PY="$SCRIPT_DIR/skill-add-kgref.py"

# 1) FILE → expected ATOM
PAIRS_FILE="$(mktemp)"
trap 'rm -f "$PAIRS_FILE"' EXIT
python3 -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('m', '$PY')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
for k,v in sorted(m.MAPPING.items()): print(k, v)
" > "$PAIRS_FILE"

rc=0
while IFS=' ' read -r dir atom; do
  [[ -z "$dir" ]] && continue
  fpath="$SKILLS_ROOT/$dir/SKILL.md"
  if [[ ! -f "$fpath" ]]; then
    echo "KG_ORPHAN    $atom (expected $fpath missing)"
    rc=1
    continue
  fi
  if ! grep -q "^kg_ref: $atom" "$fpath"; then
    echo "FILE_ORPHAN  $fpath (kg_ref mismatch or missing for $atom)"
    rc=1
    continue
  fi
  [[ $QUIET -eq 0 ]] && echo "OK           $dir ↔ $atom"
done < "$PAIRS_FILE"

# 2) Files in SKILLS_ROOT but not in MAPPING (un-tracked skills)
while IFS= read -r f; do
  dir="$(basename "$(dirname "$f")")"
  if ! awk '{print $1}' "$PAIRS_FILE" | grep -qx "$dir"; then
    echo "FILE_ORPHAN  $f (no KG mapping for dir '$dir')"
    rc=1
  fi
done < <(find "$SKILLS_ROOT" -maxdepth 2 -name 'SKILL.md' -type f -not -path "*/.git/*" -not -path "*/_backup_*/*")

exit "$rc"
