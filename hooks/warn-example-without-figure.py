#!/usr/bin/env python3
"""PreToolUse warn: an edit adds an example div to a notes-repo page with no figure.

Rule: `shared/writing/visuals-everywhere.md` (Ezra, 2026-10-23): nearly every
`#exm-` div gets a figure, or a `<!-- no-figure: reason -->` comment saying why
there is nothing to plot. The full rule is in psw `chapters/teaching.qmd`, which
agents do not load while drafting, so this puts it in front of the agent at the
moment it writes the example (ai-config#4851, thread "Make agents add figures
to examples").

It fires on Write and Edit of a `.qmd` file under a notes repo (lds, mds, pds,
sds, mcs, rme, cds, ids, win, cie) when the added text opens an `#exm-` div and
holds no figure marker. It warns, never blocks: the figure may sit in a subfile
the example includes, or in a later edit of the same turn.

Deliberate limits:
  - A repo is recognised by a path component naming it; a checkout renamed
    away from those names is not seen.
  - The figure markers are the ones gha `check-exm-figures` accepts: an image,
    a `fig-` label, an `@fig-` reference, an include of a `_fig` subfile, or a
    `no-figure` comment. A `_fig` include written after the example in the same
    div by a later edit is not seen until that edit lands.
  - An edit that touches an existing example without adding its opening line is
    not seen.
  - Fails open on any parse trouble.
"""
import json
import re
import sys

NOTES_REPOS = {"lds", "mds", "pds", "sds", "mcs", "rme", "cds", "ids", "win", "cie"}
EXAMPLE = re.compile(r"^\s*:{3,}\s*\{[^}\n]*#exm-", re.M)
FIGURE = re.compile(
    r"!\[|\{#fig-|\bfig-|@fig-|_fig[\w-]*\.qmd|<!--\s*no-figure\b|\bno-figure:",
    re.I)

NOTE = (
    "This edit adds an example div (`#exm-`) with no figure in it. Ezra, 2026-10-23: "
    "nearly every example gets a figure of its data, model or results, put in the div "
    "or in a `_fig` subfile it includes. When there is nothing to plot, such as a "
    "single number, put `<!-- no-figure: reason -->` in the div. Build the figure "
    "with R or Python code (ggplot2, the qnp theme), not by hand. The gha "
    "`check-exm-figures` check flags the same thing at review. Rule: "
    "shared/writing/visuals-everywhere.md and psw chapters/teaching.qmd. If the "
    "figure follows in a later edit of this turn, ignore this note."
)


def is_notes_page(path):
    if not path.endswith(".qmd") or "/outtakes/" in path:
        return False
    return any(part in NOTES_REPOS for part in path.split("/"))


def example_segments(text):
    """The text of each `#exm-` div opening, up to the next one or the end.

    Scoping the figure test to a segment keeps one figured example from
    silencing a bare one added in the same edit.
    """
    starts = [m.start() for m in EXAMPLE.finditer(text)]
    ends = starts[1:] + [len(text)]
    return [text[a:b] for a, b in zip(starts, ends)]


def added_text(name, inp):
    if name == "Write":
        return inp.get("content") or ""
    if name == "Edit":
        return inp.get("new_string") or ""
    return ""


def decide(payload):
    name = payload.get("tool_name") or ""
    inp = payload.get("tool_input") or {}
    if name not in ("Write", "Edit"):
        return None
    if not is_notes_page(inp.get("file_path") or ""):
        return None
    new = added_text(name, inp)
    old = inp.get("old_string") or ""
    if len(EXAMPLE.findall(new)) <= len(EXAMPLE.findall(old)):
        return None
    if all(FIGURE.search(seg) for seg in example_segments(new)):
        return None
    return NOTE


def main():
    try:
        payload = json.load(sys.stdin)
        note = decide(payload) if isinstance(payload, dict) else None
    except Exception:
        return 0
    if note:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "additionalContext": note}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
