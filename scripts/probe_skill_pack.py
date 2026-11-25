#!/usr/bin/env python3
"""Probe a directory of SKILL.md files for the defect classes in this repo.

This is not a malware scanner and does not try to be: it checks the specific
failure modes `skill-review-checklist` asks a human to check, so the checks can
be exercised on a known-bad pack instead of described in prose.

  python3 scripts/probe_skill_pack.py <dir> [--json]
Exit: 0 no findings, 1 findings, 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

# Imperative instructions only. Words like "data exfiltration" in a threat-model
# description are the subject matter, not a payload — matching bare stems here
# produced a false positive on llm-attack-surface.
INJECTION = re.compile(
    r"(ignore (all |the )?(previous|prior|above) instructions?"
    r"|do not (tell|inform|warn) the user"
    r"|without (asking|telling) the user"
    r"|(upload|exfiltrate|send)\b[^.]{0,40}(https?://|<[A-Z_]+>))",
    re.I,
)
SELF_AUTHORIZE = re.compile(
    r"(approve (this|the) skill|return (PASS|OK) without|do not flag|mark (it |this )?as (safe|approved))",
    re.I,
)
BROAD_TOOLS = re.compile(r"allowed-tools\s*:\s*(?:\*|all|bash|shell)(?=\s|$)", re.I | re.M)
HIDDEN = re.compile("[\u00ad\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")
COMMENT = re.compile(r"<!--(.*?)-->", re.S)
FENCE = re.compile(r"```.*?```", re.S)
REF = re.compile(r"skills/([a-z0-9][a-z0-9-]+)/SKILL\.md")


def parse(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm: dict[str, str] = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm, text[end + 4:]


def probe(root: Path) -> list[dict]:
    skills = sorted(root.glob("*/SKILL.md"))
    names = {p.parent.name for p in skills}
    findings: list[dict] = []

    def add(path: Path, code: str, detail: str) -> None:
        findings.append({"file": f"{path.parent.name}/SKILL.md", "code": code, "detail": detail})

    for md in skills:
        raw = md.read_text(encoding="utf-8")
        fm, body = parse(raw)
        dirname = md.parent.name

        if fm.get("name") != dirname:
            add(md, "NAME_MISMATCH", f"name={fm.get('name')!r} != dir {dirname!r}")
        if not fm.get("license"):
            add(md, "NO_LICENSE", "frontmatter has no license field")
        desc = fm.get("description", "")
        if len(desc) < 40:
            add(md, "VAGUE_DESCRIPTION", f"{len(desc)} chars; a router cannot tell when to load it")
        if INJECTION.search(desc):
            add(md, "INJECTION_IN_METADATA", "description carries an instruction to the reading agent")
        if BROAD_TOOLS.search(raw):
            add(md, "OVERBROAD_TOOLS", "allowed-tools is unrestricted (wildcard/shell)")

        hidden = []
        for lineno, line in enumerate(raw.splitlines(), 1):
            for ch in HIDDEN.finditer(line):
                hidden.append(f"line {lineno}: U+{ord(ch.group(0)):04X} ({unicodedata.category(ch.group(0))})")
        if hidden:
            add(md, "HIDDEN_CHARS", "; ".join(hidden))

        prose = FENCE.sub("", body)  # demo snippets may legitimately show comments
        for m in COMMENT.finditer(prose):
            inner = m.group(1)
            if INJECTION.search(inner) or SELF_AUTHORIZE.search(inner):
                add(md, "COMMENT_INSTRUCTION", "HTML comment (invisible when rendered) carries an instruction")

        if SELF_AUTHORIZE.search(raw):
            add(md, "SELF_AUTHORIZING", "text tries to instruct the reviewer's verdict")

        for ref in sorted(set(REF.findall(raw)) - names):
            add(md, "DANGLING_REF", f"references skills/{ref}/SKILL.md which is not in the pack")

    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"FAIL: not a directory: {root}", file=sys.stderr)
        return 2
    findings = probe(root)
    if args.json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
    else:
        for f in findings:
            print(f"{f['file']}: {f['code']} — {f['detail']}")
        print(f"\n{len(findings)} finding(s) across {len(list(root.glob('*/SKILL.md')))} skill file(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
