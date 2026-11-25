#!/usr/bin/env python3
"""Leak guard: block client identifiers, credentials, and private paths.

Motivation: the leak that hurts a security repo is never a payload — it is a
client name, an engagement codename, an email, or a key that slipped into a
README while writing "anonymised" examples. Manual redaction fails eventually.

Two layers:
  1. pattern layer — secrets, emails, global IPs, absolute home paths
  2. denylist layer — sha256 hashes of identifiers that must never appear.
     Hashes only: the file is public, plaintext would be the leak itself.

FAIL CLOSED: missing, empty, or malformed denylist exits 2. A guard that
silently scans nothing is worse than no guard.

  python3 scripts/scan_identifiers.py [--root DIR] [--denylist FILE]
Exit: 0 clean, 1 hits, 2 denylist unusable.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DENYLIST = ROOT / ".github" / "identifier-denylist.sha256"

SECRET_PATTERNS = [
    ("aws_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
IPV4_RE = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")
HOME_RE = re.compile(r"/home/[a-z][a-z0-9_-]{1,}/")
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{7,}")

ALLOWED_EMAIL_DOMAINS = {
    "users.noreply.github.com", "noreply.github.com",
    "example.com", "example.org", "example.net", "localhost",
}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
             ".mypy_cache", ".pytest_cache", ".ruff_cache"}
SKIP_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".woff", ".woff2",
             ".ttf", ".otf", ".pdf", ".zip", ".gz", ".tar", ".mp4", ".jar", ".pyc"}
MAX_BYTES = 2 * 1024 * 1024


def sha(token: str) -> str:
    return hashlib.sha256(token.strip().lower().encode("utf-8")).hexdigest()


def load_denylist(path: Path) -> set[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"FAIL(closed): denylist not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    except OSError as exc:
        print(f"FAIL(closed): cannot read denylist: {exc}", file=sys.stderr)
        raise SystemExit(2)

    hashes = set()
    for lineno, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", line):
            print(f"FAIL(closed): denylist line {lineno} is not a sha256 hex digest", file=sys.stderr)
            raise SystemExit(2)
        hashes.add(line)
    if not hashes:
        print(f"FAIL(closed): denylist is empty: {path}", file=sys.stderr)
        raise SystemExit(2)
    return hashes


def iter_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in SKIP_EXTS:
            continue
        try:
            if p.stat().st_size > MAX_BYTES:
                continue
            data = p.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:1024]:
            continue
        yield p, data.decode("utf-8", errors="replace")


def mask(value: str) -> str:
    return f"{value[:4]}…({len(value)} chars)"


def scan(root: Path, denylist: set[str]) -> list[tuple[str, int, str, str]]:
    hits: list[tuple[str, int, str, str]] = []
    for path, text in iter_files(root):
        rel = str(path.relative_to(root))
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pattern in SECRET_PATTERNS:
                for m in pattern.finditer(line):
                    hits.append((rel, lineno, label, mask(m.group(0))))
            for m in EMAIL_RE.finditer(line):
                if m.group(1).lower() in ALLOWED_EMAIL_DOMAINS:
                    continue
                hits.append((rel, lineno, "email", mask(m.group(0))))
            for m in IPV4_RE.finditer(line):
                try:
                    ip = ipaddress.ip_address(m.group(0))
                except ValueError:
                    continue
                if ip.is_global:  # private/loopback/reserved/documentation are fine
                    hits.append((rel, lineno, "public_ip", mask(m.group(0))))
            for m in HOME_RE.finditer(line):
                hits.append((rel, lineno, "home_path", m.group(0)))
            for m in TOKEN_RE.finditer(line):
                token = m.group(0)
                if sha(token) in denylist:
                    hits.append((rel, lineno, "denylisted_identifier", mask(token)))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--denylist", default=str(DEFAULT_DENYLIST))
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"FAIL(closed): root is not a directory: {root}", file=sys.stderr)
        return 2

    denylist = load_denylist(Path(args.denylist))
    hits = scan(root, denylist)

    if hits:
        print(f"FAIL: {len(hits)} potential leak(s) found", file=sys.stderr)
        for rel, lineno, label, shown in hits:
            print(f"  {rel}:{lineno}  [{label}] {shown}", file=sys.stderr)
        print("\nRedact, replace with a synthetic example, or add the identifier's "
              "sha256 to .github/identifier-denylist.sha256 if it is a false positive.",
              file=sys.stderr)
        return 1

    print(f"OK: no identifiers or secrets found ({len(denylist)} hashed entries active)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
