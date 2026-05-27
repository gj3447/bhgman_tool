import sys
from pathlib import Path

# Bare-import bridge (flat-layout). Legion orchestrator.
# KG: adr-seven-commander-legion-architecture-2026-05-27
sys.path.insert(0, str(Path(__file__).parent.parent))
