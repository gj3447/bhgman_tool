"""hades 패키지 flat import용 path 설정. # KG: hades-canonical-2026-05-27"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
