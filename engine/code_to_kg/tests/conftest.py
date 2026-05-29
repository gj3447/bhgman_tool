import sys
from pathlib import Path

# Bare-import bridge (occam/longinus_drift_audit 패턴 1:1): unified pytest(testpaths=["engine"])
# 에서 `from ts_extractor import ...` 가능하도록 subsystem 루트 + engine 루트를 sys.path 주입.
# KG: ap-bhgman-longinus-import-drift-fix-2026-05-15 (Option A precedent)
_here = Path(__file__).parent.parent
sys.path.insert(0, str(_here))  # engine/code_to_kg  (bare ts_extractor/kg_writer)
sys.path.insert(0, str(_here.parent.parent))  # repo root (engine.kg_local.store)
