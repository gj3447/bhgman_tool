#!/usr/bin/env bash
# bhgman bot 데몬 런처 — legion 닫힌루프 자율 봇을 백그라운드로 구동.
#   vLLM(추론) + SearXNG(인터넷) + Neo4j(KG) + 하네스(legion Contract+oracle gate).
# 사용: bin/bhgman-bot.sh {start|stop|status|restart|tail|once}
#
# secret(NEO4J_PASSWORD)은 커밋 금지 → 런타임에 .mcp.json 에서 추출. vLLM/SearXNG 는 env.vllm.sh.
# graceful: stop = SIGTERM → 봇이 현재 tick 마치고 종료(daemon._Stopper).
# KG: bhgman-bot-daemon-2026-06-16
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="${BHGMAN_BOT_PID:-$HOME/.bhgman_bot.pid}"
LOG="${BHGMAN_BOT_LOG:-$HOME/.bhgman_bot.log}"
MCP_JSON="${BHGMAN_MCP_JSON:-$HOME/CD/.mcp.json}"
INTERVAL="${BHGMAN_BOT_INTERVAL:-600}"

load_env() {
  # shellcheck disable=SC1091
  [ -f "$ROOT/env.vllm.sh" ] && source "$ROOT/env.vllm.sh"  # vLLM + SearXNG + NO_THINK
  export NEO4J_URI="${NEO4J_URI:-bolt://100.64.0.3:7687}"
  export NEO4J_USERNAME="${NEO4J_USERNAME:-neo4j}"
  if [ -z "${NEO4J_PASSWORD:-}" ] && [ -f "$MCP_JSON" ]; then
    NEO4J_PASSWORD="$(python3 -c "import json,sys;print(json.load(open('$MCP_JSON'))['mcpServers']['neo4j']['env']['NEO4J_PASSWORD'])" 2>/dev/null)"
    export NEO4J_PASSWORD
  fi
}

is_running() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

start() {
  if is_running; then echo "already running (pid $(cat "$PIDFILE"))"; return 0; fi
  load_env
  cd "$ROOT" || exit 1
  nohup uv run bhgman-tool bot --interval "$INTERVAL" --llm --web --no-disk-scan \
    >>"$LOG" 2>&1 &
  echo $! >"$PIDFILE"
  echo "started pid $(cat "$PIDFILE") interval=${INTERVAL}s (dry-run) log=$LOG"
}

stop() {
  if ! is_running; then echo "not running"; rm -f "$PIDFILE"; return 0; fi
  local pid; pid="$(cat "$PIDFILE")"
  kill "$pid" 2>/dev/null && echo "SIGTERM → pid $pid (graceful, finishes current tick)"
  rm -f "$PIDFILE"
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) stop; sleep 1; start ;;
  status) is_running && echo "running pid $(cat "$PIDFILE")" || echo "not running" ;;
  tail) tail -f "$LOG" ;;
  once) load_env; cd "$ROOT" && exec uv run bhgman-tool bot --once --llm --web --no-disk-scan ;;
  *) echo "usage: $0 {start|stop|status|restart|tail|once}"; exit 2 ;;
esac
