# Security Policy — GnomeMan4201 / badBANANA Research

## Scope

This document provides namespace-level security reporting guidance for public repositories maintained under `GnomeMan4201`.

When a repository contains its own `SECURITY.md`, that repository-specific policy is authoritative for its supported versions, security boundaries, and reporting details.

## Reporting a vulnerability

**Do not open a public GitHub issue for a suspected vulnerability or safety-boundary failure.**

Preferred reporting path:

1. Open the affected repository's **Security** tab and use **Report a vulnerability** when private vulnerability reporting is enabled.
2. If the repository does not expose that flow, email **badbanana@proton.me** with the subject `<repository> security report`.

GitHub private vulnerability reports and security advisories are repository-scoped. Do not submit a vulnerability affecting another project to the profile repository merely because it is under the same account.

Include, where applicable:

- affected repository, version, and commit hash;
- affected file, command, endpoint, workflow, or artifact;
- expected security or safety invariant;
- observed behavior and impact;
- minimal reproduction steps;
- suggested mitigation, if known.

Do not send live credentials, unrelated personal data, production secrets, malware samples, or third-party data you are not authorized to disclose.

## PGP

PGP-encrypted disclosure is available for sensitive reports:

```text
pub   rsa4096
      D6BB 6A66 78D1 AC8F 9234  3982 C6A7 2EB5 BAB2 262E
uid   GnomeMan4201 (badBANANA Research Collective)
```

Verify the fingerprint before relying on a key obtained from an untrusted mirror or message.

## Response expectations

I aim to acknowledge a reproducible private report within seven days. Validation, remediation, release, and coordinated-disclosure timing depend on severity, reproducibility, project status, and available capacity.

No fixed remediation deadline is promised before the report is validated. This is an independent research operation, so the policy should describe a process I can actually sustain rather than imply an institutional response team.

## What belongs in a private report

Examples include:

- unintended command, subprocess, shell, or payload execution;
- authentication or authorization failures;
- unsafe network behavior that violates a documented local/synthetic boundary;
- path traversal, unsafe archive handling, or unintended filesystem writes;
- committed secrets or sensitive generated artifacts;
- insecure cryptographic or transport behavior;
- CI/release workflows with unnecessary or unsafe privileges;
- dependency or supply-chain issues with a meaningful exploit path;
- evidence/validation code silently accepting data outside its documented contract.

Ordinary bugs, feature requests, documentation corrections, and non-sensitive false-positive discussions may use public issues when the affected repository enables them.

## Good-faith research and disclosure

- Please allow a reasonable remediation window before public disclosure.
- Confirmed fixes should be documented when practical.
- Reporter credit is welcome unless anonymity is requested.
- Good-faith security research and responsible disclosure are not grounds for retaliation.

## Dual-use research

Some repositories contain adversarial-simulation or other dual-use security research. A public repository description is not authorization to test third-party systems. Use security tooling only in environments you own or are explicitly authorized to assess.

---

*GnomeMan4201 / badBANANA Research · Updated 2026-08*
