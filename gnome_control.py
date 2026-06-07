#!/usr/bin/env python3
"""
gnome // mission control v10
badBANANA Research Collective — full operator dashboard
New in v10: correlation engine, briefing generator (client-side Claude API),
PRAXIS write-back, alert dedup+diff, keyboard shortcuts, age indicators,
structured nightly log, export button.
"""

import os, sys, json, sqlite3, subprocess, hashlib, re, time
import urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import threading

# ── paths ─────────────────────────────────────────────────────────────────────
MONITOR_DB   = Path.home() / ".badbanana/monitor.db"
INVHUB_DB    = Path.home() / "research_hub/hub.db"
SHENRON_DIR  = Path.home() / "research_hub/repos/shenron"
NIGHTLY_LOG  = Path.home() / "research_hub/logs/nightly.log"
PRAXIS_BIN   = Path.home() / "research_hub/praxis/bin/praxis"
DEVTO_KEY    = os.environ.get("DEVTO_API_KEY", "")

# ── helpers ───────────────────────────────────────────────────────────────────
def db(path, query, params=()):
    try:
        con = sqlite3.connect(path); con.row_factory = sqlite3.Row
        rows = con.execute(query, params).fetchall()
        con.close()
        return [dict(r) for r in rows]
    except: return []

def db_write(path, query, params=()):
    try:
        con = sqlite3.connect(path)
        cur = con.execute(query, params)
        con.commit(); rowid = cur.lastrowid; con.close()
        return rowid
    except: return None

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def days_ago(ts_str):
    if not ts_str: return None
    try:
        ts = datetime.fromisoformat(ts_str.replace('Z','+00:00'))
        return (datetime.now(timezone.utc) - ts).days
    except: return None

# ── nightly log (structured JSON) ─────────────────────────────────────────────
def log_event(event_type, message, inv_id=None, meta=None):
    NIGHTLY_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": now_iso(), "type": event_type, "msg": message}
    if inv_id: entry["inv_id"] = inv_id
    if meta:   entry["meta"]   = meta
    try:
        with open(str(NIGHTLY_LOG), "a") as f:
            f.write(json.dumps(entry) + "\n")
    except: pass

def get_nightly_log(n=20):
    try:
        lines = NIGHTLY_LOG.read_text().strip().splitlines()
        entries = []
        for line in reversed(lines[-n*2:]):
            try:
                entries.append(json.loads(line))
            except:
                # legacy plaintext lines
                entries.append({"ts": "", "type": "log", "msg": line.strip()})
            if len(entries) >= n: break
        return entries
    except: return []

# ── monitor data ──────────────────────────────────────────────────────────────
def get_monitor_data():
    alerts  = db(MONITOR_DB, "SELECT COUNT(*) as n FROM alerts")
    total   = alerts[0]["n"] if alerts else 0
    snaps   = db(MONITOR_DB, "SELECT COUNT(*) as n FROM infra_snapshots")
    snaps_n = snaps[0]["n"] if snaps else 0
    recent  = db(MONITOR_DB,
        "SELECT alert_type, details, timestamp as created_at FROM alerts ORDER BY timestamp DESC LIMIT 60")
    last_t  = db(MONITOR_DB, "SELECT timestamp FROM alerts ORDER BY timestamp DESC LIMIT 1")
    last_ts = last_t[0]["timestamp"] if last_t else None
    state   = db(MONITOR_DB, "SELECT key, value FROM state WHERE key LIKE 'last_ips_%'")
    ip_rows = [{"target": r["key"][len("last_ips_"):], "ips": r["value"]} for r in state]

    # dedup + diff alerts
    deduped = []
    seen = {}
    for a in recent:
        key = a["alert_type"] + "|" + (a["details"] or "")
        if key in seen:
            seen[key]["count"] = seen[key].get("count", 1) + 1
        else:
            a["count"] = 1
            seen[key] = a
            deduped.append(a)

    # compute diff for DNS_CHANGE alerts
    prev_ips = {}
    for a in reversed(recent):
        if a["alert_type"] == "DNS_CHANGE" and a.get("details"):
            parts = a["details"].split(",")
            if len(parts) >= 2:
                target = parts[0].strip() if len(parts) > 2 else "unknown"
                ips = a["details"]
                if target in prev_ips and prev_ips[target] != ips:
                    a["diff"] = {"from": prev_ips[target], "to": ips}
                prev_ips[target] = ips

    return {"total": total, "snapshots": snaps_n, "recent_alerts": deduped[:20],
            "last_ts": last_ts, "ips": ip_rows}

# ── investigations ─────────────────────────────────────────────────────────────
def get_investigations():
    rows = db(INVHUB_DB, """
        SELECT id, inv_id, title, status, risk_score, threat_class, opened_at
        FROM investigations ORDER BY risk_score DESC
    """)
    for r in rows:
        r["category"]   = r.pop("threat_class", "")
        r["created_at"] = r.pop("opened_at", "")
        r["updated_at"] = r.get("created_at", "")
        # last activity from timeline
        last = db(INVHUB_DB,
            "SELECT MAX(occurred_at) as last FROM timeline_events WHERE inv_id=?", (r["id"],))
        r["last_activity"] = last[0]["last"] if last and last[0]["last"] else r["created_at"]
        r["days_stale"]    = days_ago(r["last_activity"])
    return rows

def get_inv_detail(inv_id):
    inv = db(INVHUB_DB, "SELECT * FROM investigations WHERE inv_id=?", (inv_id,))
    if not inv:
        return {"investigation": {}, "timeline": [], "evidence": [], "targets": [], "notes": []}
    row_id = inv[0]["id"]

    tl = db(INVHUB_DB, """
        SELECT id, event_type, description, occurred_at, evidence_id
        FROM timeline_events WHERE inv_id=? ORDER BY occurred_at DESC LIMIT 100
    """, (row_id,))
    for e in tl:
        e["event"] = e.pop("description", "")
        e["event_time"] = e.pop("occurred_at", "")
        e["detail"] = ""

    evid = db(INVHUB_DB, """
        SELECT id, filename, type, description, sha256, integrity_status, ingested_at
        FROM evidence WHERE inv_id=? ORDER BY ingested_at DESC LIMIT 50
    """, (row_id,))
    for e in evid:
        e["title"] = e.get("filename","")
        e["evidence_type"] = e.pop("type","")
        e["notes"] = e.pop("description","")
        e["collected_at"] = e.pop("ingested_at","")

    tgts = db(INVHUB_DB, """
        SELECT t.id, t.type, t.value, t.description, it.role, t.created_at
        FROM targets t JOIN inv_targets it ON it.target_id=t.id
        WHERE it.inv_id=? ORDER BY t.created_at DESC LIMIT 50
    """, (row_id,))
    for t in tgts:
        t["target_type"] = t.pop("type","")
        t["added_at"] = t.pop("created_at","")

    notes = db(INVHUB_DB, """
        SELECT id, content_md, tag, created_at FROM case_notes
        WHERE inv_id=? ORDER BY created_at DESC LIMIT 30
    """, (row_id,))
    for n in notes: n["content"] = n.pop("content_md","")

    inv_out = dict(inv[0])
    inv_out["category"] = inv_out.pop("threat_class","")
    inv_out["created_at"] = inv_out.pop("opened_at","")

    return {"investigation": inv_out, "timeline": tl,
            "evidence": evid, "targets": tgts, "notes": notes}

# ── correlation engine ────────────────────────────────────────────────────────
def get_correlations():
    invs = db(INVHUB_DB, "SELECT id, inv_id, title FROM investigations")
    edges = []
    seen  = set()

    for i, a in enumerate(invs):
        for b in invs[i+1:]:
            shared = []
            # shared targets
            shared_targets = db(INVHUB_DB, """
                SELECT t.value, t.type FROM targets t
                JOIN inv_targets ita ON ita.target_id=t.id AND ita.inv_id=?
                JOIN inv_targets itb ON itb.target_id=t.id AND itb.inv_id=?
            """, (a["id"], b["id"]))
            for t in shared_targets:
                shared.append({"type": "target", "value": t["value"], "kind": t["type"]})

            # shared IPs from monitor (check if any target value appears in alerts)
            if shared:
                key = tuple(sorted([a["inv_id"], b["inv_id"]]))
                if key not in seen:
                    seen.add(key)
                    edges.append({
                        "a": a["inv_id"], "a_title": a["title"],
                        "b": b["inv_id"], "b_title": b["title"],
                        "shared": shared,
                        "strength": len(shared)
                    })

    # also correlate via alert IPs matching known targets
    all_targets = db(INVHUB_DB, """
        SELECT t.value, t.type, GROUP_CONCAT(DISTINCT i.inv_id) as inv_ids
        FROM targets t
        JOIN inv_targets it ON it.target_id=t.id
        JOIN investigations i ON i.id=it.inv_id
        GROUP BY t.value HAVING COUNT(DISTINCT i.id) > 1
    """)

    return {"edges": edges, "shared_targets": all_targets}

# ── SHENRON ───────────────────────────────────────────────────────────────────
def get_shenron():
    data = {"layers": 0, "payloads": 0, "coverage": 0, "health": [], "by_category": {}}
    manifest = SHENRON_DIR / "shenron_manifest.json"
    if manifest.exists():
        try:
            m = json.loads(manifest.read_text())
            summary = m.get("summary", {})
            layers_list = m.get("layers", [])
            data["layers"]      = summary.get("total_canonical", len(layers_list))
            data["payloads"]    = summary.get("total_variants", 0)
            data["coverage"]    = summary.get("detection_coverage", 0)
            data["by_category"] = summary.get("by_category", {})
        except: pass

    try:
        r = subprocess.run(
            ["python3", str(SHENRON_DIR / "shenron.py"), "--validate-all-assumptions"],
            capture_output=True, text=True, timeout=30, cwd=str(SHENRON_DIR)
        )
        skip = {'verdict:','verdict','checked_at','categories','rerun','shenron'}
        for line in (r.stdout + r.stderr).splitlines():
            s = line.strip()
            if s.startswith("[✓]"):
                name = s[3:].strip().split()[0]
                if name.lower() not in skip: data["health"].append({"name": name, "status": "pass"})
            elif s.startswith("[✗]"):
                name = s[3:].strip().split()[0]
                if name.lower() not in skip: data["health"].append({"name": name, "status": "fail"})
            elif s.startswith("[?]"):
                name = s[3:].strip().split()[0]
                if name and name.lower() not in skip and not name.startswith(('=','-')):
                    data["health"].append({"name": name, "status": "unknown"})
    except: pass
    return data

# ── canary ────────────────────────────────────────────────────────────────────
def get_canary():
    state = db(MONITOR_DB, "SELECT key, value FROM state")
    s = {r["key"]: r["value"] for r in state}
    return {
        "crx_version":        s.get("last_ext_version","—"),
        "crx_checked":        s.get("last_ext_check", s.get("last_check","—")),
        "operator_repos":     s.get("operator_repos","—"),
        "operator_followers": s.get("operator_followers","—"),
        "_raw": s,
    }

