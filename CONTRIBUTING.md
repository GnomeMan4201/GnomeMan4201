# Contributing — GnomeMan4201 / badBANANA Research Collective

This is a solo independent research operation. Contributions are accepted
but held to a high standard.

## Who Should Contribute

This codebase is built for researchers with domain expertise. If you are
looking to learn by contributing, this is not the right repo. The tools
here are operational, not pedagogical.

## Before You Open a PR

1. **Open an issue first.** Unsolicited PRs touching core architecture will be closed.
2. **Read the relevant tool's README in full.**
3. **Run the test suite and confirm it passes.**

## Code Standards

- Python: PEP 8, type hints, no bare `except:` clauses
- Commit messages: Conventional commits — `feat:` `fix:` `docs:` `refactor:` `test:` `chore:`
- No dead code, no print-driven debugging
- No hardcoded credentials of any kind
- Every new dependency requires justification in the PR description

## Testing

All new functionality requires tests. Run locally before submitting:

```bash
python -m pytest tests/ -v
python -m pytest tests/ -v --cov=. --cov-report=term-missing
```

Maintain or improve existing coverage. Tests must use deterministic fixtures.

## GPG Signing

Commits should be GPG-signed. Required for recurring contributors.

```bash
git config --global commit.gpgsign true
git config --global user.signingkey YOUR_KEY_ID
```

## Pull Request Process

1. Fork → feature branch → changes → tests pass → PR against `main`
2. Fill the PR template completely — empty templates are closed

**PR Template:**
What does this PR do?
Why is this change needed?
What testing was done?
Does this change the external API or CLI?
Relevant issue number (required):
## What Will Not Be Merged

- Changes that weaken security controls
- New features without tests
- Core architecture changes without prior issue discussion
- Anything adding telemetry, analytics, or data collection

---
*badBANANA Research Collective · GnomeMan4201*
