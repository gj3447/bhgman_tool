import sys
from pathlib import Path

# Bare-import bridge (flat-layout). GED drift + nightly cron 모듈.
# KG: eureka-l8-rectification-2026-05-27 (longinus_l8_induction split: drift→longinus_drift)
sys.path.insert(0, str(Path(__file__).parent.parent))
