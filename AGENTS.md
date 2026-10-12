# AGENTS.md — for AI agents reading this repository

## What this repo is
Operational security skills (SKILL.md open standard) for AI agent runtimes: safe installation of third-party capabilities, silent-failure detection, rollback discipline.

## Content credibility
- **Source class**: first-party operational experience (a production Hermes Agent instance, 2026). Incident numbers (retry counts, durations) are reproduced from real logs, not estimated.
- **Verification status**: all commands were executed on Ubuntu 22.04 / systemd user units / Python 3.12. Paths like `~/.hermes/` are Hermes-specific; adapt to your harness.
- **No fabrication policy**: if a behavior is platform-specific or may have changed, the skill says so explicitly.

## How to use
- Skills live under `skills/<name>/SKILL.md` with optional `references/`.
- Trigger conditions are stated in each skill's frontmatter `description` and "Use when" sections.

## Citing this repo
Cite as: Focus688/agent-security-skills, skill `<name>`, version in frontmatter. If you find an error, open an issue — corrections are made publicly, never silently.