# ── devto (cached) ────────────────────────────────────────────────────────────
_devto_cache = {"followers": "—", "ts": 0}
def get_devto_followers():
    global _devto_cache
    if time.time() - _devto_cache["ts"] < 300:
        return {"followers": _devto_cache["followers"], "username": "gnomeman4201"}
    if not DEVTO_KEY:
        return {"followers": "—", "username": "gnomeman4201"}
    try:
        total = 0; page = 1
        while True:
            req = urllib.request.Request(
                f"https://dev.to/api/followers/users?per_page=1000&page={page}",
                headers={"api-key": DEVTO_KEY, "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                batch = json.loads(r.read())
            total += len(batch)
            if len(batch) < 1000: break
            page += 1
            if page > 20: break
        _devto_cache = {"followers": total, "ts": time.time()}
        return {"followers": total, "username": "gnomeman4201"}
    except:
        return {"followers": _devto_cache["followers"], "username": "gnomeman4201"}

# ── enrichment ────────────────────────────────────────────────────────────────
def enrich_target(target):
    results = {}
    try:
        r = subprocess.run(["whois", target], capture_output=True, text=True, timeout=10)
        results["whois"] = r.stdout[:2000]
    except: results["whois"] = "whois unavailable"
    try:
        import socket
        results["dns_a"] = socket.gethostbyname_ex(target)[2]
    except: results["dns_a"] = []
    try:
        r = subprocess.run(["dig","+short","TXT",target], capture_output=True, text=True, timeout=5)
        results["dns_txt"] = r.stdout.strip().splitlines()
    except: results["dns_txt"] = []
    vt_key = os.environ.get("VT_API_KEY","")
    if vt_key:
        try:
            req = urllib.request.Request(
                f"https://www.virustotal.com/api/v3/domains/{target}",
                headers={"x-apikey": vt_key, "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                vt = json.loads(resp.read())
            results["virustotal"] = vt.get("data",{}).get("attributes",{}).get("last_analysis_stats",{})
        except Exception as e:
            results["virustotal"] = {"error": str(e)}
    else:
        results["virustotal"] = {"note": "VT_API_KEY not set"}
    results["enriched_at"] = now_iso()
    return results

# ── PRAXIS integration ────────────────────────────────────────────────────────
def praxis_capture(text, inv_id=None, tags=None, confidence=3, url=None):
    if not PRAXIS_BIN.exists():
        return {"error": "PRAXIS not found"}
    cmd = [str(PRAXIS_BIN), "capture", text, "--quiet"]
    if inv_id:     cmd += ["--inv", inv_id]
    if tags:       cmd += ["--tags", tags]
    if confidence: cmd += ["--confidence", str(confidence)]
    if url:        cmd += ["--url", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        praxis_id = r.stdout.strip()
        return {"ok": True, "praxis_id": praxis_id, "stderr": r.stderr[:200]}
    except Exception as e:
        return {"error": str(e)}

def praxis_publish(inv_id, fmt="devto"):
    if not PRAXIS_BIN.exists():
        return {"error": "PRAXIS not found"}
    try:
        r = subprocess.run(
            [str(PRAXIS_BIN), "publish", inv_id, "--format", fmt, "--no-save"],
            capture_output=True, text=True, timeout=30
        )
        return {"ok": True, "output": r.stdout, "stderr": r.stderr[:300]}
    except Exception as e:
        return {"error": str(e)}

def praxis_timeline(inv_id):
    if not PRAXIS_BIN.exists():
        return {"error": "PRAXIS not found"}
    try:
        r = subprocess.run(
            [str(PRAXIS_BIN), "timeline", inv_id, "--format", "json"],
            capture_output=True, text=True, timeout=15
        )
        try:
            return {"ok": True, "timeline": json.loads(r.stdout)}
        except:
            return {"ok": True, "timeline_md": r.stdout}
    except Exception as e:
        return {"error": str(e)}

# ── export ────────────────────────────────────────────────────────────────────
def export_investigation(inv_id):
    d = get_inv_detail(inv_id)
    inv = d["investigation"]
    lines = [
        f"# {inv.get('inv_id',inv_id)} — {inv.get('title','')}",
        f"**Status:** {inv.get('status','')} | **Risk:** {inv.get('risk_score','')}/10 | **Category:** {inv.get('category','')}",
        f"**Opened:** {inv.get('created_at','')}",
        f"\n## Timeline\n",
    ]
    for e in reversed(d["timeline"]):
        lines.append(f"- `{e.get('event_time','')[:19]}` **{e.get('event_type','')}** — {e.get('event','')}")
    lines.append("\n## Evidence\n")
    for e in d["evidence"]:
        lines.append(f"- `{e.get('evidence_type','')}` **{e.get('title','')}** ({e.get('collected_at','')[:10]}) — {e.get('notes','')}")
    lines.append("\n## Targets\n")
    for t in d["targets"]:
        lines.append(f"- `{t.get('target_type','')}` **{t.get('value','')}** ({t.get('role','')})")
    lines.append("\n## Notes\n")
    for n in d["notes"]:
        lines.append(f"### {n.get('tag','')} — {n.get('created_at','')[:10]}\n{n.get('content','')}\n")
    lines.append(f"\n---\n*Exported from gnome // mission control {now_iso()}*")
    return "\n".join(lines)

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
    --bg:#0a0c0a; --bg2:#0f120f; --bg3:#141814; --border:#1e2a1e; --border2:#2a3d2a;
    --green:#39ff7a; --green2:#22c55e; --green3:#16a34a; --dim:#4a6650; --dimmer:#2d3e2d;
    --red:#ff4444; --yellow:#f5c518; --orange:#ff8c00; --blue:#4db8ff;
    --text:#c8e6c9; --text2:#7a9e7a; --text3:#4a6650;
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--text); font-family:'JetBrains Mono',monospace;
         font-size:11px; min-height:100vh; overflow-x:hidden; }
  body::before { content:''; position:fixed; inset:0; z-index:9999;
    background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.04) 2px,rgba(0,0,0,.04) 4px);
    pointer-events:none; }

  header { display:flex; align-items:center; justify-content:space-between;
    padding:10px 20px; border-bottom:1px solid var(--border2); background:var(--bg2);
    position:sticky; top:0; z-index:100; }
  .logo { font-family:'Share Tech Mono'; font-size:15px; color:var(--green); letter-spacing:2px; }
  .logo span { color:var(--text3); }
  .status-bar { display:flex; align-items:center; gap:10px; color:var(--text2); font-size:10px; flex-wrap:wrap; }
  .live-dot { width:7px; height:7px; border-radius:50%; background:var(--green);
              box-shadow:0 0 8px var(--green); animation:pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1}50%{opacity:.4} }
  #clock { color:var(--green2); }
  .hbtn { background:none; border:1px solid var(--border2); color:var(--text2);
          padding:3px 8px; cursor:pointer; font-family:inherit; font-size:9px;
          letter-spacing:1px; transition:all .2s; }
  .hbtn:hover { border-color:var(--green3); color:var(--green); }
  .hbtn.blue  { color:var(--blue); border-color:#1a3d5c; }
  .hbtn.blue:hover { border-color:var(--blue); }

  .grid { display:grid; grid-template-columns:280px 1fr 220px;
          gap:1px; background:var(--border); min-height:calc(100vh - 41px); }
  .panel { background:var(--bg2); padding:14px; display:flex; flex-direction:column; gap:10px; }

  .section-label { font-size:9px; letter-spacing:3px; color:var(--dim); text-transform:uppercase;
    padding-bottom:8px; border-bottom:1px solid var(--border); margin-bottom:4px;
    display:flex; align-items:center; justify-content:space-between; }
  .badge { background:var(--green3); color:#000; font-size:8px; padding:1px 6px; letter-spacing:1px; }
  .badge.orange { background:var(--orange); }
  .badge.red    { background:var(--red); }
  .badge.blue   { background:var(--blue); }

  .stat-row { display:flex; gap:8px; }
  .stat { flex:1; background:var(--bg3); border:1px solid var(--border); padding:8px 10px; }
  .stat-label { font-size:8px; color:var(--text3); letter-spacing:2px; margin-bottom:4px; }
  .stat-val { font-size:22px; color:var(--green); font-weight:700; line-height:1; }
  .stat-sub { font-size:9px; color:var(--text3); margin-top:3px; }

  .ip-group { margin-bottom:8px; }
  .ip-label { font-size:9px; color:var(--text3); margin-bottom:4px; }
  .ip-tags { display:flex; flex-wrap:wrap; gap:4px; }
  .ip-tag { background:var(--bg3); border:1px solid var(--green3); color:var(--green2);
            padding:2px 8px; font-size:10px; cursor:pointer; transition:all .15s; }
  .ip-tag:hover { background:var(--green3); color:#000; }

  .alert-list { display:flex; flex-direction:column; gap:2px; max-height:240px; overflow-y:auto; }
  .alert-item { display:grid; grid-template-columns:110px 90px 1fr auto auto;
    gap:6px; padding:5px 8px; background:var(--bg3); border-left:2px solid transparent;
    align-items:center; transition:all .15s; }
  .alert-item:hover { border-left-color:var(--green3); background:var(--bg); }
  .alert-ts   { color:var(--text3); font-size:9px; }
  .alert-type { color:var(--orange); font-size:9px; letter-spacing:1px; }
  .alert-val  { color:var(--text2); font-size:9px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .alert-count { color:var(--dim); font-size:8px; white-space:nowrap; }
  .triage-btns { display:flex; gap:3px; opacity:0; transition:opacity .15s; }
  .alert-item:hover .triage-btns { opacity:1; }
  .tbtn { border:none; cursor:pointer; padding:2px 5px; font-family:inherit; font-size:8px; transition:all .15s; }
  .tbtn-dismiss  { background:var(--dimmer); color:var(--dim); }
  .tbtn-dismiss:hover  { background:var(--text3); color:#000; }
  .tbtn-escalate { background:#3d1a00; color:var(--orange); }
  .tbtn-escalate:hover { background:var(--orange); color:#000; }
  .tbtn-tag      { background:#001a3d; color:var(--blue); }
  .tbtn-tag:hover { background:var(--blue); color:#000; }

  /* investigations */
  .inv-table { width:100%; border-collapse:collapse; }
  .inv-table thead th { font-size:8px; letter-spacing:2px; color:var(--dim); text-align:left;
    padding:4px 8px; border-bottom:1px solid var(--border2); font-weight:400; }
  .inv-row { cursor:pointer; transition:all .15s; border-bottom:1px solid var(--border); }
  .inv-row:hover { background:var(--bg3); }
  .inv-row.focused { background:var(--bg3); outline:1px solid var(--green3); }
  .inv-row td { padding:7px 8px; vertical-align:middle; }
  .inv-id { color:var(--text3); font-size:10px; }
  .risk-badge { display:inline-block; padding:2px 6px; font-size:9px; font-weight:700; min-width:32px; text-align:center; }
  .risk-9,.risk-10 { background:var(--red);    color:#000; }
  .risk-7,.risk-8  { background:var(--orange);  color:#000; }
  .risk-5,.risk-6  { background:var(--yellow);  color:#000; }
  .risk-3,.risk-4  { background:var(--green3);  color:#000; }
  .risk-1,.risk-2  { background:var(--dimmer);  color:var(--dim); }
  .status-chip { display:inline-block; padding:2px 6px; font-size:8px; letter-spacing:1px; border:1px solid; }
  .status-active    { border-color:var(--green3); color:var(--green2); }
  .status-pending   { border-color:var(--yellow); color:var(--yellow); }
  .status-disclosed { border-color:var(--dim);    color:var(--dim); }
  .status-archived  { border-color:var(--dimmer); color:var(--dimmer); }
  .inv-title { color:var(--text); font-size:10px; }
  .inv-cat   { color:var(--text3); font-size:9px; }
  .age-badge { font-size:8px; padding:1px 4px; }
  .age-stale  { color:var(--orange); border:1px solid #3d2000; }
  .age-active { color:var(--green3); }
  .inv-arrow { color:var(--dim); font-size:10px; }
  .inv-row:hover .inv-arrow { color:var(--green); }

  /* correlations */
  .corr-edge { padding:6px 8px; background:var(--bg3); border-left:2px solid var(--blue);
               margin-bottom:4px; cursor:pointer; }
  .corr-edge:hover { border-left-color:var(--green); }
  .corr-ids   { font-size:9px; color:var(--blue); margin-bottom:3px; }
  .corr-shared { font-size:8px; color:var(--text3); }
  .corr-strength { float:right; font-size:8px; color:var(--dim); }

  /* SHENRON */
  .shenron-stats { display:grid; grid-template-columns:1fr 1fr; gap:6px; }
  .shenron-stat { background:var(--bg3); padding:7px; }
  .shenron-stat-label { font-size:8px; color:var(--text3); letter-spacing:1px; }
  .shenron-stat-val   { font-size:16px; color:var(--green); font-weight:700; margin-top:2px; }
  .health-grid { display:flex; flex-direction:column; gap:4px; }
  .health-item { display:flex; align-items:center; justify-content:space-between;
                 padding:4px 8px; background:var(--bg3); }
  .health-name { color:var(--text2); font-size:10px; }
  .health-dot { width:8px; height:8px; border-radius:50%; }
  .health-dot.pass    { background:var(--green); box-shadow:0 0 6px var(--green); }
  .health-dot.fail    { background:var(--red);   box-shadow:0 0 6px var(--red); }
  .health-dot.unknown { background:var(--dim); }

  .canary-row { display:flex; justify-content:space-between; padding:5px 0;
                border-bottom:1px solid var(--border); }
  .canary-key { color:var(--text3); font-size:9px; }
  .canary-val { color:var(--green2); font-size:9px; }

  .pub-followers { font-size:36px; color:var(--green); font-weight:700; line-height:1; }
  .pub-sub { font-size:9px; color:var(--text3); margin-top:3px; }

  /* nightly log */
  .log-feed { display:flex; flex-direction:column; gap:2px; max-height:130px; overflow-y:auto; }
  .log-entry { padding:3px 6px; display:flex; gap:8px; align-items:baseline; }
  .log-entry:hover { background:var(--bg3); }
  .log-ts   { font-size:8px; color:var(--text3); white-space:nowrap; flex-shrink:0; }
  .log-type { font-size:8px; padding:0 4px; flex-shrink:0; }
  .log-type.triage   { color:var(--orange); }
  .log-type.enrich   { color:var(--blue); }
  .log-type.capture  { color:var(--green2); }
  .log-type.briefing { color:var(--yellow); }
  .log-type.log      { color:var(--dim); }
  .log-msg  { font-size:9px; color:var(--text2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

  /* ── DRAWER ── */
  .drawer-overlay { position:fixed; inset:0; background:rgba(0,0,0,.7); z-index:200;
                    opacity:0; pointer-events:none; transition:opacity .25s; }
  .drawer-overlay.open { opacity:1; pointer-events:all; }
  .drawer { position:fixed; right:0; top:0; bottom:0; width:700px; background:var(--bg2);
            border-left:1px solid var(--border2); z-index:201; display:flex; flex-direction:column;
            transform:translateX(100%); transition:transform .25s cubic-bezier(.4,0,.2,1); overflow:hidden; }
  .drawer.open { transform:translateX(0); }
  .drawer-header { padding:14px 18px; border-bottom:1px solid var(--border2);
    display:flex; align-items:center; justify-content:space-between;
    background:var(--bg3); flex-shrink:0; }
  .drawer-title { font-family:'Share Tech Mono'; font-size:13px; color:var(--green); }
  .drawer-close { background:none; border:1px solid var(--border2); color:var(--text3);
    width:26px; height:26px; cursor:pointer; font-size:14px; display:flex;
    align-items:center; justify-content:center; font-family:inherit; transition:all .15s; }
  .drawer-close:hover { border-color:var(--red); color:var(--red); }
  .drawer-tabs { display:flex; border-bottom:1px solid var(--border); flex-shrink:0; overflow-x:auto; }
  .dtab { padding:8px 14px; font-size:9px; letter-spacing:2px; color:var(--text3);
          cursor:pointer; border-bottom:2px solid transparent; transition:all .15s;
          background:none; border-top:none; border-left:none; border-right:none;
          font-family:inherit; text-transform:uppercase; white-space:nowrap; }
  .dtab.active { color:var(--green); border-bottom-color:var(--green); }
  .dtab:hover:not(.active) { color:var(--text2); }
  .drawer-body { flex:1; overflow-y:auto; padding:16px 18px; }
  .drawer-pane { display:none; }
  .drawer-pane.active { display:block; }

  /* timeline */
  .tl-item { display:flex; gap:12px; margin-bottom:12px; }
  .tl-dot  { width:8px; height:8px; border-radius:50%; background:var(--green3);
             margin-top:3px; flex-shrink:0; box-shadow:0 0 4px var(--green3); }
  .tl-content { flex:1; }
  .tl-time  { font-size:8px; color:var(--text3); margin-bottom:2px; }
  .tl-event { font-size:10px; color:var(--text); }

  .ev-item { background:var(--bg3); border:1px solid var(--border); padding:8px; margin-bottom:6px; }
  .ev-title { font-size:10px; color:var(--green2); margin-bottom:3px; }
  .ev-meta  { font-size:8px; color:var(--text3); }

  /* forms */
  .action-section { margin-bottom:20px; }
  .action-label { font-size:9px; letter-spacing:2px; color:var(--dim); text-transform:uppercase;
                  margin-bottom:8px; padding-bottom:5px; border-bottom:1px solid var(--border); }
  .form-row { display:flex; gap:8px; margin-bottom:8px; flex-wrap:wrap; }
  .form-input { background:var(--bg3); border:1px solid var(--border2); color:var(--text);
    padding:6px 10px; font-family:inherit; font-size:10px; flex:1; min-width:120px;
    outline:none; transition:border .15s; }
  .form-input:focus { border-color:var(--green3); }
  .form-select { background:var(--bg3); border:1px solid var(--border2); color:var(--text);
    padding:6px 10px; font-family:inherit; font-size:10px; outline:none; cursor:pointer; }
  .form-textarea { background:var(--bg3); border:1px solid var(--border2); color:var(--text);
    padding:6px 10px; font-family:inherit; font-size:10px; width:100%; resize:vertical;
    min-height:70px; outline:none; transition:border .15s; }
  .form-textarea:focus { border-color:var(--green3); }
  .btn { background:var(--green3); color:#000; border:none; padding:6px 14px;
         font-family:inherit; font-size:9px; letter-spacing:2px; text-transform:uppercase;
         cursor:pointer; transition:all .15s; }
  .btn:hover { background:var(--green2); }
  .btn-ghost { background:none; border:1px solid var(--border2); color:var(--text2); }
  .btn-ghost:hover { border-color:var(--green3); color:var(--green); }
  .btn-blue { background:#001a3d; color:var(--blue); border:1px solid #1a3d5c; }
  .btn-blue:hover { background:var(--blue); color:#000; }
  .btn-orange { background:#2d1000; color:var(--orange); border:1px solid #5c2a00; }
  .btn-orange:hover { background:var(--orange); color:#000; }
  .form-msg { font-size:9px; padding:5px 8px; margin-top:6px; }
  .form-msg.ok  { background:#0a2d0a; color:var(--green2); border-left:2px solid var(--green3); }
  .form-msg.err { background:#2d0a0a; color:var(--red);    border-left:2px solid var(--red); }

  /* briefing */
  .briefing-output { background:var(--bg3); border:1px solid var(--border); padding:12px;
    font-size:9px; color:var(--text); white-space:pre-wrap; max-height:400px; overflow-y:auto;
    line-height:1.6; margin-top:8px; }
  .briefing-tabs { display:flex; gap:4px; margin-bottom:8px; }
  .briefing-tab { padding:4px 10px; font-size:8px; letter-spacing:2px; cursor:pointer;
    background:none; border:1px solid var(--border2); color:var(--text3); font-family:inherit; }
  .briefing-tab.active { border-color:var(--yellow); color:var(--yellow); }
  .key-prompt { background:var(--bg3); border:1px solid var(--orange); padding:10px;
    color:var(--orange); font-size:9px; margin-bottom:10px; }
  .spinner { display:inline-block; animation:spin .8s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }

  /* export */
  .export-output { background:var(--bg3); border:1px solid var(--border); padding:10px;
    font-size:9px; color:var(--text2); white-space:pre-wrap; max-height:300px; overflow-y:auto;
    font-family:'JetBrains Mono',monospace; margin-top:8px; }

  /* enrichment panel */
  .enrich-panel { position:fixed; left:0; top:0; bottom:0; width:560px; background:var(--bg2);
    border-right:1px solid var(--border2); z-index:201; display:flex; flex-direction:column;
    transform:translateX(-100%); transition:transform .25s cubic-bezier(.4,0,.2,1); overflow:hidden; }
  .enrich-panel.open { transform:translateX(0); }
  .enrich-header { padding:14px 18px; border-bottom:1px solid var(--border2); background:var(--bg3);
    display:flex; align-items:center; justify-content:space-between; flex-shrink:0; }
  .enrich-title { font-family:'Share Tech Mono'; font-size:13px; color:var(--blue); }
  .enrich-body  { flex:1; overflow-y:auto; padding:16px 18px; }
  .enrich-section { margin-bottom:14px; }
  .enrich-section-label { color:var(--dim); letter-spacing:2px; font-size:8px; margin-bottom:6px; }
  .enrich-code { background:var(--bg3); border:1px solid var(--border); padding:8px;
    white-space:pre-wrap; word-break:break-all; font-size:9px; color:var(--text);
    max-height:200px; overflow-y:auto; }
  .enrich-actions { display:flex; gap:6px; margin-top:10px; }

  /* theme */
  .theme-popover { position:fixed; top:41px; right:10px; z-index:500; background:var(--bg3);
    border:1px solid var(--border2); padding:14px; width:260px; display:none;
    box-shadow:0 8px 32px rgba(0,0,0,.6); }
  .theme-popover.open { display:block; }
  .theme-popover-title { font-size:8px; letter-spacing:3px; color:var(--dim);
    text-transform:uppercase; margin-bottom:10px; }
  .theme-presets { display:flex; flex-wrap:wrap; gap:5px; margin-bottom:12px; }
  .preset-swatch { width:28px; height:28px; border-radius:2px; cursor:pointer;
    border:2px solid transparent; transition:all .15s; }
  .preset-swatch.active { border-color:#fff; }
  .preset-swatch:hover { transform:scale(1.1); }
  .slider-row { margin-bottom:8px; }
  .slider-label { font-size:8px; color:var(--text3); letter-spacing:2px; margin-bottom:5px;
    display:flex; justify-content:space-between; }
  .theme-slider { -webkit-appearance:none; appearance:none; width:100%; height:4px;
    outline:none; cursor:pointer; border-radius:2px; }
  .theme-slider::-webkit-slider-thumb { -webkit-appearance:none; width:12px; height:12px;
    border-radius:50%; background:var(--green); cursor:pointer; border:2px solid var(--bg); }
  #hue-slider { background:linear-gradient(to right,hsl(0,80%,45%),hsl(60,80%,45%),
    hsl(120,80%,45%),hsl(180,80%,45%),hsl(240,80%,45%),hsl(300,80%,45%),hsl(360,80%,45%)); }

  /* kbd hints */
  .kbd-hint { position:fixed; bottom:10px; right:10px; z-index:150; font-size:8px;
    color:var(--text3); display:flex; gap:10px; pointer-events:none; }
  .kbd { background:var(--bg3); border:1px solid var(--border2); padding:2px 5px; color:var(--dim); }

  /* api key modal */
  .modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,.8); z-index:300;
    display:flex; align-items:center; justify-content:center; }
  .modal { background:var(--bg2); border:1px solid var(--border2); padding:24px; width:420px; }
  .modal-title { font-family:'Share Tech Mono'; font-size:14px; color:var(--yellow); margin-bottom:12px; }
  .modal-sub { font-size:9px; color:var(--text3); margin-bottom:16px; line-height:1.6; }

  ::-webkit-scrollbar { width:4px; height:4px; }
  ::-webkit-scrollbar-track { background:var(--bg); }
  ::-webkit-scrollbar-thumb { background:var(--border2); }
  ::-webkit-scrollbar-thumb:hover { background:var(--dim); }

  .toast { position:fixed; bottom:20px; left:50%; transform:translateX(-50%);
    background:var(--bg3); border:1px solid var(--green3); color:var(--green2);
    padding:8px 18px; font-size:10px; z-index:9998; opacity:0; transition:opacity .3s;
    pointer-events:none; }
  .toast.show { opacity:1; }
  .toast.err { border-color:var(--red); color:var(--red); }
</style>
</head>
<body>

<header>
  <div class="logo">gnome <span>//</span> mission control</div>
  <div class="status-bar">
    <div class="live-dot"></div>
    <span id="clock">—</span>
    <span id="last-refresh" style="color:var(--text3)">loading...</span>
    <button class="hbtn" onclick="loadAll()">refresh</button>
    <button class="hbtn blue" onclick="openEnrich()">⬡ enrich</button>
    <button class="hbtn" onclick="toggleThemePopover()" id="theme-toggle-btn">◐ theme</button>
    <span style="color:var(--border2)">|</span>
    <span style="font-size:8px;color:var(--text3)">j/k nav · e enrich · esc close</span>
  </div>
</header>

<!-- theme popover -->
<div class="theme-popover" id="theme-popover">
  <div class="theme-popover-title">color theme</div>
  <div class="theme-presets" id="theme-presets"></div>
  <div class="slider-row"><div class="slider-label"><span>HUE</span><span id="hue-val">120°</span></div>
    <input type="range" class="theme-slider" id="hue-slider" min="0" max="360" value="120"></div>
  <div class="slider-row"><div class="slider-label"><span>SATURATION</span><span id="sat-val">100%</span></div>
    <input type="range" class="theme-slider" id="sat-slider" min="20" max="100" value="100"></div>
  <div class="slider-row"><div class="slider-label"><span>BRIGHTNESS</span><span id="bright-val">60%</span></div>
    <input type="range" class="theme-slider" id="bright-slider" min="30" max="90" value="60"></div>
  <div style="margin-top:10px;display:flex;gap:6px">
    <button class="hbtn" onclick="resetTheme()" style="flex:1">reset</button>
    <button class="hbtn" onclick="toggleThemePopover()" style="flex:1">close</button>
  </div>
</div>

<div class="grid">
<!-- LEFT -->
<div class="panel">
  <div class="section-label">badBANANA monitor <span class="badge" id="monitor-badge">active</span></div>
  <div class="stat-row">
    <div class="stat"><div class="stat-label">total alerts</div>
      <div class="stat-val" id="total-alerts">—</div><div class="stat-sub" id="alerts-ago">—</div></div>
    <div class="stat"><div class="stat-label">infra snapshots</div>
      <div class="stat-val" id="total-snaps">—</div><div class="stat-sub">dns + headers</div></div>
  </div>
  <div id="ip-groups"></div>
  <div class="section-label">recent alerts <span id="alert-dedup-note" style="font-size:8px;color:var(--dim)"></span></div>
  <div class="alert-list" id="alert-list"></div>

  <div class="section-label" style="margin-top:8px">publishing / reach</div>
  <div class="stat-row">
    <div class="stat"><div class="stat-label">dev.to followers</div>
      <div class="pub-followers" id="devto-followers">—</div>
      <div class="pub-sub" id="devto-user">gnomeman4201</div></div>
  </div>

  <div class="section-label" style="margin-top:4px">nightly log</div>
  <div class="log-feed" id="nightly-log"></div>
</div>

<!-- MID -->
<div class="panel">
  <div class="section-label">investigations
    <span class="badge orange" id="inv-active-badge">— active</span></div>
  <div style="display:flex;gap:16px;margin-bottom:8px;font-size:9px;color:var(--text3)">
    <span>total: <span id="inv-total" style="color:var(--green2)">—</span></span>
    <span>timeline events: <span id="inv-events" style="color:var(--green2)">—</span></span>
  </div>
  <table class="inv-table">
    <thead><tr><th>id</th><th>risk</th><th>status</th><th>title</th><th>cat</th><th>age</th><th></th></tr></thead>
    <tbody id="inv-tbody"></tbody>
  </table>

  <!-- correlations -->
  <div class="section-label" style="margin-top:12px">
    infrastructure correlations
    <span class="badge blue" id="corr-badge">—</span>
  </div>
  <div id="corr-list" style="max-height:180px;overflow-y:auto"></div>
</div>

<!-- RIGHT -->
<div class="panel">
  <div class="section-label">SHENRON</div>
  <div class="shenron-stats" id="shenron-stats"></div>
  <div class="section-label" style="margin-top:8px">health checks</div>
  <div class="health-grid" id="shenron-health"></div>

  <div class="section-label" style="margin-top:12px">canary watchdogs</div>
  <div id="canary-rows"></div>

  <div class="section-label" style="margin-top:12px">quick enrich</div>
  <div style="display:flex;flex-direction:column;gap:4px">
    <input class="form-input" id="quick-enrich-input" placeholder="domain or IP…" style="width:100%">
    <button class="btn btn-blue" style="width:100%" onclick="quickEnrich()">⬡ run enrichment</button>
  </div>
</div>
</div><!-- /grid -->

<!-- ── INVESTIGATION DRAWER ── -->
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
      <button class="hbtn btn-orange" onclick="exportInv()" title="Export markdown">⬇ export</button>
      <button class="drawer-close" onclick="closeDrawer()">×</button>
    </div>
  </div>
  <div class="drawer-tabs">
    <button class="dtab active" onclick="switchTab('timeline')">timeline</button>
    <button class="dtab" onclick="switchTab('evidence')">evidence</button>
    <button class="dtab" onclick="switchTab('targets')">targets</button>
    <button class="dtab" onclick="switchTab('actions')">actions</button>
    <button class="dtab" onclick="switchTab('briefing')">✦ briefing</button>
    <button class="dtab" onclick="switchTab('praxis')">praxis</button>
    <button class="dtab" onclick="switchTab('export')">export</button>
  </div>
  <div class="drawer-body">
    <!-- timeline -->
    <div class="drawer-pane active" id="pane-timeline">
      <div id="timeline-list"><div style="color:var(--text3);font-size:9px">loading…</div></div>
    </div>
    <!-- evidence -->
    <div class="drawer-pane" id="pane-evidence"><div id="evidence-list"></div></div>
    <!-- targets -->
    <div class="drawer-pane" id="pane-targets"><div id="targets-list"></div></div>
    <!-- actions -->
    <div class="drawer-pane" id="pane-actions">
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
          <input class="form-input" id="action-risk" type="number" min="1" max="10" placeholder="risk (1-10)">
          <button class="btn" onclick="submitUpdateInv()">update</button>
        </div>
        <div id="update-inv-msg"></div>
      </div>
      <div class="action-section">
        <div class="action-label">add note</div>
        <textarea class="form-textarea" id="action-note" placeholder="note content…"></textarea>
        <div class="form-row" style="margin-top:6px">
          <input class="form-input" id="action-note-tag" placeholder="tag (optional)">
          <button class="btn" onclick="submitNote()">save note</button>
        </div>
        <div id="note-msg"></div>
      </div>
      <div class="action-section">
        <div class="action-label">log timeline event</div>
        <div class="form-row">
          <input class="form-input" id="action-tl-event" placeholder="event description">
          <select class="form-select" id="action-tl-type">
            <option value="discovery">discovery</option>
            <option value="evidence_collected">evidence_collected</option>
            <option value="report_filed">report_filed</option>
            <option value="response_received">response_received</option>
            <option value="disclosed">disclosed</option>
            <option value="published">published</option>
            <option value="other">other</option>
          </select>
        </div>
        <div class="form-row" style="margin-top:4px">
          <button class="btn" onclick="submitTimeline()">log event</button>
        </div>
        <div id="tl-msg"></div>
      </div>
      <div class="action-section">
        <div class="action-label">add evidence</div>
        <div class="form-row">
          <input class="form-input" id="action-ev-title" placeholder="title / filename">
          <select class="form-select" id="action-ev-type">
            <option value="screenshot">screenshot</option>
            <option value="json">json</option>
            <option value="log">log</option>
            <option value="whois">whois</option>
            <option value="dns">dns</option>
            <option value="api_response">api_response</option>
            <option value="html">html</option>
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
    <!-- briefing generator -->
    <div class="drawer-pane" id="pane-briefing">
      <div id="api-key-prompt" style="display:none">
        <div class="key-prompt">
          ✦ Anthropic API key required for briefing generation.<br>
          Your key is stored only in this browser (localStorage) and sent directly to Anthropic — never to this server.
        </div>
        <div class="form-row">
          <input class="form-input" id="briefing-api-key" type="password" placeholder="sk-ant-…">
          <button class="btn" onclick="saveApiKey()">save key</button>
        </div>
      </div>
      <div id="briefing-ui">
        <div class="briefing-tabs">
          <button class="briefing-tab active" onclick="setBriefingMode('internal')" id="bmode-internal">internal</button>
          <button class="briefing-tab" onclick="setBriefingMode('devto')" id="bmode-devto">dev.to draft</button>
          <button class="briefing-tab" onclick="setBriefingMode('ioc')" id="bmode-ioc">ioc table</button>
        </div>
        <div class="form-row">
          <button class="btn" onclick="generateBriefing()" id="briefing-btn">✦ generate briefing</button>
          <button class="btn btn-ghost" onclick="clearApiKey()">clear key</button>
          <button class="btn btn-blue" id="praxis-publish-btn" onclick="runPraxisPublish()">praxis publish</button>
        </div>
        <div id="briefing-output" class="briefing-output" style="display:none"></div>
        <div style="display:flex;gap:6px;margin-top:6px;display:none" id="briefing-copy-row">
          <button class="btn btn-ghost" onclick="copyBriefing()">copy</button>
          <button class="btn btn-ghost" onclick="captureToPraxis()">→ praxis capture</button>
        </div>
      </div>
    </div>
    <!-- praxis -->
    <div class="drawer-pane" id="pane-praxis">
      <div class="action-section">
        <div class="action-label">praxis capture</div>
        <textarea class="form-textarea" id="praxis-text" placeholder="observation, IOC, or finding…" style="min-height:80px"></textarea>
        <div class="form-row" style="margin-top:6px">
          <input class="form-input" id="praxis-url" placeholder="source URL (optional)">
          <input class="form-input" id="praxis-tags" placeholder="tags (comma-sep)">
          <select class="form-select" id="praxis-confidence">
            <option value="3">confidence 3</option>
            <option value="1">1 — low</option>
            <option value="2">2</option>
            <option value="4">4</option>
            <option value="5">5 — confirmed</option>
          </select>
        </div>
        <button class="btn" onclick="submitPraxisCapture()">→ praxis capture</button>
        <div id="praxis-capture-msg"></div>
      </div>
      <div class="action-section">
        <div class="action-label">praxis timeline</div>
        <button class="btn btn-ghost" onclick="loadPraxisTimeline()">pull praxis timeline</button>
        <div id="praxis-timeline-output" style="margin-top:8px;font-size:9px;color:var(--text2);white-space:pre-wrap;max-height:200px;overflow-y:auto"></div>
      </div>
    </div>
    <!-- export -->
    <div class="drawer-pane" id="pane-export">
      <div class="action-section">
        <div class="action-label">markdown export</div>
        <div class="form-row">
          <button class="btn" onclick="loadExport()">generate export</button>
          <button class="btn btn-ghost" onclick="copyExport()">copy</button>
          <button class="btn btn-ghost" onclick="downloadExport()">download</button>
        </div>
        <div id="export-output" class="export-output" style="display:none"></div>
      </div>
    </div>
  </div>
</div>

<!-- ── ENRICHMENT PANEL ── -->
<div class="drawer-overlay" id="enrich-overlay" onclick="closeEnrich()"></div>
<div class="enrich-panel" id="enrich-panel">
  <div class="enrich-header">
    <div class="enrich-title">⬡ target enrichment</div>
    <button class="drawer-close" onclick="closeEnrich()">×</button>
  </div>
  <div class="enrich-body">
    <div class="form-row" style="margin-bottom:12px">
      <input class="form-input" id="enrich-input" placeholder="domain or IP address…">
      <button class="btn btn-blue" onclick="runEnrich()">run</button>
    </div>
    <div id="enrich-results"></div>
  </div>
</div>

<div class="toast" id="toast"></div>
<div class="kbd-hint">
  <span><span class="kbd">j/k</span> navigate</span>
  <span><span class="kbd">Enter</span> open</span>
  <span><span class="kbd">e</span> enrich</span>
  <span><span class="kbd">Esc</span> close</span>
  <span><span class="kbd">b</span> briefing</span>
  <span><span class="kbd">x</span> export</span>
</div>

<script>
// ── state ──────────────────────────────────────────────────────────────────
let currentInvId = null;
let activeTab    = 'timeline';
let invList      = [];
let focusedInvIdx = -1;
let briefingMode = 'internal';
let currentExportMd = '';

// ── clock ──────────────────────────────────────────────────────────────────
function updateClock() {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString('en-US',{hour12:false});
}
setInterval(updateClock,1000); updateClock();

// ── toast ──────────────────────────────────────────────────────────────────
function toast(msg, err=false) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (err?' err':'');
  setTimeout(()=>t.className='toast',2500);
}

// ── api ────────────────────────────────────────────────────────────────────
async function api(path, method='GET', body=null) {
  const opts = {method, headers:{'Content-Type':'application/json'}};
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  return r.json();
}

function ago(ts) {
  if (!ts) return '—';
  const s = Math.floor((new Date() - new Date(ts))/1000);
  if (s<60)    return s+'s ago';
  if (s<3600)  return Math.floor(s/60)+'m ago';
  if (s<86400) return Math.floor(s/3600)+'h ago';
  return Math.floor(s/86400)+'d ago';
}

function riskBadge(score) { return `<span class="risk-badge risk-${score}">${score}/10</span>`; }
function statusChip(status) { return `<span class="status-chip status-${status||'active'}">${status||'active'}</span>`; }

// ── main load ──────────────────────────────────────────────────────────────
async function loadAll() {
  try {
    const d = await api('/api/dashboard');
    renderMonitor(d.monitor);
    renderInvestigations(d.investigations);
    renderCorrelations(d.correlations);
    renderShenron(d.shenron);
    renderCanary(d.canary);
    renderPublishing(d.publishing);
    renderNightlyLog(d.nightly_log);
    document.getElementById('last-refresh').textContent = 'updated ' + ago(new Date().toISOString());
  } catch(e) { toast('load failed: '+e.message, true); }
}

function renderMonitor(m) {
  document.getElementById('total-alerts').textContent = m.total||'—';
  document.getElementById('total-snaps').textContent  = m.snapshots||'—';
  document.getElementById('alerts-ago').textContent   = ago(m.last_ts);

  const ipg = document.getElementById('ip-groups');
  ipg.innerHTML = '';
  (m.ips||[]).forEach(g => {
    const ips = (g.ips||'').split(',').filter(Boolean).filter((v,i,a)=>a.indexOf(v)===i).slice(0,4);
    if (!ips.length) return;
    ipg.innerHTML += `<div class="ip-group">
      <div class="ip-label">${g.target}</div>
      <div class="ip-tags">${ips.map(ip=>`<span class="ip-tag" onclick="openEnrichWith('${ip}')">${ip}</span>`).join('')}</div>
    </div>`;
  });

  const totalShown = (m.recent_alerts||[]).reduce((s,a)=>s+(a.count||1),0);
  const deduped = (m.recent_alerts||[]).length;
  if (totalShown > deduped) {
    document.getElementById('alert-dedup-note').textContent = `${totalShown} total → ${deduped} deduped`;
  }

  document.getElementById('alert-list').innerHTML = (m.recent_alerts||[]).map((a,i) => {
    const diffHtml = a.diff ? `<span style="font-size:8px;color:var(--yellow)" title="was: ${a.diff.from}">Δ</span>` : '';
    const countHtml = (a.count||1) > 1 ? `<span class="alert-count">×${a.count}</span>` : '<span></span>';
    return `<div class="alert-item" id="alert-${i}">
      <span class="alert-ts">${(a.created_at||'').replace('T',' ').slice(0,16)}</span>
      <span class="alert-type">${a.alert_type||''} ${diffHtml}</span>
      <span class="alert-val" title="${a.details||''}">${(a.details||'').slice(0,40)}</span>
      ${countHtml}
      <div class="triage-btns">
        <button class="tbtn tbtn-dismiss"  onclick="triageAlert(${i},'dismiss')">dis</button>
        <button class="tbtn tbtn-escalate" onclick="triageAlert(${i},'escalate')">esc</button>
        <button class="tbtn tbtn-tag"      onclick="triageAlert(${i},'tag')">tag</button>
      </div>
    </div>`;
  }).join('');
}

function renderInvestigations(invs) {
  invList = invs||[];
  const active = invList.filter(i=>i.status==='active').length;
  document.getElementById('inv-active-badge').textContent = active+' active';
  document.getElementById('inv-total').textContent = invList.length;

  document.getElementById('inv-tbody').innerHTML = invList.map((inv,idx) => {
    const stale = inv.days_stale;
    const ageBadge = stale > 7
      ? `<span class="age-badge age-stale">${stale}d</span>`
      : stale !== null ? `<span class="age-badge age-active">${stale}d</span>` : '—';
    return `<tr class="inv-row" id="inv-row-${idx}" onclick="openInv('${inv.inv_id||inv.id}',${idx})">
      <td class="inv-id">${inv.inv_id||inv.id}</td>
      <td>${riskBadge(inv.risk_score||0)}</td>
      <td>${statusChip(inv.status)}</td>
      <td class="inv-title">${inv.title||'—'}</td>
      <td class="inv-cat">${(inv.category||'').slice(0,16)}</td>
      <td>${ageBadge}</td>
      <td class="inv-arrow">›</td>
    </tr>`;
  }).join('');
}

function renderCorrelations(corr) {
  if (!corr) return;
  const edges = corr.edges||[];
  const shared = corr.shared_targets||[];
  document.getElementById('corr-badge').textContent = edges.length + ' links';
  const el = document.getElementById('corr-list');
  if (!edges.length && !shared.length) {
    el.innerHTML = '<div style="color:var(--text3);font-size:9px">no shared infrastructure detected</div>';
    return;
  }
  el.innerHTML = edges.map(e => `
    <div class="corr-edge" onclick="openInv('${e.a}')">
      <div class="corr-ids">${e.a} ↔ ${e.b} <span class="corr-strength">${e.strength} shared</span></div>
      <div class="corr-shared">${e.shared.slice(0,3).map(s=>`${s.value} (${s.kind})`).join(' · ')}</div>
    </div>`).join('') +
    shared.filter(t=>!edges.find(e=>e.shared.some(s=>s.value===t.value))).map(t=>`
    <div class="corr-edge" style="border-left-color:var(--yellow)">
      <div class="corr-ids" style="color:var(--yellow)">${t.value}</div>
      <div class="corr-shared">shared across: ${t.inv_ids}</div>
    </div>`).join('');
}

function renderShenron(s) {
  document.getElementById('shenron-stats').innerHTML = `
    <div class="shenron-stat"><div class="shenron-stat-label">LAYERS</div>
      <div class="shenron-stat-val">${s.layers||0}</div></div>
    <div class="shenron-stat"><div class="shenron-stat-label">VARIANTS</div>
      <div class="shenron-stat-val">${(s.payloads||0).toLocaleString()}</div></div>`;
  const hg = document.getElementById('shenron-health');
  hg.innerHTML = (s.health||[]).length===0
    ? '<div style="color:var(--text3);font-size:9px">no health data</div>'
    : (s.health||[]).map(h=>`<div class="health-item">
        <span class="health-name">${h.name}</span>
        <span class="health-dot ${h.status}"></span></div>`).join('');
}

function renderCanary(c) {
  const raw = c._raw||{};
  const rows = [
    {k:'crx version',v:c.crx_version||'—'},
    {k:'crx last check',v:(c.crx_checked||'—').slice(0,16)},
    {k:'operator repos',v:c.operator_repos||'—'},
    {k:'operator followers',v:c.operator_followers||'—'},
  ];
  const skip = new Set(['last_ext_version','last_ext_check','last_check','operator_repos',
    'last_operator_repos','operator_followers','last_operator_followers']);
  Object.entries(raw).forEach(([k,v])=>{
    if(!skip.has(k)&&!k.startsWith('last_ips'))
      rows.push({k,v:String(v).slice(0,40)});
  });
  document.getElementById('canary-rows').innerHTML = rows.map(r=>
    `<div class="canary-row"><span class="canary-key">${r.k}</span><span class="canary-val">${r.v}</span></div>`
  ).join('');
}

function renderPublishing(p) {
  document.getElementById('devto-followers').textContent = (p.followers||'—').toLocaleString?.() ?? p.followers;
  document.getElementById('devto-user').textContent = p.username||'gnomeman4201';
}

function renderNightlyLog(entries) {
  document.getElementById('nightly-log').innerHTML = (entries||[]).map(e => {
    const ts = (e.ts||'').slice(11,19) || '';
    const typeClass = e.type||'log';
    return `<div class="log-entry">
      <span class="log-ts">${ts}</span>
      <span class="log-type ${typeClass}">${e.type||'log'}</span>
      <span class="log-msg" title="${e.msg||''}">${e.msg||''}</span>
    </div>`;
  }).join('');
}

// ── keyboard navigation ────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  const tag = document.activeElement.tagName;
  if (['INPUT','TEXTAREA','SELECT'].includes(tag)) return;

  if (e.key === 'Escape') { closeDrawer(); closeEnrich(); return; }
  if (e.key === 'e' && !currentInvId) { openEnrich(); return; }
  if (e.key === 'b' && currentInvId) { switchTab('briefing'); return; }
  if (e.key === 'x' && currentInvId) { switchTab('export'); loadExport(); return; }

  if (e.key === 'j' || e.key === 'ArrowDown') {
    e.preventDefault();
    focusedInvIdx = Math.min(focusedInvIdx+1, invList.length-1);
    highlightInvRow(focusedInvIdx);
  }
  if (e.key === 'k' || e.key === 'ArrowUp') {
    e.preventDefault();
    focusedInvIdx = Math.max(focusedInvIdx-1, 0);
    highlightInvRow(focusedInvIdx);
  }
  if (e.key === 'Enter' && focusedInvIdx >= 0 && focusedInvIdx < invList.length) {
    const inv = invList[focusedInvIdx];
    openInv(inv.inv_id||inv.id, focusedInvIdx);
  }
});

function highlightInvRow(idx) {
  document.querySelectorAll('.inv-row').forEach(r=>r.classList.remove('focused'));
  const row = document.getElementById('inv-row-'+idx);
  if (row) { row.classList.add('focused'); row.scrollIntoView({block:'nearest'}); }
}

// ── investigation drawer ───────────────────────────────────────────────────
async function openInv(invId, idx=-1) {
  currentInvId = invId;
  if (idx >= 0) focusedInvIdx = idx;
  document.getElementById('drawer-inv-id').textContent = invId;
  document.getElementById('drawer-inv-title').textContent = 'loading…';
  document.getElementById('drawer-overlay').classList.add('open');
  document.getElementById('inv-drawer').classList.add('open');
  switchTab('timeline');
  checkApiKey();
  await loadInvDetail(invId);
}

function closeDrawer() {
  document.getElementById('drawer-overlay').classList.remove('open');
  document.getElementById('inv-drawer').classList.remove('open');
  currentInvId = null;
}

async function loadInvDetail(invId) {
  try {
    const d = await api('/api/inv/'+encodeURIComponent(invId));
    const inv = d.investigation||{};
    document.getElementById('drawer-inv-id').textContent    = inv.inv_id||invId;
    document.getElementById('drawer-inv-title').textContent = inv.title||'—';
    document.getElementById('drawer-risk-badge').innerHTML  = riskBadge(inv.risk_score||0);
    document.getElementById('drawer-status-chip').innerHTML = statusChip(inv.status);

    document.getElementById('timeline-list').innerHTML = (d.timeline||[]).length===0
      ? '<div style="color:var(--text3);font-size:9px">no timeline events</div>'
      : (d.timeline||[]).map(e=>`<div class="tl-item">
          <div class="tl-dot"></div>
          <div class="tl-content">
            <div class="tl-time">${(e.event_time||'').slice(0,19)} · ${e.event_type||''}</div>
            <div class="tl-event">${e.event||''}</div>
          </div></div>`).join('');

    document.getElementById('evidence-list').innerHTML = (d.evidence||[]).length===0
      ? '<div style="color:var(--text3);font-size:9px">no evidence logged</div>'
      : (d.evidence||[]).map(e=>`<div class="ev-item">
          <div class="ev-title">${e.title||'—'}</div>
          <div class="ev-meta">${e.evidence_type||''} · ${(e.collected_at||'').slice(0,10)}</div>
          ${e.notes?`<div style="font-size:9px;color:var(--text2);margin-top:4px">${e.notes}</div>`:''}`
          +`</div>`).join('');

    document.getElementById('targets-list').innerHTML = (d.targets||[]).length===0
      ? '<div style="color:var(--text3);font-size:9px">no targets logged</div>'
      : (d.targets||[]).map(t=>`<div class="ev-item">
          <div class="ev-title" style="cursor:pointer" onclick="openEnrichWith('${t.value||''}')">
            ${t.value||'—'} <span style="color:var(--dim);font-size:8px">↗ enrich</span>
          </div>
          <div class="ev-meta">${t.target_type||''} · ${t.role||''} · ${(t.added_at||'').slice(0,10)}</div>
        </div>`).join('');
  } catch(e) {
    document.getElementById('timeline-list').innerHTML =
      `<div style="color:var(--red);font-size:9px">error: ${e.message}</div>`;
  }
}

function switchTab(name) {
  activeTab = name;
  const tabs = ['timeline','evidence','targets','actions','briefing','praxis','export'];
  document.querySelectorAll('.dtab').forEach((t,i)=>t.className='dtab'+(tabs[i]===name?' active':''));
  document.querySelectorAll('.drawer-pane').forEach(p=>p.classList.remove('active'));
  document.getElementById('pane-'+name).classList.add('active');
}

// ── action submitters ──────────────────────────────────────────────────────
async function submitUpdateInv() {
  if (!currentInvId) return;
  const status = document.getElementById('action-status').value;
  const risk   = parseInt(document.getElementById('action-risk').value)||null;
  const msg    = document.getElementById('update-inv-msg');
  try {
    await api('/api/inv/update','POST',{inv_id:currentInvId,status,risk_score:risk});
    msg.innerHTML = `<div class="form-msg ok">updated</div>`;
    await loadAll(); await loadInvDetail(currentInvId); toast('updated');
  } catch(e) { msg.innerHTML=`<div class="form-msg err">${e.message}</div>`; }
}

async function submitNote() {
  if (!currentInvId) return;
  const note = document.getElementById('action-note').value.trim();
  const tag  = document.getElementById('action-note-tag').value.trim();
  if (!note) return;
  const msg = document.getElementById('note-msg');
  try {
    await api('/api/inv/note','POST',{inv_id:currentInvId,content:note,tag});
    msg.innerHTML=`<div class="form-msg ok">note saved</div>`;
    document.getElementById('action-note').value='';
    await loadInvDetail(currentInvId); toast('note saved');
  } catch(e) { msg.innerHTML=`<div class="form-msg err">${e.message}</div>`; }
}

async function submitTimeline() {
  if (!currentInvId) return;
  const event = document.getElementById('action-tl-event').value.trim();
  const type  = document.getElementById('action-tl-type').value;
  if (!event) return;
  const msg = document.getElementById('tl-msg');
  try {
    await api('/api/inv/timeline','POST',{inv_id:currentInvId,event,event_type:type});
    msg.innerHTML=`<div class="form-msg ok">logged</div>`;
    document.getElementById('action-tl-event').value='';
    await loadInvDetail(currentInvId); toast('event logged');
  } catch(e) { msg.innerHTML=`<div class="form-msg err">${e.message}</div>`; }
}

async function submitEvidence() {
  if (!currentInvId) return;
  const title = document.getElementById('action-ev-title').value.trim();
  const type  = document.getElementById('action-ev-type').value;
  const notes = document.getElementById('action-ev-notes').value.trim();
  if (!title) return;
  const msg = document.getElementById('ev-msg');
  try {
    await api('/api/inv/evidence','POST',{inv_id:currentInvId,title,evidence_type:type,notes});
    msg.innerHTML=`<div class="form-msg ok">evidence logged</div>`;
    document.getElementById('action-ev-title').value='';
    document.getElementById('action-ev-notes').value='';
    await loadInvDetail(currentInvId); toast('evidence logged');
  } catch(e) { msg.innerHTML=`<div class="form-msg err">${e.message}</div>`; }
}

// ── triage ─────────────────────────────────────────────────────────────────
async function triageAlert(idx, action) {
  const row = document.getElementById('alert-'+idx);
  const ts  = row?.querySelector('.alert-ts')?.textContent;
  const typ = row?.querySelector('.alert-type')?.textContent;
  try {
    await api('/api/alert/triage','POST',{idx,action,ts,alert_type:typ});
    if (action==='dismiss') { row.style.opacity='.3'; row.style.textDecoration='line-through'; }
    else if (action==='escalate') { row.style.borderLeftColor='var(--orange)'; row.style.background='#1a0a00'; }
    else { row.style.borderLeftColor='var(--blue)'; }
    toast(action+' applied');
  } catch(e) { toast('triage failed',true); }
}

// ── enrichment ─────────────────────────────────────────────────────────────
function openEnrich()  { document.getElementById('enrich-overlay').classList.add('open'); document.getElementById('enrich-panel').classList.add('open'); document.getElementById('enrich-input').focus(); }
function closeEnrich() { document.getElementById('enrich-overlay').classList.remove('open'); document.getElementById('enrich-panel').classList.remove('open'); }

function openEnrichWith(target) {
  document.getElementById('enrich-input').value = target;
  document.getElementById('quick-enrich-input').value = target;
  openEnrich(); runEnrich();
}
function quickEnrich() {
  const t = document.getElementById('quick-enrich-input').value.trim();
  if (!t) return;
  document.getElementById('enrich-input').value = t;
  openEnrich(); runEnrich();
}
document.getElementById('enrich-input').addEventListener('keydown',e=>{if(e.key==='Enter')runEnrich();});
document.getElementById('quick-enrich-input').addEventListener('keydown',e=>{if(e.key==='Enter')quickEnrich();});

async function runEnrich() {
  const target = document.getElementById('enrich-input').value.trim();
  if (!target) return;
  const res = document.getElementById('enrich-results');
  res.innerHTML = `<div style="color:var(--blue)">⬡ enriching ${target}…</div>`;
  try {
    const d = await api('/api/enrich','POST',{target});
    if (d.error) { res.innerHTML=`<div style="color:var(--red)">error: ${d.error}</div>`; return; }
    let html = '';
    if (d.dns_a?.length) html+=`<div class="enrich-section"><div class="enrich-section-label">A RECORDS</div><div class="enrich-code">${d.dns_a.join('\n')}</div></div>`;
    if (d.dns_txt?.length) html+=`<div class="enrich-section"><div class="enrich-section-label">TXT RECORDS</div><div class="enrich-code">${d.dns_txt.join('\n')}</div></div>`;
    if (d.virustotal&&!d.virustotal.note) html+=`<div class="enrich-section"><div class="enrich-section-label">VIRUSTOTAL</div><div class="enrich-code">${JSON.stringify(d.virustotal,null,2)}</div></div>`;
    if (d.whois) html+=`<div class="enrich-section"><div class="enrich-section-label">WHOIS</div><div class="enrich-code">${d.whois.substring(0,2000)}</div></div>`;
    html+=`<div class="enrich-actions">`;
    if (currentInvId) html+=`<button class="btn btn-blue" onclick="captureEnrichToPraxis('${target}')">→ praxis capture</button>`;
    html+=`</div>`;
    html+=`<div style="color:var(--text3);font-size:8px;margin-top:8px">enriched at ${d.enriched_at}</div>`;
    res.innerHTML = html;
  } catch(e) { res.innerHTML=`<div style="color:var(--red)">error: ${e.message}</div>`; }
}

async function captureEnrichToPraxis(target) {
  if (!currentInvId) return;
  const r = await api('/api/praxis/capture','POST',{
    text:`Enrichment run on target: ${target}`,
    inv_id: currentInvId, tags:'enrichment,infra', confidence:3
  });
  toast(r.ok ? 'captured to PRAXIS: '+r.praxis_id : 'PRAXIS error: '+r.error, !r.ok);
}

// ── PRAXIS tab ─────────────────────────────────────────────────────────────
async function submitPraxisCapture() {
  if (!currentInvId) return;
  const text = document.getElementById('praxis-text').value.trim();
  const url  = document.getElementById('praxis-url').value.trim();
  const tags = document.getElementById('praxis-tags').value.trim();
  const conf = document.getElementById('praxis-confidence').value;
  if (!text) return;
  const msg = document.getElementById('praxis-capture-msg');
  try {
    const r = await api('/api/praxis/capture','POST',{text,inv_id:currentInvId,tags,confidence:parseInt(conf),url});
    if (r.ok) {
      msg.innerHTML=`<div class="form-msg ok">captured → ${r.praxis_id}</div>`;
      document.getElementById('praxis-text').value='';
      toast('PRAXIS: '+r.praxis_id);
    } else {
      msg.innerHTML=`<div class="form-msg err">${r.error}</div>`;
    }
  } catch(e) { msg.innerHTML=`<div class="form-msg err">${e.message}</div>`; }
}

async function loadPraxisTimeline() {
  if (!currentInvId) return;
  const el = document.getElementById('praxis-timeline-output');
  el.textContent = 'loading…';
  try {
    const r = await api('/api/praxis/timeline','POST',{inv_id:currentInvId});
    if (r.error) { el.textContent='error: '+r.error; return; }
    el.textContent = r.timeline_md || JSON.stringify(r.timeline,null,2);
  } catch(e) { el.textContent='error: '+e.message; }
}

// ── briefing generator (client-side Claude API) ────────────────────────────
function checkApiKey() {
  const key = localStorage.getItem('anthropic_key');
  document.getElementById('api-key-prompt').style.display = key ? 'none' : 'block';
  document.getElementById('briefing-ui').style.display    = key ? 'block' : 'none';
}
function saveApiKey() {
  const k = document.getElementById('briefing-api-key').value.trim();
  if (!k.startsWith('sk-ant')) { toast('invalid key format',true); return; }
  localStorage.setItem('anthropic_key', k);
  checkApiKey(); toast('key saved');
}
function clearApiKey() { localStorage.removeItem('anthropic_key'); checkApiKey(); toast('key cleared'); }
function setBriefingMode(mode) {
  briefingMode = mode;
  document.querySelectorAll('.briefing-tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('bmode-'+mode)?.classList.add('active');
}

async function generateBriefing() {
  const key = localStorage.getItem('anthropic_key');
  if (!key || !currentInvId) return;
  const btn = document.getElementById('briefing-btn');
  const out = document.getElementById('briefing-output');
  const copyRow = document.getElementById('briefing-copy-row');
  btn.innerHTML = '<span class="spinner">⟳</span> generating…';
  btn.disabled = true;
  out.style.display='block'; out.textContent='';

  // gather investigation data
  const d = await api('/api/inv/'+encodeURIComponent(currentInvId));
  const inv = d.investigation||{};

  const summaryCtx = `
Investigation: ${inv.inv_id} — ${inv.title}
Status: ${inv.status} | Risk: ${inv.risk_score}/10 | Category: ${inv.category||inv.threat_class}
Opened: ${inv.created_at||inv.opened_at}

TIMELINE (${(d.timeline||[]).length} events):
${(d.timeline||[]).slice(0,30).map(e=>`[${(e.event_time||'').slice(0,10)}] ${e.event_type}: ${e.event}`).join('\n')}

TARGETS (${(d.targets||[]).length}):
${(d.targets||[]).slice(0,20).map(t=>`${t.target_type}: ${t.value} (${t.role})`).join('\n')}

EVIDENCE (${(d.evidence||[]).length} items):
${(d.evidence||[]).slice(0,15).map(e=>`${e.evidence_type}: ${e.title} — ${e.notes}`).join('\n')}

NOTES:
${(d.notes||[]).slice(0,5).map(n=>`[${n.tag}] ${n.content}`).join('\n')}
`.trim();

  const prompts = {
    internal: `You are a security researcher writing an internal investigation briefing for the badBANANA Research Collective. Based on the following investigation data, write a structured internal briefing with sections: EXECUTIVE SUMMARY, THREAT ACTOR PROFILE, INFRASTRUCTURE ANALYSIS, KEY FINDINGS, IOC TABLE (markdown table with Type/Value/Confidence/Notes), RECOMMENDED NEXT STEPS.\n\nInvestigation data:\n${summaryCtx}`,
    devto: `You are GnomeMan4201, a self-taught security researcher writing for dev.to. Based on the following investigation data, write a compelling, technically detailed dev.to article draft. Include: a hook opening paragraph, background context, methodology, key findings with technical detail, IOCs, and a conclusion. Use markdown formatting suitable for dev.to. Voice: direct, technical, first-person.\n\nInvestigation data:\n${summaryCtx}`,
    ioc: `Based on the following investigation data, extract and format ALL indicators of compromise (IOCs) into a structured markdown table with columns: Type | Value | Confidence (1-5) | First Seen | Context/Notes. Be thorough.\n\nInvestigation data:\n${summaryCtx}`,
  };

  try {
    const resp = await fetch('https://api.anthropic.com/v1/messages', {
      method:'POST',
      headers:{
        'Content-Type':'application/json',
        'x-api-key': key,
        'anthropic-version':'2023-06-01',
        'anthropic-dangerous-direct-browser-access':'true',
      },
      body: JSON.stringify({
        model:'claude-sonnet-4-20250514',
        max_tokens:2000,
        messages:[{role:'user',content:prompts[briefingMode]}]
      })
    });
    const data = await resp.json();
    if (data.error) { out.textContent='API error: '+data.error.message; return; }
    const text = data.content?.[0]?.text || 'no response';
    out.textContent = text;
    copyRow.style.display='flex';
    // log to nightly
    await api('/api/nightly/log','POST',{type:'briefing',msg:`Briefing generated: ${currentInvId} (${briefingMode})`,inv_id:currentInvId});
    toast('briefing generated');
  } catch(e) {
    out.textContent = 'error: '+e.message;
  } finally {
    btn.innerHTML='✦ generate briefing'; btn.disabled=false;
  }
}

function copyBriefing() {
  const text = document.getElementById('briefing-output').textContent;
  navigator.clipboard.writeText(text).then(()=>toast('copied'));
}

async function captureToPraxis() {
  const text = document.getElementById('briefing-output').textContent.slice(0,500);
  if (!text || !currentInvId) return;
  const r = await api('/api/praxis/capture','POST',{
    text:`Briefing draft: ${text}`,
    inv_id:currentInvId, tags:'briefing,draft', confidence:3
  });
  toast(r.ok?'captured to PRAXIS':'PRAXIS error',!r.ok);
}

async function runPraxisPublish() {
  if (!currentInvId) return;
  const out = document.getElementById('briefing-output');
  out.style.display='block';
  out.textContent='running praxis publish…';
  try {
    const r = await api('/api/praxis/publish','POST',{inv_id:currentInvId,format:'devto'});
    out.textContent = r.output || r.error || 'no output';
    toast('praxis publish done');
  } catch(e) { out.textContent='error: '+e.message; }
}

// ── export ─────────────────────────────────────────────────────────────────
async function exportInv() { switchTab('export'); await loadExport(); }

async function loadExport() {
  if (!currentInvId) return;
  const el = document.getElementById('export-output');
  el.style.display='block'; el.textContent='generating…';
  try {
    const r = await api('/api/inv/export','POST',{inv_id:currentInvId});
    currentExportMd = r.markdown||'';
    el.textContent = currentExportMd;
  } catch(e) { el.textContent='error: '+e.message; }
}

function copyExport() {
  navigator.clipboard.writeText(currentExportMd).then(()=>toast('copied'));
}

function downloadExport() {
  if (!currentExportMd) return;
  const blob = new Blob([currentExportMd],{type:'text/markdown'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = (currentInvId||'investigation')+'-export.md';
  a.click();
}

// ── theme ──────────────────────────────────────────────────────────────────
const PRESETS=[
  {name:'terminal',hue:120,sat:100,bri:60},{name:'amber',hue:38,sat:100,bri:62},
  {name:'ice',hue:195,sat:90,bri:65},{name:'red',hue:0,sat:90,bri:55},
  {name:'violet',hue:270,sat:80,bri:65},{name:'ghost',hue:200,sat:20,bri:70},
  {name:'toxic',hue:80,sat:100,bri:65},{name:'solar',hue:55,sat:95,bri:68},
];
function hslPalette(h,s,b){const p=(ls,lb)=>`hsl(${h},${Math.round(s*ls)}%,${Math.round(b*lb)}%)`;return{'--green':p(1,1),'--green2':p(.85,.85),'--green3':p(.75,.65),'--dim':p(.45,.5),'--dimmer':p(.3,.25),'--border2':p(.35,.2),'--border':p(.25,.12),'--text':p(.25,.9),'--text2':p(.35,.62),'--text3':p(.4,.42),'--bg3':`hsl(${h},10%,8%)`,'--bg2':`hsl(${h},10%,6%)`,'--bg':`hsl(${h},10%,4%)`};}
function applyTheme(h,s,b){const root=document.documentElement;Object.entries(hslPalette(h,s,b)).forEach(([k,v])=>root.style.setProperty(k,v));['hue','sat','bright'].forEach(n=>{const el=document.getElementById(n+'-slider');if(el)el.value=n==='hue'?h:n==='sat'?s:b;});document.getElementById('hue-val').textContent=h+'°';document.getElementById('sat-val').textContent=s+'%';document.getElementById('bright-val').textContent=b+'%';document.querySelectorAll('.preset-swatch').forEach(sw=>sw.classList.toggle('active',+sw.dataset.h===h&&+sw.dataset.s===s&&+sw.dataset.b===b));try{localStorage.setItem('gnome_theme',JSON.stringify({h,s,b}));}catch(e){}}
function loadPersistedTheme(){try{const t=JSON.parse(localStorage.getItem('gnome_theme'));if(t&&t.h!=null){applyTheme(t.h,t.s,t.b);return;}}catch(e){}applyTheme(120,100,60);}
function resetTheme(){applyTheme(120,100,60);}
function buildPresets(){document.getElementById('theme-presets').innerHTML=PRESETS.map(p=>`<div class="preset-swatch" title="${p.name}" style="background:hsl(${p.hue},${p.sat}%,${Math.round(p.bri*.8)}%)" data-h="${p.hue}" data-s="${p.sat}" data-b="${p.bri}" onclick="applyTheme(${p.hue},${p.sat},${p.bri})"></div>`).join('');}
function toggleThemePopover(){document.getElementById('theme-popover').classList.toggle('open');}
document.addEventListener('click',e=>{const pop=document.getElementById('theme-popover');const btn=document.getElementById('theme-toggle-btn');if(pop.classList.contains('open')&&!pop.contains(e.target)&&e.target!==btn)pop.classList.remove('open');});
['hue','sat','bright'].forEach(name=>{const el=document.getElementById(name+'-slider');if(el)el.addEventListener('input',()=>{applyTheme(+document.getElementById('hue-slider').value,+document.getElementById('sat-slider').value,+document.getElementById('bright-slider').value);});});
buildPresets(); loadPersistedTheme();

loadAll();
setInterval(loadAll,30000);
</script>
</body>
</html>"""

# ── HTTP handler ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def send_json(self, data, code=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",len(body))
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        n = int(self.headers.get("Content-Length",0))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/","/index.html"):
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type","text/html")
            self.send_header("Content-Length",len(body))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/dashboard":
            self.send_json({
                "monitor":        get_monitor_data(),
                "investigations": get_investigations(),
                "correlations":   get_correlations(),
                "shenron":        get_shenron(),
                "canary":         get_canary(),
                "publishing":     get_devto_followers(),
                "nightly_log":    get_nightly_log(15),
            })
        elif path.startswith("/api/inv/"):
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
            valid_statuses = {"active","pending","disclosed","archived"}
            if status and status not in valid_statuses:
                return self.send_json({"error":f"invalid status '{status}'"}, 400)
            if not inv_id:
                return self.send_json({"error":"missing inv_id"}, 400)
            rows = db(INVHUB_DB,"SELECT id FROM investigations WHERE inv_id=?",(inv_id,))
            if not rows: return self.send_json({"error":"not found"},404)
            row_id = rows[0]["id"]
            fields = []
            if status: fields.append(("status",status))
            if risk:   fields.append(("risk_score",int(risk)))
            if not fields: return self.send_json({"error":"nothing to update"},400)
            set_clause = ", ".join(f"{f}=?" for f,_ in fields)
            db_write(INVHUB_DB,f"UPDATE investigations SET {set_clause} WHERE id=?",
                     [v for _,v in fields]+[row_id])
            if status:
                db_write(INVHUB_DB,"INSERT INTO timeline_events (inv_id,event_type,description,occurred_at) VALUES (?,?,?,?)",
                         (row_id,"status_change",f"Status → '{status}' via mission control",now_iso()))
            log_event("action",f"Updated {inv_id}: {fields}",inv_id)
            self.send_json({"ok":True})

        elif path == "/api/inv/note":
            inv_id  = body.get("inv_id"); content = body.get("content","").strip()
            tag     = body.get("tag","")
            if not inv_id or not content: return self.send_json({"error":"missing fields"},400)
            rows = db(INVHUB_DB,"SELECT id FROM investigations WHERE inv_id=?",(inv_id,))
            if not rows: return self.send_json({"error":"not found"},404)
            row_id = rows[0]["id"]
            db_write(INVHUB_DB,"INSERT INTO case_notes (inv_id,content_md,tag,created_at) VALUES (?,?,?,?)",
                     (row_id,content,tag,now_iso()))
            db_write(INVHUB_DB,"INSERT INTO timeline_events (inv_id,event_type,description,occurred_at) VALUES (?,?,?,?)",
                     (row_id,"note_added","Note added via mission control",now_iso()))
            log_event("action",f"Note added to {inv_id}",inv_id)
            self.send_json({"ok":True})

        elif path == "/api/inv/timeline":
            inv_id = body.get("inv_id"); desc = body.get("event","").strip()
            etype  = body.get("event_type","other")
            if not inv_id or not desc: return self.send_json({"error":"missing fields"},400)
            valid_e = {"discovery","evidence_collected","report_filed","response_received",
                       "disclosed","published","note_added","target_added","status_change","other"}
            if etype not in valid_e: etype = "other"
            rows = db(INVHUB_DB,"SELECT id FROM investigations WHERE inv_id=?",(inv_id,))
            if not rows: return self.send_json({"error":"not found"},404)
            row_id = rows[0]["id"]
            db_write(INVHUB_DB,"INSERT INTO timeline_events (inv_id,event_type,description,occurred_at) VALUES (?,?,?,?)",
                     (row_id,etype,desc,now_iso()))
            self.send_json({"ok":True})

        elif path == "/api/inv/evidence":
            inv_id = body.get("inv_id"); title = body.get("title","").strip()
            etype  = body.get("evidence_type","other"); notes = body.get("notes","").strip()
            if not inv_id or not title: return self.send_json({"error":"missing fields"},400)
            valid_e = {"screenshot","json","log","whois","dns","api_response","pcap","html","binary","other"}
            if etype not in valid_e: etype = "other"
            rows = db(INVHUB_DB,"SELECT id FROM investigations WHERE inv_id=?",(inv_id,))
            if not rows: return self.send_json({"error":"not found"},404)
            row_id = rows[0]["id"]
            ts_str = now_iso().replace(":","").replace("-","")
            safe   = re.sub(r'[^a-zA-Z0-9._-]','_',title)
            canon  = f"manual/{inv_id}/{ts_str}_{safe}"
            sha    = hashlib.sha256(f"{title}{notes}{ts_str}".encode()).hexdigest()
            db_write(INVHUB_DB,"""INSERT INTO evidence
                (inv_id,filename,original_path,canonical_path,type,description,sha256,integrity_status,ingested_at)
                VALUES (?,?,?,?,?,?,?,'unverified',?)""",
                (row_id,title,notes or "mission-control",canon,etype,notes or title,sha,now_iso()))
            db_write(INVHUB_DB,"INSERT INTO timeline_events (inv_id,event_type,description,occurred_at) VALUES (?,?,?,?)",
                     (row_id,"evidence_collected",f"Evidence logged: {title}",now_iso()))
            log_event("capture",f"Evidence: {title} → {inv_id}",inv_id)
            self.send_json({"ok":True})

        elif path == "/api/alert/triage":
            action = body.get("action",""); ts = body.get("ts",""); atype = body.get("alert_type","")
            log_event("triage",f"TRIAGE {action.upper()} [{atype}] {ts}")
            self.send_json({"ok":True})

        elif path == "/api/enrich":
            target = body.get("target","").strip()
            if not target: return self.send_json({"error":"no target"},400)
            try:
                results = enrich_target(target)
                log_event("enrich",f"Enriched: {target}")
                self.send_json(results)
            except Exception as e:
                self.send_json({"error":str(e)},500)

        elif path == "/api/praxis/capture":
            text  = body.get("text","").strip()
            inv_id = body.get("inv_id")
            tags  = body.get("tags","")
            conf  = body.get("confidence",3)
            url   = body.get("url")
            if not text: return self.send_json({"error":"no text"},400)
            r = praxis_capture(text, inv_id, tags, conf, url)
            if r.get("ok"):
                log_event("capture",f"PRAXIS {r.get('praxis_id','')} ← {text[:60]}",inv_id)
            self.send_json(r)

        elif path == "/api/praxis/timeline":
            inv_id = body.get("inv_id")
            if not inv_id: return self.send_json({"error":"no inv_id"},400)
            self.send_json(praxis_timeline(inv_id))

        elif path == "/api/praxis/publish":
            inv_id = body.get("inv_id"); fmt = body.get("format","devto")
            if not inv_id: return self.send_json({"error":"no inv_id"},400)
            r = praxis_publish(inv_id, fmt)
            if r.get("ok"):
                log_event("briefing",f"PRAXIS publish: {inv_id} ({fmt})",inv_id)
            self.send_json(r)

        elif path == "/api/inv/export":
            inv_id = body.get("inv_id")
            if not inv_id: return self.send_json({"error":"no inv_id"},400)
            md = export_investigation(inv_id)
            log_event("action",f"Export: {inv_id}",inv_id)
            self.send_json({"markdown":md})

        elif path == "/api/nightly/log":
            event_type = body.get("type","log")
            msg        = body.get("msg","")
            inv_id     = body.get("inv_id")
            log_event(event_type, msg, inv_id)
            self.send_json({"ok":True})

        else:
            self.send_response(404); self.end_headers()

# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    PORT = 7333
    NIGHTLY_LOG.parent.mkdir(parents=True, exist_ok=True)
    server = HTTPServer(("", PORT), Handler)
    print(f"gnome // mission control v10")
    print(f"http://localhost:{PORT}")
    print(f"monitor db : {MONITOR_DB}")
    print(f"inv-hub db : {INVHUB_DB}")
    print(f"SHENRON    : {SHENRON_DIR}")
    print(f"PRAXIS     : {PRAXIS_BIN} ({'ok' if PRAXIS_BIN.exists() else 'NOT FOUND'})")
    print(f"DEV.TO key : {'set' if DEVTO_KEY else 'not set'}")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.shutdown()
