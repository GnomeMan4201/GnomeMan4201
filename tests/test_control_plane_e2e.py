from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.execute_with_policy import execute
from orchestrator.policy_mode import runtime_mode_for
from orchestrator.governed_stream import create_governed_stream

def main() -> None:
    print("LANimals:", execute("LANimals", "scan"))
    print("drift_orchestrator:", execute("drift_orchestrator", "planner_run"))
    print("mode:", runtime_mode_for("drift_orchestrator"))
    stream = create_governed_stream()
    print("stream mode:", stream._policy_mode)

if __name__ == "__main__":
    main()
