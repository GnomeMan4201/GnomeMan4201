from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.posture_guard import PostureGuardError, assert_node_allows_execution, get_execution_policy


def run_node_task(node: str) -> dict[str, object]:
    policy = get_execution_policy(node)
    assert_node_allows_execution(node)

    return {
        "node": node,
        "executed": True,
        "mode": policy["mode"],
        "message": f"{node} execution permitted under {policy['posture']} posture",
    }


if __name__ == "__main__":
    node = sys.argv[1] if len(sys.argv) > 1 else "SHENRON"

    try:
        result = run_node_task(node)
        print(json.dumps(result, indent=2, sort_keys=True))
    except PostureGuardError as e:
        print(json.dumps({
            "node": node,
            "executed": False,
            "error": str(e),
        }, indent=2, sort_keys=True))
        raise SystemExit(1)
