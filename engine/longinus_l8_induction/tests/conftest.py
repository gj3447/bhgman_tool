"""Make l8 package modules importable for tests.

Collision-with-sibling note (2026-05-21): `engine/longinus_drift_audit` and
this package both have flat-layout `models.py` / `validator.py` /
`pipeline.py` with different contents. A single pytest invocation that
collects both packages races on `from models import ...` — whichever
conftest seeds sys.path first wins, the other side breaks. The repo-level
fix is to invoke pytest twice with --ignore between the two roots; see
.pre-commit-config.yaml stage 5 pytest hook. This conftest just exposes
the local PACKAGE_ROOT for our own tests.
"""

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
