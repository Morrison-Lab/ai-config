#!/usr/bin/env python3
"""Measure what each kind of agent session loads from ai-config at start.

`check-context-closure.py`, `validate-skills.py` and the hook tests each gate
one file against its own cap. None of them says what a whole session loads,
and several sit within a few characters of their cap, so every new rule turns
into a budgeting exercise (ai-config#5310, step 1; ai-config#1138).

This prints one table per session kind: each component it loads at start,
its size, the cap that component is gated against, and a target. The target
is TARGET_FRACTION of the cap, so the corpus has room to grow before a gate
fails instead of meeting it at the gate. The caps are imported from the
scripts and tests that enforce them rather than restated.

Report-only by default. `--strict` exits 1 when a component is over target.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Each component's target is this share of its cap: a quarter of every cap
# kept free (ai-config#5310, "a target well under the caps rather than at them").
TARGET_FRACTION = 0.75

# The hook tests assert these budgets inline rather than as named constants:
# hooks/test-inject-core-rules.py and hooks/test-inject-subagent-rules.py.
HOOK_CONTEXT_CAP_CHARS = 10_000


def load(name: str):
    """Import a hyphen-named script from scripts/ as a module."""
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


closure = load("check-context-closure")
skills = load("validate-skills")


def file_size(rel: str, unit: str) -> int:
    text = (ROOT / rel).read_text(encoding="utf-8")
    if unit == "bytes":
        return len(text.encode("utf-8"))
    return closure.cli_char_count(text)


def hook_context(rel: str, event: str) -> int:
    """Characters of additionalContext the hook injects for a synthetic event."""
    payload = {"hook_event_name": event, "source": "startup", "session_id": "measure", "cwd": str(ROOT)}
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(ROOT)}
    out = subprocess.run(
        [sys.executable, str(ROOT / rel)],
        input=json.dumps(payload), capture_output=True, text=True, env=env, check=True,
    ).stdout
    data = json.loads(out)
    return len(data.get("hookSpecificOutput", data).get("additionalContext", ""))


def skill_listing() -> int:
    entries = []
    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        fm = skills.parse_frontmatter(skill_md.read_text(encoding="utf-8"), str(skill_md))
        if fm and isinstance(fm.get("name"), str) and isinstance(fm.get("description"), str):
            entries.append((fm["name"], fm["description"]))
    return skills.listing_chars(entries)


def cursor_rules() -> int:
    return sum(file_size(str(p.relative_to(ROOT)), "chars") for p in sorted((ROOT / ".cursor/rules").glob("*.mdc")))


# name -> (measure, unit, cap or None, where the cap is enforced)
COMPONENTS = {
    "SessionStart core rules": (
        lambda: hook_context("hooks/inject-core-rules.py", "SessionStart"),
        "chars", HOOK_CONTEXT_CAP_CHARS, "hooks/test-inject-core-rules.py",
    ),
    "AGENTS.md": (
        lambda: file_size("AGENTS.md", "bytes"),
        "bytes", closure.DEFAULT_AGENTS_MD_CAP_BYTES, "Codex project_doc_max_bytes",
    ),
    "skill listing": (
        skill_listing, "chars", skills.SKILL_LISTING_BUDGET_CHARS, "scripts/validate-skills.py",
    ),
    "CLAUDE.md": (
        lambda: file_size("CLAUDE.md", "chars"),
        "chars", closure.DEFAULT_BUDGET_BYTES, "scripts/check-context-closure.py",
    ),
    "SubagentStart rules": (
        lambda: hook_context("hooks/inject-subagent-rules.py", "SubagentStart"),
        "chars", HOOK_CONTEXT_CAP_CHARS, "hooks/test-inject-subagent-rules.py",
    ),
    "GEMINI.md": (lambda: file_size("GEMINI.md", "chars"), "chars", None, "none"),
    "Antigravity plugin rules": (
        lambda: file_size("plugins/ai-config/rules/ai-config.md", "chars"), "chars", None, "none",
    ),
    "Cursor rules": (cursor_rules, "chars", None, "none"),
}

# What each session kind loads at start, by component name.
# A Claude Code session reads AGENTS.md because the core-rules hook tells it to.
# A subagent also loads the repository's CLAUDE.md unless its definition sets
# omitClaudeMd (skills/agent-builder/SKILL.md); that file is the consumer's.
SESSION_KINDS = {
    "Claude Code, plugin, any repo": ["SessionStart core rules", "AGENTS.md", "skill listing"],
    "Claude Code, in ai-config": ["SessionStart core rules", "AGENTS.md", "skill listing", "CLAUDE.md"],
    "Claude Code subagent": ["SubagentStart rules"],
    "Codex": ["AGENTS.md"],
    "Antigravity": ["GEMINI.md", "Antigravity plugin rules"],
    "Cursor": ["Cursor rules"],
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true", help="exit 1 when a component is over target")
    args = parser.parse_args(argv)

    sizes = {name: spec[0]() for name, spec in COMPONENTS.items()}
    over = []
    for kind, names in SESSION_KINDS.items():
        print(f"\n{kind}: {sum(sizes[n] for n in names):,} loaded at start")
        for name in names:
            _, unit, cap, where = COMPONENTS[name]
            if cap is None:
                print(f"  {name:26} {sizes[name]:>8,} {unit:5}  no cap")
                continue
            target = int(cap * TARGET_FRACTION)
            status = "over target" if sizes[name] > target else "ok"
            print(
                f"  {name:26} {sizes[name]:>8,} {unit:5}  {sizes[name] / cap:6.1%} of {cap:,}"
                f" ({where}); target {target:,}: {status}"
            )
            if sizes[name] > target and name not in over:
                over.append(name)
    print(f"\n{len(COMPONENTS)} component(s) measured; {len(over)} over target"
          + (f": {', '.join(over)}" if over else ""))
    return 1 if args.strict and over else 0


if __name__ == "__main__":
    sys.exit(main())
