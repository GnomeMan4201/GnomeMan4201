from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.execute_with_policy import execute


def main() -> None:
    node = "drift_orchestrator"
    task = sys.argv[1] if len(sys.argv) > 1 else "default_task"

    result = execute(node, task)

    if not result["executed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        raise SystemExit(1)

    mode = result["mode"]

    # --- THIS IS WHERE REAL WORK WILL GO ---
    # simulate constrained execution
    output = {
        "node": node,
        "task": task,
        "mode": mode,
        "steps_allowed": mode["max_steps"],
        "network_allowed": mode["allow_network"],
        "writeback_allowed": mode["allow_writeback"],
        "status": "executed_under_policy",
    }

    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
