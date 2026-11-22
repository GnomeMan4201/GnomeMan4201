#!/usr/bin/env python3
"""Builds assets/evidence-status.svg from the public CISA KEV feed.
Missing data is never shown as zero: a failed fetch renders as UNAVAILABLE."""
import json, os, re, sys, urllib.request
from datetime import date
from datetime import datetime, timedelta, timezone
from html import escape

URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
OUT, STATE = "assets/evidence-status.svg", "data/evidence-status.json"
CVE = re.compile(r"^CVE-\d{4}-\d{4,}$")
OBS_URL = "https://badbanana-threat-observatory.badbanana6969.workers.dev/api/status"
USER_AGENT = "badBANANA-profile-status/1.0"
SOURCE_NAMES = {
    "cisa-kev": "CISA KEV", "threatfox": "ThreatFox",
    "urlhaus": "URLhaus", "malwarebazaar": "MalwareBazaar",
}
SOURCE_STATUSES = {"healthy": "OK", "stale": "STALE", "offline": "OFFLINE", "disabled": "DISABLED"}


def fetch(path=None):
    if path:
        return json.load(open(path))
    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
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

def fetch_observatory():
    """One read-only request; no ingestion or other Observatory endpoints."""
    req = urllib.request.Request(OBS_URL, headers={"User-Agent": USER_AGENT}, method="GET")
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def parse_utc(value):
    if not isinstance(value, str) or not value:
        raise ValueError("Invalid timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp requires timezone")
    return parsed.astimezone(timezone.utc)


