#!/usr/bin/env bash
# SYMPOSIUM Skills — external bootstrap installer.
#
# Usage (curl-pipe, default):
#   curl -sSL https://install.metahumotonic.com/install | bash
#   curl -sSL https://raw.githubusercontent.com/airobotics-inc/symposium-skills/main/install.sh | bash
#
# Usage (manual clone):
#   git clone https://github.com/airobotics-inc/symposium-skills.git ~/.symposium
#   bash ~/.symposium/install.sh
#
# Env overrides:
#   SYMPOSIUM_GIT_URL=https://github.com/airobotics-inc/symposium-skills.git
#   SYMPOSIUM_BRANCH=main
#   SYMPOSIUM_PREFIX=$HOME/.symposium
#   SYMPOSIUM_KG=1                     # 1 = bootstrap Neo4j (docker), 0 = skip (default 0)
#   SYMPOSIUM_KG_PASSWORD=symposium    # neo4j password (default: symposium)
#   SYMPOSIUM_NO_HOOKS=1               # skip ~/.claude/hooks/ install
#   SYMPOSIUM_NO_SETTINGS=1            # skip settings.json patch
#   SYMPOSIUM_YES=1                    # non-interactive (assume yes)
#   SYMPOSIUM_DRY_RUN=1                # print actions, do nothing
#
# Flags (when run directly, not via curl-pipe):
#   --yes            non-interactive
#   --dry-run        show actions only
#   --with-kg        bootstrap Neo4j docker + load KG snapshot
#   --no-hooks       skip hook install
#   --no-settings    skip settings.json patch
#   --branch <b>     git branch (default: main)
#   --prefix <p>     install location (default: $HOME/.symposium)
#
# Idempotent: safe to re-run. Existing settings.json is backed up + merged.

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════
# Defaults
# ═══════════════════════════════════════════════════════════════════════════
SYMPOSIUM_GIT_URL="${SYMPOSIUM_GIT_URL:-https://github.com/airobotics-inc/symposium-skills.git}"
SYMPOSIUM_BRANCH="${SYMPOSIUM_BRANCH:-main}"
SYMPOSIUM_PREFIX="${SYMPOSIUM_PREFIX:-$HOME/.symposium}"
SYMPOSIUM_KG="${SYMPOSIUM_KG:-0}"
SYMPOSIUM_KG_PASSWORD="${SYMPOSIUM_KG_PASSWORD:-symposium}"
SYMPOSIUM_NO_HOOKS="${SYMPOSIUM_NO_HOOKS:-0}"
SYMPOSIUM_NO_SETTINGS="${SYMPOSIUM_NO_SETTINGS:-0}"
SYMPOSIUM_YES="${SYMPOSIUM_YES:-0}"
SYMPOSIUM_DRY_RUN="${SYMPOSIUM_DRY_RUN:-0}"

# Parse flags (only applies when run directly, not via curl-pipe)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes)          SYMPOSIUM_YES=1; shift ;;
    --dry-run)      SYMPOSIUM_DRY_RUN=1; shift ;;
    --with-kg)      SYMPOSIUM_KG=1; shift ;;
    --no-hooks)     SYMPOSIUM_NO_HOOKS=1; shift ;;
    --no-settings)  SYMPOSIUM_NO_SETTINGS=1; shift ;;
    --branch)       SYMPOSIUM_BRANCH="$2"; shift 2 ;;
    --prefix)       SYMPOSIUM_PREFIX="$2"; shift 2 ;;
    -h|--help)      sed -n '2,30p' "$0"; exit 0 ;;
    *)              echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

CLAUDE_DIR="$HOME/.claude"
SKILLS_LINK_DIR="$CLAUDE_DIR/skills"
HOOKS_DIR="$CLAUDE_DIR/hooks"
SETTINGS="$CLAUDE_DIR/settings.json"

# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════
say()  { printf '\033[1;36m▸\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }
run()  {
  if [[ $SYMPOSIUM_DRY_RUN -eq 1 ]]; then
    printf '\033[2m  $ %s\033[0m\n' "$*"
  else
    eval "$@"
  fi
}
confirm() {
  [[ $SYMPOSIUM_YES -eq 1 ]] && return 0
  [[ $SYMPOSIUM_DRY_RUN -eq 1 ]] && return 0
  read -r -p "$1 [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]]
}
have() { command -v "$1" >/dev/null 2>&1; }

# ═══════════════════════════════════════════════════════════════════════════
# Step 0: prereq check
# ═══════════════════════════════════════════════════════════════════════════
say "SYMPOSIUM Skills installer — prereq check"

OS="$(uname -s)"
case "$OS" in
  Darwin) PLATFORM=macos ;;
  Linux)  PLATFORM=linux ;;
  *)      die "unsupported OS: $OS (need macOS or Linux)" ;;
