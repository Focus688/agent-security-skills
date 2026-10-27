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

## Release gate (how changes ship)
1. Run every skill's rules against real usage; a rule without a real incident behind it does not ship.
2. **Adversarial review before release**: every SKILL.md is red-teamed by a frontier model (Claude Opus) acting as an attacker, with one question — *can this text be turned against the agent that follows it?*
3. Findings are fixed or explicitly rejected in the commit message; findings that change a rule are credited in the rule itself.
   Example: the injection guard in `skill-review-checklist` §2 exists because red-team review found that the checklist told reviewers to read untrusted text without telling them to treat it as inert data.
4. Tag `vX.Y.Z`; the skills.sh listing updates from install telemetry, not from a submission form.
