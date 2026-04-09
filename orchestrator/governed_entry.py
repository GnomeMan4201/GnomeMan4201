from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.execute_with_policy import execute

NODE = "drift_orchestrator"


def run_read_only_status(mode: dict[str, object]) -> dict[str, object]:
    return {
        "node": NODE,
        "task": "show_policy",
        "mode": mode,
        "status": "executed_under_policy",
        "network_allowed": mode["allow_network"],
        "writeback_allowed": mode["allow_writeback"],
        "steps_allowed": mode["max_steps"],
    }


def run_read_runtime_signals(mode: dict[str, object]) -> dict[str, object]:
    path = ROOT / "docs" / "data" / "runtime_signals.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "node": NODE,
        "task": "read_runtime_signals",
        "executed": True,
        "signal_nodes": sorted(payload.keys()),
        "count": len(payload),
        "mode": mode,
    }


def run_refresh_runtime_signals(mode: dict[str, object]) -> dict[str, object]:
    if not mode["allow_writeback"]:
        return {
            "node": NODE,
            "task": "refresh_runtime_signals",
            "executed": False,
            "reason": "writeback disabled by control plane",
            "mode": mode,
        }

    cmd = [sys.executable, ".github/scripts/generate_runtime_signals.py"]
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    return {
        "node": NODE,
        "task": "refresh_runtime_signals",
        "executed": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "mode": mode,
    }


def main() -> None:
    task = sys.argv[1] if len(sys.argv) > 1 else "show_policy"

    result = execute(NODE, task)

    if not result["executed"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        raise SystemExit(1)

    mode = result["mode"]

    if task == "show_policy":
        output = run_read_only_status(mode)
    elif task == "read_runtime_signals":
        output = run_read_runtime_signals(mode)
    elif task == "refresh_runtime_signals":
        output = run_refresh_runtime_signals(mode)
    else:
        output = {
            "node": NODE,
            "task": task,
            "executed": False,
            "reason": f"unknown task: {task}",
            "mode": mode,
        }

    print(json.dumps(output, indent=2, sort_keys=True))

    if output.get("executed") is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
