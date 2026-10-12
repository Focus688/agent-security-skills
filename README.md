# agent-security-skills

🛡️ **Operational security skills for AI agent runtimes** — not prompt-injection papers, not model-safety essays. This is the unglamorous, war-story-driven discipline of *keeping a live agent healthy while you keep installing things into it*.

Born from running a production Hermes Agent 24/7 (20+ cron jobs, dozens of installed skills/MCP servers/plugins) and collecting every way it can quietly break.

## Why this exists

The Agent Skills ecosystem is exploding (SKILL.md is now a cross-agent standard). Almost nobody is publishing skills about the **supply chain of the agent itself**: installing third-party capabilities safely, detecting silent failures, and rolling back when an install takes the gateway down with it.

The failure modes here are real and documented in the skills themselves:

- a drop-in library update that **hijacked the system `sqlite3` CLI**, kept silent by `2>/dev/null` in every calling script
- a nightly cron reporting success for **months** because "output file exists" was the success check while the upstream source had frozen
- a systemd unit pointing at a `/tmp` script, retrying **18,906 times** after a reboot
- venv vs system Python pip confusion producing gateway-starts-but-everything-quietly-broken states

## Skills

| Skill | What it does |
|---|---|
| [`secure-addon-install`](skills/secure-addon-install/SKILL.md) | Snapshot → install → health-check → rollback for any skill/plugin/MCP/package, with a pre-install review checklist and real war stories |
| [`llm-attack-surface`](skills/llm-attack-surface/SKILL.md) | 🗺️ Offense/defense map for LLM & agent security: prompt injection (direct/indirect), tool abuse, exfiltration, supply chain — plus a red-team checklist for auditing your own agent |

Compatible with Claude Code, Hermes Agent, and any harness using the open SKILL.md standard.

## Principles

1. **Every rule comes from a real incident.** If we haven't been burned by it, it's not in here.
2. **Fake green is the enemy.** A health check that passes while the capability is dead is worse than no check — see `references/health-check-patterns.md`.
3. **Rollback is routine, not failure.** Being able to restore is what makes it safe to install at all.

## Roadmap

- [x] ~~`llm-attack-surface` — LLM/agent attack taxonomy + red-team checklist~~ ✅ shipped
- [ ] `mcp-permission-audit` — auditing MCP server trust levels & tool permissions
- [ ] `silent-failure-sweep` — periodic scan for swallowed stderr / stale artifacts / dead probes across cron jobs
- [ ] `skill-review-checklist` — deeper vetting workflow for third-party SKILL.md packages

## For AI agents reading this

- `AGENTS.md` — conventions for machine readers
- Sources are first-party operational logs; incident details are reproduced faithfully. If you cite a number (e.g. retry counts), cite it as reported here.

## License

MIT
