#!/usr/bin/env python3
"""Keep user-global cursor-rules/ in sync with the project copies.

``.cursor/rules/`` is what Cursor loads when this repo is the workspace.
``cursor-rules/`` is what the Cursor plugin ships as user-global rules,
and what ``bootstrap.sh`` links into ``~/.cursor/rules`` when no plugin
is already serving them.

Files that exist in both places must be byte-identical. Project-only rules
(currently ``002-use-repo-skills.mdc``) live only under ``.cursor/rules/``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER = ROOT / "cursor-rules"
PROJECT = ROOT / ".cursor" / "rules"

passes = failures = 0


def check(name: str, condition: bool) -> None:
    global passes, failures
    print(f"{'PASS' if condition else 'FAIL'}: {name}")
    passes += condition
    failures += not condition


user_files = {p.name: p for p in USER.glob("*.mdc")}
project_files = {p.name: p for p in PROJECT.glob("*.mdc")}

check("user-global cursor-rules/ exists", USER.is_dir())
check("project .cursor/rules/ exists", PROJECT.is_dir())
check("every user-global rule has a project copy",
      set(user_files).issubset(project_files))

for name, user_path in sorted(user_files.items()):
    project_path = project_files[name]
    check(
        f"{name} is identical in cursor-rules/ and .cursor/rules/",
        user_path.read_bytes() == project_path.read_bytes(),
    )

plugin = json.loads((ROOT / ".cursor-plugin" / "plugin.json").read_text(encoding="utf-8"))
check(
    "plugin ships user-global cursor-rules, not project-only 002",
    plugin.get("rules") == "cursor-rules",
)

print(f"\n{passes} passed, {failures} failed")
raise SystemExit(1 if failures else 0)
