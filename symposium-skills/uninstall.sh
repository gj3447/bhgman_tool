#!/usr/bin/env bash
# SYMPOSIUM Skills — uninstall.
#
# Removes:
#   - ~/.claude/skills/<name> symlinks pointing into the install prefix
#   - ~/.claude/hooks/{auto_continue,autoloop_*}.sh
#   - Stop hook entry from ~/.claude/settings.json (best-effort jq filter)
#
# Does NOT remove:
#   - the install prefix itself (default: $HOME/.symposium) — manual `rm -rf` if desired
#   - Neo4j docker container (manual: `docker rm -f symposium-neo4j`)
#   - your settings.json backups (.bak.symposium-*)

set -euo pipefail

PREFIX="${SYMPOSIUM_PREFIX:-$HOME/.symposium}"
CLAUDE_DIR="$HOME/.claude"
SKILLS_LINK_DIR="$CLAUDE_DIR/skills"
HOOKS_DIR="$CLAUDE_DIR/hooks"
SETTINGS="$CLAUDE_DIR/settings.json"
YES="${SYMPOSIUM_YES:-0}"

[[ "${1:-}" == "--yes" ]] && YES=1

ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*" >&2; }

if [[ $YES -eq 0 ]]; then
  read -r -p "uninstall SYMPOSIUM Skills (skill symlinks + hooks + settings entry)? [y/N] " r
  [[ "$r" =~ ^[Yy]$ ]] || exit 0
fi

# 1. Remove skill symlinks pointing into PREFIX
COUNT=0
if [[ -d "$SKILLS_LINK_DIR" ]]; then
  while IFS= read -r link; do
    target="$(readlink "$link")"
    if [[ "$target" == "$PREFIX"/* || "$target" == "$PREFIX/SKILLS"/* ]]; then
      rm -f "$link"
      COUNT=$((COUNT+1))
    fi
  done < <(find "$SKILLS_LINK_DIR" -maxdepth 1 -mindepth 1 -type l)
fi
ok "removed $COUNT skill symlinks"

# 2. Remove hooks
for h in auto_continue.sh autoloop_start.sh autoloop_stop.sh apt-gate-check.sh; do
  if [[ -f "$HOOKS_DIR/$h" ]]; then
    rm -f "$HOOKS_DIR/$h"
    ok "removed hook: $h"
  fi
done

# 3. Remove Stop hook entry from settings.json
if [[ -f "$SETTINGS" ]] && command -v jq >/dev/null 2>&1; then
  cp "$SETTINGS" "$SETTINGS.bak.uninstall-$(date +%Y%m%d-%H%M%S)"
  jq 'if .hooks.Stop then .hooks.Stop |= map(select((.hooks // []) | all(.command | contains("auto_continue.sh") | not))) else . end' \
    "$SETTINGS" > "$SETTINGS.new"
  mv "$SETTINGS.new" "$SETTINGS"
  ok "settings.json Stop hook entry pruned"
fi

cat <<DONE

═══════════════════════════════════════════════════════════════════════════
SYMPOSIUM Skills uninstalled. ✓

To also remove:
  • repo:    rm -rf '$PREFIX'
  • neo4j:   docker rm -f symposium-neo4j && docker volume rm symposium-neo4j-data
  • backups: ls $CLAUDE_DIR/settings.json.bak.symposium-*

DONE
