"""Make l8 package modules importable for tests.

Sibling-collision FIXED (2026-05-25, Naesengmoon ensemble
VR_bhgman_tool_ensemble_2026-05-25_5f5a905 finding #1): the only top-level
module name shared with `engine/longinus_drift_audit` was `models.py`. This
package's copy was renamed `models.py` -> `induction_models.py`, so a single
root `pytest` now collects both flat-layout packages without a
`from models import ...` sys.modules race. (The earlier note also listed
validator.py/pipeline.py as colliding — empirically drift_audit ships neither
at top level, so `models` was the sole collision.) This conftest just exposes
the local PACKAGE_ROOT so the flat-layout modules resolve when collected from
the monorepo root.
"""

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
