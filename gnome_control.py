#!/usr/bin/env python3
"""
gnome // mission control v8
Interactive operator dashboard — badBANANA Research Collective
Serves at :7333. All data live from local SQLite + APIs.
POST routes for inv-hub actions, evidence, triage, enrichment.
"""

import os, sys, json, sqlite3, subprocess, socket, urllib.request, urllib.parse
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import threading, time, re

# ── paths ─────────────────────────────────────────────────────────────────────
MONITOR_DB   = Path.home() / ".badbanana/monitor.db"
INVHUB_DB    = Path.home() / "research_hub/hub.db"
SHENRON_DIR  = Path.home() / "research_hub/repos/shenron"
NIGHTLY_LOG  = Path.home() / "research_hub/logs/nightly.log"
DEVTO_KEY    = os.environ.get("DEVTO_API_KEY", "")

# ── helpers ───────────────────────────────────────────────────────────────────
def db(path, query, params=()):
    try:
        con = sqlite3.connect(path); con.row_factory = sqlite3.Row
        rows = con.execute(query, params).fetchall()
        con.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return []

def db_write(path, query, params=()):
    try:
        con = sqlite3.connect(path)
        cur = con.execute(query, params)
        con.commit(); rowid = cur.lastrowid; con.close()
        return rowid
    except Exception as e:
        return None

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

# ── data fetchers ─────────────────────────────────────────────────────────────
def get_monitor_data():
    alerts  = db(MONITOR_DB, "SELECT COUNT(*) as n FROM alerts")
    total   = alerts[0]["n"] if alerts else 0
    snaps   = db(MONITOR_DB, "SELECT COUNT(*) as n FROM infra_snapshots")
    snaps_n = snaps[0]["n"] if snaps else 0
    recent  = db(MONITOR_DB,
        "SELECT alert_type, details, timestamp as created_at FROM alerts ORDER BY timestamp DESC LIMIT 20")
    last_t  = db(MONITOR_DB, "SELECT timestamp FROM alerts ORDER BY timestamp DESC LIMIT 1")
    last_ts = last_t[0]["timestamp"] if last_t else None
    state   = db(MONITOR_DB, "SELECT key, value FROM state WHERE key LIKE \'last_ips_%\'")
    ip_rows = [{"target": r["key"][len("last_ips_"):], "ips": r["value"]} for r in state]
    return {"total": total, "snapshots": snaps_n, "recent_alerts": recent,
            "last_ts": last_ts, "ips": ip_rows}

def get_investigations():
    rows = db(INVHUB_DB, """
        SELECT id, inv_id, title, status, risk_score, threat_class, opened_at
        FROM investigations ORDER BY risk_score DESC
    """)
    # normalise field names for the frontend
    for r in rows:
        r["category"]   = r.pop("threat_class", "")
        r["created_at"] = r.pop("opened_at", "")
        r["updated_at"] = r.get("created_at", "")
    return rows

def get_inv_detail(inv_id):
    # inv_id is the text identifier (e.g. INV-001)
    inv   = db(INVHUB_DB, "SELECT * FROM investigations WHERE inv_id=?", (inv_id,))
    if not inv:
        return {"investigation": {}, "timeline": [], "evidence": [], "targets": [], "notes": []}
    row_id = inv[0]["id"]

    tl = db(INVHUB_DB, """
        SELECT id, event_type, description, occurred_at, evidence_id
        FROM timeline_events WHERE inv_id=? ORDER BY occurred_at DESC LIMIT 50
    """, (row_id,))
    # normalise for frontend
    for e in tl:
        e["event"]      = e.pop("description", "")
        e["event_time"] = e.pop("occurred_at", "")
        e["detail"]     = ""

    evid = db(INVHUB_DB, """
        SELECT id, filename, type, description, sha256, integrity_status, ingested_at
        FROM evidence WHERE inv_id=? ORDER BY ingested_at DESC LIMIT 30
    """, (row_id,))
    for e in evid:
        e["title"]         = e.get("filename", "")
        e["evidence_type"] = e.pop("type", "")
        e["notes"]         = e.pop("description", "")
        e["collected_at"]  = e.pop("ingested_at", "")

    tgts = db(INVHUB_DB, """
        SELECT t.id, t.type, t.value, t.description, it.role, t.created_at
        FROM targets t
        JOIN inv_targets it ON it.target_id = t.id
        WHERE it.inv_id=? ORDER BY t.created_at DESC LIMIT 30
    """, (row_id,))
    for t in tgts:
        t["target_type"] = t.pop("type", "")
        t["added_at"]    = t.pop("created_at", "")

    notes = db(INVHUB_DB, """
        SELECT id, content_md, tag, created_at
        FROM case_notes WHERE inv_id=? ORDER BY created_at DESC LIMIT 20
    """, (row_id,))
    for n in notes:
        n["content"] = n.pop("content_md", "")

    # attach normalised fields to investigation row
    inv_out = dict(inv[0])
    inv_out["category"]   = inv_out.pop("threat_class", "")
    inv_out["created_at"] = inv_out.pop("opened_at", "")

    return {"investigation": inv_out, "timeline": tl,
            "evidence": evid, "targets": tgts, "notes": notes}

def get_shenron():
    data = {"layers": 0, "payloads": 0, "coverage": 0, "health": []}
    # layer count from manifest JSON
    manifest = SHENRON_DIR / "shenron_manifest.json"
    if manifest.exists():
        try:
            m = json.loads(manifest.read_text())
            layers_list = m.get("layers", [])
            data["layers"]   = m.get("total_layers", len(layers_list))
            summary = m.get("summary", {})
            data["layers"]   = summary.get("total_canonical", data["layers"])
            data["payloads"] = summary.get("total_variants", summary.get("total_payloads", 0))
            data["coverage"] = summary.get("detection_coverage", m.get("detection_coverage", 0))
            data["by_category"] = summary.get("by_category", {})
        except: pass
    # layer count fallback from --list
    if data["layers"] == 0:
        try:
            r = subprocess.run(
                ["python3", str(SHENRON_DIR / "shenron.py"), "--list"],
                capture_output=True, text=True, timeout=15, cwd=str(SHENRON_DIR)
            )
            count = sum(1 for line in r.stdout.splitlines() if line.strip() and not line.strip().startswith(("LAYER","---","SHENRON")))
            data["layers"] = count
        except: pass
    # health from --validate-all-assumptions
    # format: "  [?] category    reason" or "[✓] category" or "[✗] category"
    try:
        r = subprocess.run(
            ["python3", str(SHENRON_DIR / "shenron.py"), "--validate-all-assumptions"],
            capture_output=True, text=True, timeout=30, cwd=str(SHENRON_DIR)
        )
        for line in (r.stdout + r.stderr).splitlines():
            stripped = line.strip()
            if stripped.startswith("[✓]"):
                name = stripped[3:].strip().split()[0]
                data["health"].append({"name": name, "status": "pass"})
            elif stripped.startswith("[✗]"):
                name = stripped[3:].strip().split()[0]
                data["health"].append({"name": name, "status": "fail"})
            elif stripped.startswith("[?]"):
                name = stripped[3:].strip().split()[0]
                skip = {'verdict:','verdict','checked_at','categories','rerun','shenron'}
                if name and name.lower() not in skip and not name.startswith('=') and not name.startswith('-'):
                    data["health"].append({"name": name, "status": "unknown"})
    except: pass
    return data

def get_canary():
    state = db(MONITOR_DB, "SELECT key, value FROM state")
    s = {r["key"]: r["value"] for r in state}
    return {
        "crx_version":        s.get("last_ext_version", "—"),
        "crx_checked":        s.get("last_ext_check", "—"),
        "operator_repos":     s.get("operator_repos", "—"),
        "operator_followers": s.get("operator_followers", "—"),
        "_raw": s,
    }

