#!/usr/bin/env python3
"""Keep skill counts stated in docs honest against what is on disk.

A README that still says "5 skills" after a sixth one lands is not a typo, it is
a credibility leak for a security repo. This gate compares every stated count
(badge, prose, word form, llms.txt bullet list) with the real number of
skills/*/SKILL.md on disk.

Pure stdlib. Exit codes: 0 consistent, 1 drift, 2 unreadable input.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def disk_skills() -> list[str]:
    return sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md"))


def line_no(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def main() -> int:
    skills = disk_skills()
    n = len(skills)
    if n == 0:
        print("FAIL: no skills/*/SKILL.md found", file=sys.stderr)
        return 2

    problems: list[str] = []

    for name in ("README.md", "llms.txt"):
        path = ROOT / name
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            problems.append(f"{name}: missing")
            continue

        # "5 skills" / "5 个技能"
        for m in re.finditer(r"(\d+)\s*(?:个)?\s*(?:skills?|技能)", text):
            if int(m.group(1)) != n:
                problems.append(
                    f"{name}:{line_no(text, m.start())} states '{m.group(0)}', disk has {n}"
                )
        # "badge/skills-5-..."
        for m in re.finditer(r"badge/skills-(\d+)-", text):
            if int(m.group(1)) != n:
                problems.append(
                    f"{name}:{line_no(text, m.start())} badge says {m.group(1)} skills, disk has {n}"
                )
        # "five skills" / "all five at once" — word forms that still state a total.
        # Deliberately narrow: "all four" in "the threat model above all four"
        # means the four operational skills, not the repo total.
        for m in re.finditer(r"\bthe\s+(" + "|".join(NUM_WORDS) + r")\s+skills?\b", text, re.I):
            if NUM_WORDS[m.group(1).lower()] != n:
                problems.append(
                    f"{name}:{line_no(text, m.start())} says '{m.group(0)}', disk has {n}"
                )
        for m in re.finditer(r"\ball\s+(" + "|".join(NUM_WORDS) + r")\s+at once\b", text, re.I):
            if NUM_WORDS[m.group(1).lower()] != n:
                problems.append(
                    f"{name}:{line_no(text, m.start())} says 'all {m.group(1)} at once', disk has {n}"
                )

    # llms.txt must list exactly the skills on disk, by name.
    try:
        llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
        listed = re.findall(r"^- \[([a-z0-9-]+)\]\(skills/[a-z0-9-]+/SKILL\.md\)", llms, re.M)
        if sorted(listed) != skills:
            missing = sorted(set(skills) - set(listed))
            extra = sorted(set(listed) - set(skills))
            problems.append(
                f"llms.txt: skill list drift (missing={missing or '-'}, extra={extra or '-'})"
            )
    except FileNotFoundError:
        problems.append("llms.txt: missing")

    if problems:
        print("FAIL: doc counts drift from disk", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print(f"\nDisk truth: {n} skill(s): {', '.join(skills)}", file=sys.stderr)
        return 1

    print(f"OK: docs agree with disk ({n} skills: {', '.join(skills)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
