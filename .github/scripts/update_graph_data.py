#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OWNER = "GnomeMan4201"

REPO_MAP = {
    "LANimals": "LANimals",
    "drift_orchestrator": "drift_orchestrator",
    "OpenSight": "OpenSight",
    "SHENRON": "shenron",
    "LANIMORPH": "lanimorph",
    "PHANTOM": "PHANTOM",
    "chain": "chain",
    "aliasOS": "aliasOS",
    "LUNE": "Lune",
    "zer0DAYSlater": "zer0DAYSlater",
    "HYDRA": "HYDRA",
    "Pickle Hunter": "Pickle-Hunter",
    "bad_BANANA": "bad_BANANA",
    "DevToReconSuite": "DevToReconSuite",
    "repo_alias_forge": "repo_alias_forge",
    "OWN": "OWN",
    "Blackglass": "Blackglass",
    "pwn": "pwn",
}

REPOS_JSON = Path("docs/data/repos.json")
STATUS_JSON = Path("docs/data/ecosystem_status.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def gh_get(url: str) -> dict | list | None:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "GnomeMan4201-graph-updater",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def classify_repo_status(pushed_at: str | None) -> str:
    if not pushed_at:
        return "idle"
    try:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - pushed).total_seconds() / 3600
        if age_hours < 24:
            return "active"
        if age_hours < 24 * 7:
            return "warning"
        return "idle"
    except Exception:
        return "idle"


def classify_health(status: str) -> str:
    if status == "active":
        return "ok"
    if status == "warning":
        return "warning"
    return "ok"


def build_repos_json() -> dict:
    updated_at = now_iso()
    repos: dict[str, dict] = {}

    for node_name, repo_name in REPO_MAP.items():
        data = gh_get(f"https://api.github.com/repos/{OWNER}/{repo_name}")
        if not isinstance(data, dict) or data.get("message") == "Not Found":
            repos[node_name] = {
                "stars": 0,
                "forks": 0,
                "open_issues": 0,
                "pushed_at": None,
                "status": "idle",
            }
            continue

        pushed_at = data.get("pushed_at")
        repos[node_name] = {
            "stars": int(data.get("stargazers_count", 0) or 0),
            "forks": int(data.get("forks_count", 0) or 0),
            "open_issues": int(data.get("open_issues_count", 0) or 0),
            "pushed_at": pushed_at,
            "status": classify_repo_status(pushed_at),
        }

    return {"updated_at": updated_at, "repos": repos}


def build_status_json(repos_payload: dict) -> dict:
    updated_at = now_iso()
    repos = repos_payload.get("repos", {})

    def activity(node_name: str, base: int) -> int:
        repo = repos.get(node_name, {})
        stars = int(repo.get("stars", 0) or 0)
        issues = int(repo.get("open_issues", 0) or 0)
        status = repo.get("status", "idle")
        freshness = {"active": 22, "warning": 10, "idle": 0}.get(status, 0)
        return min(100, base + stars * 2 + issues + freshness)

    shenron_status = repos.get("SHENRON", {}).get("status", "active")
    lanimals_status = repos.get("LANimals", {}).get("status", "idle")
    drift_status = repos.get("drift_orchestrator", {}).get("status", "idle")
    tree_status = "active" if any(
        repos.get(name, {}).get("status") == "active"
        for name in ("LANimals", "drift_orchestrator", "SHENRON", "OpenSight")
    ) else "warning"

    payload = {
        "updated_at": updated_at,
        "nodes": {
            "SHENRON": {
                "health": classify_health(shenron_status),
                "activity": activity("SHENRON", 55),
                "status": shenron_status,
                "last_event": "repo telemetry refresh",
                "last_updated": updated_at,
            },
            "LANimals": {
                "health": classify_health(lanimals_status),
                "activity": activity("LANimals", 42),
                "status": lanimals_status,
                "active_hosts": 0,
                "alerts": 0,
                "last_event": "repo telemetry refresh",
                "last_updated": updated_at,
            },
            "drift_orchestrator": {
                "health": classify_health(drift_status),
                "activity": activity("drift_orchestrator", 44),
                "status": drift_status,
                "drift_score": 0.0,
                "last_event": "repo telemetry refresh",
                "last_updated": updated_at,
            },
            "BANANA_TREE": {
                "health": classify_health(tree_status),
                "activity": 40 if tree_status == "active" else 24,
                "status": tree_status,
                "alerts": 0,
                "last_event": "ecosystem aggregate refreshed",
                "last_updated": updated_at,
            },
        },
        "edges": {
            "LANimals->SHENRON": {
                "active": repos.get("LANimals", {}).get("status") == "active",
                "throughput": 28 if repos.get("LANimals", {}).get("status") == "active" else 10,
            },
            "drift_orchestrator->Autonomy &\nOrchestration": {
                "active": repos.get("drift_orchestrator", {}).get("status") in {"active", "warning"},
                "throughput": 22 if repos.get("drift_orchestrator", {}).get("status") == "active" else 8,
            },
            "BANANA_TREE->SHENRON": {
                "active": True,
                "throughput": 12,
            },
        },
    }
    return payload


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repos_payload = build_repos_json()
    status_payload = build_status_json(repos_payload)
    write_json(REPOS_JSON, repos_payload)
    write_json(STATUS_JSON, status_payload)
    print("updated graph data")


if __name__ == "__main__":
    main()
