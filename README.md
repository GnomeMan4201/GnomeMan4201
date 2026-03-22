# LUNE

**Modular Adversary Simulation & Live Deception Framework**

[![CI](https://github.com/GnomeMan4201/Lune/actions/workflows/ci.yml/badge.svg)](https://github.com/GnomeMan4201/Lune/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)

---

LUNE is a modular adversary simulation platform built for operators who need real deception capability, not demos. It combines a 57-module tradecraft library, an LLM-powered mutation engine, pre-built operation chains, encrypted C2 infrastructure, and a unified persona system into a single operator console.

It is designed for authorized red team operations, controlled lab simulation, and security research. Nothing here is academic scaffolding — every module is executable, every chain is tested.

---

## Architecture

```
lune/
├── lune/ # Core operator environment
│ ├── lune-tui.py # Unified entry point — single command interface
│ ├── lune.py # Recon sweep + TUI launcher
│ ├── modules/ # 57 tradecraft modules
│ │ ├── mutagen.py # LLM mutation engine (Ollama/mistral)
│ │ ├── chainforge.py # Operation chain executor
│ │ ├── persona_engine.py # Unified identity + attribution controller
│ │ ├── session.py # Shared operation state
│ │ ├── orchestrator.py # Module chain builder
│ │ └── [54 others] # Full tradecraft surface
│ └── decoy_mirage/ # Pre-generated deception artifact tree
├── server/
│ └── c2.py # Hardened C2 — AES-128-CBC + HMAC-SHA256
├── agents/
│ └── lune_agent.py # Hardened agent — encrypted beacon/report cycle
├── modules/
│ ├── core/ # Perception control, history poisoner, pollution daemon
│ └── deception/ # Deception injectors, signal obfuscators, decoy forge
└── docs/ # Architecture, design notes, project structure
```

---

## Module Surface

LUNE ships 57 executable modules organized by function:

**Recon** — `aether` `dryad` `vane` `wisp` `wallflower` `meta`

**Deception** — `decoy` `fable` `wraith` `grackle` `brine` `smudge` `lurestate` `mimesis` `alibi` `persona_engine`

**Persistence** — `dreamtether` `sliphook` `spindle` `hollowroot` `stealth` `stitch` `thresh`

**Injection** — `fracture` `ghostload` `helix` `palebox` `parasite` `shellsworn` `shuck` `obscura` `veil`

**C2 / Comms** — `ghostctl` `glint` `nullflow` `siphon` `velvetroom` `pivot` `hearse`

**Cleanup** — `bleachmouth` `relic` `vanish` `etch` `shade`

**LLM / Intel** — `mutagen` `chainforge` `orchestrator` `session`

---

## Key Systems

### mutagen
LLM-powered module backed by local Ollama (mistral). Four capabilities:

- **Artifact generation** — environment-fingerprinted fake credentials, bash history entries, config files, SSH keys, JWT tokens, AWS key pairs styled to blend with the target environment
- **Persona IOC generation** — synthetic C2 domains, file hashes, registry keys, user-agent strings styled after APT28, Lazarus, Charcoal Typhoon, FIN7, or a custom threat actor profile
- **OPSEC analysis** — structured assessment of a proposed action: detection risk rating, specific detection mechanisms, forensic artifacts left behind, evasion recommendations, OPSEC score
- **Payload mutation** — takes a raw payload (bash, python, powershell, C, or technique description) and generates evasion-optimized variants across six strategies: obfuscation, LOLbins, fragmentation, timing evasion, process masquerade, encoding chain

Runs entirely offline. No external API calls.

### chainforge
Pre-built operation chain executor with session logging.

Five built-in chains:

| Chain | Steps | Risk | Description |
|---|---|---|---|
| ghost_op | 7 | High | Fingerprint → cloak → deception → persist → vanish |
| deception_flood | 6 | Medium | Saturate environment with false artifacts |
| recon_sweep | 6 | Low | Passive-first host and network recon |
| persistence_web | 7 | High | Multi-vector persistence across reboot |
| clean_exit | 5 | Medium | Evidence destruction and teardown |

Custom chain builder lets operators compose any sequence from the full module library. All chains write timestamped `.log` and `.json` to `.lune_sessions/`. Dry run mode previews execution without touching anything.

### persona_engine
Unified identity and attribution controller wrapping `fable`, `alibi`, and `mimesis`.

- Generates synthetic operator identities via Faker
- Renames the process to a trusted system binary via `prctl(PR_SET_NAME)`
- Applies network noise to obscure behavioral patterns
- Four built-in threat actor profiles with real TTPs, process names, fake domain patterns, user agents, and MITRE ATT&CK technique IDs
- Attribution injection plants profile-specific IOCs (user agents in bash history, fake C2 domain references, MITRE technique markers) to frame a specific threat actor
- Persona state persists to `active_persona.json` and integrates with the session context

### session
Shared operation state module. Any module can read and write:

- `record_module(name, status, note)` — log what ran and when
- `record_artifact(kind, value, source)` — track planted artifacts
- `set_flag / get_flag` — arbitrary key-value op state
- `set_persona / get_persona` — active persona tracking
- `archive_session()` — move active session to timestamped archive

State persists in `.lune_sessions/active_session.json`. TUI status line reflects live session state.

### C2 infrastructure
The C2 server and agent use matching crypto and auth:

- AES-128-CBC encryption on all task delivery and result collection
- HMAC-SHA256 request signing — every request verified before processing
- Key material loaded from environment variables or auto-generated key files (chmod 600, never hardcoded)
- Agent registry with beacon count, last seen, task count, and result storage
- Activity log at `server/data/c2_activity.log`
- Agent uses Gaussian-jittered beacon interval and exponential backoff on failures

---

## Install

```bash
git clone https://github.com/GnomeMan4201/Lune.git
cd Lune
python3 -m venv .venv
source .venv/bin/activate
pip install -r lune/lune/requirements.txt
```

For `mutagen` (optional — LLM features):
```bash
# Install Ollama: https://ollama.com
ollama pull mistral
```

---

## Quickstart

```bash
cd lune/lune
python3 lune-tui.py
```

```
lune: session new op_name
lune: list
lune: chain
lune: persona
lune: mutagen
lune: status
```

Run the C2 server:
```bash
cd lune/server
python3 c2.py --host 127.0.0.1 --port 5000
```

Deploy an agent:
```bash
cd lune/agents
LUNE_C2_URL=http://127.0.0.1:5000 \
LUNE_AGENT_ID=agent_001 \
LUNE_MASQ=sshd \
python3 lune_agent.py
```

Queue a task (keys auto-generated on first C2 start):
```bash
# Read the generated key
KEY=$(cat lune/server/.lune_c2.key)
HMAC=$(cat lune/server/.lune_hmac.secret)

# Encrypt and sign via Python helper
python3 -c "
from lune.server.utils.crypto import encrypt_message
import hmac, hashlib, json, requests
payload = json.dumps({'data': encrypt_message({'task': 'whoami'})})
sig = hmac.new('$HMAC'.encode(), payload.encode(), hashlib.sha256).hexdigest()
r = requests.post('http://127.0.0.1:5000/api/queue/agent_001',
 data=payload,
 headers={'Content-Type': 'application/json', 'X-LUNE-SIG': sig})
print(r.text)
"
```

---

## Diagnosis

```bash
cd lune/lune
python3 lune-diagnose.py
```

Scans all modules, auto-installs missing dependencies, reports import errors and missing `run()` functions.

---

## Documentation

- `docs/ARCHITECTURE.md` — system design and data flow
- `docs/DESIGN_NOTES.md` — tradecraft logic and intent
- `docs/PROJECT_STRUCTURE.md` — full file layout
- `docs/CONTRIBUTING.md` — extending LUNE

---

## Legal

For authorized security research, red team simulation, and education only. Use exclusively on systems you own or have explicit written permission to test. You are solely responsible for compliance with all applicable laws.

---

*LUNE // badBANANA research // GnomeMan4201*
