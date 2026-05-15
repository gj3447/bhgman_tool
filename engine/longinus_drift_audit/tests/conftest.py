import sys
from pathlib import Path

# Bridge: flat-layout standalone package + monorepo unified pytest dual-mode.
# CI working-directory: engine/longinus_drift_audit with `pip install -e .`
# resolves modules via egg-link. Parent unified pytest (testpaths=["engine"])
# bypasses egg-link → bare imports (from models import ...) need sys.path.
# Insert is idempotent vs egg-link (same target dir); also incidentally
# bypasses local stale-egg drift (Wave 6 modules not re-registered).
# KG: ap-bhgman-longinus-import-drift-fix-2026-05-15 (Option A, APPROVED 2026-05-15)
sys.path.insert(0, str(Path(__file__).parent.parent))
