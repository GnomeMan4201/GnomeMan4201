from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.guarded_runner import run_node_task
from orchestrator.posture_guard import PostureGuardError


def main() -> None:
    ok = run_node_task("SHENRON")
    print("SHENRON", ok)

    try:
        run_node_task("LANimals")
    except PostureGuardError as e:
        print("LANimals blocked:", e)
    else:
        raise SystemExit("expected LANimals to be blocked")


if __name__ == "__main__":
    main()
