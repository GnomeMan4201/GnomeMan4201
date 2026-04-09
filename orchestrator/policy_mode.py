from __future__ import annotations

from orchestrator.posture_guard import get_execution_policy

def runtime_mode_for(node: str) -> dict[str, object]:
    policy = get_execution_policy(node)

    if policy["mode"] == "blocked":
        return {
            "allow_execution": False,
            "allow_network": False,
            "allow_writeback": False,
            "max_steps": 0,
        }

    if policy["mode"] == "restricted":
        return {
            "allow_execution": True,
            "allow_network": False,
            "allow_writeback": False,
            "max_steps": 1,
        }

    return {
        "allow_execution": True,
        "allow_network": True,
        "allow_writeback": True,
        "max_steps": 5,
    }
