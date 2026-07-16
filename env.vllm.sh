# bhgman_tool → dgx vLLM (Qwen3.6-27B) openai-compat backend
# 활성화: `source env.vllm.sh`  (또는 ~/.zshrc 가 자동 source — 2026-06-16 설치)
#
# 경로: Mac LAN → dgx-worker 192.168.0.23:8000 (OpenAI-compatible vLLM)
#   - 2026-07-16: 옛 Tailscale 주소 100.64.0.3은 connect timeout, LAN endpoint는 /v1/models 200.
#   - 이 경로는 SYMPOSIUM/PI/DELLTOWER_OFFLOAD.md의 dgx-worker 상시 vLLM 경로와 일치한다.
#   - AgentClient(engine/agents/client.py) 우선순위: BHGMAN_LLM_BASE_URL > ANTHROPIC_API_KEY.
#     즉 이 값들이 export 되면 bhgman 은 anthropic 무시하고 항상 로컬 vLLM 사용.
#
# 점검:  curl -s http://192.168.0.23:8000/v1/models | python3 -m json.tool
export BHGMAN_LLM_BASE_URL="http://192.168.0.23:8000/v1"
export BHGMAN_LLM_MODEL="qwen3.6-27b"
export BHGMAN_LLM_API_KEY="EMPTY"
# GB10(~4tok/s)은 느려서 라운드당 여유 필요 — 상향
export BHGMAN_LLM_TIMEOUT="300"
# Qwen reasoning(think) 끄기 — 느린 GPU에서 ReAct 멀티라운드 think 토큰 폭발 방지 (속도+SEARCH 신호 명확)
export BHGMAN_LLM_NO_THINK="1"
# 로컬 웹검색 (SearXNG self-host @ dgx, 키 0). 설정 시 openai-compat 경로가 ReAct 검색 루프 활성.
# 검색은 *우리 인프라*가 실행 → vLLM agent 가 SEARCH: 신호로 호출. (Anthropic server-side web_search 와 무관)
export BHGMAN_SEARXNG_URL="http://192.168.0.23:8888"
export BHGMAN_LLM_SEARCH_ROUNDS="4"
