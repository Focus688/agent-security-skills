#!/usr/bin/env python3
"""Self-test for probe_skill_pack.py: catches the planted pack, stays quiet on ours.

Two assertions, both necessary:
  1. labs/bad-skill-pack produces exactly the frozen finding set (no extras, no
     misses) — a probe that fires on everything is as useless as one that fires
     on nothing.
  2. skills/ (the shipped pack) produces zero findings — the checks must not cry
     wolf on the material this repo asks others to write.

  python3 scripts/test_probe_skill_pack.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from probe_skill_pack import probe  # noqa: E402


def pairs(findings: list[dict]) -> list[tuple[str, str]]:
    return sorted((f["file"], f["code"]) for f in findings)


def main() -> int:
    expected = json.loads((ROOT / "labs" / "expected.json").read_text(encoding="utf-8"))
    want = sorted((f["file"], f["code"]) for f in expected["findings"])

    got_bad = pairs(probe(ROOT / "labs" / "bad-skill-pack"))
    got_clean = pairs(probe(ROOT / "skills"))

    ok = True
    if got_bad != want:
        ok = False
        print("FAIL: planted pack does not match expected findings")
        for item in sorted(set(want) - set(got_bad)):
            print(f"  missing: {item}")
        for item in sorted(set(got_bad) - set(want)):
            print(f"  unexpected: {item}")
    else:
        print(f"PASS  planted pack: {len(got_bad)} findings, exact match")

    if got_clean:
        ok = False
        print(f"FAIL: probe flags the shipped skills ({len(got_clean)} false positive(s))")
        for item in got_clean:
            print(f"  {item}")
    else:
        print("PASS  shipped skills: 0 findings")

    print(f"\n{'SELF-TEST PASS' if ok else 'SELF-TEST FAIL'}: planted={len(got_bad)} clean={len(got_clean)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
