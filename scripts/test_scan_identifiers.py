#!/usr/bin/env python3
"""Self-test for scan_identifiers.py — the guard must fail closed.

Each case builds a throwaway tree and asserts the exit code. A leak guard that
passes when its own denylist is missing is theatre, so cases 5-6 are the point.

  python3 scripts/test_scan_identifiers.py
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCANNER = HERE / "scan_identifiers.py"
CLEAN = "# Notes\n\nNothing sensitive here. See `skills/index.json`.\n"


def sha(token: str) -> str:
    return hashlib.sha256(token.strip().lower().encode()).hexdigest()


def run(root: Path, denylist: Path | None):
    cmd = [sys.executable, str(SCANNER), "--root", str(root)]
    if denylist is not None:
        cmd += ["--denylist", str(denylist)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def case(name: str, files: dict[str, str], expect: int, denylist: str | None = "AUTO"):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "README.md").write_text(files.pop("README.md", CLEAN), encoding="utf-8")
        for rel, body in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")

        if denylist == "AUTO":
            dl = root / "denylist.sha256"
            dl.write_text(f"# test denylist\n{sha('client-acme-8842')}\n", encoding="utf-8")
        elif denylist is None:
            dl = root / "missing.sha256"
        else:
            dl = root / "denylist.sha256"
            dl.write_text(denylist, encoding="utf-8")

        rc, out = run(root, dl)
        ok = rc == expect
        print(f"{'PASS' if ok else 'FAIL'}  {name}: exit {rc} (expected {expect})")
        if not ok:
            print("      " + out.replace("\n", "\n      ")[:800])
        return ok


def main() -> int:
    results = [
        case("clean tree", {}, 0),
        # Fixtures are assembled at runtime so this test file itself stays leak-free
        # (the guard scans its own repo; a literal sample key would trip it).
        case("client email", {"docs/note.md": "contact " + "alice" + "@" + "acme-corp.com\n"}, 1),
        case("aws key", {"README.md": "key " + "AKIA" + "IOSFODNN7EXAMPLE\n"}, 1),
        case("private key block", {"k.md": "-----BEGIN RSA " + "PRIVATE KEY-----\n"}, 1),
        case("denylisted identifier", {"README.md": "engagement: " + "client-acme-" + "8842\n"}, 1),
        case("public ip", {"n.md": "host " + "45.33" + ".12.9\n"}, 1),
        case("private ip allowed", {"n.md": "host 10.0.0.5\n"}, 0),
        case("noreply email allowed", {"n.md": "bot@users.noreply.github.com\n"}, 0),
        case("denylist missing -> fail closed", {"README.md": CLEAN}, 2, denylist=None),
        case("denylist empty -> fail closed", {}, 2, denylist="# only comments\n"),
        case("denylist malformed -> fail closed", {}, 2, denylist="not-a-hash\n"),
    ]
    failed = results.count(False)
    print(f"\n{'SELF-TEST PASS' if failed == 0 else 'SELF-TEST FAIL'}: {len(results) - failed}/{len(results)} cases")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
