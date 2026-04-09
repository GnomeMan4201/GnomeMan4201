from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.runtime_adapter import get_drift_score, get_posture, is_locked


class PostureGuardError(RuntimeError):
    pass


def assert_node_allows_execution(node: str) -> None:
    if is_locked(node):
        raise PostureGuardError(f"{node} is LOCKED by control plane")


def get_execution_policy(node: str) -> dict[str, object]:
    posture = get_posture(node)
    drift = get_drift_score(node)

    if posture == "LOCKED":
        return {
            "node": node,
            "posture": posture,
            "drift_score": drift,
            "allow_execution": False,
            "mode": "blocked",
        }

    if posture == "CAUTIOUS":
        return {
            "node": node,
            "posture": posture,
            "drift_score": drift,
            "allow_execution": True,
            "mode": "restricted",
        }

    return {
        "node": node,
        "posture": posture,
        "drift_score": drift,
        "allow_execution": True,
        "mode": "normal",
    }


if __name__ == "__main__":
    node = sys.argv[1] if len(sys.argv) > 1 else "LANimals"
    print(json.dumps(get_execution_policy(node), indent=2, sort_keys=True))