def get_devto_followers():
    if not DEVTO_KEY:
        return {"followers": "—", "username": "gnomeman4201"}
    try:
        req = urllib.request.Request(
            "https://dev.to/api/users/by_username?url=gnomeman4201",
            headers={"api-key": DEVTO_KEY, "User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        followers = data.get("followers_count", data.get("follower_count", data.get("following_count", "—")))
        return {"followers": followers, "username": "gnomeman4201"}
    except:
        return {"followers": "—", "username": "gnomeman4201"}

def get_nightly_log(n=10):
    try:
        lines = NIGHTLY_LOG.read_text().strip().splitlines()
        return lines[-n:]
    except:
        return []

# ── enrichment ────────────────────────────────────────────────────────────────
def enrich_target(target):
    results = {}
    # whois via shell
    try:
        r = subprocess.run(["whois", target], capture_output=True, text=True, timeout=10)
        results["whois"] = r.stdout[:2000]
    except:
        results["whois"] = "whois unavailable"
    # DNS
    try:
        import socket
        results["dns_a"] = socket.gethostbyname_ex(target)[2]
    except:
        results["dns_a"] = []
    # dig TXT
    try:
        r = subprocess.run(["dig", "+short", "TXT", target], capture_output=True, text=True, timeout=5)
        results["dns_txt"] = r.stdout.strip().splitlines()
    except:
        results["dns_txt"] = []
    # VT via API if key present
    vt_key = os.environ.get("VT_API_KEY", "")
    if vt_key:
        try:
            req = urllib.request.Request(
                f"https://www.virustotal.com/api/v3/domains/{target}",
                headers={"x-apikey": vt_key, "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                vt = json.loads(resp.read())
            stats = vt.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            results["virustotal"] = stats
        except Exception as e:
            results["virustotal"] = {"error": str(e)}
    else:
        results["virustotal"] = {"note": "VT_API_KEY not set"}
    results["enriched_at"] = now_iso()
    return results

# ── HTML ──────────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>gnome // mission control</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Share+Tech+Mono&display=swap');

  :root {
    --bg:      #0a0c0a;
    --bg2:     #0f120f;
    --bg3:     #141814;
    --border:  #1e2a1e;
    --border2: #2a3d2a;
    --green:   #39ff7a;
    --green2:  #22c55e;
    --green3:  #16a34a;
    --dim:     #4a6650;
    --dimmer:  #2d3e2d;
    --red:     #ff4444;
    --yellow:  #f5c518;
    --orange:  #ff8c00;
    --blue:    #4db8ff;
    --text:    #c8e6c9;
    --text2:   #7a9e7a;
    --text3:   #4a6650;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* scanline overlay */
  body::before {
    content: '';
    position: fixed; inset: 0; z-index: 9999;
    background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.04) 2px, rgba(0,0,0,0.04) 4px);
    pointer-events: none;
  }

  header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 20px;
    border-bottom: 1px solid var(--border2);
    background: var(--bg2);
    position: sticky; top: 0; z-index: 100;
  }
  .logo { font-family: 'Share Tech Mono'; font-size: 15px; color: var(--green); letter-spacing: 2px; }
  .logo span { color: var(--text3); }
  .status-bar { display: flex; align-items: center; gap: 16px; color: var(--text2); font-size: 10px; }
  .live-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--green); 
              box-shadow: 0 0 8px var(--green); animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.4; } }
  #clock { color: var(--green2); }
  .refresh-btn {
    background: none; border: 1px solid var(--border2); color: var(--text2);
    padding: 3px 10px; cursor: pointer; font-family: inherit; font-size: 10px;
    transition: all .2s;
  }
  .refresh-btn:hover { border-color: var(--green3); color: var(--green); }

  .grid {
    display: grid;
    grid-template-columns: 280px 1fr 220px;
    grid-template-rows: auto auto;
    gap: 1px;
    background: var(--border);
    min-height: calc(100vh - 41px);
  }

  .panel {
    background: var(--bg2);
    padding: 14px;
    display: flex; flex-direction: column; gap: 10px;
  }
  .panel-full { grid-column: 1 / -1; }
  .panel-left  { grid-column: 1; }
  .panel-mid   { grid-column: 2; }
  .panel-right { grid-column: 3; }

  .section-label {
    font-size: 9px; letter-spacing: 3px; color: var(--dim);
    text-transform: uppercase; padding-bottom: 8px;
    border-bottom: 1px solid var(--border); margin-bottom: 4px;
    display: flex; align-items: center; justify-content: space-between;
  }
  .section-label .badge {
    background: var(--green3); color: #000; font-size: 8px;
    padding: 1px 6px; letter-spacing: 1px;
  }
  .section-label .badge.orange { background: var(--orange); }
  .section-label .badge.red    { background: var(--red); }

  /* stat blocks */
  .stat-row { display: flex; gap: 8px; }
  .stat {
    flex: 1; background: var(--bg3); border: 1px solid var(--border);
    padding: 8px 10px;
  }
  .stat-label { font-size: 8px; color: var(--text3); letter-spacing: 2px; margin-bottom: 4px; }
  .stat-val { font-size: 22px; color: var(--green); font-weight: 700; line-height: 1; }
  .stat-sub { font-size: 9px; color: var(--text3); margin-top: 3px; }

  /* IP tags */
  .ip-group { margin-bottom: 8px; }
  .ip-label { font-size: 9px; color: var(--text3); margin-bottom: 4px; }
  .ip-tags { display: flex; flex-wrap: wrap; gap: 4px; }
  .ip-tag {
    background: var(--bg3); border: 1px solid var(--green3);
    color: var(--green2); padding: 2px 8px; font-size: 10px;
    cursor: pointer; transition: all .15s;
  }
  .ip-tag:hover { background: var(--green3); color: #000; }

  /* alert list */
  .alert-list { display: flex; flex-direction: column; gap: 2px; max-height: 220px; overflow-y: auto; }
  .alert-item {
    display: grid; grid-template-columns: 130px 100px 1fr auto;
    gap: 8px; padding: 5px 8px; background: var(--bg3);
    border-left: 2px solid transparent; align-items: center;
    transition: all .15s;
  }
  .alert-item:hover { border-left-color: var(--green3); background: var(--bg); }
  .alert-ts   { color: var(--text3); font-size: 9px; }
  .alert-type { color: var(--orange); font-size: 9px; letter-spacing: 1px; }
  .alert-val  { color: var(--text2); font-size: 9px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .triage-btns { display: flex; gap: 3px; opacity: 0; transition: opacity .15s; }
  .alert-item:hover .triage-btns { opacity: 1; }
  .tbtn {
    border: none; cursor: pointer; padding: 2px 5px; font-family: inherit;
    font-size: 8px; letter-spacing: 1px; transition: all .15s;
  }
  .tbtn-dismiss { background: var(--dimmer); color: var(--dim); }
  .tbtn-dismiss:hover { background: var(--text3); color: #000; }
  .tbtn-escalate { background: #3d1a00; color: var(--orange); }
  .tbtn-escalate:hover { background: var(--orange); color: #000; }
  .tbtn-tag { background: #001a3d; color: var(--blue); }
  .tbtn-tag:hover { background: var(--blue); color: #000; }

  /* investigations table */
  .inv-table { width: 100%; border-collapse: collapse; }
  .inv-table thead th {
    font-size: 8px; letter-spacing: 2px; color: var(--dim); text-align: left;
    padding: 4px 8px; border-bottom: 1px solid var(--border2); font-weight: 400;
  }
  .inv-row {
    cursor: pointer; transition: all .15s;
    border-bottom: 1px solid var(--border);
  }
  .inv-row:hover { background: var(--bg3); }
  .inv-row td { padding: 8px; vertical-align: middle; }
  .inv-id { color: var(--text3); font-size: 10px; }
  .risk-badge {
    display: inline-block; padding: 2px 6px; font-size: 9px; font-weight: 700;
    min-width: 32px; text-align: center;
  }
  .risk-9,.risk-10 { background: var(--red);    color: #000; }
  .risk-7,.risk-8  { background: var(--orange);  color: #000; }
  .risk-5,.risk-6  { background: var(--yellow);  color: #000; }
  .risk-3,.risk-4  { background: var(--green3);  color: #000; }
  .risk-1,.risk-2  { background: var(--dimmer);  color: var(--dim); }
  .status-chip {
    display: inline-block; padding: 2px 6px; font-size: 8px; letter-spacing: 1px;
    border: 1px solid;
  }
  .status-active    { border-color: var(--green3); color: var(--green2); }
  .status-pending   { border-color: var(--yellow);  color: var(--yellow); }
  .status-disclosed { border-color: var(--dim);    color: var(--dim); }
  .status-archived  { border-color: var(--dimmer); color: var(--dimmer); }
  .inv-title { color: var(--text); font-size: 10px; }
  .inv-cat   { color: var(--text3); font-size: 9px; }
  .inv-arrow { color: var(--dim); font-size: 10px; transition: color .15s; }
  .inv-row:hover .inv-arrow { color: var(--green); }

  /* shenron */
  .health-grid { display: flex; flex-direction: column; gap: 5px; }
  .health-item {
    display: flex; align-items: center; justify-content: space-between;
    padding: 5px 8px; background: var(--bg3);
  }
  .health-name { color: var(--text2); font-size: 10px; }
  .health-dot { width: 8px; height: 8px; border-radius: 50%; }
  .health-dot.pass { background: var(--green); box-shadow: 0 0 6px var(--green); }
  .health-dot.fail { background: var(--red);   box-shadow: 0 0 6px var(--red); }
  .health-dot.unknown { background: var(--dim); }

  .shenron-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .shenron-stat { background: var(--bg3); padding: 7px; }
  .shenron-stat-label { font-size: 8px; color: var(--text3); letter-spacing: 1px; }
  .shenron-stat-val   { font-size: 16px; color: var(--green); font-weight: 700; margin-top: 2px; }

  /* canary */
  .canary-row { display: flex; justify-content: space-between; padding: 5px 0;
                border-bottom: 1px solid var(--border); }
  .canary-key { color: var(--text3); font-size: 9px; }
  .canary-val { color: var(--green2); font-size: 9px; }

  /* nightly log */
  .log-lines { font-size: 9px; color: var(--text3); display: flex; flex-direction: column; gap: 2px; max-height: 120px; overflow-y: auto; }
  .log-line { padding: 2px 4px; }
  .log-line:hover { background: var(--bg3); color: var(--text2); }

  /* publishing */
  .pub-followers { font-size: 36px; color: var(--green); font-weight: 700; line-height: 1; }
  .pub-sub { font-size: 9px; color: var(--text3); margin-top: 3px; }

  /* ── DRAWER ──────────────────────────────────────────────────────────── */
  .drawer-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,.7);
    z-index: 200; opacity: 0; pointer-events: none; transition: opacity .25s;
  }
  .drawer-overlay.open { opacity: 1; pointer-events: all; }
  .drawer {
    position: fixed; right: 0; top: 0; bottom: 0; width: 680px;
    background: var(--bg2); border-left: 1px solid var(--border2);
    z-index: 201; display: flex; flex-direction: column;
    transform: translateX(100%); transition: transform .25s cubic-bezier(.4,0,.2,1);
    overflow: hidden;
  }
  .drawer.open { transform: translateX(0); }
  .drawer-header {
    padding: 14px 18px; border-bottom: 1px solid var(--border2);
    display: flex; align-items: center; justify-content: space-between;
    background: var(--bg3); flex-shrink: 0;
  }
  .drawer-title { font-family: 'Share Tech Mono'; font-size: 13px; color: var(--green); }
  .drawer-close {
    background: none; border: 1px solid var(--border2); color: var(--text3);
    width: 26px; height: 26px; cursor: pointer; font-size: 14px;
    display: flex; align-items: center; justify-content: center;
    font-family: inherit; transition: all .15s;
  }
  .drawer-close:hover { border-color: var(--red); color: var(--red); }
  .drawer-tabs { display: flex; border-bottom: 1px solid var(--border); flex-shrink: 0; }
  .dtab {
    padding: 8px 16px; font-size: 9px; letter-spacing: 2px; color: var(--text3);
    cursor: pointer; border-bottom: 2px solid transparent; transition: all .15s;
    background: none; border-top: none; border-left: none; border-right: none;
    font-family: inherit; text-transform: uppercase;
  }
  .dtab.active { color: var(--green); border-bottom-color: var(--green); }
  .dtab:hover:not(.active) { color: var(--text2); }
  .drawer-body { flex: 1; overflow-y: auto; padding: 16px 18px; }

  .drawer-pane { display: none; }
  .drawer-pane.active { display: block; }

  /* timeline in drawer */
  .tl-item { display: flex; gap: 12px; margin-bottom: 12px; }
  .tl-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green3);
             margin-top: 3px; flex-shrink: 0; box-shadow: 0 0 4px var(--green3); }
  .tl-content { flex: 1; }
  .tl-time  { font-size: 8px; color: var(--text3); margin-bottom: 2px; }
  .tl-event { font-size: 10px; color: var(--text); }
  .tl-detail { font-size: 9px; color: var(--text2); margin-top: 2px; }

  /* evidence / targets list */
  .ev-item { background: var(--bg3); border: 1px solid var(--border); padding: 8px; margin-bottom: 6px; }
  .ev-title { font-size: 10px; color: var(--green2); margin-bottom: 3px; }
  .ev-meta  { font-size: 8px; color: var(--text3); }

  /* action forms */
  .action-section { margin-bottom: 20px; }
  .action-label { font-size: 9px; letter-spacing: 2px; color: var(--dim); text-transform: uppercase;
                  margin-bottom: 8px; padding-bottom: 5px; border-bottom: 1px solid var(--border); }
  .form-row { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
  .form-input {
    background: var(--bg3); border: 1px solid var(--border2); color: var(--text);
    padding: 6px 10px; font-family: inherit; font-size: 10px; flex: 1; min-width: 120px;
    outline: none; transition: border .15s;
  }
  .form-input:focus { border-color: var(--green3); }
  .form-select {
    background: var(--bg3); border: 1px solid var(--border2); color: var(--text);
    padding: 6px 10px; font-family: inherit; font-size: 10px;
    outline: none; cursor: pointer;
  }
  .form-textarea {
    background: var(--bg3); border: 1px solid var(--border2); color: var(--text);
    padding: 6px 10px; font-family: inherit; font-size: 10px; width: 100%;
    resize: vertical; min-height: 70px; outline: none; transition: border .15s;
  }
  .form-textarea:focus { border-color: var(--green3); }
  .btn {
    background: var(--green3); color: #000; border: none;
    padding: 6px 14px; font-family: inherit; font-size: 9px;
    letter-spacing: 2px; text-transform: uppercase; cursor: pointer; transition: all .15s;
  }
  .btn:hover { background: var(--green2); }
  .btn-ghost { background: none; border: 1px solid var(--border2); color: var(--text2); }
  .btn-ghost:hover { border-color: var(--green3); color: var(--green); }
  .btn-danger { background: #3d0000; color: var(--red); border: 1px solid #600; }
  .btn-danger:hover { background: var(--red); color: #000; }

  .form-msg { font-size: 9px; padding: 5px 8px; margin-top: 6px; }
  .form-msg.ok  { background: #0a2d0a; color: var(--green2); border-left: 2px solid var(--green3); }
  .form-msg.err { background: #2d0a0a; color: var(--red);    border-left: 2px solid var(--red); }

  /* ── ENRICHMENT PANEL ─────────────────────────────────────────────── */
  .enrich-panel {
    position: fixed; left: 0; top: 0; bottom: 0; width: 560px;
    background: var(--bg2); border-right: 1px solid var(--border2);
    z-index: 201; display: flex; flex-direction: column;
    transform: translateX(-100%); transition: transform .25s cubic-bezier(.4,0,.2,1);
    overflow: hidden;
  }
  .enrich-panel.open { transform: translateX(0); }
  .enrich-header {
    padding: 14px 18px; border-bottom: 1px solid var(--border2);
    background: var(--bg3); display: flex; align-items: center; justify-content: space-between;
    flex-shrink: 0;
  }
  .enrich-title { font-family: 'Share Tech Mono'; font-size: 13px; color: var(--blue); }
  .enrich-body { flex: 1; overflow-y: auto; padding: 16px 18px; }
  .enrich-results { font-size: 9px; color: var(--text2); }
  .enrich-section { margin-bottom: 14px; }
  .enrich-section-label { color: var(--dim); letter-spacing: 2px; font-size: 8px; margin-bottom: 6px; }
  .enrich-code { background: var(--bg3); border: 1px solid var(--border); padding: 8px; 
                 white-space: pre-wrap; word-break: break-all; font-size: 9px; color: var(--text); 
                 max-height: 200px; overflow-y: auto; }
  .enrich-spinner { color: var(--blue); font-size: 11px; }

  /* scrollbar styling */
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: var(--border2); }
  ::-webkit-scrollbar-thumb:hover { background: var(--dim); }

  /* toast */
  .toast {
    position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
    background: var(--bg3); border: 1px solid var(--green3); color: var(--green2);
    padding: 8px 18px; font-size: 10px; z-index: 9998;
    opacity: 0; transition: opacity .3s; pointer-events: none;
  }
  .toast.show { opacity: 1; }
  .toast.err { border-color: var(--red); color: var(--red); }

  /* loading skeleton */
  .skeleton { background: var(--bg3); height: 12px; border-radius: 2px;
              animation: shimmer 1.5s infinite; margin-bottom: 4px; }
  @keyframes shimmer { 0%,100% { opacity:.3; } 50% { opacity:.7; } }

  .theme-btn { background:none;border:1px solid var(--border2);color:var(--text2);padding:3px 10px;cursor:pointer;font-family:inherit;font-size:10px;transition:all .2s;letter-spacing:1px; }
  .theme-btn:hover { border-color:var(--green3);color:var(--green); }
  .theme-popover { position:fixed;top:41px;right:10px;z-index:500;background:var(--bg3);border:1px solid var(--border2);padding:14px;width:260px;display:none;box-shadow:0 8px 32px rgba(0,0,0,.6); }
  .theme-popover.open { display:block; }
  .theme-popover-title { font-size:8px;letter-spacing:3px;color:var(--dim);text-transform:uppercase;margin-bottom:10px; }
  .theme-presets { display:flex;flex-wrap:wrap;gap:5px;margin-bottom:12px; }
  .preset-swatch { width:28px;height:28px;border-radius:2px;cursor:pointer;border:2px solid transparent;transition:all .15s; }
  .preset-swatch.active { border-color:#fff; }
  .preset-swatch:hover { transform:scale(1.1); }
  .slider-row { margin-bottom:8px; }
  .slider-label { font-size:8px;color:var(--text3);letter-spacing:2px;margin-bottom:5px;display:flex;justify-content:space-between; }
  .theme-slider { -webkit-appearance:none;appearance:none;width:100%;height:4px;outline:none;cursor:pointer;border-radius:2px; }
  .theme-slider::-webkit-slider-thumb { -webkit-appearance:none;width:12px;height:12px;border-radius:50%;background:var(--green);cursor:pointer;border:2px solid var(--bg); }
  #hue-slider { background:linear-gradient(to right,hsl(0,80%,45%),hsl(60,80%,45%),hsl(120,80%,45%),hsl(180,80%,45%),hsl(240,80%,45%),hsl(300,80%,45%),hsl(360,80%,45%)); }
</style>
</head>
<body>

<header>
  <div class="logo">gnome <span>//</span> mission control</div>
  <div class="status-bar">
    <div class="live-dot"></div>
    <span id="clock">—</span>
    <span id="last-refresh" style="color:var(--text3)">loading...</span>
    <button class="refresh-btn" onclick="loadAll()">refresh</button>
    <button class="theme-btn" onclick="toggleThemePopover()" id="theme-toggle-btn">◐ theme</button>
    <button class="refresh-btn" onclick="openEnrich()" style="color:var(--blue);border-color:#1a3d5c">⬡ enrich</button>
  </div>
</header>
<div class="theme-popover" id="theme-popover">
  <div class="theme-popover-title">color theme</div>
  <div class="theme-presets" id="theme-presets"></div>
  <div class="slider-row"><div class="slider-label"><span>HUE</span><span id="hue-val">120°</span></div><input type="range" class="theme-slider" id="hue-slider" min="0" max="360" value="120"></div>
  <div class="slider-row"><div class="slider-label"><span>SATURATION</span><span id="sat-val">100%</span></div><input type="range" class="theme-slider" id="sat-slider" min="20" max="100" value="100"></div>
  <div class="slider-row"><div class="slider-label"><span>BRIGHTNESS</span><span id="bright-val">60%</span></div><input type="range" class="theme-slider" id="bright-slider" min="30" max="90" value="60"></div>
  <div style="margin-top:10px;display:flex;gap:6px"><button class="refresh-btn" onclick="resetTheme()" style="flex:1">reset</button><button class="refresh-btn" onclick="toggleThemePopover()" style="flex:1">close</button></div>
</div>

<div class="grid">

  <!-- LEFT: monitor + publishing -->
  <div class="panel panel-left">
    <div class="section-label">badBANANA monitor <span class="badge" id="monitor-badge">active</span></div>
    
    <div class="stat-row">
      <div class="stat">
        <div class="stat-label">total alerts</div>
        <div class="stat-val" id="total-alerts">—</div>
        <div class="stat-sub" id="alerts-ago">—</div>
      </div>
      <div class="stat">
        <div class="stat-label">infra snapshots</div>
        <div class="stat-val" id="total-snaps">—</div>
        <div class="stat-sub">dns + headers</div>
      </div>
    </div>

    <div id="ip-groups"></div>

    <div class="section-label" style="margin-top:4px">recent alerts</div>
    <div class="alert-list" id="alert-list"></div>

    <!-- publishing -->
    <div class="section-label" style="margin-top:8px">publishing / reach</div>
    <div class="stat-row">
      <div class="stat">
        <div class="stat-label">dev.to followers</div>
        <div class="pub-followers" id="devto-followers">—</div>
        <div class="pub-sub" id="devto-user">gnomeman4201</div>
      </div>
    </div>

    <!-- nightly log -->
    <div class="section-label" style="margin-top:4px">nightly log</div>
    <div class="log-lines" id="nightly-log"></div>
  </div>

  <!-- MID: investigations -->
  <div class="panel panel-mid">
    <div class="section-label">
      investigations
      <span class="badge orange" id="inv-active-badge">— active</span>
    </div>
    <div style="display:flex;gap:16px;margin-bottom:10px;font-size:9px;color:var(--text3)">
      <span>total: <span id="inv-total" style="color:var(--green2)">—</span></span>
      <span>timeline events: <span id="inv-events" style="color:var(--green2)">—</span></span>
    </div>

    <table class="inv-table">
      <thead>
        <tr>
          <th>id</th><th>risk</th><th>status</th><th>title</th><th>category</th><th></th>
        </tr>
      </thead>
      <tbody id="inv-tbody"></tbody>
    </table>
  </div>

  <!-- RIGHT: SHENRON + canary -->
  <div class="panel panel-right">
    <div class="section-label">SHENRON</div>
    <div class="shenron-stats" id="shenron-stats"></div>
    <div class="section-label" style="margin-top:8px">health checks</div>
    <div class="health-grid" id="shenron-health"></div>

    <div class="section-label" style="margin-top:12px">canary watchdogs</div>
    <div id="canary-rows"></div>

    <!-- quick enrichment from right panel -->
    <div class="section-label" style="margin-top:12px">quick enrich</div>
    <div class="form-row" style="flex-direction:column">
      <input class="form-input" id="quick-enrich-input" placeholder="domain or IP…" style="width:100%">
      <button class="btn" style="width:100%;margin-top:4px" onclick="quickEnrich()">⬡ run enrichment</button>
    </div>
  </div>

</div>

<!-- ── INVESTIGATION DRAWER ──────────────────────────────────────────────── -->
<div class="drawer-overlay" id="drawer-overlay" onclick="closeDrawer()"></div>
<div class="drawer" id="inv-drawer">
  <div class="drawer-header">
    <div>
      <div class="drawer-title" id="drawer-inv-id">—</div>
      <div style="font-size:9px;color:var(--text2);margin-top:3px" id="drawer-inv-title">—</div>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <div id="drawer-risk-badge"></div>
      <div id="drawer-status-chip"></div>
      <button class="drawer-close" onclick="closeDrawer()">×</button>
    </div>
  </div>
  <div class="drawer-tabs">
    <button class="dtab active" onclick="switchTab('timeline')">timeline</button>
    <button class="dtab" onclick="switchTab('evidence')">evidence</button>
    <button class="dtab" onclick="switchTab('targets')">targets</button>
    <button class="dtab" onclick="switchTab('actions')">actions</button>
  </div>
  <div class="drawer-body">
    <!-- timeline -->
    <div class="drawer-pane active" id="pane-timeline">
      <div id="timeline-list"><div class="skeleton" style="width:80%"></div><div class="skeleton" style="width:60%"></div></div>
    </div>
    <!-- evidence -->
    <div class="drawer-pane" id="pane-evidence">
      <div id="evidence-list"></div>
    </div>
    <!-- targets -->
    <div class="drawer-pane" id="pane-targets">
      <div id="targets-list"></div>
    </div>
    <!-- actions -->
    <div class="drawer-pane" id="pane-actions">
      <!-- update investigation -->
      <div class="action-section">
        <div class="action-label">update investigation</div>
        <div class="form-row">
          <select class="form-select" id="action-status">
            <option value="">— status —</option>
            <option value="active">active</option>
            <option value="pending">pending</option>
            <option value="disclosed">disclosed</option>
            <option value="archived">archived</option>
          </select>
          <input class="form-input" id="action-risk" type="number" min="1" max="10" placeholder="risk score (1-10)">
          <button class="btn" onclick="submitUpdateInv()">update</button>
        </div>
        <div id="update-inv-msg"></div>
      </div>

      <!-- add note -->
      <div class="action-section">
        <div class="action-label">add note</div>
        <textarea class="form-textarea" id="action-note" placeholder="note content…"></textarea>
        <div class="form-row" style="margin-top:6px">
          <button class="btn" onclick="submitNote()">save note</button>
        </div>
        <div id="note-msg"></div>
      </div>

      <!-- log timeline event -->
      <div class="action-section">
        <div class="action-label">log timeline event</div>
        <div class="form-row">
          <input class="form-input" id="action-tl-event" placeholder="event description">
          <select class="form-select" id="action-tl-type">
            <option value="discovery">discovery</option>
            <option value="analysis">analysis</option>
            <option value="disclosure">disclosure</option>
            <option value="infrastructure">infrastructure</option>
            <option value="other">other</option>
          </select>
        </div>
        <textarea class="form-textarea" id="action-tl-detail" placeholder="detail / notes…" style="min-height:50px"></textarea>
        <div class="form-row" style="margin-top:6px">
          <button class="btn" onclick="submitTimeline()">log event</button>
        </div>
        <div id="tl-msg"></div>
      </div>

      <!-- add evidence -->
      <div class="action-section">
        <div class="action-label">add evidence</div>
        <div class="form-row">
          <input class="form-input" id="action-ev-title" placeholder="title / filename">
          <select class="form-select" id="action-ev-type">
            <option value="screenshot">screenshot</option>
            <option value="network_capture">network capture</option>
            <option value="source_code">source code</option>
            <option value="whois">whois</option>
            <option value="dns">dns</option>
            <option value="api_response">api response</option>
            <option value="other">other</option>
          </select>
        </div>
        <textarea class="form-textarea" id="action-ev-notes" placeholder="notes / path / content…" style="min-height:50px"></textarea>
        <div class="form-row" style="margin-top:6px">
          <button class="btn" onclick="submitEvidence()">log evidence</button>
        </div>
        <div id="ev-msg"></div>
      </div>
    </div>
  </div>
</div>

<!-- ── ENRICHMENT PANEL ───────────────────────────────────────────────────── -->
<div class="drawer-overlay" id="enrich-overlay" onclick="closeEnrich()"></div>
<div class="enrich-panel" id="enrich-panel">
  <div class="enrich-header">
    <div class="enrich-title">⬡ target enrichment</div>
    <button class="drawer-close" onclick="closeEnrich()">×</button>
  </div>
  <div class="enrich-body">
    <div class="form-row" style="margin-bottom:16px">
      <input class="form-input" id="enrich-input" placeholder="domain or IP address…">
      <button class="btn" style="background:#001a3d;color:var(--blue);border:1px solid #1a3d5c" onclick="runEnrich()">run</button>
    </div>
    <div id="enrich-results" class="enrich-results"></div>
  </div>
</div>

<!-- toast -->
<div class="toast" id="toast"></div>

<script>
let currentInvId = null;
let activeTab = 'timeline';
let autoRefreshTimer = null;

// ── clock ──────────────────────────────────────────────────────────────────
function updateClock() {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString('en-US', {hour12:false});
}
setInterval(updateClock, 1000); updateClock();

// ── toast ──────────────────────────────────────────────────────────────────
function toast(msg, err=false) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (err ? ' err' : '');
  setTimeout(() => t.className = 'toast', 2500);
}

// ── API helpers ────────────────────────────────────────────────────────────
async function api(path, method='GET', body=null) {
  const opts = { method, headers: {'Content-Type':'application/json'} };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  return r.json();
}

function ago(ts) {
  if (!ts) return '—';
  const d = new Date(ts), now = new Date();
  const s = Math.floor((now - d) / 1000);
  if (s < 60)  return s + 's ago';
  if (s < 3600) return Math.floor(s/60) + 'm ago';
  if (s < 86400) return Math.floor(s/3600) + 'h ago';
  return Math.floor(s/86400) + 'd ago';
}

// ── risk / status helpers ──────────────────────────────────────────────────
function riskBadge(score) {
  return `<span class="risk-badge risk-${score}">${score}/10</span>`;
}
function statusChip(status) {
  return `<span class="status-chip status-${status||'active'}">${status||'active'}</span>`;
}

// ── main data load ─────────────────────────────────────────────────────────
async function loadAll() {
  try {
    const d = await api('/api/dashboard');
    renderMonitor(d.monitor);
    renderInvestigations(d.investigations);
    renderShenron(d.shenron);
    renderCanary(d.canary);
    renderPublishing(d.publishing);
    renderNightlyLog(d.nightly_log);
    document.getElementById('last-refresh').textContent = 'updated ' + ago(new Date().toISOString());
  } catch(e) {
    toast('load failed: ' + e.message, true);
  }
}

function renderMonitor(m) {
  document.getElementById('total-alerts').textContent = m.total || '—';
  document.getElementById('total-snaps').textContent  = m.snapshots || '—';
  document.getElementById('alerts-ago').textContent   = ago(m.last_ts);

  // IP groups
  const ipg = document.getElementById('ip-groups');
  ipg.innerHTML = '';
  (m.ips || []).forEach(g => {
    const ips = (g.ips||'').split(',').filter(Boolean).filter((v,i,a)=>a.indexOf(v)===i).slice(0,4);
    if (!ips.length) return;
    ipg.innerHTML += `<div class="ip-group">
      <div class="ip-label">${g.target}</div>
      <div class="ip-tags">${ips.map(ip => `<span class="ip-tag" onclick="openEnrichWith('${ip}')">${ip}</span>`).join('')}</div>
    </div>`;
  });

  // alert list
  const al = document.getElementById('alert-list');
  al.innerHTML = (m.recent_alerts||[]).map((a,i) => `
    <div class="alert-item" id="alert-${i}">
      <span class="alert-ts">${(a.created_at||'').replace('T',' ').slice(0,19)}</span>
      <span class="alert-type">${a.alert_type||''}</span>
      <span class="alert-val">${(a.details||a.target||'')}</span>
      <div class="triage-btns">
        <button class="tbtn tbtn-dismiss"  onclick="triageAlert(${i},'dismiss')">dismiss</button>
        <button class="tbtn tbtn-escalate" onclick="triageAlert(${i},'escalate')">escalate</button>
        <button class="tbtn tbtn-tag"      onclick="triageAlert(${i},'tag')">tag</button>
      </div>
    </div>`).join('');
}

function renderInvestigations(invs) {
  const active = (invs||[]).filter(i => i.status === 'active').length;
  document.getElementById('inv-active-badge').textContent = active + ' active';
  document.getElementById('inv-total').textContent = (invs||[]).length;

  const tbody = document.getElementById('inv-tbody');
  tbody.innerHTML = (invs||[]).map(inv => `
    <tr class="inv-row" onclick="openInv('${inv.inv_id||inv.id}')">
      <td class="inv-id">${inv.inv_id||inv.id}</td>
      <td>${riskBadge(inv.risk_score||0)}</td>
      <td>${statusChip(inv.status)}</td>
      <td class="inv-title">${inv.title||'—'}</td>
      <td class="inv-cat">${inv.category||''}</td>
      <td class="inv-arrow">›</td>
    </tr>`).join('');
}

function renderShenron(s) {
  document.getElementById('shenron-stats').innerHTML = `
    <div class="shenron-stat"><div class="shenron-stat-label">LAYERS</div><div class="shenron-stat-val">${s.layers||0}</div></div>
    <div class="shenron-stat"><div class="shenron-stat-label">PAYLOADS</div><div class="shenron-stat-val">${s.payloads||0}</div></div>
  `;
  const hg = document.getElementById('shenron-health');
  if ((s.health||[]).length === 0) {
    hg.innerHTML = '<div style="color:var(--text3);font-size:9px">no health data</div>';
    return;
  }
  hg.innerHTML = s.health.map(h => `
    <div class="health-item">
      <span class="health-name">${h.name}</span>
      <span class="health-dot ${h.status}"></span>
    </div>`).join('');
}

function renderCanary(c) {
  document.getElementById('canary-rows').innerHTML = `
    <div class="canary-row"><span class="canary-key">crx version</span><span class="canary-val">${c.crx_version||'—'}</span></div>
    <div class="canary-row"><span class="canary-key">crx last check</span><span class="canary-val">${(c.crx_checked||'—').slice(0,10)}</span></div>
    <div class="canary-row"><span class="canary-key">operator repos</span><span class="canary-val">${c.operator_repos||'—'}</span></div>
    <div class="canary-row"><span class="canary-key">operator followers</span><span class="canary-val">${c.operator_followers||'—'}</span></div>
  `;
}

function renderPublishing(p) {
  document.getElementById('devto-followers').textContent = p.followers||'—';
  document.getElementById('devto-user').textContent = p.username||'gnomeman4201';
}

function renderNightlyLog(lines) {
  document.getElementById('nightly-log').innerHTML = (lines||[]).map(l =>
    `<div class="log-line">${l}</div>`).join('');
}

// ── investigation drawer ───────────────────────────────────────────────────
async function openInv(invId) {
  currentInvId = invId;
  document.getElementById('drawer-inv-id').textContent = invId;
  document.getElementById('drawer-inv-title').textContent = 'loading…';
  document.getElementById('drawer-overlay').classList.add('open');
  document.getElementById('inv-drawer').classList.add('open');
  switchTab('timeline');
  await loadInvDetail(invId);
}

function closeDrawer() {
  document.getElementById('drawer-overlay').classList.remove('open');
  document.getElementById('inv-drawer').classList.remove('open');
  currentInvId = null;
}

async function loadInvDetail(invId) {
  try {
    const d = await api('/api/inv/' + encodeURIComponent(invId));
    const inv = d.investigation || {};
    document.getElementById('drawer-inv-id').textContent    = inv.inv_id || invId;
    document.getElementById('drawer-inv-title').textContent = inv.title || '—';
    document.getElementById('drawer-risk-badge').innerHTML  = riskBadge(inv.risk_score||0);
    document.getElementById('drawer-status-chip').innerHTML = statusChip(inv.status);

    // timeline
    const tl = document.getElementById('timeline-list');
    tl.innerHTML = (d.timeline||[]).length === 0
      ? '<div style="color:var(--text3);font-size:9px">no timeline events</div>'
      : (d.timeline||[]).map(e => `
          <div class="tl-item">
            <div class="tl-dot"></div>
            <div class="tl-content">
              <div class="tl-time">${(e.event_time||e.created_at||'').slice(0,19)} · ${e.event_type||''}</div>
              <div class="tl-event">${e.event||e.description||''}</div>
              ${e.detail ? `<div class="tl-detail">${e.detail}</div>` : ''}
            </div>
          </div>`).join('');

    // evidence
    document.getElementById('evidence-list').innerHTML = (d.evidence||[]).length === 0
      ? '<div style="color:var(--text3);font-size:9px">no evidence logged</div>'
      : (d.evidence||[]).map(e => `
          <div class="ev-item">
            <div class="ev-title">${e.title||e.filename||'—'}</div>
            <div class="ev-meta">${e.evidence_type||''} · ${(e.collected_at||e.created_at||'').slice(0,10)}</div>
            ${e.notes ? `<div style="font-size:9px;color:var(--text2);margin-top:4px">${e.notes}</div>` : ''}
          </div>`).join('');

    // targets
    document.getElementById('targets-list').innerHTML = (d.targets||[]).length === 0
      ? '<div style="color:var(--text3);font-size:9px">no targets logged</div>'
      : (d.targets||[]).map(t => `
          <div class="ev-item">
            <div class="ev-title" style="cursor:pointer" onclick="openEnrichWith('${t.value||t.target||''}')">
              ${t.value||t.target||'—'} <span style="color:var(--dim);font-size:8px">↗ enrich</span>
            </div>
            <div class="ev-meta">${t.target_type||''} · added ${(t.added_at||t.created_at||'').slice(0,10)}</div>
          </div>`).join('');
  } catch(e) {
    document.getElementById('timeline-list').innerHTML =
      `<div style="color:var(--red);font-size:9px">error: ${e.message}</div>`;
  }
}

function switchTab(name) {
  activeTab = name;
  document.querySelectorAll('.dtab').forEach((t,i) => {
    const tabs = ['timeline','evidence','targets','actions'];
    t.className = 'dtab' + (tabs[i]===name ? ' active' : '');
  });
  document.querySelectorAll('.drawer-pane').forEach(p => p.classList.remove('active'));
  document.getElementById('pane-' + name).classList.add('active');
}

// ── drawer action submitters ───────────────────────────────────────────────
async function submitUpdateInv() {
  if (!currentInvId) return;
  const status = document.getElementById('action-status').value;
  const risk   = parseInt(document.getElementById('action-risk').value) || null;
  const msg    = document.getElementById('update-inv-msg');
  try {
    const r = await api('/api/inv/update', 'POST', {inv_id: currentInvId, status, risk_score: risk});
    msg.innerHTML = `<div class="form-msg ok">updated successfully</div>`;
    await loadAll(); await loadInvDetail(currentInvId);
    toast('investigation updated');
  } catch(e) { msg.innerHTML = `<div class="form-msg err">${e.message}</div>`; }
}

async function submitNote() {
  if (!currentInvId) return;
  const note = document.getElementById('action-note').value.trim();
  if (!note) return;
  const msg = document.getElementById('note-msg');
  try {
    await api('/api/inv/note', 'POST', {inv_id: currentInvId, content: note});
    msg.innerHTML = `<div class="form-msg ok">note saved</div>`;
    document.getElementById('action-note').value = '';
    toast('note saved');
  } catch(e) { msg.innerHTML = `<div class="form-msg err">${e.message}</div>`; }
}

async function submitTimeline() {
  if (!currentInvId) return;
  const event  = document.getElementById('action-tl-event').value.trim();
  const type   = document.getElementById('action-tl-type').value;
  const detail = document.getElementById('action-tl-detail').value.trim();
  if (!event) return;
  const msg = document.getElementById('tl-msg');
  try {
    await api('/api/inv/timeline', 'POST', {inv_id: currentInvId, event, event_type: type, detail});
    msg.innerHTML = `<div class="form-msg ok">event logged</div>`;
    document.getElementById('action-tl-event').value  = '';
    document.getElementById('action-tl-detail').value = '';
    await loadInvDetail(currentInvId);
    toast('timeline event logged');
  } catch(e) { msg.innerHTML = `<div class="form-msg err">${e.message}</div>`; }
}

async function submitEvidence() {
  if (!currentInvId) return;
  const title = document.getElementById('action-ev-title').value.trim();
  const type  = document.getElementById('action-ev-type').value;
  const notes = document.getElementById('action-ev-notes').value.trim();
  if (!title) return;
  const msg = document.getElementById('ev-msg');
  try {
    await api('/api/inv/evidence', 'POST', {inv_id: currentInvId, title, evidence_type: type, notes});
    msg.innerHTML = `<div class="form-msg ok">evidence logged</div>`;
    document.getElementById('action-ev-title').value = '';
    document.getElementById('action-ev-notes').value = '';
    await loadInvDetail(currentInvId);
    toast('evidence logged');
  } catch(e) { msg.innerHTML = `<div class="form-msg err">${e.message}</div>`; }
}

// ── alert triage ───────────────────────────────────────────────────────────
async function triageAlert(idx, action) {
  const row = document.getElementById('alert-' + idx);
  const ts  = row?.querySelector('.alert-ts')?.textContent;
  const typ = row?.querySelector('.alert-type')?.textContent;
  try {
    await api('/api/alert/triage', 'POST', {idx, action, ts, alert_type: typ});
    if (action === 'dismiss') {
      row.style.opacity = '0.3';
      row.style.textDecoration = 'line-through';
    } else if (action === 'escalate') {
      row.style.borderLeftColor = 'var(--orange)';
      row.style.background = '#1a0a00';
    } else {
      row.style.borderLeftColor = 'var(--blue)';
    }
    toast(action + ' applied');
  } catch(e) { toast('triage failed: ' + e.message, true); }
}

// ── enrichment panel ───────────────────────────────────────────────────────
function openEnrich() {
  document.getElementById('enrich-overlay').classList.add('open');
  document.getElementById('enrich-panel').classList.add('open');
  document.getElementById('enrich-input').focus();
}

function openEnrichWith(target) {
  document.getElementById('enrich-input').value = target;
  document.getElementById('quick-enrich-input').value = target;
  openEnrich();
  runEnrich();
}

function closeEnrich() {
  document.getElementById('enrich-overlay').classList.remove('open');
  document.getElementById('enrich-panel').classList.remove('open');
}

function quickEnrich() {
  const t = document.getElementById('quick-enrich-input').value.trim();
  if (!t) return;
  document.getElementById('enrich-input').value = t;
  openEnrich();
  runEnrich();
}

async function runEnrich() {
  const target = document.getElementById('enrich-input').value.trim();
  if (!target) return;
  const res = document.getElementById('enrich-results');
  res.innerHTML = `<div class="enrich-spinner">⬡ enriching ${target}…</div>`;
  try {
    const d = await api('/api/enrich', 'POST', {target});
    let html = '';
    if (d.error) { res.innerHTML = `<div style="color:var(--red)">error: ${d.error}</div>`; return; }
    
    if (d.dns_a?.length) html += `
      <div class="enrich-section">
        <div class="enrich-section-label">A RECORDS</div>
        <div class="enrich-code">${d.dns_a.join('\n')}</div>
      </div>`;
    
    if (d.dns_txt?.length) html += `
      <div class="enrich-section">
        <div class="enrich-section-label">TXT RECORDS</div>
        <div class="enrich-code">${d.dns_txt.join('\n')}</div>
      </div>`;

    if (d.virustotal && !d.virustotal.note) html += `
      <div class="enrich-section">
        <div class="enrich-section-label">VIRUSTOTAL</div>
        <div class="enrich-code">${JSON.stringify(d.virustotal, null, 2)}</div>
      </div>`;

    if (d.whois) html += `
      <div class="enrich-section">
        <div class="enrich-section-label">WHOIS</div>
        <div class="enrich-code">${d.whois.substring(0,1500)}</div>
      </div>`;

    html += `<div style="color:var(--text3);font-size:8px;margin-top:10px">enriched at ${d.enriched_at}</div>`;
    res.innerHTML = html;
  } catch(e) {
    res.innerHTML = `<div style="color:var(--red)">error: ${e.message}</div>`;
  }
}

// enter key on enrich input
document.getElementById('enrich-input').addEventListener('keydown', e => { if(e.key==='Enter') runEnrich(); });
document.getElementById('quick-enrich-input').addEventListener('keydown', e => { if(e.key==='Enter') quickEnrich(); });


// THEME SYSTEM
const PRESETS=[{name:'terminal',hue:120,sat:100,bri:60},{name:'amber',hue:38,sat:100,bri:62},{name:'ice',hue:195,sat:90,bri:65},{name:'red',hue:0,sat:90,bri:55},{name:'violet',hue:270,sat:80,bri:65},{name:'ghost',hue:200,sat:20,bri:70},{name:'toxic',hue:80,sat:100,bri:65},{name:'solar',hue:55,sat:95,bri:68}];
function hslPalette(h,s,b){const p=(ls,lb)=>`hsl(${h},${Math.round(s*ls)}%,${Math.round(b*lb)}%)`;return{'--green':p(1,1),'--green2':p(.85,.85),'--green3':p(.75,.65),'--dim':p(.45,.5),'--dimmer':p(.3,.25),'--border2':p(.35,.2),'--border':p(.25,.12),'--text':p(.25,.9),'--text2':p(.35,.62),'--text3':p(.4,.42),'--bg3':`hsl(${h},10%,8%)`,'--bg2':`hsl(${h},10%,6%)`,'--bg':`hsl(${h},10%,4%)`};}
function applyTheme(h,s,b){const root=document.documentElement;Object.entries(hslPalette(h,s,b)).forEach(([k,v])=>root.style.setProperty(k,v));document.getElementById('hue-slider').value=h;document.getElementById('sat-slider').value=s;document.getElementById('bright-slider').value=b;document.getElementById('hue-val').textContent=h+'°';document.getElementById('sat-val').textContent=s+'%';document.getElementById('bright-val').textContent=b+'%';document.querySelectorAll('.preset-swatch').forEach(sw=>sw.classList.toggle('active',+sw.dataset.h===h&&+sw.dataset.s===s&&+sw.dataset.b===b));try{localStorage.setItem('gnome_theme',JSON.stringify({h,s,b}));}catch(e){}}
function loadPersistedTheme(){try{const t=JSON.parse(localStorage.getItem('gnome_theme'));if(t&&t.h!=null){applyTheme(t.h,t.s,t.b);return;}}catch(e){}applyTheme(120,100,60);}
function resetTheme(){applyTheme(120,100,60);}
function buildPresets(){document.getElementById('theme-presets').innerHTML=PRESETS.map(p=>`<div class="preset-swatch" title="${p.name}" style="background:hsl(${p.hue},${p.sat}%,${Math.round(p.bri*.8)}%)" data-h="${p.hue}" data-s="${p.sat}" data-b="${p.bri}" onclick="applyTheme(${p.hue},${p.sat},${p.bri})"></div>`).join('');}
function toggleThemePopover(){document.getElementById('theme-popover').classList.toggle('open');}
document.addEventListener('click',e=>{const pop=document.getElementById('theme-popover');const btn=document.getElementById('theme-toggle-btn');if(pop.classList.contains('open')&&!pop.contains(e.target)&&e.target!==btn)pop.classList.remove('open');});
['hue','sat','bright'].forEach(name=>{document.getElementById(name+'-slider').addEventListener('input',()=>{applyTheme(+document.getElementById('hue-slider').value,+document.getElementById('sat-slider').value,+document.getElementById('bright-slider').value);});});
buildPresets();loadPersistedTheme();
// ── auto-refresh ───────────────────────────────────────────────────────────
loadAll();
autoRefreshTimer = setInterval(loadAll, 30000);
</script>
</body>
</html>"""

# ── HTTP handler ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass  # quiet

    def send_json(self, data, code=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/" or path == "/index.html":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif path == "/api/dashboard":
            self.send_json({
                "monitor":       get_monitor_data(),
                "investigations": get_investigations(),
                "shenron":       get_shenron(),
                "canary":        get_canary(),
                "publishing":    get_devto_followers(),
                "nightly_log":   get_nightly_log(10),
            })

        elif path.startswith("/api/inv/") and self.command == "GET":
            inv_id = path[len("/api/inv/"):]
            self.send_json(get_inv_detail(inv_id))

        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        path = self.path.split("?")[0]
        body = self.read_body()

        if path == "/api/inv/update":
            inv_id = body.get("inv_id")
            status = body.get("status")
            risk   = body.get("risk_score")
            # validate status against schema CHECK constraint
            valid_statuses = {"active", "pending", "disclosed", "archived"}
            if status and status not in valid_statuses:
                return self.send_json({"error": f"invalid status '{status}'; must be one of {sorted(valid_statuses)}"}, 400)
            if not inv_id:
                return self.send_json({"error": "missing inv_id"}, 400)
            # resolve text inv_id → integer id
            rows = db(INVHUB_DB, "SELECT id FROM investigations WHERE inv_id=?", (inv_id,))
            if not rows:
                return self.send_json({"error": "investigation not found"}, 404)
            row_id = rows[0]["id"]
            fields = []
            if status: fields.append(("status", status))
            if risk:   fields.append(("risk_score", int(risk)))
            if not fields:
                return self.send_json({"error": "nothing to update"}, 400)
            set_clause = ", ".join(f"{f}=?" for f,_ in fields)
            vals       = [v for _,v in fields] + [row_id]
            db_write(INVHUB_DB, f"UPDATE investigations SET {set_clause} WHERE id=?", vals)
            # log status change to timeline
            if status:
                db_write(INVHUB_DB,
                    "INSERT INTO timeline_events (inv_id, event_type, description, occurred_at) VALUES (?,?,?,?)",
                    (row_id, "status_change", f"Status updated to '{status}' via mission control", now_iso()))
            self.send_json({"ok": True})

        elif path == "/api/inv/note":
            inv_id  = body.get("inv_id")
            content = body.get("content","").strip()
            tag     = body.get("tag","")
            if not inv_id or not content:
                return self.send_json({"error": "missing fields"}, 400)
            rows = db(INVHUB_DB, "SELECT id FROM investigations WHERE inv_id=?", (inv_id,))
            if not rows:
                return self.send_json({"error": "investigation not found"}, 404)
            row_id = rows[0]["id"]
            db_write(INVHUB_DB,
                "INSERT INTO case_notes (inv_id, content_md, tag, created_at) VALUES (?,?,?,?)",
                (row_id, content, tag, now_iso()))
            # also log to timeline
            db_write(INVHUB_DB,
                "INSERT INTO timeline_events (inv_id, event_type, description, occurred_at) VALUES (?,?,?,?)",
                (row_id, "note_added", f"Note added via mission control", now_iso()))
            self.send_json({"ok": True})

        elif path == "/api/inv/timeline":
            inv_id = body.get("inv_id")
            desc   = body.get("event","").strip()
            etype  = body.get("event_type","other")
            if not inv_id or not desc:
                return self.send_json({"error": "missing fields"}, 400)
            valid_etypes = {"discovery","evidence_collected","report_filed","response_received",
                            "disclosed","published","note_added","target_added","status_change","other"}
            if etype not in valid_etypes:
                etype = "other"
            rows = db(INVHUB_DB, "SELECT id FROM investigations WHERE inv_id=?", (inv_id,))
            if not rows:
                return self.send_json({"error": "investigation not found"}, 404)
            row_id = rows[0]["id"]
            db_write(INVHUB_DB,
                "INSERT INTO timeline_events (inv_id, event_type, description, occurred_at) VALUES (?,?,?,?)",
                (row_id, etype, desc, now_iso()))
            self.send_json({"ok": True})

        elif path == "/api/inv/evidence":
            inv_id = body.get("inv_id")
            title  = body.get("title","").strip()
            etype  = body.get("evidence_type","other")
            notes  = body.get("notes","").strip()
            if not inv_id or not title:
                return self.send_json({"error": "missing fields"}, 400)
            valid_etypes = {"screenshot","json","log","whois","dns","api_response","pcap","html","binary","other"}
            if etype not in valid_etypes:
                etype = "other"
            rows = db(INVHUB_DB, "SELECT id FROM investigations WHERE inv_id=?", (inv_id,))
            if not rows:
                return self.send_json({"error": "investigation not found"}, 404)
            row_id = rows[0]["id"]
            import hashlib
            ts_str = now_iso().replace(":","").replace("-","")
            safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', title)
            canonical = f"manual/{inv_id}/{ts_str}_{safe_name}"
            sha = hashlib.sha256(f"{title}{notes}{ts_str}".encode()).hexdigest()
            db_write(INVHUB_DB,
                """INSERT INTO evidence
                   (inv_id, filename, original_path, canonical_path, type,
                    description, sha256, integrity_status, ingested_at)
                   VALUES (?,?,?,?,?,?,?,'unverified',?)""",
                (row_id, title, notes or "mission-control-entry", canonical,
                 etype, notes or title, sha, now_iso()))
            db_write(INVHUB_DB,
                "INSERT INTO timeline_events (inv_id, event_type, description, occurred_at) VALUES (?,?,?,?)",
                (row_id, "evidence_collected", f"Evidence logged via mission control: {title}", now_iso()))
            self.send_json({"ok": True})

        elif path == "/api/alert/triage":
            # triage is UI-side state for now; log to nightly log as annotation
            action = body.get("action","")
            ts     = body.get("ts","")
            atype  = body.get("alert_type","")
            try:
                with open(str(NIGHTLY_LOG), "a") as f:
                    f.write(f"{now_iso()} TRIAGE {action.upper()} [{atype}] {ts}\n")
            except: pass
            self.send_json({"ok": True})

        elif path == "/api/enrich":
            target = body.get("target","").strip()
            if not target:
                return self.send_json({"error": "no target"}, 400)
            try:
                results = enrich_target(target)
                self.send_json(results)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        else:
            self.send_response(404); self.end_headers()

# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    PORT = 7333
    server = HTTPServer(("", PORT), Handler)
    print(f"gnome // mission control v8")
    print(f"http://localhost:{PORT}")
    print(f"monitor db : {MONITOR_DB}")
    print(f"inv-hub db : {INVHUB_DB}")
    print(f"SHENRON    : {SHENRON_DIR}")
    print(f"DEV.TO key : {'set' if DEVTO_KEY else 'not set'}")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.shutdown()
