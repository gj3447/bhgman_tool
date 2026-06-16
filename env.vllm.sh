# bhgman_tool → dgx vLLM (Qwen3.6-27B) openai-compat backend
# 활성화: `source env.vllm.sh`  (또는 ~/.zshrc 가 자동 source — 2026-06-16 설치)
#
# 경로: Mac → tailscale 100.64.0.3 → dgx host :8000 → (vllm-relay.service) → k8s vllm pod :8000
#   - vLLM 은 k8s Deployment(vllm-79c46fffc7) 안에서 정상 서빙. control plane(kubectl) unreachable.
#   - dgx 의 systemd `vllm-relay.service` 가 pod IP(동적) → host :8000 노출 (kubectl 없이).
#   - AgentClient(engine/agents/client.py) 우선순위: BHGMAN_LLM_BASE_URL > ANTHROPIC_API_KEY.
#     즉 이 값들이 export 되면 bhgman 은 anthropic 무시하고 항상 로컬 vLLM 사용.
#
# 점검:  curl -s http://100.64.0.3:8000/v1/models | python3 -m json.tool
export BHGMAN_LLM_BASE_URL="http://100.64.0.3:8000/v1"
export BHGMAN_LLM_MODEL="qwen3.6-27b"
export BHGMAN_LLM_API_KEY="EMPTY"
# reasoning 모델은 로딩/사고가 느려 기본 120s 로는 부족할 수 있어 상향
export BHGMAN_LLM_TIMEOUT="180"
