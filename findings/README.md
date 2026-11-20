# Field Audits: War Stories from Real Supply Chains

This is the index of audits we actually ran against third-party agent capabilities — not hypothetical threat models. Each entry links the published report, states what was found, and points to the skill in this repo that encodes the lesson.

Every number below is reported as published in the linked report; the reports themselves quote the raw evidence (file paths, line numbers, screenshots of behaviour).

| Date | Target | Core finding | Skills that encode the lesson | Report |
|---|---|---|---|---|
| 2026-11-14 | **Cindy** — open-source desktop Agent shell, 7.4k★. All 10 officially bundled skills audited. | **10/10 skills had high-severity defects; zero passed.** The defects shared one template: no credential exclusion zone, no data-source boundary, no failure semantics for scripts, no definition of what counts as an authorised action. | [`skill-review-checklist`](../skills/skill-review-checklist/SKILL.md) (the 4 seams to check in any vendor template) · [`secure-addon-install`](../skills/secure-addon-install/SKILL.md) (snapshot before install, verify behaviour after) | [cindy-audit.html](https://focus688.github.io/levi-focus/cindy-audit.html) |
| 2026-11-14 · re-tested 2026-11-18 | **vercel-labs/skills** — the `skills` CLI, 39.3k★, the distribution entry point behind ~3.7M installs. 3 bundled skills + CLI source audited. | **0 high, 4 medium** — but the gap is structural: Cindy lacked skill-authoring discipline, vercel lacks distribution gatekeeping. The `find-skills` entry point is exactly where the two sides meet. | [`skill-review-checklist`](../skills/skill-review-checklist/SKILL.md) (4-step channel audit: telemetry disclosure, `-y` defaults, install-count/star trust signals, scripts written to disk) · [`secure-addon-install`](../skills/secure-addon-install/SKILL.md) | [vercel-skills-audit.html](https://focus688.github.io/levi-focus/vercel-skills-audit.html) |

## How to read this table

- **"0 high" is not "safe".** The vercel audit found no high-severity issues in the code it covered; it still documents an unguarded distribution surface. Read the medium findings before installing anything through that channel.
- **Coverage is stated, not implied.** The Cindy audit covered all 10 bundled skills; the vercel audit covered 3 skills plus CLI source. Neither audit covers the whole registry behind each project.
- **Findings are time-stamped.** Both reports list what was tested and when; treat the numbers as a snapshot, not a permanent rating of the upstream project.

## Contributing a field audit

An audit belongs here only if it has: (1) a public report with reproducible evidence, (2) a named target and version/commit, (3) at least one finding that maps back to a skill in this repo (or a concrete proposal for a new one). We do not index vendor marketing pages or unreproducible claims.