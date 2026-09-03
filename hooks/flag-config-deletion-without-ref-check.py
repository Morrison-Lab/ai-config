#!/usr/bin/env python3
"""Stop-hook guard: recommending deletion of config files without checking refs.

Measured 2026-09-02 (ai-config#3096). I recommended

    find "$HOME/.claude/hooks" -maxdepth 1 -name '*.py' -delete

believing those files were orphaned leftovers the plugin superseded. They were
the LIVE guard set: `~/.claude/settings.json` registers 46 hooks by explicit
`$HOME/.claude/hooks/<name>.py` path, so the command would have unregistered
every one. The remedy was to refresh the copies, not remove them (#3094).

Why a rule did not reach it. The corpus already says to look before deleting,
and a content diff over all 94 files HAD been run --- so the removal felt like
the documented cleanup. The question never asked was whether anything POINTS AT
the files, which is different from whether their contents are stale. Staleness
is a property of a file; safety-to-delete is a property of the graph around it.

Warns, never blocks. The condition cannot tell an orphan from a registered file
without reading the config; the point is to prompt that read, not replace it.
Fires once per distinct message (sentinel keyed by content hash).
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Configuration roots whose files are typically referenced by a manifest rather
# than discovered by scanning. Deleting one here unregisters behaviour.
CONFIG_ROOTS = (
    r"~/[.]claude", r"[$]HOME/[.]claude", r"[$]{HOME}/[.]claude",
    r"~/[.]config", r"[$]HOME/[.]config",
    r"~/[.]codex", r"[$]HOME/[.]codex",
    r"~/[.]gemini", r"[$]HOME/[.]gemini",
    r"~/[.]cursor", r"[$]HOME/[.]cursor",
)
_ROOTS = "(?:" + "|".join(CONFIG_ROOTS) + ")"

# A destructive verb applied to a path under one of those roots. `find ... -delete`
# puts the verb AFTER the path, so both orders are matched.
RX_DESTRUCTIVE = re.compile(
    r"(?:{r}[^\n`'\"]*?[^\n]*?(?:-delete|-exec[ ]+rm)"
    r"|"
    r"(?:{b}rm{b}(?:[ ]+-[A-Za-z]+)*|{b}rmdir{b}|git[ ]+clean{b}[^\n]*?)[ ]+[^\n]*?{r})".format(
        r=_ROOTS, b=r"{b}".format(b="\\b")
    ),
)

# Evidence the author looked for references before proposing removal: any
# earlier command that read a manifest in a config root.
RX_REF_CHECK = re.compile(
    r"(?:grep|rg|jq|cat|sed|awk|python3?)[^\n]*?"
    r"(?:settings[.]json|config[.]toml|config[.]json|[.]mcp[.]json)",
)


def transcript_records(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
    except OSError:
        return


def ref_check_ran(path):
    """True when some earlier Bash command read a config manifest."""
    for record in transcript_records(path):
        if record.get("type") != "assistant":
            continue
        for block in (record.get("message") or {}).get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") not in {"Bash", "bash", "run_command"}:
                continue
            command = str((block.get("input") or {}).get("command") or "")
            if RX_REF_CHECK.search(command):
                return True
    return False


def last_assistant_text(path):
    last = ""
    for record in transcript_records(path):
        if record.get("type") != "assistant":
            continue
        blocks = (record.get("message") or {}).get("content") or []
        text = "".join(
            b.get("text", "") for b in blocks
            if isinstance(b, dict) and b.get("type") == "text"
        )
        if text.strip():
            last = text
    return last


REASON = (
    "This reply recommends DELETING files under a configuration directory, and "
    "no earlier command in this session read a manifest there to see what "
    "references them.\n\n"
    "Staleness is a property of a file. Safety-to-delete is a property of the "
    "graph around it, and a content diff answers only the first.\n\n"
    "Measured 2026-09-02 (ai-config#3096): `find \"$HOME/.claude/hooks\" "
    "-name '*.py' -delete` was recommended over what turned out to be the live "
    "guard set --- `settings.json` registered 46 of those files by explicit "
    "path, so the command would have unregistered every one. The fix was to "
    "refresh them, not remove them.\n\n"
    "Check what points at the files first:\n\n"
    "    grep -o 'hooks/[a-z0-9-]*[.]py' ~/.claude/settings.json | sort -u\n\n"
    "then recommend refresh or removal on that evidence. This warns and never "
    "blocks; if you have already established the files are unreferenced, say "
    "so and carry on."
)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    path = payload.get("transcript_path") or ""
    if not path:
        return
    text = last_assistant_text(path)
    if not text or not RX_DESTRUCTIVE.search(text):
        return
    if ref_check_ran(path):
        return
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(
        tempfile.gettempdir(), ".claude-config-deletion-{0}".format(key)
    )
    if os.path.exists(sentinel):
        return
    try:
        open(sentinel, "w").close()
    except OSError:
        pass
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "Stop", "additionalContext": REASON,
        },
        "systemMessage": REASON,
    }))


if __name__ == "__main__":
    main()
