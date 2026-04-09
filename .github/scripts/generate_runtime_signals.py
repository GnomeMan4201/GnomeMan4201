#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


OUT = Path("docs/data/runtime_signals.json")


BASE_SIGNALS = {
    "SHENRON": {
        "node": "SHENRON",
        "status": "idle",
        "activity": 65,
        "last_event": "pipeline execution",
        "last_event_recent": True,
    },
    "LANimals": {
        "node": "LANimals",
        "status": "warning",
        "activity": 90,
        "last_event": "telemetry refresh",
        "last_event_recent": True,
    },
    "OpenSight": {
        "node": "OpenSight",
        "status": "warning",
        "activity": 35,
        "last_event": "signal update",
        "last_event_recent": True,
    },
    "drift_orchestrator": {
        "node": "drift_orchestrator",
        "status": "idle",
        "activity": 86,
        "last_event": "signal update",
        "last_event_recent": True,
    },
    "zeroDAYSlater": {
        "node": "zeroDAYSlater",
        "status": "warning",
        "activity": 70,
        "last_event": "telemetry refresh",
        "last_event_recent": True,
    },
    "PHANTOM": {
        "node": "PHANTOM",
        "status": "warning",
        "activity": 56,
        "last_event": "telemetry refresh",
        "last_event_recent": True,
    },
    "LUNE": {
        "node": "LUNE",
        "status": "idle",
        "activity": 35,
        "last_event": "pipeline execution",
        "last_event_recent": True,
    },
}


def compute_drift_score(status: str, activity: int, recent: bool) -> float:
    score = 0.0

    if status == "warning":
        score += 0.35
    elif status == "idle":
        score += 0.10
    else:
        score += 0.20

    if activity >= 85:
        score += 0.40
    elif activity >= 65:
        score += 0.25
    elif activity >= 40:
        score += 0.15
    else:
        score += 0.05

    if recent:
        score += 0.10

    return round(min(score, 0.99), 2)


def posture_for_drift(drift_score: float) -> str:
    if drift_score >= 0.70:
        return "LOCKED"
    if drift_score >= 0.35:
        return "CAUTIOUS"
    return "ROUTINE"


def build_signals() -> dict[str, dict]:
    ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    out: dict[str, dict] = {}

    for name, signal in BASE_SIGNALS.items():
        record = dict(signal)
        drift_score = compute_drift_score(
            status=record["status"],
            activity=record["activity"],
            recent=record["last_event_recent"],
        )
        record["drift_score"] = drift_score
        record["posture"] = posture_for_drift(drift_score)
        record["updated_at"] = ts
        out[name] = record

    return out


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build_signals()
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("generated runtime signals")


if __name__ == "__main__":
    main()
