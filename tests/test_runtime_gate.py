from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.runtime_adapter import get_posture, get_drift_score, is_locked

for node in ["LANimals", "SHENRON", "drift_orchestrator", "LUNE"]:
    print(
        node,
        "posture=", get_posture(node),
        "drift=", get_drift_score(node),
        "locked=", is_locked(node),
    )
