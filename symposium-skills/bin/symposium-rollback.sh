#!/usr/bin/env bash
# symposium-rollback.sh — SYMPOSIUM/SKILLS 롤백 (git 기반) + tmutil 스냅샷 조회
# 사용:
#   symposium-rollback.sh list                  # git 커밋 + tmutil 스냅샷 목록
#   symposium-rollback.sh git <sha>             # SYMPOSIUM/SKILLS git 체크아웃 (detached)
#   symposium-rollback.sh git-restore <sha> <path>   # 특정 파일만 복구
#   symposium-rollback.sh snapshot              # 최신 tmutil localsnapshot 즉시 생성
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SKILLS_GIT="$(dirname "$_SCRIPT_DIR")"

cmd="${1:-help}"

case "$cmd" in
  list)
    echo "=== git history (SYMPOSIUM/SKILLS) ==="
    git -C "$SKILLS_GIT" log --oneline -20 2>&1
    echo
    echo "=== tmutil localsnapshots ==="
    tmutil listlocalsnapshots / 2>&1 | head -20
    ;;
  git)
    sha="${2:?sha required}"
    echo "Checkout $sha in $SKILLS_GIT (detached HEAD)"
    git -C "$SKILLS_GIT" status --short
    git -C "$SKILLS_GIT" checkout "$sha"
    ;;
  git-restore)
    sha="${2:?sha required}"; path="${3:?path required}"
    git -C "$SKILLS_GIT" checkout "$sha" -- "$path"
    echo "Restored $path from $sha"
    ;;
  snapshot)
    /usr/bin/tmutil localsnapshot
    /usr/bin/tmutil listlocalsnapshots / | head -3
    ;;
  *)
    cat <<EOF >&2
usage: $(basename "$0") {list|git <sha>|git-restore <sha> <path>|snapshot}
EOF
    exit 2
    ;;
esac