def validate_observatory(payload, now):
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        raise ValueError("Missing Observatory sources")
    if not isinstance(payload.get("ingestion"), dict) or not isinstance(payload.get("freshness"), dict):
        raise ValueError("Missing Observatory ingestion/freshness")
    ingestion, freshness = payload["ingestion"], payload["freshness"]
    mode, state = ingestion.get("mode"), freshness.get("state")
    if mode not in ("scheduled", "demand-driven") or state not in ("fresh", "stale", "offline", "disabled"):
        raise ValueError("Malformed Observatory ingestion/freshness")
    parse_utc(payload.get("generatedAt"))
    by_id = {}
    for entry in payload["sources"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError("Malformed Observatory source")
        source_id = entry["id"]
        if source_id in by_id:
            raise ValueError("Duplicate Observatory source")
        by_id[source_id] = entry
    if any(source_id not in by_id for source_id in SOURCE_NAMES):
        raise ValueError("Missing expected Observatory source")
    sources = []
    for source_id, display in SOURCE_NAMES.items():
        entry = by_id[source_id]
        raw_status, count = entry.get("status"), entry.get("recordCount")
        if raw_status not in SOURCE_STATUSES or type(count) is not int or count < 0:
            raise ValueError("Invalid source status or record count")
        if not isinstance(entry.get("name"), str) or not entry["name"] or type(entry.get("configured")) is not bool:
            raise ValueError("Invalid source name/configuration")
        if entry["configured"] is False and raw_status == "healthy":
            raise ValueError("Healthy source marked unconfigured")
        raw_success = entry.get("lastSuccess")
        if raw_success is None:
            if raw_status in ("healthy", "stale"):
                raise ValueError("Missing lastSuccess for healthy/stale source")
            success_date, age_days = None, None
        else:
            success_time = parse_utc(raw_success)
            if success_time > now:
                raise ValueError("Future lastSuccess")
            success_date = success_time.strftime("%Y-%m-%d")
            age_days = (now.date() - success_time.date()).days
        failures = entry.get("consecutiveFailures")
        if failures is not None and (type(failures) is not int or failures < 0):
            raise ValueError("Malformed source failure count")
        sources.append({"id": source_id, "name": display, "status": SOURCE_STATUSES[raw_status],
                        "lastSuccess": raw_success, "lastSuccessDate": success_date,
                        "recordCount": count, "consecutiveFailures": failures,
                        "ageDays": age_days})
    return {"generatedAt": payload["generatedAt"], "ingestionMode": mode,
            "freshnessState": state, "sources": sources}


def render_observatory(status, snapshot, last_good):
    """Append a separate stored-Observatory section below the unchanged CISA block."""
    heading = '<text class="t" x="20" y="218">OBSERVATORY SNAPSHOT (STORED, NOT LIVE)</text>'
    description = '<text class="f" x="20" y="237">Older stored counts may differ from live CISA KEV.</text>'
    divider = '<path d="M20 195H460" stroke="#30363d" stroke-width="1"/>'
    if status != "OK":
        return "\n".join((divider, heading, description,
            '<text class="s" x="20" y="267" style="fill:#ff7b8f">UNAVAILABLE</text>',
            f'<text class="f" x="20" y="288">last good {escape(last_good or "never")} UTC</text>'))
    lines = [divider, heading, description]
    lines.append('<text class="k" x="20" y="257">source</text><text class="k" x="143" y="257">state</text><text class="k" x="277" y="257">last success</text><text class="k" x="419" y="257">count</text>')
    for i, source in enumerate(snapshot["sources"]):
        y = 282 + 24 * i
        state_label = source["status"]
        if state_label == "STALE":
            state_label += f' {source["ageDays"]}d'
        # Counts here are from the stored Observatory snapshot, never the live CISA fetch.
        success = source["lastSuccessDate"] or "unknown"
        count_text = f'{source["recordCount"]:,}' if source["lastSuccessDate"] else "—"
        lines.append(f'<text class="v" x="20" y="{y}" style="font-size:11px">{escape(source["name"])}</text>'
                     f'<text class="v" x="143" y="{y}" style="font-size:11px">{escape(state_label)}</text>'
                     f'<text class="v" x="277" y="{y}" style="font-size:11px">{escape(success)}</text>'
                     f'<text class="v" x="460" y="{y}" text-anchor="end" style="font-size:11px">{escape(count_text)}</text>')
    lines.append(f'<text class="f" x="20" y="396">ingestion: {escape(snapshot["ingestionMode"])}  /  freshness: {escape(snapshot["freshnessState"])}</text>')
    return "\n".join(lines)


def extend_svg(cisa_svg, obs_status, obs_snapshot, obs_last_good):
    # Only the outer canvas height and rect are enlarged. Existing CISA markup,
    # coordinates, classes, and footer remain byte-for-byte intact.
    height = 422 if obs_status == "OK" else 317
    cisa_svg = cisa_svg.replace('height="190" viewBox="0 0 480 190"',
                                f'height="{height}" viewBox="0 0 480 {height}"', 1)
    cisa_svg = cisa_svg.replace('height="188" rx="8"', f'height="{height - 2}" rx="8"', 1)
    cisa_svg = cisa_svg.replace('</svg>', render_observatory(obs_status, obs_snapshot, obs_last_good) + '\n</svg>', 1)
    return cisa_svg


def build(now=None, kev_input=None, state_file=STATE, output_file=OUT):
    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d %H:%M")
    old = json.load(open(state_file, encoding="utf-8")) if os.path.exists(state_file) else {}
    new = dict(old)
    try:
        kev = summarize(fetch(kev_input))
        kev_status = "OK"
        new.update({"last_good_utc": stamp, "summary": kev})
    except Exception as error:
        print("CISA fetch failed:", type(error).__name__, file=sys.stderr)
        kev, kev_status = None, "UNAVAILABLE"
    # Exactly one GET of the Observatory per build, irrespective of CISA success.
    try:
        observation = validate_observatory(fetch_observatory(), now)
        obs_status = "OK"
        new["observatory"] = {"last_good_utc": stamp, **observation}
    except Exception as error:
        print("Observatory fetch failed:", type(error).__name__, file=sys.stderr)
        observation, obs_status = None, "UNAVAILABLE"
    svg = extend_svg(render(kev_status, kev, stamp, old.get("last_good_utc")),
                     obs_status, observation, (old.get("observatory") or {}).get("last_good_utc"))
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(svg)
    with open(state_file, "w", encoding="utf-8") as file:
        json.dump(new, file, indent=2)
        file.write("\n")
    return kev_status, obs_status


def main():
    inp = sys.argv[sys.argv.index("--input") + 1] if "--input" in sys.argv else None
    build(kev_input=inp)


if __name__ == "__main__":
    main()