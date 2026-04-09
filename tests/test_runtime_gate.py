from orchestrator.runtime_adapter import get_posture, get_drift_score, is_locked

for node in ["LANimals", "SHENRON", "drift_orchestrator", "LUNE"]:
    print(
        node,
        "posture=", get_posture(node),
        "drift=", get_drift_score(node),
        "locked=", is_locked(node),
    )
