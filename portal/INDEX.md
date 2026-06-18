# badBANANA Research Collective

> Independent security research · OSINT tooling · CIB investigations

**[→ r4b1t](https://gnomeman4201.github.io/r4b1t)** · **[→ dev.to](https://dev.to/gnomeman4201)** · **[→ GitHub](https://github.com/GnomeMan4201)**

---

## Investigations

| ID | Title | Tags | Status |
|----|-------|------|--------|
| [INV-001](../investigations/INV-001.md) | NSBoost / upvote.club fake engagement network | `browser-extension` `CIB` `attribution` | Disclosed · Published |
| [INV-002](../investigations/INV-002.md) | GhostLoader/RemcosRAT GitHub malware network | `malware` `RAT` `supply-chain` | Disclosed |
| [INV-003](../investigations/INV-003.md) | IPASIS.com IOC cross-reference | `IOC` `awesome-list` | Active |
| [INV-004](../investigations/INV-004.md) | myLittleAdmin SQL admin exposure | `exposure` `OSINT` | Closed |
| [INV-005](../investigations/INV-005.md) | hajigur69 CIB network — 26 accounts, 6 waves | `CIB` `avatar-hashing` `GitHub` | Disclosed |

## Published writeups

| Title | Publication | Tags |
|-------|------------|------|
| [Reverse engineering a browser extension fake engagement loop](https://dev.to/gnomeman4201) | dev.to | `INV-001` `reverse-engineering` `browser-extension` |
| [GitHub malware network delivering RemcosRAT to 2,100+ victims](https://dev.to/gnomeman4201) | dev.to | `INV-002` `malware` `GitHub` |

---

## Tool catalog

| Tool | Category | Description |
|------|----------|-------------|
| [r4b1t](https://github.com/GnomeMan4201/r4b1t) | Discovery | 53,869-URL OSINT discovery engine |
| [inv-hub](https://github.com/GnomeMan4201/inv-hub) | Operations | Investigation lifecycle management |
| [PRAXIS](https://github.com/GnomeMan4201/PRAXIS) | Knowledge | Research knowledge base CLI |
| [SHENRON](https://github.com/GnomeMan4201/SHENRON) | Detection | Detection engineering framework |
| [bpf-watch](https://github.com/GnomeMan4201/bpf-watch) | Detection | eBPF runtime monitoring |
| [gnome_control](https://github.com/GnomeMan4201/GnomeMan4201) | Operations | Operator dashboard |
| [MISF](https://github.com/GnomeMan4201/MISF) | Framework | Intelligence & security framework |
| [drift_orchestrator](https://github.com/GnomeMan4201/GnomeMan4201) | Analysis | LLM behavioral drift detection |

---

## Dataset catalog

| Dataset | Size | Description | Access |
|---------|------|-------------|--------|
| urls.txt | 53,869 URLs | Verified live OSINT/security URLs | [r4b1t repo](https://github.com/GnomeMan4201/r4b1t) |
| hub.db | 16,577 unique URLs | FTS5-indexed research corpus | Internal |
| onion_intel | 864 addresses | Verified .onion addresses with metadata | Internal |
| consensus_tools | 738 tools | Cross-referenced security tool list | Internal |

---

## Disclosure archive

| ID | Target | Date | Reference |
|----|--------|------|-----------|
| DISC-001 | upvote.club / Codemarket OÜ | 2025 | INV-001 |
| DISC-002 | GitHub Trust & Safety (GhostLoader wave 1–4) | 2025–2026 | INV-002 |
| DISC-003 | hajigur69 network | 2026 | INV-005 |

---

## Ecosystem map

→ [ECOSYSTEM.md](../ECOSYSTEM.md)

---

<sub>badBANANA Research Collective · GnomeMan4201 · Pop!_OS · terminal-native</sub>
