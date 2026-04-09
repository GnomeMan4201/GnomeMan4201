from __future__ import annotations

import json
from orchestrator.policy_mode import runtime_mode_for

NODE = "drift_orchestrator"

def main() -> None:
    mode = runtime_mode_for(NODE)

    if not mode["allow_execution"]:
        raise SystemExit(f"{NODE} blocked by control plane")

    result = {
        "node": NODE,
        "allow_network": mode["allow_network"],
        "allow_writeback": mode["allow_writeback"],
        "max_steps": mode["max_steps"],
        "status": "ready",
    }
    print(json.dumps(result, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