esac
ok "platform: $PLATFORM"

MISSING=()
for tool in git jq curl bash; do
  have "$tool" || MISSING+=("$tool")
done
if (( ${#MISSING[@]} > 0 )); then
  warn "missing tools: ${MISSING[*]}"
  if [[ $PLATFORM == macos ]]; then
    warn "install with: brew install ${MISSING[*]}"
  else
    warn "install with: sudo apt-get install -y ${MISSING[*]}"
  fi
  die "abort"
fi
ok "tools: git jq curl bash"

if [[ $SYMPOSIUM_KG -eq 1 ]]; then
  have docker || die "--with-kg requires docker (install via https://docs.docker.com/get-docker/)"
  ok "docker available"
fi

if [[ "$SYMPOSIUM_GIT_URL" == *"REPLACE-ME"* ]]; then
  die "SYMPOSIUM_GIT_URL is placeholder. Set env: export SYMPOSIUM_GIT_URL=https://github.com/<you>/symposium-skills.git"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Step 1: clone or update
# ═══════════════════════════════════════════════════════════════════════════
say "Step 1/6: clone repo to $SYMPOSIUM_PREFIX"
if [[ -d "$SYMPOSIUM_PREFIX/.git" ]]; then
  warn "existing repo at $SYMPOSIUM_PREFIX — pulling latest"
  run "git -C '$SYMPOSIUM_PREFIX' fetch --quiet origin '$SYMPOSIUM_BRANCH'"
  run "git -C '$SYMPOSIUM_PREFIX' checkout --quiet '$SYMPOSIUM_BRANCH'"
  run "git -C '$SYMPOSIUM_PREFIX' pull --quiet --ff-only origin '$SYMPOSIUM_BRANCH'"
elif [[ -d "$SYMPOSIUM_PREFIX" && -n "$(ls -A "$SYMPOSIUM_PREFIX" 2>/dev/null)" ]]; then
  die "$SYMPOSIUM_PREFIX exists and is not empty (and not a git repo). Move or remove."
else
  run "git clone --quiet --branch '$SYMPOSIUM_BRANCH' '$SYMPOSIUM_GIT_URL' '$SYMPOSIUM_PREFIX'"
fi
ok "repo at $SYMPOSIUM_PREFIX"

# Detect SKILLS root inside the repo. Both layouts supported:
#   layout A: repo root == SKILLS root (frontmatter, marketplace.json at top)
#   layout B: repo has SKILLS/ subdir
if [[ -d "$SYMPOSIUM_PREFIX/SKILLS" && -f "$SYMPOSIUM_PREFIX/SKILLS/MANIFEST.json" ]]; then
  SKILLS_ROOT="$SYMPOSIUM_PREFIX/SKILLS"
elif [[ -f "$SYMPOSIUM_PREFIX/MANIFEST.json" ]]; then
  SKILLS_ROOT="$SYMPOSIUM_PREFIX"
else
  die "cannot find SKILLS root (no MANIFEST.json at $SYMPOSIUM_PREFIX or $SYMPOSIUM_PREFIX/SKILLS)"
fi
ok "SKILLS root: $SKILLS_ROOT"

# ═══════════════════════════════════════════════════════════════════════════
# Step 2: symlink skill folders into ~/.claude/skills/
# ═══════════════════════════════════════════════════════════════════════════
say "Step 2/6: symlink skills into $SKILLS_LINK_DIR"
run "mkdir -p '$SKILLS_LINK_DIR'"

LINKED=0
SKIPPED=0
for skill_dir in "$SKILLS_ROOT"/*/; do
  [[ -f "$skill_dir/SKILL.md" ]] || continue
  name="$(basename "$skill_dir")"
  link="$SKILLS_LINK_DIR/$name"
  if [[ -L "$link" || -e "$link" ]]; then
    if [[ -L "$link" && "$(readlink "$link")" == "${skill_dir%/}" ]]; then
      SKIPPED=$((SKIPPED+1))
      continue
    fi
    warn "  $name: existing entry — overwriting"
    run "rm -rf '$link'"
  fi
  run "ln -sfn '${skill_dir%/}' '$link'"
  LINKED=$((LINKED+1))
done
ok "skills: $LINKED new + $SKIPPED already-linked"

# ═══════════════════════════════════════════════════════════════════════════
# Step 3: install hooks (copy, not symlink — hook updates require re-run)
# ═══════════════════════════════════════════════════════════════════════════
if [[ $SYMPOSIUM_NO_HOOKS -eq 1 ]]; then
  warn "Step 3/6: hooks SKIPPED (SYMPOSIUM_NO_HOOKS=1)"
else
  say "Step 3/6: install hooks → $HOOKS_DIR"
  run "mkdir -p '$HOOKS_DIR'"

  # Stop hook (autoloop, opt-in via /tmp/claude_autoloop_active)
  if [[ $SYMPOSIUM_DRY_RUN -eq 0 ]]; then
    cat > "$HOOKS_DIR/auto_continue.sh" <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail
INPUT=$(cat)
ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
[ "$ACTIVE" = "true" ] && exit 0
[ ! -f /tmp/claude_autoloop_active ] && exit 0
SID=$(echo "$INPUT" | jq -r '.session_id // "default"')
COUNT_FILE="/tmp/claude_iter_${SID}"
ITER=$(cat "$COUNT_FILE" 2>/dev/null || echo 0)
MAX_ITER=$(grep -oE 'max_iter=[0-9]+' /tmp/claude_autoloop_active 2>/dev/null | cut -d= -f2)
MAX_ITER=${MAX_ITER:-120}
if [ "$ITER" -ge "$MAX_ITER" ]; then
  rm -f "$COUNT_FILE" /tmp/claude_autoloop_active
  printf '{"decision":"approve","systemMessage":"autoloop: max %s reached"}\n' "$MAX_ITER"
  exit 0
fi
if [ -f /tmp/claude_task_complete ]; then
  rm -f "$COUNT_FILE" /tmp/claude_autoloop_active /tmp/claude_task_complete
  echo '{"decision":"approve","systemMessage":"autoloop: task_complete marker"}'
  exit 0
fi
echo $((ITER+1)) > "$COUNT_FILE"
printf '{"decision":"block","reason":"autoloop active (iter %s/%s); touch /tmp/claude_task_complete to release"}\n' "$((ITER+1))" "$MAX_ITER"
exit 2
HOOK

    cat > "$HOOKS_DIR/autoloop_start.sh" <<'START'
#!/usr/bin/env bash
set -euo pipefail
MAX_ITER="${1:-120}"
echo "max_iter=${MAX_ITER}" > /tmp/claude_autoloop_active
echo "autoloop: max_iter=${MAX_ITER}. release: touch /tmp/claude_task_complete OR rm /tmp/claude_autoloop_active"
START

    cat > "$HOOKS_DIR/autoloop_stop.sh" <<'STOP'
#!/usr/bin/env bash
set -euo pipefail
rm -f /tmp/claude_autoloop_active /tmp/claude_iter_* /tmp/claude_task_complete
echo "autoloop: cleared."
STOP

    chmod +x "$HOOKS_DIR"/auto_continue.sh "$HOOKS_DIR"/autoloop_start.sh "$HOOKS_DIR"/autoloop_stop.sh
  fi

  # APT gate-check hook (if shipped in SKILLS/bin)
  if [[ -f "$SKILLS_ROOT/bin/apt-gate-check.sh" ]]; then
    run "cp '$SKILLS_ROOT/bin/apt-gate-check.sh' '$HOOKS_DIR/apt-gate-check.sh' && chmod +x '$HOOKS_DIR/apt-gate-check.sh'"
  fi

  ok "hooks: auto_continue + autoloop_start/stop$([ -f "$SKILLS_ROOT/bin/apt-gate-check.sh" ] && echo " + apt-gate-check")"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Step 4: patch ~/.claude/settings.json
# ═══════════════════════════════════════════════════════════════════════════
if [[ $SYMPOSIUM_NO_SETTINGS -eq 1 ]]; then
  warn "Step 4/6: settings.json SKIPPED (SYMPOSIUM_NO_SETTINGS=1)"
else
  say "Step 4/6: patch $SETTINGS"
  run "mkdir -p '$CLAUDE_DIR'"

  if [[ -f "$SETTINGS" ]]; then
    BACKUP="$SETTINGS.bak.symposium-$(date +%Y%m%d-%H%M%S)"
    run "cp '$SETTINGS' '$BACKUP'"
    ok "  backup: $BACKUP"
  else
    [[ $SYMPOSIUM_DRY_RUN -eq 0 ]] && echo '{"permissions":{"defaultMode":"default"}}' > "$SETTINGS"
    ok "  created stub: $SETTINGS"
  fi

  if [[ $SYMPOSIUM_DRY_RUN -eq 0 ]]; then
    PATCH=$(cat <<EOF
{
  "permissions": {
    "defaultMode": "default",
    "allow": [
      "Skill(*)", "Agent(*)",
      "Bash($SKILLS_ROOT/bin/*)",
      "Read($SYMPOSIUM_PREFIX/**)",
      "mcp__neo4j__*"
    ],
    "deny": [
      "Bash(rm -rf /*)",
      "Bash(rm -rf ~*)",
      "Bash(rm -rf \$HOME*)",
      "Bash(git push --force *)",
      "Bash(git reset --hard origin/main*)",
      "Bash(sudo rm *)",
      "Bash(sudo dd *)",
      "Bash(mkfs*)",
      "Write(/etc/**)",
      "Write(~/.ssh/**)",
      "Write(~/.aws/credentials)",
      "Write(~/.gnupg/**)"
    ]
  },
  "hooks": {
    "Stop": [
      {"hooks": [{"type": "command", "command": "$HOOKS_DIR/auto_continue.sh", "timeout": 5}]}
    ]
  }
}
EOF
)
    jq -s '.[0] * .[1]' "$SETTINGS" <(echo "$PATCH") > "$SETTINGS.new"
    mv "$SETTINGS.new" "$SETTINGS"
    jq . "$SETTINGS" >/dev/null
  fi
  ok "  settings.json patched (deep-merged, user keys preserved)"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Step 5: KG (Neo4j) bootstrap (optional)
# ═══════════════════════════════════════════════════════════════════════════
if [[ $SYMPOSIUM_KG -eq 1 ]]; then
  say "Step 5/6: bootstrap Neo4j (docker)"
  CONTAINER=symposium-neo4j
  if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    warn "  container '$CONTAINER' exists — starting if stopped"
    run "docker start '$CONTAINER' >/dev/null"
  else
    run "docker run -d --name '$CONTAINER' \
      -p 7474:7474 -p 7687:7687 \
      -e NEO4J_AUTH=neo4j/'$SYMPOSIUM_KG_PASSWORD' \
      -v symposium-neo4j-data:/data \
      neo4j:5 >/dev/null"
    ok "  Neo4j container started (bolt://localhost:7687, password=$SYMPOSIUM_KG_PASSWORD)"
    say "  waiting for bolt port to open ..."
    if [[ $SYMPOSIUM_DRY_RUN -eq 0 ]]; then
      for i in $(seq 1 30); do
        if (echo > /dev/tcp/localhost/7687) 2>/dev/null; then break; fi
        sleep 2
      done
    fi
  fi

  SNAPSHOT="$SKILLS_ROOT/kg/snapshot.cypher"
  if [[ -f "$SNAPSHOT" ]]; then
    say "  loading KG snapshot: $SNAPSHOT"
    run "docker exec -i '$CONTAINER' cypher-shell -u neo4j -p '$SYMPOSIUM_KG_PASSWORD' < '$SNAPSHOT'"
    ok "  KG snapshot loaded"
  else
    warn "  no snapshot at $SNAPSHOT — KG started empty"
  fi
else
  warn "Step 5/6: KG SKIPPED (use --with-kg or SYMPOSIUM_KG=1 to bootstrap Neo4j)"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Step 6: smoke test
# ═══════════════════════════════════════════════════════════════════════════
say "Step 6/6: smoke test"
LINK_COUNT=$(find "$SKILLS_LINK_DIR" -maxdepth 1 -mindepth 1 -type l 2>/dev/null | wc -l | tr -d ' ')
ok "  $LINK_COUNT skill symlinks under $SKILLS_LINK_DIR"

if [[ -f "$SETTINGS" && $SYMPOSIUM_NO_SETTINGS -eq 0 ]]; then
  jq . "$SETTINGS" >/dev/null && ok "  settings.json valid JSON"
fi

if [[ $SYMPOSIUM_NO_HOOKS -eq 0 && -f "$HOOKS_DIR/auto_continue.sh" ]]; then
  RC=0
  echo '{"stop_hook_active":false,"session_id":"smoke"}' | "$HOOKS_DIR/auto_continue.sh" >/dev/null 2>&1 || RC=$?
  [[ $RC -eq 0 ]] && ok "  auto_continue hook smoke pass" || warn "  auto_continue hook smoke exit=$RC"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Done
# ═══════════════════════════════════════════════════════════════════════════
cat <<DONE

═══════════════════════════════════════════════════════════════════════════
SYMPOSIUM Skills installed. ✓

  repo:     $SYMPOSIUM_PREFIX
  skills:   $LINK_COUNT linked under $SKILLS_LINK_DIR
  hooks:    $([ $SYMPOSIUM_NO_HOOKS -eq 0 ] && echo "$HOOKS_DIR" || echo "skipped")
  settings: $([ $SYMPOSIUM_NO_SETTINGS -eq 0 ] && echo "$SETTINGS" || echo "skipped")
  kg:       $([ $SYMPOSIUM_KG -eq 1 ] && echo "neo4j @ bolt://localhost:7687" || echo "skipped (re-run with --with-kg)")

Next:
  • Restart your Claude Code session (or run: /plugin reload)
  • List skills:  ls $SKILLS_LINK_DIR
  • Update later: bash $SYMPOSIUM_PREFIX/install.sh   (idempotent)
  • Uninstall:    bash $SYMPOSIUM_PREFIX/uninstall.sh

DONE
