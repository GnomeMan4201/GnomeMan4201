# Public Repository Standard

Canonical portfolio metadata and presentation checklist for repositories intentionally kept public under `GnomeMan4201`.

This file exists because repository descriptions/topics are GitHub metadata rather than version-controlled README content. When those fields are changed in the GitHub UI or API, use the values below as the portfolio source of truth.

## Non-negotiable presentation rules

Every active public tool/research project should have:

- a one-sentence description that states what the project actually does
- focused GitHub topics rather than generic keyword stuffing
- a copy/paste quick-start or, for static research artifacts, a local-preview path
- an explicit verification command and a truthful statement of what that verification proves
- CI when a deterministic automated check is meaningful
- clear requirements and environment assumptions
- scope / evidence boundaries for research and security claims
- existing first-party logos, demo screenshots, and demonstration media preserved
- upstream provenance made explicit for forks/reference corpora
- no green badge backed by fail-open test commands

Not every repository needs a generated marketing banner. Reference forks and legacy tombstones should prefer provenance clarity over branding.

---

## Canonical metadata

### LANimals

**Type:** active tool  
**Description:** `Local-first network inventory and change-detection tooling for discovering, classifying, and tracking devices on a LAN.`  
**Topics:** `network-security`, `network-monitoring`, `asset-inventory`, `nmap`, `python`, `local-first`, `change-detection`, `security-tools`  
**Visuals:** keep existing LANimals logo, demo GIF, and personality-overlay artwork.  
**Verification posture:** existing CI/test workflows; preserve real test commands in README.

### zer0DAYSlater

**Type:** active security research tool  
**Description:** `Red-team research toolkit with reproducible lab workflows, defender-oriented analysis, smoke tests, and documented detection surfaces.`  
**Topics:** `security-research`, `red-team`, `detection-engineering`, `python`, `security-tools`, `adversary-emulation`, `lab`, `defensive-security`  
**Visuals:** keep existing zer0DAYSlater logo and any current demonstration assets.  
**Verification posture:** existing smoke/quality tooling and CI.

### Blackglass_Suite

**Type:** active security research tool  
**Description:** `Offline payload-research forge for controlled red-team labs, with local artifact generation and defensive inspection workflows.`  
**Topics:** `security-research`, `red-team`, `payload-analysis`, `powershell`, `python`, `local-first`, `adversary-emulation`, `defensive-security`  
**Visuals:** keep `.github/branding/demo.png`.  
**Verification posture:** fail-closed runtime CI; lint/type/static-security scans are explicitly advisory where red-team patterns create expected findings.

### shenron

**Type:** flagship active research tool  
**Description:** `Synthetic adversarial telemetry and detection-engineering research for measuring Sigma rule and campaign-correlation brittleness.`  
**Topics:** `detection-engineering`, `sigma-rules`, `security-research`, `synthetic-telemetry`, `mitre-attack`, `blue-team`, `python`, `adversary-simulation`, `llm-security`  
**Visuals:** keep `assets/shenron_banner.png` and all committed demonstration artifacts.  
**Verification posture:** existing multi-surface CI, safety gates, integration tests, and golden-demo checks.

### GnomeMan4201

**Type:** GitHub profile / research hub  
**Description:** `Independent security research: OSINT, detection engineering, provenance, reproducibility, and evidence-first analytical tooling.`  
**Topics:** `security-research`, `osint`, `detection-engineering`, `provenance`, `reproducibility`, `local-first`  
**Visuals:** preserve the badBANANA banner, section art, research signature, and EOF artwork.  
**Verification posture:** not an installable project; keep the profile selective and link to evidence-bearing repositories.

### devto-analytics-pro

**Type:** active analytics tool  
**Description:** `Local CLI analytics for DEV.to authors covering article performance, tags, audience signals, publishing patterns, and exportable reports.`  
**Topics:** `devto`, `analytics`, `content-analytics`, `python`, `cli`, `local-first`, `data-analysis`, `technical-writing`  
**Visuals:** keep `assets/banner.svg` and `assets/bad_banana_end.png`.  
**Verification posture:** CI plus honest smoke-test boundary; live API behavior remains integration-dependent.

### Decoy-Hunter

**Type:** attributed security-tool fork  
**Description:** `Protocol-aware service validation for networks where deception infrastructure makes large numbers of TCP ports appear open.`  
**Topics:** `network-security`, `deception`, `honeypot`, `service-detection`, `python`, `red-team`, `defensive-security`, `nmap`  
**Visuals:** keep `assets/decoy_hunter_demo.png`.  
**Verification posture:** fail-closed compile/test gate; upstream authorship remains explicit.

### devto-bot-audit

**Type:** legacy tombstone  
**Description:** `Legacy project pointer retained for DEV.to coordinated-behavior investigation lineage; active successor is currently private.`  
**Topics:** `legacy`, `osint`, `coordinated-inauthentic-behavior`, `devto`, `research-archive`  
**Visuals:** no new promo asset required.  
**Verification posture:** intentionally non-installable; README must clearly say superseded.

### drift-artifact

**Type:** static research artifact  
**Description:** `Static research artifact and method for examining authorship and coherence drift across iterative AI-assisted writing passes.`  
**Topics:** `ai-research`, `llm`, `authorship`, `provenance`, `research-artifact`, `reproducibility`, `human-ai-interaction`  
**Visuals:** current artifact remains authoritative; a dedicated repository-card screenshot/banner would improve presentation.  
**Verification posture:** zero-dependency static integrity validation plus explicit research-claim boundary.

