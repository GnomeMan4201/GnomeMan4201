#!/usr/bin/env bash
set -euo pipefail

OWNER="GnomeMan4201"

if ! command -v gh >/dev/null 2>&1; then
  echo "error: GitHub CLI (gh) is required" >&2
  exit 1
fi

gh auth status >/dev/null

apply_repo() {
  local repo="$1"
  local description="$2"
  shift 2
  local topics=("$@")

  echo "==> ${OWNER}/${repo}"

  gh api \
    --method PATCH \
    -H "Accept: application/vnd.github+json" \
    "repos/${OWNER}/${repo}" \
    -f "description=${description}" \
    >/dev/null

  local args=(
    --method PUT
    -H "Accept: application/vnd.github+json"
    "repos/${OWNER}/${repo}/topics"
  )
  local topic
  for topic in "${topics[@]}"; do
    args+=( -f "names[]=${topic}" )
  done
  gh api "${args[@]}" >/dev/null
}

apply_repo "LANimals" \
  "Local-first network inventory and change-detection tooling for discovering, classifying, and tracking devices on a LAN." \
  network-security network-monitoring asset-inventory nmap python local-first change-detection security-tools

apply_repo "zer0DAYSlater" \
  "Red-team research toolkit with reproducible lab workflows, defender-oriented analysis, smoke tests, and documented detection surfaces." \
  security-research red-team detection-engineering python security-tools adversary-emulation lab defensive-security

apply_repo "Blackglass_Suite" \
  "Offline payload-research forge for controlled red-team labs, with local artifact generation and defensive inspection workflows." \
  security-research red-team payload-analysis powershell python local-first adversary-emulation defensive-security

apply_repo "shenron" \
  "Synthetic adversarial telemetry and detection-engineering research for measuring Sigma rule and campaign-correlation brittleness." \
  detection-engineering sigma-rules security-research synthetic-telemetry mitre-attack blue-team python adversary-simulation llm-security

apply_repo "GnomeMan4201" \
  "Independent security research: OSINT, detection engineering, provenance, reproducibility, and evidence-first analytical tooling." \
  security-research osint detection-engineering provenance reproducibility local-first

apply_repo "devto-analytics-pro" \
  "Local CLI analytics for DEV.to authors covering article performance, tags, audience signals, publishing patterns, and exportable reports." \
  devto analytics content-analytics python cli local-first data-analysis technical-writing

apply_repo "Decoy-Hunter" \
  "Protocol-aware service validation for networks where deception infrastructure makes large numbers of TCP ports appear open." \
  network-security deception honeypot service-detection python red-team defensive-security nmap

apply_repo "devto-bot-audit" \
  "Legacy project pointer retained for DEV.to coordinated-behavior investigation lineage; active successor is currently private." \
  legacy osint coordinated-inauthentic-behavior devto research-archive

apply_repo "drift-artifact" \
  "Static research artifact and method for examining authorship and coherence drift across iterative AI-assisted writing passes." \
  ai-research llm authorship provenance research-artifact reproducibility human-ai-interaction

apply_repo "drift_orchestrator" \
  "Experimental tooling for studying policy drift, evaluator failure, and adversarial pressure in coupled LLM safety-monitor systems." \
  ai-safety llm-security red-teaming security-research adversarial-ml evaluation python reproducibility

apply_repo "gnome-prompt-field-manual" \
  "Structured field manual for inspectable, provenance-aware AI prompting and evidence-first analytical workflows." \
  prompt-engineering ai-workflows provenance reproducibility research-methods llm security-research documentation

apply_repo "graph_anomaly_detector" \
  "Explainable graph-anomaly pipeline for detecting suspicious nodes and coordinated behavioral structure in interaction datasets." \
  graph-analysis anomaly-detection osint networkx scikit-learn coordinated-behavior python machine-learning explainability

apply_repo "OpenRedTeaming" \
  "Research fork and literature index for generative-AI red teaming, with upstream provenance preserved and local taxonomy additions tracked in Git." \
  llm-security red-teaming ai-safety research-papers literature-review adversarial-ml reference

apply_repo "r4b1t" \
  "Browser-based discovery engine for a curated corpus of live security, OSINT, research, and reference URLs." \
  osint security-research discovery web-app javascript playwright pwa research-tools curated-list

apply_repo "threatmap" \
  "Interactive D3 investigation graph for mapping actors, infrastructure, evidence, and relationships in security research." \
  osint threat-intelligence data-visualization d3js investigation security-research graph-visualization static-site

apply_repo "SubDomainizer" \
  "Retained fork of nsonaniya2010/SubDomainizer for subdomain, cloud-endpoint, and candidate-secret discovery research." \
  subdomain-enumeration reconnaissance python web-security cloud-security security-tools legacy fork

apply_repo "reasoning-diff-lab" \
  "Local-first research instrument for testing whether structured reasoning-path comparison exposes useful analytical review divergences." \
  reasoning human-ai-interaction research-tool local-first provenance reproducibility javascript analytical-methods

echo "Applied canonical descriptions and topics to 17 public repositories."
