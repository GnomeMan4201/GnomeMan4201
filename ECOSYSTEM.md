# BANANA_TREE Ecosystem Map

> **Historical snapshot — June 2026.** This document preserves a point-in-time ecosystem state and is **not** the authoritative list of currently public repositories, current project status, or current corpus counts. Some linked projects are now private or unavailable, and numeric corpus values below are intentionally preserved as historical evidence. For the current public starting set, use the repository's main [`README.md`](README.md).

> badBANANA Research Collective · GnomeMan4201 · June 2026

---

## Architecture
┌─────────────────────────────────────────────────────────────────────┐

│                    BANANA_TREE ECOSYSTEM                            │

│                                                                     │

│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │

│  │   CORPUS     │    │  OPERATIONS  │    │   PUBLIC SURFACE      │  │

│  │              │    │              │    │                        │  │

│  │  hub.db      │───▶│  inv-hub     │───▶│  dev.to writeups      │  │

│  │  urls.txt    │    │  PRAXIS      │    │  GitHub disclosures   │  │

│  │  onion_intel │    │  gnome_ctrl  │    │  r4b1t (live tool)   │  │

│  │  FTS5 index  │    │  aliasOS     │    │  GNOME Field Journal  │  │

│  └──────┬───────┘    └──────┬───────┘    └──────────────────────┘  │

│         │                   │                                       │

│         ▼                   ▼                                       │

│  ┌──────────────┐    ┌──────────────┐                              │

│  │  COLLECTION  │    │  DETECTION   │                              │

│  │              │    │              │                              │

│  │  8x scrapers │    │  SHENRON     │                              │

│  │  pool_sweep  │    │  bpf-watch   │                              │

│  │  MISF        │    │  zer0DAYSltr │                              │

│  │  r4b1t tools │    │  drift_orch  │                              │

│  └──────────────┘    └──────────────┘                              │

└─────────────────────────────────────────────────────────────────────┘
---

## Projects

### Public tools

| Project | Repo | Live | Purpose |
|---------|------|------|---------|
| r4b1t | [GnomeMan4201/r4b1t](https://github.com/GnomeMan4201/r4b1t) | [gnomeman4201.github.io/r4b1t](https://gnomeman4201.github.io/r4b1t) | OSINT/security URL discovery engine |
| SHENRON | [GnomeMan4201/SHENRON](https://github.com/GnomeMan4201/SHENRON) | — | Detection engineering framework, simulation layers, Sigma rules |
| bpf-watch | [GnomeMan4201/bpf-watch](https://github.com/GnomeMan4201/bpf-watch) | — | eBPF monitoring — cap_watcher, xdp_monitor, kprobe_sentinel |

### Research infrastructure

| Project | Purpose | Key components |
|---------|---------|----------------|
| inv-hub | Investigation lifecycle management | 11 Python modules, Rich TUI, systemd timer, disclosure age alerts |
| PRAXIS | Research knowledge base | SQLite/FTS5, BagIt archival, 14 templates, 13 CLI commands |
| gnome_control | Operator dashboard | Port 7333, live monitor, SVG correlation graph, cross-platform identity resolver |
| MISF | Intelligence framework | 6 modules: infra attribution, identity attribution, developer forensics, analyst OPSEC, threat feeds, orchestration |

### Collection pipeline

| Script | Role |
|--------|------|
| CDP scraper | Playwright/CDP — start.me OSINT pages |
| GitHub miner | awesome-list harvesting across 21 categories |
| pools scraper | Aggregator scraping |
| onion harvester | .onion address collection |
| onion crawler | Tor-routed content fetch |
| dedup ranker | Deduplication + consensus scoring |
| corpus cleaner | Normalization + liveness pre-filter |
| publication builders | hub.db ingestion, FTS5 indexing |

### Detection & analysis

| Tool | Purpose |
|------|---------|
| SHENRON | MITRE ATT&CK drift checker, 53 simulation layers, 390 tests |
| bpf-watch | eBPF runtime monitoring with Sigma-schema telemetry |
| zer0DAYSlater | Vulnerability tracking |
| drift_orchestrator | LLM behavioral drift detection |

---

## Investigations

| ID | Subject | Infrastructure | Status |
|----|---------|---------------|--------|
| INV-001 | upvote.club / NSBoost fake engagement | code.market / Vercel 216.150.1.1 | Disclosed + published |
| INV-002 | GhostLoader/RemcosRAT network | cloudcraftshub.com, dropras.xyz, trackpipe.dev, devcodee.com | Disclosed to GitHub (4 waves) |
| INV-003 | IPASIS.com IOC | awesome-incident-response, OpenClaw AI | Active |
| INV-004 | myLittleAdmin SQL exposure | — | Closed |
| INV-005 | hajigur69 CIB network | carox.tech / code.market / Vercel (overlaps INV-001) | Disclosed |

**Infrastructure overlap confirmed:** INV-001 ↔ INV-005 via code.market/carox.tech/Vercel IP 216.150.1.1

---

## Corpus stats
Input:    ~120,000 raw URLs

After pipeline:

53,869  verified live URLs (urls.txt / r4b1t pool)

16,577  unique URLs in hub.db

     864  onion addresses (onion_intel table)

738  consensus security tools

537  source files
---

## Data flows
Scrapers ──▶ raw corpus ──▶ dedup/rank ──▶ hub.db (FTS5)

                       ├──▶ urls.txt (r4b1t pool)

                          └──▶ onion_intel tableInvestigations ──▶ inv-hub CLI ──▶ hub.db (resource_ioc_hits)

         ├──▶ PRAXIS archive (BagIt)

                          ├──▶ gnome_control dashboard

                   └──▶ disclosure documentsDetection ──▶ SHENRON layers ──▶ Sigma rules ──▶ MITRE ATT&CK mapping

──▶ bpf-watch telemetry ──▶ Sigma-schema output
---

## Cross-links

Every project README links:
- Up: this ecosystem map
- Sideways: related projects in same track
- Out: relevant published writeups or disclosures

Template: [templates/cross-link-footer.md](templates/cross-link-footer.md)
