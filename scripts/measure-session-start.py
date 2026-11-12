#!/usr/bin/env python3
"""Measure what each kind of agent session loads from ai-config at start.

`check-context-closure.py`, `validate-skills.py` and the hook tests each gate
one file against its own cap. None of them says what a whole session loads,
and several sit within a few characters of their cap, so every new rule turns
into a budgeting exercise (ai-config#5310, step 1; ai-config#1138).

This prints one table per session kind: each component it loads at start,
its size, the cap that gates that component, and a target. The target is
TARGET_FRACTION of the cap, so the corpus has room to grow before a gate
fails instead of meeting it at the gate. Every cap is imported from the
script or hook that holds it rather than restated here. The session kinds
follow docs/delivery-paths.md, which names what each supported path delivers.

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


def load(rel: str):
    """Import a hyphen-named script or hook as a module."""
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


closure = load("scripts/check-context-closure.py")
skills = load("scripts/validate-skills.py")
core_hook = load("hooks/inject-core-rules.py")
subagent_hook = load("hooks/inject-subagent-rules.py")


def file_size(path: Path, unit: str) -> int:
    text = path.read_text(encoding="utf-8")
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
    return len(data["hookSpecificOutput"]["additionalContext"])


def listing(directory: str) -> int:
    entries = skills.listing_entries(sorted((ROOT / directory).glob("*/SKILL.md")))
    return skills.listing_chars(entries)


def cursor_rules() -> int:
    return sum(file_size(p, "chars") for p in sorted((ROOT / "cursor-rules").glob("*.mdc")))


CLOSURE = "scripts/check-context-closure.py"
VALIDATE = "scripts/validate-skills.py"

# name -> (measure, unit, cap or None, the script or test that fails over the cap)
COMPONENTS = {
    "SessionStart core rules": (
        lambda: hook_context("hooks/inject-core-rules.py", "SessionStart"),
        "chars", core_hook.CAP, "hooks/inject-core-rules.py cuts at it",
    ),
    "AGENTS.md": (
        lambda: file_size(ROOT / "AGENTS.md", "bytes"),
        "bytes", closure.DEFAULT_AGENTS_MD_CAP_BYTES, CLOSURE,
    ),
    "skill listing": (lambda: listing("skills"), "chars", skills.SKILL_LISTING_BUDGET_CHARS, VALIDATE),
    "Codex skill listing": (
        lambda: listing("codex-skills"), "chars", skills.SKILL_LISTING_BUDGET_CHARS, VALIDATE,
    ),
    "CLAUDE.md": (
        lambda: file_size(ROOT / "CLAUDE.md", "bytes"),
        "bytes", closure.DEFAULT_BUDGET_BYTES, CLOSURE,
    ),
    "subagent rules file": (
        lambda: file_size(subagent_hook.RULES, "chars"),
        "chars", subagent_hook.RULES_BUDGET, "hooks/test-inject-subagent-rules.py",
    ),
    "Antigravity plugin rules": (
        lambda: file_size(ROOT / "plugins/ai-config/rules/ai-config.md", "chars"), "chars", None, "",
    ),
    "Cursor plugin rules": (cursor_rules, "chars", None, ""),
}

# What each session kind loads from ai-config at start, per docs/delivery-paths.md.
# A Claude Code session reads AGENTS.md because the core-rules hook tells it to.
# A subagent loads the repository's CLAUDE.md unless its definition sets
# omitClaudeMd (skills/agent-builder/SKILL.md); built-in subagents cannot opt
# out. The CLAUDE.md here is ai-config's own, so the second subagent row is
# a subagent working in ai-config; elsewhere it is that repository's file.
SESSION_KINDS = {
    "Claude Code, plugin, any repo": ["SessionStart core rules", "AGENTS.md", "skill listing"],
    "Claude Code, in ai-config": ["SessionStart core rules", "AGENTS.md", "skill listing", "CLAUDE.md"],
    "Claude Code subagent with omitClaudeMd": ["subagent rules file"],
    "Claude Code subagent in ai-config, without omitClaudeMd": ["subagent rules file", "CLAUDE.md"],
    "Codex": ["AGENTS.md", "Codex skill listing"],
    "Gemini CLI": ["AGENTS.md", "skill listing"],
    "Antigravity": ["AGENTS.md", "Antigravity plugin rules", "skill listing"],
    "Cursor": ["Cursor plugin rules", "skill listing"],
    "opencode": ["AGENTS.md"],
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true", help="exit 1 when a component is over target")
    args = parser.parse_args(argv)

    sizes = {name: spec[0]() for name, spec in COMPONENTS.items()}
    over = []
    for kind, names in SESSION_KINDS.items():
        print(f"\n{kind}: about {sum(sizes[n] for n in names):,} characters at start")
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
