#!/usr/bin/env python3
"""SessionStart: put ai-config's always-on rules in front of every session.

The ai-config plugin ships `skills/`, `commands/` and `hooks/hooks.json`, and
Claude Code loads all three wherever the plugin is enabled: the CLI and
desktop app, claude.ai cloud and project sessions (through the account's
plugin sync), Remote Control sessions, and the `@claude` GitHub Actions bots
(gha installs `ai-config@Morrison-Lab` by default). It does NOT load the
plugin's `AGENTS.md` or `CLAUDE.md`: a plugin has no instruction-file slot,
so those files sat in the synced plugin directory unread. A project thread
on 2026-10-02 saw the AGENTS.md rules only after cloning ai-config by hand
(ai-config#4206).

Plugin docs route instructions through skills, but a skill body loads only
when invoked; a SessionStart hook is the plugin component that puts text into
context unprompted, so this hook is how the always-on rules travel with it.

It does not inline AGENTS.md. Claude Code caps each injected hook string at
10,000 characters; over the cap it saves the output to a file and injects
only the path plus a 2,000-character preview, and its docs say to keep what
the model must always see within the cap (code.claude.com/docs/en/hooks).
AGENTS.md is about three times the cap, so inlining it would deliver a
preview and a spill file every session. Instead the hook prints, all within
the cap (the test pins it against the real AGENTS.md):

  - a header naming AGENTS.md and CLAUDE.md by absolute path, with the order
    to read AGENTS.md in full before the first action;
  - an index of AGENTS.md's section headings, so every rule's name is in
    context even before the read.

CLAUDE.md is named, never ordered read in full: it is several times the size
of AGENTS.md, and AGENTS.md says to consult its sections on demand.

Which copy is named is measured from the filesystem rather than assumed:

  - When the session's project is an ai-config checkout (the project
    directory, or a parent of it, carries `.claude-plugin/marketplace.json`
    named Morrison-Lab), the checkout's own files: Claude Code's default
    loads only that checkout's CLAUDE.md, which does not import AGENTS.md,
    and the checkout may be newer than the plugin's cached copy. Under
    Cursor (CURSOR_PROJECT_DIR set) the hook is silent there instead,
    because Cursor reads the workspace's root AGENTS.md itself.
  - Otherwise the plugin's own copy, two directories above this file. A
    copy of this script outside a plugin or checkout (the old
    ~/.claude/hooks install) finds no `.claude-plugin/` there, says so on
    stderr and exits 0, rather than naming whatever AGENTS.md it finds.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

CAP = 10_000

HEADER = """\
# ai-config always-on rules (Morrison-Lab/ai-config)

These are the user's standing, cross-project instructions, delivered by the
ai-config plugin's SessionStart hook. They apply in every repository and
project unless the user narrows them, and they rank like a user-level
CLAUDE.md: a repository's own instructions add to them, and win only where
they are more specific.

Before acting on the first request, read AGENTS.md in full with the Read
tool; only its section index is below. Consult CLAUDE.md only for the
sections that apply; do not load it whole.

- {agents}  (the authoritative cross-agent contract)
- {claude}  (Claude-specific workflows)

Relative links inside them (`shared/...`, `memories/...`, `skills/...`)
resolve against {root}.
"""


def plugin_root() -> Path:
    # This file lives at <root>/hooks/. CLAUDE_PLUGIN_ROOT is not used: the
    # generated hooks-only plugin exports its own directory there, which
    # holds no AGENTS.md.
    return Path(__file__).resolve().parent.parent


def ai_config_root(directory: Path) -> Path | None:
    """The ai-config checkout containing directory, if any."""
    for candidate in (directory, *directory.parents):
        manifest = candidate / ".claude-plugin" / "marketplace.json"
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("name") == "Morrison-Lab":
            return candidate
    return None


def project_dir(payload: dict) -> Path:
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd")
    return Path(raw) if raw else Path.cwd()


def render(root: Path) -> str:
    agents = root / "AGENTS.md"
    text = HEADER.format(agents=agents, claude=root / "CLAUDE.md", root=root)
    headings = re.findall(r"^## (.+)$", agents.read_text(encoding="utf-8"), re.MULTILINE)
    index = "\nAGENTS.md sections:\n" + "".join(f"- {h.strip()}\n" for h in headings)
    if len(text) + len(index) > CAP:
        index = "\n(AGENTS.md section index omitted: it would exceed the hook output cap.)\n"
    return text + index


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    checkout = ai_config_root(project_dir(payload).resolve())
    if checkout and os.environ.get("CURSOR_PROJECT_DIR"):
        return 0
    root = checkout or plugin_root()
    if not checkout and not (root / ".claude-plugin").is_dir():
        print(f"inject-core-rules: {root} is not an ai-config plugin or checkout; "
              "this copy of the hook is stray (register the plugin instead)",
              file=sys.stderr)
        return 0
    if not (root / "AGENTS.md").is_file():
        print(f"inject-core-rules: no AGENTS.md under {root}; "
              "that ai-config copy looks incomplete", file=sys.stderr)
        return 0

    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": render(root),
        }
    }, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
