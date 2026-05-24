<!-- GnomeMan4201 // badBANANA collective -->

<div align="center">

[![Ecosystem Graph](https://img.shields.io/badge/SHENRON-Ecosystem_Graph-00ff9d?style=for-the-badge)](https://gnomeman4201.github.io/GnomeMan4201/)

</div>

---

Security researcher and tool developer building local-first systems for network deception, document intelligence, LLM runtime monitoring, and adversarial simulation. Stack: Python, FastAPI, SQLite, Linux, C.

**Start here:** [LANimals](https://github.com/GnomeMan4201/LANimals) · [drift_orchestrator](https://github.com/GnomeMan4201/drift_orchestrator) · [OpenSight](https://github.com/GnomeMan4201/OpenSight)

Self-taught. No lab access, no team, no institutional backing. Everything here started as friction — and became a tool.

Part of the **badBANANA collective** — a one-person operation that treats security research as a craft, not a career move.

---

## The Ecosystem

The BANANA_TREE is an adversarial training loop. Every tool feeds the next.

```
  OBSERVE                          SIMULATE
  LANimals ─ network deception      Lune ─ 64-module tradecraft
  OpenSight ─ OSINT / graphs        PHANTOM ─ honeypot detection
  Decoy-Hunter ─ decoy analysis     SHENRON ─ adversarial telemetry
  TERRAIN ─ local intelligence      Blackglass_Suite ─ offline mutation

  EXECUTE                          ADAPT
  zer0DAYSlater ─ post-exploit      drift_orchestrator ─ LLM drift
  bad_BANANA ─ Android/Termux       chain ─ mutation lineage
  pwn ─ modular pentest             aliasOS ─ operator shell
  OWN ─ execution layer             reflexive-identity ─ self-auth agent

  RESEARCH                         UTILITY
  drift-artifact ─ authorship       devto-botnet-hunter ─ network forensics
  gnome-prompt-field-manual         devto-analytics-pro ─ platform intel

  observe → simulate → execute → adapt → observe
```

Nothing here is speculative. Every tool in the map is operational.

---

## Last Operation

```
[BANANA_TREE] kill chain — synthetic demonstration
──────────────────────────────────────────────────────────────────────
$ lanimals scan --subnet 192.168.1.0/24 --score behavioral
  [+] 14 hosts discovered
  [+] 3 flagged: elevated entropy, unusual port cadence
  [→] exporting target profiles → lanimorph

$ lanimorph inject --profile target_03 --subnet 192.168.1.0/24
  [+] XOR mutation: xor_delta=0.847
  [+] persona selected: volatile_mirror
  [→] sealed mesh export → shenron handoff

$ shenron mutate --input target_03.sealed --layers 7
  [2026-05-24T03:12:44Z]  layer_41  entropy=7.91  sig=a3f9e1c2  ✓
  [2026-05-24T03:13:01Z]  layer_42  entropy=7.94  sig=b8d02f4a  ✓ fork
  [2026-05-24T03:13:19Z]  layer_43  entropy=7.88  sig=c1e74b91  ✓ sealed
  [→] lineage logged → chain

$ drift_orchestrator monitor --session op_volatile_mirror
  [+] flight recorder active — SQLite telemetry open
  [+] semantic baseline established
  [!] drift event at t+00:04:12 — composite score: 0.73
  [→] hysteresis policy: INTERVENE

$ phantom probe --target 192.168.1.47
  [+] signature match: Cowrie 2.x  confidence=0.94
  [!] honeypot confirmed — aborting contact
──────────────────────────────────────────────────────────────────────
synthetic only // no live targets // authorized research environments
──────────────────────────────────────────────────────────────────────
```

---

## What Got Built

| tool | what it does |
|------|-------------|
| [LANimals](https://github.com/GnomeMan4201/LANimals) | Local network deception platform. Discovers hosts, scores behavioral risk, deploys honeypot traps, assigns adversarial personalities to targets, force-directed graph UI. |
| [Lune](https://github.com/GnomeMan4201/Lune) | 64-module adversary simulation framework for controlled research environments. Encrypted C2, LLM mutation engine, unified persona system. |
| [zer0DAYSlater](https://github.com/GnomeMan4201/zer0DAYSlater) | Post-exploitation research framework. LLM-driven operator, session drift monitoring, entropy capsule, mTLS mesh with ephemeral NaCl keypairs. Authorized environments only. |
| [drift_orchestrator](https://github.com/GnomeMan4201/drift_orchestrator) | Runtime drift control for LLM sessions. SQLite flight recording, semantic embeddings, composite density scoring, hysteresis policy engine. |
| [OpenSight](https://github.com/GnomeMan4201/OpenSight) | Document intelligence and OSINT platform. Entity extraction, typed knowledge graph, investigation bundles, demonstrated on FBI corpus. |
| [SHENRON](https://github.com/GnomeMan4201/shenron) | Synthetic adversarial telemetry pipeline. 49-layer mutation engine, Sigma rule evaluation, detection validation, HTML reports. |
| [LANIMORPH](https://github.com/GnomeMan4201/lanimorph) | LAN-aware morphing payload system. Per-subnet XOR mutation, personality-driven selection, sealed mesh exports. |
| [PHANTOM](https://github.com/GnomeMan4201/PHANTOM) | Honeypot fingerprinting layer. Identifies Cowrie, Kippo, OpenCanary, Thinkst and 4 others. Extends Decoy-Hunter. |
| [Decoy-Hunter](https://github.com/GnomeMan4201/Decoy-Hunter) | Advanced decoy detection toolkit. Foundation layer for PHANTOM's fingerprinting stack. |
| [reflexive-identity](https://github.com/GnomeMan4201/reflexive-identity) | Zero-trust AI agent framework. Self-authentication, integrity monitoring, and autonomous privilege revocation. |
| [Blackglass_Suite](https://github.com/GnomeMan4201/Blackglass_Suite) | Offline AI-powered payload mutation, scoring, and stealth delivery. Runs in Termux and Linux — no network required. |
| [bad_BANANA](https://github.com/GnomeMan4201/bad_BANANA) | Field-ready, no-root offensive toolkit for Android (Termux) and Debian. |
| [pwn](https://github.com/GnomeMan4201/pwn) | Modular penetration testing platform. Interactive network recon, native ASCII dashboards, dynamic payload management. |
| [chain](https://github.com/GnomeMan4201/chain) | Mutation engine and lineage tracker. DNA-style payload evolution with XP system and replay. |
| [aliasOS](https://github.com/GnomeMan4201/aliasOS) | Textual TUI for managing operator shell aliases. Browse, CRUD, health check, history mining, gap analysis. |
| [devto-botnet-hunter](https://github.com/GnomeMan4201/devto-botnet-hunter) | DEV.to coordinated follow network investigator and deep forensics engine. |
| [drift-artifact](https://github.com/GnomeMan4201/drift-artifact) | Stylometric drift experiment. Documents that demonstrate iterative authorship instability as their own argument. |
| [OWN](https://github.com/GnomeMan4201/OWN) | Adaptive offensive/payload framework and execution layer. |

---

## Signals

```
VERIFIED // GnomeMan4201
──────────────────────────────────────────────────────────────────
GitHub Stars                38        across 24 public repos
GitHub Forks                5         drift_orchestrator · LANimals · zer0DAYSlater ×3
GitHub Followers            88        organic
Contributions              911        last 12 months
──────────────────────────────────────────────────────────────────
Dev.to Followers         2,987        gnomeman4201
Dev.to Articles             42        published
Dev.to Views             7,597        total reads
──────────────────────────────────────────────────────────────────
Lune Tests                  92        passing — CI green
OpenSight Tests             52        passing — CI green
aliasOS                 v1.0.0        296 aliases · live demo
──────────────────────────────────────────────────────────────────
every number above is verifiable.
──────────────────────────────────────────────────────────────────
methodology: necessity-driven development
             build when friction exceeds build cost
             publish when the work can stand alone
──────────────────────────────────────────────────────────────────
```

---

## Build Status

| repo | build |
|------|-------|
| [LANimals](https://github.com/GnomeMan4201/LANimals) | [![CI](https://github.com/GnomeMan4201/LANimals/actions/workflows/ci.yml/badge.svg)](https://github.com/GnomeMan4201/LANimals/actions) |
| [Lune](https://github.com/GnomeMan4201/Lune) | [![CI](https://github.com/GnomeMan4201/Lune/actions/workflows/ci.yml/badge.svg)](https://github.com/GnomeMan4201/Lune/actions) |
| [drift_orchestrator](https://github.com/GnomeMan4201/drift_orchestrator) | [![CI](https://github.com/GnomeMan4201/drift_orchestrator/actions/workflows/ci.yml/badge.svg)](https://github.com/GnomeMan4201/drift_orchestrator/actions) |
| [zer0DAYSlater](https://github.com/GnomeMan4201/zer0DAYSlater) | [![CI](https://github.com/GnomeMan4201/zer0DAYSlater/actions/workflows/ci.yml/badge.svg)](https://github.com/GnomeMan4201/zer0DAYSlater/actions) |
| [OpenSight](https://github.com/GnomeMan4201/OpenSight) | [![CI](https://github.com/GnomeMan4201/OpenSight/actions/workflows/ci.yml/badge.svg)](https://github.com/GnomeMan4201/OpenSight/actions) |
| [chain](https://github.com/GnomeMan4201/chain) | [![CI](https://github.com/GnomeMan4201/chain/actions/workflows/ci.yml/badge.svg)](https://github.com/GnomeMan4201/chain/actions) |
| [aliasOS](https://github.com/GnomeMan4201/aliasOS) | [![CI](https://github.com/GnomeMan4201/aliasOS/actions/workflows/ci.yml/badge.svg)](https://github.com/GnomeMan4201/aliasOS/actions) |

---

## Writing

[dev.to/gnomeman4201](https://dev.to/gnomeman4201) — 42 articles. Adversarial tooling, LLM security, network deception, platform analysis, and the philosophy behind building in the open under a pseudonym.

---

## Contact

```
preferred:  GitHub issues / security advisories
writing:    dev.to/gnomeman4201
PGP:        324C 4301 54C2 3C8E 3956 1B10 0CFD 6761 AA75 4969
            github.com/GnomeMan4201.gpg
```

---

<div align="center">

<img src="assets/bad_banana_end.png" width="460" alt="end of file" />

</div>
