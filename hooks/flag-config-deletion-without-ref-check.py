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

Limits, in both directions, deliberately unclosed.
UNDER: `unlink`, `trash`, `mv <root> /tmp`, `ls <root> | xargs rm`, a path held
in a variable, an already-expanded absolute path, and a `find` split across a
line continuation all miss. Several are as likely as the matched form; each
would need a construct-specific clause, and a warn-only reminder is not worth
that surface. A `git clean` dry run is excluded deliberately rather than
missed --- see its branch.
OVER: the guard cannot tell a recommendation from a mention, so a reply that
QUOTES a destructive command in order to warn against it still fires --- this
file's own message text included. The sentinel bounds that to one warning per
message.
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
    "claude", "config", "codex", "gemini", "cursor",
)
# Each root in its three spellings. Writing them out by hand had `${HOME}` for
# `.claude` only, so `rm -rf ${HOME}/.config` missed -- an asymmetry that reads
# as an oversight rather than one of the deliberate limits below.
_PREFIXES = (r"~", r"[$]HOME", r"[$]{HOME}")
_ROOT_ALTS = tuple(
    "{0}/[.]{1}".format(prefix, name)
    for name in CONFIG_ROOTS for prefix in _PREFIXES
)
# The trailing lookahead stops `~/.config` matching inside `~/.config-notes`,
# which would otherwise let an unrelated file discharge the guard. The class
# includes `*`, `>` and `&` because `rm -rf ~/.claude*` is a common spelling of
# exactly what this guard exists to catch; a bare path-or-space boundary
# exempted it. `~/.config-notes` and `~/.claudex` still miss, which is the
# point.
_ROOTS = "(?:" + "|".join(_ROOT_ALTS) + r")(?=[/\"'`.,;)\]*&>|]|\s|$)"

# A destructive verb applied to a path under one of those roots. `find` puts
# the verb AFTER the path and `rm` before it, so both orders are matched.
#
# Only OPTION tokens may sit between `rm` and its operand. An earlier draft
# allowed arbitrary same-line text, which matched an unrelated `rm -rf /tmp/x`
# in the same sentence as a later `~/.config` mention -- the misfire
# README.md:560 calls worse than a missing guard.
_DESTRUCTIVE_PARTS = [
    r"\bfind\b[ ]+[\"']?" + _ROOTS + r"[^\n]{0,200}?-(?:delete|exec[ ]+rm)",
    r"(?:\brm\b|\brmdir\b)(?:[ ]+-[-A-Za-z0-9]+)*[ ]+[\"']?" + _ROOTS,
    r"\bcd\b[ ]+[\"']?" + _ROOTS + r"[^\n]{0,80}?&&[ ]*(?:rm\b|git[ ]+clean\b)",
    # `git clean -fdx <root>`. Kept as a standalone verb: narrowing the `rm`
    # branch to option-tokens-only dropped it, which silently lost
    # `git clean -fdx ~/.claude` -- a real destructive recommendation the
    # first draft caught.
    # `-n`/`--dry-run` is excluded: a dry run is non-destructive and is the
    # very look-before-you-delete step this guard promotes, so warning there
    # fires at the moment the author is complying.
    r"\bgit[ ]+clean\b(?![^\n]{0,40}?(?:[ ]-[A-Za-z]*n|--dry-run))"
    r"(?:[ ]+-[-A-Za-z0-9]+)*[ ]+[\"']?" + _ROOTS,
]
RX_DESTRUCTIVE = re.compile("(?:" + "|".join(_DESTRUCTIVE_PARTS) + ")")

# Evidence the author looked for references before proposing removal: an
# earlier command that read a manifest AND named a config root in the same
# command, in either order. Requiring both is what makes the comment true: an
# earlier draft matched any mention of `settings.json`, so
# `grep -rn 'settings.json' README.md` -- which opens no config file at all --
# discharged the guard for the rest of the session.
RX_REF_CHECK = re.compile(
    r"(?:grep|rg|jq|cat|sed|awk|python3?|head|less)[^\n]{0,200}?" + _ROOTS +
    r"[^\n]{0,120}?(?:settings[.]json|config[.]toml|config[.]json|[.]mcp[.]json)"
    r"|(?:grep|rg|jq|cat|sed|awk|python3?)[^\n]{0,200}?"
    r"(?:settings[.]json|config[.]toml|config[.]json|[.]mcp[.]json)[^\n]{0,120}?" + _ROOTS,
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
    if not isinstance(payload, dict):
        return
    path = payload.get("transcript_path") or ""
    if not isinstance(path, str) or not path:
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
