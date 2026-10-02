"""Shared pieces of scripts/wire-user-config.py and scripts/wire-repo-config.py.

Both scripts register the same marketplace, refuse to wire an ai-config
checkout into itself, and splice a marked block into a Markdown file the user
also edits (ai-config#4206). hooks/inject-core-rules.py keeps its own
version of the checkout test (`ai_config_root`), because a hook runs from
the plugin cache with no guarantee that scripts/lib is importable beside it.
"""
from __future__ import annotations

import json
from pathlib import Path

MARKETPLACE = "Morrison-Lab"
PLUGIN = f"ai-config@{MARKETPLACE}"
MARKETPLACE_SOURCE = {"source": "github", "repo": "Morrison-Lab/ai-config"}


def is_ai_config(directory: Path) -> bool:
    """True when directory is inside an ai-config checkout."""
    for candidate in (directory, *directory.parents):
        manifest = candidate / ".claude-plugin" / "marketplace.json"
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("name") == MARKETPLACE:
            return True
    return False


def splice_block(current: str, block: str, begin: str, end: str) -> str:
    """Return current with block (which starts with begin and ends with end
    plus a newline) replacing any earlier copy, or appended after a blank line.

    Raises ValueError on an unterminated earlier copy rather than appending a
    second begin marker beside the orphan.
    """
    if begin in current:
        head, rest = current.split(begin, 1)
        if end not in rest:
            raise ValueError(f"found {begin!r} with no {end!r}; fix the file by hand")
        tail = rest.split(end, 1)[1].lstrip("\n")
        return head + block + tail
    if not current or current.endswith("\n\n"):
        return current + block
    return current + ("\n" if current.endswith("\n") else "\n\n") + block
