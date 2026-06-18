<div align="center">

```
 ██████╗  █████╗ ██████╗ ██████╗  █████╗ ███╗   ██╗ █████╗ ███╗  ██╗ █████╗
 ██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔══██╗████╗  ██║██╔══██╗████╗ ██║██╔══██╗
 ██████╦╝███████║██║  ██║██████╦╝███████║██╔██╗ ██║███████║██╔██╗██║███████║
 ██╔══██╗██╔══██║██║  ██║██╔══██╗██╔══██║██║╚██╗██║██╔══██║██║╚████║██╔══██║
 ██████╔╝██║  ██║██████╔╝██████╔╝██║  ██║██║ ╚████║██║  ██║██║ ╚███║██║  ██║
 ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚══╝╚═╝  ╚═╝
                    R E S E A R C H   C O L L E C T I V E
```

**Independent security research · OSINT tooling · CIB investigations**

[![r4b1t](https://img.shields.io/badge/r4b1t-live-cc1111?style=flat-square)](https://gnomeman4201.github.io/r4b1t)
[![dev.to](https://img.shields.io/badge/dev.to-writings-0A0A0A?style=flat-square&logo=devdotto)](https://dev.to/gnomeman4201)
[![license](https://img.shields.io/badge/license-MIT-444?style=flat-square)](https://github.com/GnomeMan4201/r4b1t/blob/main/LICENSE)

</div>

---

## What this is

Independent research operation running three tracks:

**Investigations** — Coordinated inauthentic behavior networks, malware distribution campaigns, browser extension abuse. Findings disclosed responsibly, documented publicly.

**Tooling** — Open-source infrastructure for OSINT, detection engineering, and security research. Terminal-native. Built to compose.

**Analysis** — Published writeups on threat actor methodology, internet culture, and tool teardowns.

---

## Tools

| Repo | Description | Status |
|------|-------------|--------|
| [r4b1t](https://github.com/GnomeMan4201/r4b1t) | StumbleUpon-style discovery engine — 53,869 verified OSINT/security URLs, BRANCH mode, PWA | `live` |
| [inv-hub](https://github.com/GnomeMan4201/inv-hub) | Investigation management system — Rich TUI, disclosure tracking, correlation engine | `active` |
| [SHENRON](https://github.com/GnomeMan4201/SHENRON) | Detection engineering framework — 390 tests, 53 simulation layers, 20 Sigma rules, MITRE ATT&CK drift checker | `active` |
| [gnome_control](https://github.com/GnomeMan4201/GnomeMan4201) | Operator dashboard — live monitor, SVG correlation graph, Anthropic briefing generator | `active` |
| [PRAXIS](https://github.com/GnomeMan4201/PRAXIS) | Research knowledge base CLI — SQLite/FTS5, BagIt archival, 14 templates, 13 commands | `active` |

---

## Investigations

| ID | Subject | Outcome |
|----|---------|---------|
| INV-001 | [upvote.club / NSBoost](https://dev.to/gnomeman4201) — browser extension fake engagement network. Operator attributed: Alexey Ignatov, Codemarket OÜ (Tallinn) | `disclosed · published` |
| INV-002 | GhostLoader/RemcosRAT — 32+ repo malware network, bot-inflated stars, 2,100+ victims. Delivery: cloudcraftshub.com, dropras.xyz | `disclosed to GitHub` |
| INV-003 | IPASIS.com — IOC cross-reference across awesome-lists and threat intel repos | `active` |
| INV-004 | myLittleAdmin — SQL admin panel exposure | `closed` |
| INV-005 | hajigur69 CIB network — 26 accounts, 39 duplicate avatar hash groups, 6 deployment waves, carox.tech infra. Overlap with INV-001 confirmed | `disclosed` |

---

## Corpus

Assembled via eight-script scraper pipeline (CDP, GitHub miner, onion harvester, dedup ranker):

```
53,869  verified live URLs (security / OSINT / research)
   864  verified onion addresses
   738  consensus security tools
16,577  unique URLs indexed in hub.db (FTS5)
```
---

## Published

- **[Reverse engineering a browser extension fake engagement loop](https://dev.to/gnomeman4201)** — NSBoost / INV-001
- **[How I found a GitHub malware network with 2,100+ victims](https://dev.to/gnomeman4201)** — GhostLoader / INV-002

---

## Stack
Pop!_OS · Python · SQLite/FTS5 · Bash · Playwright/CDP

Vanilla JS · Cloudflare Workers · GitHub Actions · BagIt · Sigma · MITRE ATT&CK
---

<div align="center">
<sub>BANANA_TREE ecosystem · badBANANA Research Collective · GnomeMan4201</sub>
</div>
