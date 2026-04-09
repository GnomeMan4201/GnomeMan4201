from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.policy_mode import runtime_mode_for


def execute(node: str, task_name: str) -> dict[str, object]:
    mode = runtime_mode_for(node)

    if not mode["allow_execution"]:
        return {
            "node": node,
            "task": task_name,
            "executed": False,
            "reason": "blocked by control plane",
            "mode": mode,
        }

    return {
        "node": node,
        "task": task_name,
        "executed": True,
        "mode": mode,
        "message": f"{task_name} permitted for {node}",
    }


if __name__ == "__main__":
    node = sys.argv[1] if len(sys.argv) > 1 else "drift_orchestrator"
    task = sys.argv[2] if len(sys.argv) > 2 else "default_task"
    print(json.dumps(execute(node, task), indent=2, sort_keys=True))
