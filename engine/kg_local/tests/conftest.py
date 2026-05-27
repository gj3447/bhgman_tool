import sys
from pathlib import Path

# Bare-import bridge (occam/longinus_drift_audit 패턴 1:1): `from store import ...` 위해
# subsystem 루트(engine/kg_local)를 sys.path에 주입. idempotent.
# KG: bhgman-local-kg-backend-2026-05-28
sys.path.insert(0, str(Path(__file__).parent.parent))
