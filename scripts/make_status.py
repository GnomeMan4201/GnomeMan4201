#!/usr/bin/env python3
"""Builds assets/evidence-status.svg from the public CISA KEV feed.
Missing data is never shown as zero: a failed fetch renders as UNAVAILABLE."""
import json, os, re, sys, urllib.request
from datetime import datetime, timedelta, timezone
from html import escape

URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
OUT, STATE = "assets/evidence-status.svg", "data/evidence-status.json"
CVE = re.compile(r"^CVE-\d{4}-\d{4,}$")

def fetch(path=None):
    if path:
        return json.load(open(path))
    req = urllib.request.Request(URL, headers={"User-Agent": "badBANANA-profile-status/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def summarize(d):
    ok, bad = [], 0
    for v in d["vulnerabilities"]:
        try:
            if not CVE.match(v["cveID"]):
                raise ValueError
            ok.append((v["cveID"], datetime.strptime(v["dateAdded"], "%Y-%m-%d").date()))
        except Exception:
            bad += 1
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).date()
    latest = max(ok, key=lambda x: x[1]) if ok else None
    return {"version": str(d.get("catalogVersion", "unknown")), "entries": len(ok), "rejected": bad,
            "week": sum(1 for _, dt in ok if dt >= cutoff),
            "latest_id": latest[0] if latest else None,
            "latest_date": latest[1].isoformat() if latest else None}

def render(state, s, fetched, last_good):
    ok = state == "OK"
    rows = ([("source", "CISA KEV, catalog " + s["version"]),
             ("entries", f'{s["entries"]:,} valid, {s["rejected"]} rejected'),
             ("added in 7 days", str(s["week"])),
             ("latest", f'{s["latest_id"]} ({s["latest_date"]})' if s["latest_id"] else "none valid")]
            if ok else
            [("source", "CISA KEV"),
             ("status", "fetch failed, no numbers shown"),
             ("last good", last_good or "never")])
    body = "".join(f'<text class="k" x="20" y="{74+i*24}">{escape(k)}</text><text class="v" x="150" y="{74+i*24}">{escape(v)}</text>'
                   for i, (k, v) in enumerate(rows))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="190" viewBox="0 0 480 190" role="img" aria-label="Evidence snapshot: {state}">
<style>
.bg{{fill:#161b22;stroke:#30363d;stroke-width:1.5}}.bar{{fill:#c2415d}}
.t{{fill:#e6edf3;font:bold 13px 'Courier New',monospace;letter-spacing:3px}}
.k{{fill:#8b949e;font:12px 'Courier New',monospace}}.v{{fill:#e6edf3;font:12px 'Courier New',monospace}}
.s{{font:bold 12px 'Courier New',monospace;fill:{"#56d364" if ok else "#ff7b8f"}}}
.f{{fill:#8b949e;font:11px 'Courier New',monospace}}
@media (prefers-color-scheme: light){{.bg{{fill:#f6f1e7;stroke:#d8cfbd}}.bar{{fill:#800020}}.t,.v{{fill:#2b2420}}.k,.f{{fill:#6d6354}}.s{{fill:{"#1a7f37" if ok else "#b42318"}}}}}
</style>
<rect class="bg" x="1" y="1" width="478" height="188" rx="8"/>
<rect class="bar" x="1" y="14" width="5" height="34" rx="2"/>
<text class="t" x="20" y="36">EVIDENCE SNAPSHOT</text>
<text class="s" x="460" y="36" text-anchor="end">{state}</text>
{body}
<text class="f" x="20" y="176">fetched {escape(fetched)} UTC. measure first. attribute last.</text>
</svg>'''

def main():
    inp = sys.argv[sys.argv.index("--input") + 1] if "--input" in sys.argv else None
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    old = json.load(open(STATE)) if os.path.exists(STATE) else {}
    try:
        s = summarize(fetch(inp))
        svg, new = render("OK", s, now, None), {"last_good_utc": now, "summary": s}
    except Exception as e:
        print("fetch failed:", type(e).__name__, file=sys.stderr)
        svg = render("UNAVAILABLE", None, now, old.get("last_good_utc"))
        new = old
    os.makedirs("assets", exist_ok=True); os.makedirs("data", exist_ok=True)
    open(OUT, "w").write(svg); json.dump(new, open(STATE, "w"), indent=2)

main()
