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

## Pattern 2: Artifact must prove it contains fresh data

**Incident**: a nightly data-refresh cron reported success for months because success = "output file exists". The upstream source had frozen over a year earlier and never errored. Later reflection: the first "fix" (check mtime) would not have caught it either — see the mtime caveat below.

**Rule**: success = the artifact **carries its own proof of new data** — a `generated_at` / `max_date` / monotonic `id` / row count that a frozen upstream cannot fabricate by being copied again. mtime is only a **cheap first screen**: `cp -p`, `rsync -t`, and `touch` all preserve or forge it, and a nightly re-copy of a dead source gets a brand-new mtime.

```bash
# BAD: mtime only — freshness is forgeable, and "fresh file" != "fresh data"
find /data/output -name "*.json" -mtime -1 | grep -q . && echo OK

# GOOD: assert CONTENT — same rule and same incident as silent-failure-sweep §2
python3 - <<'PY'
import json, datetime, sys
WINDOW_H = 26                      # parameterise per cadence; -mtime -1 is wrong for hourly/weekly jobs
d = json.load(open("/data/output/today.json"))
ts = d.get("generated_at") or d.get("max_date") or d.get("latest_id")
ok = ts is not None and datetime.datetime.fromisoformat(ts) > datetime.datetime.now() - datetime.timedelta(hours=WINDOW_H)
print(("OK " if ok else "STALE ") + f"content_ts={ts}")
sys.exit(0 if ok else 1)
PY
```

Prefer a monotonic field (max(id), latest date, row count) over any timestamp the upstream writes into the payload — a timestamp can be stale-but-plausible, a max(id) that never advances cannot.

A watchdog cron that only fires on staleness (silent otherwise) is the right shape: quiet when healthy, loud when broken.

**Companion**: `skills/silent-failure-sweep/SKILL.md` §2 applies this same rule as a fleet-wide sweep — use that checklist to audit every job at once, and this pattern when writing the check for a single job.

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
