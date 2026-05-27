import sys
from pathlib import Path

# Bare-import bridge (longinus_drift_audit 패턴 1:1): unified pytest(testpaths=["engine"])는
# egg-link 우회 → `from occam import ...` 위해 subsystem 루트를 sys.path에 주입. idempotent.
# KG: ap-bhgman-longinus-import-drift-fix-2026-05-15 (Option A precedent)
sys.path.insert(0, str(Path(__file__).parent.parent))
