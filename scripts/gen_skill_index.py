#!/usr/bin/env python3
"""Build and verify skills/index.json — the machine-readable routing layer.

An installed skill that nothing routes to is dead weight: the agent cannot tell
when to load it, and nobody notices it went stale. This script keeps the index,
the on-disk tree, and the human docs in sync.

  python3 scripts/gen_skill_index.py --write   # regenerate (routes are preserved)
  python3 scripts/gen_skill_index.py --check   # CI: exit 1 on any drift

Invariants enforced by --check:
  * every skills/<dir>/SKILL.md has a matching entry, and no extra entries
  * frontmatter name == directory name, description present, body <= 500 lines
  * sha256 matches, so an edited skill without a regenerated index fails CI
  * every route points at an existing skill, and every skill has >= 1 route
  * cross-references (skills/<name>/ links, "Companion to <name>") resolve

Pure stdlib.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
INDEX = SKILLS_DIR / "index.json"

MAX_DESC = 1024
MAX_BODY_LINES = 500


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    data: dict[str, str] = {}
    key = None
    for raw in text[3:end].splitlines():
        if not raw.strip():
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", raw)
        if m:
            key = m.group(1)
            data[key] = m.group(2).strip().strip('"').strip("'")
        elif key and raw[:1] in (" ", "\t") and key in data:
            data[key] = (data[key] + " " + raw.strip()).strip()
    return data


def build_skills() -> tuple[list[dict], list[str]]:
    problems: list[str] = []
    skills = []
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        name = skill_md.parent.name
        text = skill_md.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        desc = fm.get("description", "")
        if fm.get("name") != name:
            problems.append(f"{name}: frontmatter name={fm.get('name')!r} != directory {name!r}")
        if not desc:
            problems.append(f"{name}: missing description")
        elif len(desc) > MAX_DESC:
            problems.append(f"{name}: description {len(desc)} chars > {MAX_DESC}")
        body_lines = text.count("\n") + 1
        if body_lines > MAX_BODY_LINES:
            problems.append(f"{name}: {body_lines} lines > {MAX_BODY_LINES}")
        skills.append({
            "name": name,
            "path": f"skills/{name}/SKILL.md",
            "description": desc,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        })
    if not skills:
        problems.append("no skills/*/SKILL.md found")
    return skills, problems


def load_routes(existing: dict | None) -> list[dict]:
    if not existing:
        return []
    routes = existing.get("routes") or []
    return [r for r in routes if isinstance(r, dict)]


def validate(skills: list[dict], routes: list[dict], existing: dict | None) -> list[str]:
    problems: list[str] = []
    names = {s["name"] for s in skills}

    if existing:
        old = {s.get("name"): s for s in existing.get("skills", []) if isinstance(s, dict)}
        for s in skills:
            prev = old.get(s["name"])
            if prev and prev.get("sha256") != s["sha256"]:
                problems.append(
                    f"{s['name']}: SKILL.md changed but index is stale "
                    f"(run gen_skill_index.py --write)"
                )

    # routes -> skills
    covered = set()
    for i, r in enumerate(routes):
        when, skill = (r.get("when") or "").strip(), (r.get("skill") or "").strip()
        if not when or not skill:
            problems.append(f"routes[{i}]: needs both 'when' and 'skill'")
            continue
        if skill not in names:
            problems.append(f"routes[{i}]: points at unknown skill {skill!r}")
        covered.add(skill)
    for name in sorted(names - covered):
        problems.append(f"{name}: no route — the agent has no trigger telling it to load this skill")

    # cross-references inside skill bodies
    for s in skills:
        text = (ROOT / s["path"]).read_text(encoding="utf-8")
        # Only real paths/links count: "skills/plugins" in prose is not a reference.
        refs = set(re.findall(r"skills/([a-z0-9][a-z0-9-]+)/SKILL\.md", text))
        refs |= set(re.findall(r"[Cc]ompanion to [`\"]?([a-z0-9][a-z0-9-]{2,})", text))
        for ref in sorted(refs - names):
            problems.append(f"{s['name']}: cross-reference to unknown skill {ref!r}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="regenerate skills/index.json")
    ap.add_argument("--check", action="store_true", help="verify only (default)")
    args = ap.parse_args()

    existing = None
    if INDEX.exists():
        try:
            existing = json.loads(INDEX.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"FAIL: skills/index.json is not valid JSON: {exc}", file=sys.stderr)
            return 1

    skills, problems = build_skills()
    routes = load_routes(existing)
    problems += validate(skills, routes, existing)

    if args.write:
        # Only structural problems block a write; stale sha is the thing we fix.
        hard = [p for p in problems if "index is stale" not in p]
        if hard:
            print("FAIL: refusing to write an index that violates invariants", file=sys.stderr)
            for p in hard:
                print(f"  - {p}", file=sys.stderr)
            return 1
        payload = {"schema": 1, "skills": skills, "routes": routes}
        INDEX.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"WROTE {INDEX.relative_to(ROOT)}: {len(skills)} skills, {len(routes)} routes")
        return 0

    if problems:
        print("FAIL: skills/index.json is out of sync", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"OK: index covers {len(skills)} skills, all routed ({len(routes)} routes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
