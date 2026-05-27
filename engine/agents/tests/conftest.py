import sys
from pathlib import Path

# flat-layout bare-import bridge (occam/kg_local 패턴 1:1): client/dispatch/models/prometheus/
# naesengmoon를 bare import하기 위해 engine/agents를 sys.path에 주입. idempotent.
# KG: bhgman-llm-commander-runtime-2026-05-28
sys.path.insert(0, str(Path(__file__).parent.parent))
