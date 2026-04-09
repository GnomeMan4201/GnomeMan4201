from __future__ import annotations

from drift_orchestrator.drift_live_signal import LiveSignalStream
from orchestrator.execute_with_policy import execute


def create_governed_stream(node: str = "drift_orchestrator") -> LiveSignalStream:
    result = execute(node, "drift_live_signal")

    if not result["executed"]:
        raise RuntimeError(result["reason"])

    mode = result["mode"]

    stream = LiveSignalStream()

    # Attach policy metadata for downstream use
    stream._policy_mode = mode

    return stream
