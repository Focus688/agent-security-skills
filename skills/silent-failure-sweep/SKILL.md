---
name: silent-failure-sweep
description: "Periodically sweep an agent's cron jobs, scripts, and pipelines for silent failures: swallowed stderr, existence-only success checks, stale artifacts, dead probes. Companion to secure-addon-install."
license: MIT
metadata:
  category: security
  compatibility: "Any agent runtime with scheduled jobs or pipelines"
  version: 1.0.0
---

# Silent-Failure Sweep for Scheduled Jobs & Pipelines

Run this sweep **periodically** (monthly is a good cadence) over every cron job, scheduled task, and data pipeline in your agent runtime. Its premise: **any pipeline that can fail silently will**, and the older the pipeline, the more likely something upstream already broke without anyone noticing.

## The five silent-failure signatures

### 1. Swallowed stderr
`grep` every cron-invoked script for `2>/dev/null` and bare `|| true`:

```bash
# Scope the corpus explicitly and fail loudly if you found nothing — a missing corpus is not "clean".
mapfile -t FILES < <(find ~/scripts /etc/cron.d -maxdepth 2 -type f 2>/dev/null; ls /etc/crontab 2>/dev/null)
[ ${#FILES[@]} -gt 0 ] || { echo "ABORT: corpus empty — paths wrong, this is not a clean result"; exit 1; }
echo "scanning ${#FILES[@]} files"
grep -rn "2>/dev/null" "${FILES[@]}" || echo "no bare 2>/dev/null in ${#FILES[@]} files"
grep -rn "|| true" "${FILES[@]}" || echo "no bare || true in ${#FILES[@]} files"
```

Note the fixed shape: no `2>/dev/null` on the `grep` itself (that would hide permission-denied and bad-glob errors and present them as *no findings*), an explicit file count, and a check that the corpus is non-empty. **An audit that silently scanned zero files reports success — the exact failure this skill exists to catch.**

Each hit is a place where a loud failure was converted into silence. **Fix**: redirect stderr to a log file. If the command is "allowed to fail", say so explicitly with a fallback action, not with the void.

**Real incident**: a system `sqlite3` CLI was hijacked by a third-party drop-in library and died on launch; every calling script had `2>/dev/null`, so the breakage was invisible for days until a human ran the binary manually.

### 2. Existence-only success checks
`grep` your job scripts for success logic that checks *presence*, not *freshness*:

```bash
# BAD: file exists = success
[ -f /data/output/today.json ] && echo OK

# ALSO BAD: mtime "freshness" — a frozen upstream re-copied nightly gets a brand-new mtime,
# and `cp -p` / `rsync -t` / `touch` preserve or forge it. mtime is a cheap screen, not proof.
find /data/output -name "today.json" -mmin -1440 | grep -q . && echo OK || echo "STALE"

# GOOD: assert CONTENT — read a timestamp/id/row count out of the artifact
python3 - <<'PY'
import json, datetime, sys
WINDOW_H = 26                      # parameterise per cadence; 1440min is wrong for weekly/hourly jobs
d = json.load(open("/data/output/today.json"))
ts = d.get("generated_at") or d.get("max_date") or d.get("latest_id")
ok = ts is not None and datetime.datetime.fromisoformat(ts) > datetime.datetime.now() - datetime.timedelta(hours=WINDOW_H)
print(("OK " if ok else "STALE ") + f"content_ts={ts}")
sys.exit(0 if ok else 1)
PY
```

The rule: **the artifact must prove it contains new data**, not merely that it was written recently. Prefer a monotonic field (max(id), latest date, row count) that a stale source cannot fabricate by being copied again.

**Real incident**: a nightly data-refresh job reported success for months because "output file exists" was the check — the upstream source had been frozen for over a year.

### 3. Dead probes (health check that can't fail)
For every "health check" ask: **what input would make it fail?** A check that returns OK regardless of upstream state (`curl` without `--fail`, a process-alive check for a process whose endpoint is dead, a ping to a load balancer) is decoration, not monitoring.

```bash
# BAD: always exits 0 if server is up, even when app is 500ing
curl -s http://svc/health

# GOOD: fails on HTTP errors and validates content
curl -sf --max-time 10 http://svc/health | grep -q '"status":"ok"'
```

### 4. Fire-and-forget writes
Any POST/publish/send without a read-back. An HTTP 200 doesn't mean the payload landed intact (truncation, encoding, dropped fields). **Fix**: read the object back after writing and compare length/key fields against what you sent.

### 5. Unverified third-party send paths
SMS, social APIs, notification platforms: some silently rate-limit or block ("page says sent, nothing arrives, no error anywhere"). Sweep for jobs that trigger external sends and verify: does the job check *receipt* through a second channel? **Rule**: after repeated silent failure, stop retrying — retries extend silent blocks.

## Sweep procedure (monthly)

1. List all scheduled jobs (`crontab -l`, `systemctl --user list-timers`, your agent's cron registry).
2. For each, classify: what is its success check? Tag each with the first signature above it exhibits.
3. For data pipelines: verify the newest artifact is within the expected freshness window **right now**. Anything stale → investigate upstream, don't just re-run.
4. For external-sending jobs: check the last N sends were actually received (platform-side read-back or a second channel).
5. Log the sweep result with a date. The sweep itself follows the calendar-forward rule: no sweep record newer than 35 days = your monitoring has silently failed too.

## Meta-lesson

Monitoring systems fail silently like everything else. Your sweep must itself have a freshness check, and its records must be written somewhere that itself gets looked at. Otherwise you have built a smoke detector with a dead battery that reports "no smoke" every day.
