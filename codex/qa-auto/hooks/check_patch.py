#!/usr/bin/env python3
"""Codex apply_patch adapter for the existing no-hardcode QA policy."""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path


def policy_module():
    source = Path(__file__).with_name('check_no_hardcode.py')
    if not source.exists():  # source-tree test / direct use
        source = Path(__file__).resolve().parents[2] / 'qa-toolkit/qa-auto/hooks/check_no_hardcode.py'
    spec = importlib.util.spec_from_file_location('qa_no_hardcode', source)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def changes(event):
    inp = event.get('tool_input') or {}
    if not isinstance(inp, dict):
        inp = {'command': inp}
    if inp.get('file_path'):
        return [(inp['file_path'], inp.get('content') or inp.get('new_string') or '')]
    patch = inp.get('command', inp.get('input', ''))
    if not isinstance(patch, str):
        return []
    found, path, added = [], None, []
    for line in patch.splitlines():
        m = re.match(r'^\*\*\* (?:Add|Update|Delete) File: (.+)$', line)
        moved = re.match(r'^\*\*\* Move to: (.+)$', line)
        if m:
            if path:
                found.append((path, '\n'.join(added)))
            path, added = m[1], []
        elif moved:
            if path:
                found.append((path, ''))
            path = moved[1]
        elif line.startswith('+'):
            added.append(line[1:])
    if path:
        found.append((path, '\n'.join(added)))
    return found


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    policy = policy_module()
    reasons = []
    for path, content in changes(event):
        root = policy._project_root(path, event.get('cwd', ''))
        if not root:
            continue
        rel = os.path.relpath(os.path.join(event.get('cwd', ''), path), root)
        if Path(path).name == '.env':
            reasons.append(f'{rel}: writing .env is forbidden; use .env.example')
        elif rel.split(os.sep, 1)[0] in policy.CODE_ROOTS:
            reasons += [f'{rel}: {v}' for v in policy.find_violations(rel, content)]
    if reasons:
        print('\n'.join(reasons), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
