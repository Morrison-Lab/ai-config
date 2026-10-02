#!/usr/bin/env python3
"""SessionStart: load ai-config's always-on rules into every session.

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
context unprompted, so this hook is how the always-on rules travel with it. It
prints a short header naming both files by absolute path, then AGENTS.md
verbatim. The header comes first on purpose: Claude Code caps each injected
hook string at 10,000 characters, and over the cap it saves the output to a
file and injects only the path plus a preview of the first 2,000 characters,
without asking the model to read the file (code.claude.com/docs/en/hooks).
AGENTS.md is far over that cap, so the header must fit inside the preview and
must itself tell the model to read AGENTS.md; the test pins it under 2,000.

CLAUDE.md is named, never inlined or ordered read in full. It is several
times the size of AGENTS.md, and AGENTS.md says not to load it wholesale at
session start but to consult the sections that apply.

Which copy is injected is measured from the filesystem rather than assumed:

  - When the session's project is an ai-config checkout (the project
    directory, or a parent of it, carries `.claude-plugin/marketplace.json`
    named Morrison-Lab), the checkout's own files are named and injected.
    Claude Code auto-loads only that checkout's CLAUDE.md, which does not
    import AGENTS.md, and the checkout may be newer than the plugin's cached
    copy (a branch editing AGENTS.md). Identity, not content. Under Cursor
    (CURSOR_PROJECT_DIR set) the hook is silent there instead, because
    Cursor already reads the workspace's root AGENTS.md.
  - Otherwise the plugin's own copy is used.
  - When the chosen root has no AGENTS.md, that is a broken install, not a
    reason to block the session; the hook says so on stderr and exits 0.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HEADER = """\
# ai-config always-on rules (Morrison-Lab/ai-config)

These are the user's standing, cross-project instructions, delivered by the
ai-config plugin's SessionStart hook. They apply in every repository and
project unless the user narrows them, and they rank like a user-level
CLAUDE.md: a repository's own instructions add to them, and win only where
they are more specific.

Before acting on the first request, read AGENTS.md in full with the Read
tool, since the copy below may be cut short. Consult CLAUDE.md only for the
sections that apply; do not load it whole.

- {agents}  (the authoritative cross-agent contract; its text follows)
- {claude}  (Claude-specific workflows)

Relative links inside them (`shared/...`, `memories/...`, `skills/...`)
resolve against {root}.
"""


def plugin_root() -> Path:
    # This file always lives at <root>/hooks/. CLAUDE_PLUGIN_ROOT is not used:
    # the generated hooks-only plugin exports its own directory there, which
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


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    checkout = ai_config_root(project_dir(payload).resolve())
    if checkout and os.environ.get("CURSOR_PROJECT_DIR"):
        # Cursor reads a workspace's root AGENTS.md natively.
        return 0
    root = checkout or plugin_root()
    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"
    if not agents.is_file():
        print(f"inject-core-rules: no AGENTS.md under {root}; "
              "the ai-config plugin install looks incomplete", file=sys.stderr)
        return 0

    text = HEADER.format(agents=agents, claude=claude, root=root)
    text += "\n---\n\n" + agents.read_text(encoding="utf-8")
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        }
    }, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
