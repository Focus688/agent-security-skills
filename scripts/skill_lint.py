#!/usr/bin/env python3
"""skill-lint: make this repo's own rules a green light.

Checks every `skills/*/SKILL.md` for:
  1. YAML frontmatter with required fields: name, description, license
  2. `name` matches the skill directory name
  3. hidden / invisible characters (Unicode Cf, Co, Cs + common zero-width &
     bidi codepoints) anywhere in the skill package's Markdown
  4. HTML comments outside fenced code blocks, unless the line carries an
     explicit `lint-allow-html-comment` marker

Pure standard library, no PyYAML: the frontmatter subset used by SKILL.md is
flat `key: value`, so a line parser is sufficient and has no install cost.

Exit 0 = all checks pass. Exit 1 = at least one finding.
Usage: python3 scripts/skill_lint.py [repo_root]
"""
import os
import re
import sys
import unicodedata

REQUIRED = ("name", "description", "license")
# Cf/Co/Cs already cover most of these; the explicit set documents intent and
# catches runtimes that normalise categories differently.
INVISIBLE_CODEPOINTS = {
    0x200B, 0x200C, 0x200D, 0x200E, 0x200F,          # zero-width, LRM/RLM
    0x202A, 0x202B, 0x202C, 0x202D, 0x202E,          # bidi embedding/override
    0x2066, 0x2067, 0x2068, 0x2069,                  # bidi isolates
    0xFEFF, 0x00AD,                                  # BOM, soft hyphen
}
FENCE_RE = re.compile(r'^ {0,3}(`{3,}|~{3,})')
COMMENT_RE = re.compile(r'<!--')
ALLOW_MARKER = 'lint-allow-html-comment'


def split_frontmatter(text):
    """Return (frontmatter_lines, body_start_index) or (None, 0)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        return None, 0
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            return lines[1:i], i + 1
    return None, 0


def parse_flat_yaml(lines):
    data = {}
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        m = re.match(r'^([A-Za-z0-9_.-]+):\s*(.*)$', raw)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in '"\'':
            val = val[1:-1]
        data[key] = val
    return data


def strip_fenced_blocks(text):
    """Drop fenced code blocks so example markup is not linted as live markup."""
    out, in_fence, fence_char, fence_len = [], False, '', 0
    for line in text.splitlines():
        m = FENCE_RE.match(line)
        if in_fence:
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len:
                in_fence = False
            out.append('')
            continue
        if m:
            in_fence, fence_char, fence_len = True, m.group(1)[0], len(m.group(1))
            out.append('')
            continue
        out.append(line)
    return '\n'.join(out)


def find_invisible(text):
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for col, ch in enumerate(line, 1):
            cp = ord(ch)
            if cp in INVISIBLE_CODEPOINTS or unicodedata.category(ch) in ('Cf', 'Co', 'Cs'):
                hits.append((lineno, col, f'U+{cp:04X}', unicodedata.name(ch, '?')))
    return hits


def find_comments(text):
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if COMMENT_RE.search(line) and ALLOW_MARKER not in line:
            hits.append((lineno, line.strip()[:100]))
    return hits


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skills_dir = os.path.join(root, 'skills')
    if not os.path.isdir(skills_dir):
        print(f'FAIL: no skills/ directory under {root}')
        return 1

    skill_dirs = sorted(
        d for d in os.listdir(skills_dir)
        if os.path.isfile(os.path.join(skills_dir, d, 'SKILL.md'))
    )
    if not skill_dirs:
        print('FAIL: no skills/*/SKILL.md found')
        return 1

    findings = []
    checked = 0

    for name in skill_dirs:
        skill_md = os.path.join(skills_dir, name, 'SKILL.md')
        text = open(skill_md, encoding='utf-8').read()
        rel = os.path.relpath(skill_md, root)
        checked += 1
        errors = []

        fm, _ = split_frontmatter(text)
        if fm is None:
            errors.append('missing YAML frontmatter (file must start with ---)')
            data = {}
        else:
            data = parse_flat_yaml(fm)
            for key in REQUIRED:
                if not data.get(key):
                    errors.append(f'frontmatter missing required field: {key}')
            if data.get('name') and data['name'] != name:
                errors.append(f"frontmatter name '{data['name']}' != directory '{name}'")
            if data.get('license') and data['license'].upper() != 'MIT':
                errors.append(f"license should be MIT, got '{data['license']}'")
            desc = data.get('description', '')
            if desc and len(desc) < 20:
                errors.append('description too short to be useful (<20 chars)')
            if desc and len(desc) > 1024:
                errors.append(f'description too long ({len(desc)} > 1024 chars)')

        # hidden characters + comments across every Markdown file in the package
        for dirpath, dirnames, filenames in os.walk(os.path.join(skills_dir, name)):
            dirnames[:] = [d for d in dirnames if d not in ('.git', '__pycache__')]
            for fn in sorted(filenames):
                if not fn.endswith('.md'):
                    continue
                p = os.path.join(dirpath, fn)
                r = os.path.relpath(p, root)
                body = open(p, encoding='utf-8').read()
                visible = strip_fenced_blocks(body)
                for lineno, col, cp, cname in find_invisible(body):
                    errors.append(f'{r}:{lineno}:{col} invisible char {cp} ({cname})')
                for lineno, snippet in find_comments(visible):
                    errors.append(f'{r}:{lineno} HTML comment without {ALLOW_MARKER}: {snippet}')

        if errors:
            findings.append((rel, errors))
            print(f'FAIL  {rel}')
            for e in errors:
                print(f'      - {e}')
        else:
            print(f'OK    {rel}  (name={data.get("name")}, license={data.get("license")}, '
                  f'desc={len(data.get("description", ""))} chars)')

    print()
    print(f'checked {checked}/{len(skill_dirs)} SKILL.md files; '
          f'{len(findings)} file(s) with findings')
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())