### drift_orchestrator

**Type:** active AI-safety research project  
**Description:** `Experimental tooling for studying policy drift, evaluator failure, and adversarial pressure in coupled LLM safety-monitor systems.`  
**Topics:** `ai-safety`, `llm-security`, `red-teaming`, `security-research`, `adversarial-ml`, `evaluation`, `python`, `reproducibility`  
**Visuals:** keep `docs/attack_chain.svg` and existing research/demo media.  
**Verification posture:** existing CI; public verification and private-gateway-dependent fresh reruns must remain clearly separated.

### gnome-prompt-field-manual

**Type:** active research/manual project  
**Description:** `Structured field manual for inspectable, provenance-aware AI prompting and evidence-first analytical workflows.`  
**Topics:** `prompt-engineering`, `ai-workflows`, `provenance`, `reproducibility`, `research-methods`, `llm`, `security-research`, `documentation`  
**Visuals:** keep the existing GNOME Prompt Field Manual banner/artwork.  
**Verification posture:** existing deterministic validators and unit tests; keep current limits-of-verification language.

### graph_anomaly_detector

**Type:** active analytical tool  
**Description:** `Explainable graph-anomaly pipeline for detecting suspicious nodes and coordinated behavioral structure in interaction datasets.`  
**Topics:** `graph-analysis`, `anomaly-detection`, `osint`, `networkx`, `scikit-learn`, `coordinated-behavior`, `python`, `machine-learning`, `explainability`  
**Visuals:** new first-party promo/banner or result screenshot recommended.  
**Verification posture:** synthetic end-to-end CI with required output-artifact checks.

### OpenRedTeaming

**Type:** upstream-derived research reference fork  
**Description:** `Research fork and literature index for generative-AI red teaming, with upstream provenance preserved and local taxonomy additions tracked in Git.`  
**Topics:** `llm-security`, `red-teaming`, `ai-safety`, `research-papers`, `literature-review`, `adversarial-ml`, `reference`  
**Visuals:** no custom promo art required unless this becomes a first-party project; provenance is more important than branding.  
**Verification posture:** catalog/reference corpus, not an installable application; linked papers remain the primary sources.

### r4b1t

**Type:** active OSINT discovery application  
**Description:** `Browser-based discovery engine for a curated corpus of live security, OSINT, research, and reference URLs.`  
**Topics:** `osint`, `security-research`, `discovery`, `web-app`, `javascript`, `playwright`, `pwa`, `research-tools`, `curated-list`  
**Visuals:** keep all five current screenshots.  
**Verification posture:** pinned Playwright desktop/mobile E2E, dependency audit, corpus maintenance, and deployment workflows.

### threatmap

**Type:** static investigation visualization  
**Description:** `Interactive D3 investigation graph for mapping actors, infrastructure, evidence, and relationships in security research.`  
**Topics:** `osint`, `threat-intelligence`, `data-visualization`, `d3js`, `investigation`, `security-research`, `graph-visualization`, `static-site`  
**Visuals:** new first-party full-page screenshot/banner recommended; do not replace the existing application design.  
**Verification posture:** static artifact validator and GitHub Actions gate.

### SubDomainizer

**Type:** retained upstream-derived fork  
**Description:** `Retained fork of nsonaniya2010/SubDomainizer for subdomain, cloud-endpoint, and candidate-secret discovery research.`  
**Topics:** `subdomain-enumeration`, `reconnaissance`, `python`, `web-security`, `cloud-security`, `security-tools`, `legacy`, `fork`  
**Visuals:** preserve all four original upstream screenshots and their attribution.  
**Verification posture:** legacy Python compile/CLI smoke check; do not imply modern production support.

### reasoning-diff-lab

**Type:** active analytical research instrument  
**Description:** `Local-first research instrument for testing whether structured reasoning-path comparison exposes useful analytical review divergences.`  
**Topics:** `reasoning`, `human-ai-interaction`, `research-tool`, `local-first`, `provenance`, `reproducibility`, `javascript`, `analytical-methods`  
**Visuals:** a clean instrument/workflow screenshot or promo card would improve the repository landing surface without changing the research framing.  
**Verification posture:** existing `npm run verify`, automated safety/build checks, and explicit empirical-validation boundary.

---

## Promo-asset priority

New imagery is worth producing only where it adds missing evidence or identity. Priority order:

1. `graph_anomaly_detector` — show a synthetic run/result/explainability surface.
2. `threatmap` — clean full-page application screenshot suitable for README/social preview.
3. `reasoning-diff-lab` — show the actual analyst/reviewer workflow or diff instrument.
4. `drift-artifact` — show the rendered artifact and pass/trace structure.

Do **not** replace existing demo/logo assets in LANimals, zer0DAYSlater, Blackglass Suite, Shenron, the profile repo, devto-analytics-pro, Decoy-Hunter, drift_orchestrator, gnome-prompt-field-manual, r4b1t, or SubDomainizer.

Legacy/reference repositories (`devto-bot-audit`, `OpenRedTeaming`) do not need promotional branding unless their role changes.

---

## Metadata application checklist

When GitHub repository metadata is editable:

1. apply the exact description above;
2. add the listed topics, removing irrelevant/generic tags;
3. confirm website/homepage points to the live demo or canonical publication when one exists;
4. verify the social-preview image uses a first-party promo asset for active flagship projects;
5. do not use a CI badge unless the corresponding workflow is meaningful and fail-closed for the behavior it claims to validate.
