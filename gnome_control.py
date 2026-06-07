#!/usr/bin/env python3
"""
gnome_control.py — operator mission control server
Aggregates: badBANANA monitor, inv-hub, SHENRON, DEV.to canary, GitHub canary
Serves JSON API + static dashboard at http://localhost:7333

Usage:
    python3 gnome_control.py
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT      = 7333
HOME      = Path.home()
ROOT      = Path(__file__).parent.resolve()
DASH      = ROOT / "gnome_control.html"

# Paths
BANANA_DB    = HOME / ".badbanana" / "monitor.db"
CANARY       = HOME / ".canary_state"
NIGHTLY_LOG  = HOME / "research_hub" / "cases" / "devto_growth_network" / "logs" / "nightly.log"
SHENRON_LOG  = HOME / "SHENRON" / "logs" / "mutation_history.json"
SHENRON_REPO = HOME / "research_hub" / "repos" / "shenron"
INV_HUB      = HOME / "research_hub" / "repos" / "inv-hub"

_cache     = {}
_cache_ts  = 0
_lock      = threading.Lock()
CACHE_TTL  = 20


# ── HELPERS ───────────────────────────────────────────────────────────────────

def read_file(path, default=""):
    try:
        return Path(path).read_text(errors="replace").strip()
    except Exception:
        return default

def read_canary(key):
    return read_file(CANARY / key)

def run_cmd(cmd, timeout=8):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""

def db_query(db_path, sql, default=None):
    try:
        con = sqlite3.connect(str(db_path))
        cur = con.execute(sql)
        rows = cur.fetchall()
        con.close()
        return rows
    except Exception:
        return default or []


# ── DATA COLLECTORS ───────────────────────────────────────────────────────────

def collect_banana():
    if not BANANA_DB.exists():
        return {"ok": False, "error": "monitor.db not found"}

    # Alert stats
    total_alerts = db_query(BANANA_DB, "SELECT COUNT(*) FROM alerts")[0][0] if db_query(BANANA_DB, "SELECT COUNT(*) FROM alerts") else 0
    last_alert   = db_query(BANANA_DB, "SELECT MAX(timestamp) FROM alerts")
    last_alert   = last_alert[0][0] if last_alert else None
    recent_alerts= db_query(BANANA_DB, "SELECT timestamp, alert_type, details FROM alerts ORDER BY timestamp DESC LIMIT 10")

    # DNS state
    nsboost_ips = db_query(BANANA_DB, "SELECT a_records, timestamp FROM infra_snapshots WHERE domain='nsboost.xyz' ORDER BY timestamp DESC LIMIT 1")
    upvote_ips  = db_query(BANANA_DB, "SELECT a_records, timestamp FROM infra_snapshots WHERE domain='upvote.club' ORDER BY timestamp DESC LIMIT 1")
    snap_count  = db_query(BANANA_DB, "SELECT COUNT(*) FROM infra_snapshots")[0][0] if db_query(BANANA_DB, "SELECT COUNT(*) FROM infra_snapshots") else 0

    # Monitor service
    monitor_status = run_cmd("systemctl --user is-active badbanana-monitor.service 2>/dev/null || echo 'unknown'")

    # Canary states
    crx_log     = read_canary("crx/run.log").splitlines()
    crx_version = ""
    for line in reversed(crx_log):
        m = re.search(r'no change \(([^)]+)\)|version[:\s]+([^\s]+)', line, re.I)
        if m:
            crx_version = m.group(1) or m.group(2)
            break
    crx_last    = crx_log[-1] if crx_log else ""

    op_log      = read_canary("operator/run.log").splitlines()
    op_last     = op_log[-1] if op_log else ""
    op_repos    = ""
    op_followers= ""
    if op_last:
        m = re.search(r'repos=(\d+)\s+followers=(\d+)', op_last)
        if m:
            op_repos, op_followers = m.group(1), m.group(2)

    carox_log   = read_canary("carox/run.log").splitlines()
    carox_last  = carox_log[-1] if carox_log else ""

    ozon_log    = read_canary("ozontech/run.log")
    ozon_last   = ozon_log.splitlines()[-1] if ozon_log else ""

    # Nightly log
    nightly_entries = []
    if NIGHTLY_LOG.exists():
        lines = NIGHTLY_LOG.read_text(errors="replace").splitlines()
        for line in reversed(lines[-50:]):
            try:
                entry = json.loads(line)
                nightly_entries.append(entry)
                if len(nightly_entries) >= 5:
                    break
            except Exception:
                pass

    return {
        "ok":              True,
        "monitor_status":  monitor_status,
        "total_alerts":    total_alerts,
        "last_alert":      last_alert,
        "recent_alerts":   [{"ts": r[0], "type": r[1], "detail": r[2]} for r in recent_alerts],
        "snap_count":      snap_count,
        "nsboost_ips":     nsboost_ips[0][0] if nsboost_ips else "—",
        "nsboost_ts":      nsboost_ips[0][1] if nsboost_ips else "—",
        "upvote_ips":      upvote_ips[0][0] if upvote_ips else "—",
        "upvote_ts":       upvote_ips[0][1] if upvote_ips else "—",
        "crx_version":     crx_version or "unknown",
        "crx_last_check":  crx_last,
        "operator_repos":  op_repos,
        "operator_followers": op_followers,
        "operator_last":   op_last,
        "carox_last":      carox_last,
        "ozon_last":       ozon_last,
        "nightly":         nightly_entries,
    }


def collect_investigations():
    try:
        venv = INV_HUB / ".venv" / "bin" / "python3"
        py   = str(venv) if venv.exists() else sys.executable
        hub  = INV_HUB / "hub.py"
        if not hub.exists():
            return {"ok": False, "error": "inv-hub not found"}
        invs = []
        # Force wide terminal so hub.py renders full untruncated table
        wide_env = {**os.environ, "COLUMNS": "250", "TERM": "dumb"}
        try:
            result = subprocess.run(
                [py, str(hub), "list"],
                capture_output=True, text=True, timeout=12,
                cwd=str(INV_HUB), env=wide_env
            )
            list_out = result.stdout
        except Exception:
            list_out = ""
        inv_ids = re.findall(r'INV-\d+', list_out)

        # Parse the wide table output directly — columns are fixed-width
        # Format: INV-NNN   RISK   STATUS   THREAT_CLASS   TITLE   OPENED
        for line in list_out.splitlines():
            m = re.match(
                r'\s*(INV-\d+)\s+(\d+)\s+(\w+)\s+(\S+)\s{2,}(.+?)\s{2,}\d{4}-\d{2}',
                line
            )
            if m:
                invs.append({
                    "id":     m.group(1),
                    "risk":   int(m.group(2)),
                    "status": m.group(3).lower(),
                    "threat": m.group(4),
                    "title":  m.group(5).strip(),
                })

        tl = run_cmd(f"{py} {hub} timeline 2>/dev/null | wc -l", timeout=10)
        return {
            "ok":              True,
            "investigations":  invs,
            "timeline_events": tl.strip() if tl else "?",
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "investigations": []}


def collect_shenron():
    if not SHENRON_REPO.exists():
        return {"ok": False, "error": "shenron repo not found"}

    # Health — fast path: just check log + manifest
    manifest_path = SHENRON_REPO / "shenron_manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except Exception:
            pass

    layers       = len(manifest.get("layers", []))
    summary      = manifest.get("summary", {})
    detection    = summary.get("detection_coverage", "—")

    # Mutation log
    mutations = 0
    last_mutation = None
    if SHENRON_LOG.exists():
        try:
            log = json.loads(SHENRON_LOG.read_text())
            mutations = len(log)
            if log:
                last_mutation = log[-1].get("timestamp","")[:19]
        except Exception:
            pass

    # Unique payloads from log
    unique_payloads = 0
    if SHENRON_LOG.exists():
        try:
            log = json.loads(SHENRON_LOG.read_text())
            unique_payloads = len(set(e.get("payload","") for e in log if e.get("payload")))
        except Exception:
            pass

    # Run health check (fast)
    health_out = run_cmd(
        f"cd {SHENRON_REPO} && python3 shenron.py health 2>/dev/null",
        timeout=20
    )
    checks = []
    verdict = "unknown"
    for line in health_out.splitlines():
        line = line.strip()
        if '[~]' in line:
            # Interim line — completed result is appended after the last [~] block
            parts = re.split(r'\[~\][^\[]+', line)
            remainder = parts[-1].strip() if len(parts) > 1 else ''
            if remainder.startswith('[✓]') or remainder.startswith('[✗]'):
                passed = remainder.startswith('[✓]')
                rest   = remainder[3:].strip()
                name   = rest.split()[0] if rest.split() else rest
                if name and len(name) < 30:
                    checks.append({"name": name, "pass": passed})
            continue
        if line.startswith('[✓]') or line.startswith('[✗]'):
            passed = line.startswith('[✓]')
            rest   = line[3:].strip()
            name   = rest.split()[0] if rest.split() else rest
            if name and len(name) < 30 and name != 'VERDICT:':
                checks.append({"name": name, "pass": passed})
        if 'HEALTHY' in line and 'VERDICT' in line:
            verdict = 'healthy'
        elif ('DEGRADED' in line or 'UNHEALTHY' in line) and 'VERDICT' in line:
            verdict = 'degraded'
        elif 'VERDICT' in line and '[✓]' in line:
            verdict = 'healthy'
        elif 'VERDICT' in line and '[✗]' in line:
            verdict = 'degraded'


    return {
        "ok":              True,
        "layers":          layers,
        "mutations":       mutations,
        "unique_payloads": unique_payloads,
        "last_mutation":   last_mutation,
        "detection":       str(detection),
        "health":          checks,
        "verdict":         verdict,
    }


def collect_publishing():
    # Fetch DEV.to followers live if API key available
    followers = ""
    api_key = os.environ.get("DEVTO_API_KEY", "")
    if api_key:
        try:
            import urllib.request as _ur
            # Use followers endpoint — count pages until empty
            page, total = 1, 0
            while True:
                url = f"https://dev.to/api/followers/users?per_page=1000&page={page}"
                req = _ur.Request(url, headers={
                    "api-key": api_key,
                    "Accept": "application/json",
                    "User-Agent": "gnome-control/1.0"
                })
                with _ur.urlopen(req, timeout=8) as resp:
                    batch = json.loads(resp.read().decode())
                if not batch:
                    break
                total += len(batch)
                if len(batch) < 1000:
                    break
                page += 1
            if total > 0:
                followers = str(total)
        except Exception:
            pass
    if not followers:
        followers = read_canary("devto_followers")
    if not followers or "parse_error" in followers or followers == "False":
        followers = "—"

    gh_stars   = read_canary("gh_stars")
    gh_forks   = read_canary("gh_forks")
    gh_watchers= read_canary("gh_watchers")
    gh_pushed  = read_canary("gh_pushed")

    # GitHub traffic totals
    views_total  = read_canary("traffic_views_total")
    clones_total = read_canary("traffic_clones_total")
    views_uniq   = read_canary("traffic_views_unique")
    clones_uniq  = read_canary("traffic_clones_unique")

    # DEV.to from canary
    devto_field  = read_canary("devto_field")

    # Latest article metrics from canary (article IDs we know about)
    article_ids = ["3704010","3719966","3728239","3744276","3685944","3683707"]
    articles = []
    for aid in article_ids:
        views   = read_canary(f"devto_{aid}_views")
        reacts  = read_canary(f"devto_{aid}_reactions")
        comments= read_canary(f"devto_{aid}_comments")
        # Only include if we have non-zero data
        v = views if views and views not in ("0","") else None
        r = reacts if reacts and reacts not in ("0","") else None
        c = comments if comments and comments not in ("0","") else None
        if r or c:  # reactions/comments are more reliably cached
            articles.append({
                "id":       aid,
                "views":    v or "—",
                "reactions":r or "0",
                "comments": c or "0",
            })

    # Mark stale values
    def clean(v, field=""):
        if not v or v in ("0","False","parse_error",""):
            return "—"
        return v

    return {
        "ok":           True,
        "followers":    followers,
        "gh_stars":     clean(gh_stars),
        "gh_forks":     clean(gh_forks),
        "gh_watchers":  clean(gh_watchers),
        "gh_pushed":    gh_pushed or "—",
        "views_total":  clean(views_total),
        "clones_total": clean(clones_total),
        "views_unique": clean(views_uniq),
        "clones_unique":clean(clones_uniq),
        "devto_field":  devto_field if devto_field and devto_field != "False" else "—",
        "articles":     articles,
        "traffic_stale": gh_pushed and gh_pushed < "2026-06-01",
    }


def build_data():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] collecting...")
    t0 = time.time()

    banana  = collect_banana()
    invs    = collect_investigations()
    shenron = collect_shenron()
    pub     = collect_publishing()

    elapsed = time.time() - t0
    print(f"[{datetime.now().strftime('%H:%M:%S')}] done in {elapsed:.1f}s — "
          f"alerts={banana.get('total_alerts',0)} "
          f"invs={len(invs.get('investigations',[]))} "
          f"mutations={shenron.get('mutations',0)}")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "banana":       banana,
        "investigations": invs,
        "shenron":      shenron,
        "publishing":   pub,
    }


def get_cached():
    global _cache_ts
    now = time.time()
    with _lock:
        if now - _cache_ts > CACHE_TTL or not _cache:
            data = build_data()
            _cache.clear()
            _cache.update(data)
            _cache_ts = now
    return dict(_cache)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._file(DASH, "text/html")
        elif self.path == "/api/data":
            self._json(get_cached())
        elif self.path == "/api/refresh":
            global _cache_ts; _cache_ts = 0
            self._json(get_cached())
        else:
            self.send_response(404); self.end_headers()

    def _file(self, path, ct):
        if not Path(path).exists():
            self.send_response(404); self.end_headers()
            self.wfile.write(b"not found"); return
        data = Path(path).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj):
        data = json.dumps(obj, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print(f"gnome mission control")
    print(f"  url:  http://localhost:{PORT}")
    print(f"  ttl:  {CACHE_TTL}s")
    print()
    threading.Thread(target=get_cached, daemon=True).start()
    try:
        HTTPServer(("", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped")
