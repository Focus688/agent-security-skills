# Health-Check Patterns: Avoiding "Fake Green"

A health check that passes while the underlying capability is broken is worse than no check — it launders failure into "verified". Patterns below are all drawn from real incidents.

## Pattern 1: Test the external command, not the wrapper

**Incident**: after a third-party update drop-in-replaced a shared library, the `sqlite3` CLI died on launch (`symbol lookup error`). Every script calling it had `2>/dev/null`, so cron jobs kept "succeeding".

**Rule**: when "a feature recently broke", first run the external binary itself, interactively, with stderr visible. Only then debug the wrapper.

```bash
# Bad (in scripts): sqlite3 db "query" 2>/dev/null
# Good: sqlite3 db "query" || { echo "sqlite3 CLI failed"; exit 1; }
```

Never route stderr to the void in automated scripts. Send it to a log file.

## Pattern 2: Artifact must be calendar-forward, not merely present

**Incident**: a nightly data-refresh cron reported success for months because success = "output file exists". The upstream source had frozen over a year earlier and never errored.

**Rule**: success = artifact is **newer than the last expected refresh window** (e.g. mtime within today / last trading day), never just "exists".

```bash
# cron-visible failure signal:
find /data/output -name "*.json" -mtime -1 | grep -q . || echo "STALE: no fresh artifact in 24h"
```

A watchdog cron that only fires on staleness (silent otherwise) is the right shape: quiet when healthy, loud when broken.

## Pattern 3: Probe with real traffic, not process state

`systemctl is-active` proves a process exists — not that it works. The meaningful probe for an LLM gateway is one real round-trip:

```bash
<agent> chat -q "reply with one word: ok"
```

For an MCP server: list its tools. For a search backend: one real query. Process-up + endpoint-dead is the most common "fake green".

## Pattern 4: Read back what you wrote/posted

An API returning 200 doesn't mean the payload landed correctly (truncation, encoding, silent field drops). Any write → read the object back and compare content length / key fields against what you sent. Close the loop.

## Pattern 5: Silent-rate-limit awareness

Third-party platforms (SMS gateways, social APIs) sometimes silently block instead of erroring: page says "sent", nothing arrives, no error anywhere. Rules:

- After repeated silent failure, **stop retrying** — retries extend the block.
- Treat "no response ≠ no send": verify receipt through a second channel before re-triggering.

## Generalization

Any pipeline that can fail silently will. Audit yours for: swallowed stderr, existence-only success checks, process-state-only probes, fire-and-forget writes, and unverified third-party send paths. Each one is a place where "green" means nothing.
