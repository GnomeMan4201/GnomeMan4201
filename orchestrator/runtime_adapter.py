from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

SIGNALS_URL = "https://gnomeman4201.github.io/GnomeMan4201/data/runtime_signals.json"
DEFAULT_POSTURE = "ROUTINE"


def fetch_signals(url: str = SIGNALS_URL, timeout: float = 5.0) -> dict[str, dict[str, Any]]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "runtime-adapter/1.0",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("runtime signals payload is not a JSON object")
    return data


def get_node_record(node: str, *, url: str = SIGNALS_URL) -> dict[str, Any]:
    data = fetch_signals(url=url)
    rec = data.get(node)
    if not isinstance(rec, dict):
        return {}
    return rec


def get_posture(node: str, *, url: str = SIGNALS_URL) -> str:
    rec = get_node_record(node, url=url)
    posture = rec.get("posture", DEFAULT_POSTURE)
    return posture if isinstance(posture, str) else DEFAULT_POSTURE


def get_drift_score(node: str, *, url: str = SIGNALS_URL) -> float:
    rec = get_node_record(node, url=url)
    try:
        return float(rec.get("drift_score", 0.0))
    except (TypeError, ValueError):
        return 0.0


def is_locked(node: str, *, url: str = SIGNALS_URL) -> bool:
    return get_posture(node, url=url) == "LOCKED"


def summary(node: str, *, url: str = SIGNALS_URL) -> dict[str, Any]:
    rec = get_node_record(node, url=url)
    return {
        "node": node,
        "status": rec.get("status", "unknown"),
        "activity": rec.get("activity", 0),
        "drift_score": get_drift_score(node, url=url),
        "posture": get_posture(node, url=url),
        "last_event": rec.get("last_event", ""),
        "updated_at": rec.get("updated_at", ""),
    }


if __name__ == "__main__":
    import sys

    node = sys.argv[1] if len(sys.argv) > 1 else "LANimals"
    try:
        print(json.dumps(summary(node), indent=2, sort_keys=True))
    except (urllib.error.URLError, ValueError) as e:
        raise SystemExit(f"runtime adapter error: {e}")
