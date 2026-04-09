#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

OUT = Path("docs/data/runtime_signals.json")
EVENTS = Path("docs/data/control_plane_events.jsonl")


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


def clamp(value: float, low: float = 0.0, high: float = 0.99) -> float:
    return max(low, min(high, value))


def load_previous() -> dict[str, dict]:
    if not OUT.exists():
        return {}
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_event_pressure() -> dict[str, float]:
    """
    Optional feedback channel:
    docs/data/control_plane_events.jsonl lines like:
    {"node":"LANimals","executed":false,"reason":"blocked by control plane"}
    {"node":"drift_orchestrator","executed":true,"mode":"restricted"}
    """
    pressure: dict[str, float] = {}
    if not EVENTS.exists():
        return pressure

    try:
        lines = EVENTS.read_text(encoding="utf-8").splitlines()[-200:]
    except Exception:
        return pressure

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue

        node = event.get("node")
        if not isinstance(node, str):
            continue

        delta = 0.0

        if event.get("executed") is False:
            delta += 0.10

        mode = event.get("mode")
        if isinstance(mode, dict):
            if mode.get("allow_network") is False:
                delta += 0.03
            if mode.get("allow_writeback") is False:
                delta += 0.03
            if int(mode.get("max_steps", 5)) <= 1:
                delta += 0.03
        elif mode == "restricted":
            delta += 0.06
        elif mode == "blocked":
            delta += 0.10

        reason = str(event.get("reason", "")).lower()
        if "blocked" in reason:
            delta += 0.06
        if "writeback disabled" in reason:
            delta += 0.04
        if "network disabled" in reason:
            delta += 0.04

        pressure[node] = pressure.get(node, 0.0) + delta

    return pressure


def target_pressure(status: str, activity: int, recent: bool) -> float:
    score = 0.0

    if status == "warning":
        score += 0.22
    elif status == "idle":
        score += 0.08
    else:
        score += 0.12

    if activity >= 85:
        score += 0.22
    elif activity >= 65:
        score += 0.16
    elif activity >= 40:
        score += 0.10
    else:
        score += 0.05

    if recent:
        score += 0.05

    return clamp(score)


def posture_for_drift(prev_posture: str, drift: float) -> str:
    """
    Hysteresis:
    - harder to enter LOCKED
    - easier to recover out of LOCKED
    - ROUTINE needs sustained lower drift
    """
    if prev_posture == "LOCKED":
        if drift >= 0.78:
            return "LOCKED"
        if drift < 0.62:
            return "CAUTIOUS"
        return "LOCKED"

    if prev_posture == "CAUTIOUS":
        if drift >= 0.78:
            return "LOCKED"
        if drift < 0.28:
            return "ROUTINE"
        return "CAUTIOUS"

    # prev ROUTINE or unknown
    if drift >= 0.72:
        return "LOCKED"
    if drift >= 0.38:
        return "CAUTIOUS"
    return "ROUTINE"


def build_signals() -> dict[str, dict]:
    ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    previous = load_previous()
    event_pressure = load_event_pressure()
    out: dict[str, dict] = {}

    for name, signal in BASE_SIGNALS.items():
        prev = previous.get(name, {}) if isinstance(previous.get(name), dict) else {}
        prev_drift = float(prev.get("drift_score", 0.0) or 0.0)
        prev_posture = str(prev.get("posture", "ROUTINE"))
        recovery_streak = int(prev.get("_recovery_streak", 0) or 0)

        record = dict(signal)

        target = target_pressure(
            status=record["status"],
            activity=record["activity"],
            recent=record["last_event_recent"],
        )

        # Event pressure raises risk, but capped so it does not explode.
        target += min(event_pressure.get(name, 0.0), 0.20)

        # Weighted smoothing:
        # keep memory of previous state, but move toward current conditions.
        drift = (prev_drift * 0.72) + (target * 0.28)

        # Recovery / damping:
        # if target is below previous drift, count stable cycles and decay faster.
        if target < prev_drift:
            recovery_streak += 1
            drift -= min(0.03 * recovery_streak, 0.12)
        else:
            recovery_streak = 0

        # Extra damping for healthy-ish nodes to prevent amber/red saturation.
        if record["status"] == "idle" and record["activity"] < 70:
            drift -= 0.04

        # Escalate a bit for noisy warning nodes under heavy activity.
        if record["status"] == "warning" and record["activity"] >= 80:
            drift += 0.05

        drift = round(clamp(drift), 2)
        posture = posture_for_drift(prev_posture, drift)

        # Strong recovery path out of LOCKED if drift has stayed lower.
        if prev_posture == "LOCKED" and recovery_streak >= 2 and drift < 0.58:
            posture = "CAUTIOUS"
        if prev_posture in {"LOCKED", "CAUTIOUS"} and recovery_streak >= 3 and drift < 0.26:
            posture = "ROUTINE"

        record["drift_score"] = drift
        record["posture"] = posture
        record["updated_at"] = ts

        # Internal control-plane bookkeeping.
        record["_target_pressure"] = round(target, 2)
        record["_recovery_streak"] = recovery_streak

        out[name] = record

    return out


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build_signals()
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("generated runtime signals with damping/recovery")


if __name__ == "__main__":
    main()
