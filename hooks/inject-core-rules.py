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
must itself tell the model to read both files; the test pins it under 2,000.

CLAUDE.md is named rather than inlined. It is several times the size of
AGENTS.md, and AGENTS.md already says to consult it on demand.

Silent in two cases, both measured from the filesystem rather than assumed:

  - The session's project IS ai-config (its own AGENTS.md is byte-identical
    to the plugin's). Claude Code already auto-loads that repo's CLAUDE.md,
    so injecting again would double the context.
  - The plugin root has no AGENTS.md. That is a broken install, not a reason
    to block the session; the hook says so on stderr and exits 0.
"""
import hashlib
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

Before acting on the first request, read both files in full (use the Read
tool; this injected copy may be truncated):

- {agents}  (the authoritative cross-agent contract, inlined below)
- {claude}  (Claude-specific workflows; consult the sections that apply)

Relative links inside them (`shared/...`, `memories/...`, `skills/...`)
resolve against {root}.
"""


def plugin_root() -> Path:
    raw = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent.parent


def digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def project_dir(payload: dict) -> Path | None:
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd")
    return Path(raw) if raw else None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    root = plugin_root()
    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"
    agents_digest = digest(agents)
    if agents_digest is None:
        print(f"inject-core-rules: no AGENTS.md under {root}; "
              "the ai-config plugin install looks incomplete", file=sys.stderr)
        return 0

    project = project_dir(payload)
    if project is not None and digest(project / "AGENTS.md") == agents_digest:
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
