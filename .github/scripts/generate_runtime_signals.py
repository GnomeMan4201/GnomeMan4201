import json
import random
from datetime import datetime

nodes = [
    "SHENRON", "LANimals", "OpenSight", "drift_orchestrator",
    "zeroDAYSlater", "PHANTOM", "LUNE"
]

def gen(node):
    return {
        "node": node,
        "status": random.choice(["active", "warning", "idle"]),
        "activity": random.randint(10, 100),
        "last_event": random.choice([
            "runtime cycle",
            "telemetry refresh",
            "signal update",
            "pipeline execution"
        ]),
        "last_event_recent": True,
        "updated_at": datetime.utcnow().isoformat() + "Z"
    }

data = {n: gen(n) for n in nodes}

with open("docs/data/runtime_signals.json", "w") as f:
    json.dump(data, f, indent=2)

print("generated runtime signals")
