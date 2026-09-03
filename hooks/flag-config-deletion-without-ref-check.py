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
message. A quoted search pattern that spells a full manifest path discharges
even though it opens nothing, for the same lack of argument-position parsing.
That one is the residue of a lexical approach: a regex has no notion of
argument position, so each narrowing trades one boundary case for another.
Parsing the command with `shlex` and asking whether a read verb's argv holds
a manifest under a targeted root would make the whole class structurally
impossible; it is filed as ai-config#3126 rather than done here.

DISCHARGE: a real manifest read can fail to clear the guard, which warns while
the author is complying. A verb outside the read list (`tail`, `wc`), an
already-expanded absolute path (`/Users/me/.claude/settings.json`), a `cd` into
a SUBdirectory then `../settings.json`, a verb-to-path gap over 120 characters,
a separator character (`|`, `;`, `&`) inside a QUOTED argument before the path,
since the gap excludes them lexically and `jq -r '.hooks|keys[]'` is the
idiomatic way to inspect a manifest, and --- most likely in this harness --- a
manifest opened with the Read tool rather than Bash, since only Bash commands
are scanned.
A command reading two manifests at once credits only the first, so a two-root
deletion needs two reads. Each is a warning to
answer in one sentence, not a block.
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
# includes `*`, `>`, `&` and `|` because `rm -rf ~/.claude*` is a common
# spelling of exactly what this guard exists to catch; a bare
# path-or-space boundary
# exempted it. `~/.config-notes` and `~/.claudex` still miss, which is the
# point.
RX_ROOT_NAME = re.compile(r"(?:~|[$]HOME|[$]{HOME})/[.](" +
                          "|".join(CONFIG_ROOTS) + r")(?=[/\"'`.,;)\]*&>|]|\s|$)")
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
    r"\bcd\b[ ]+[\"']?" + _ROOTS + r"[^\n]{0,80}?&&[ ]*"
    r"(?:rm\b|git[ ]+clean\b(?![ ]+(?:-[-A-Za-z0-9]+[ ]+)*?(?:-[A-Za-z]*n[A-Za-z]*\b|--dry-run\b)))",
    # `git clean -fdx <root>`. Kept as a standalone verb: narrowing the `rm`
    # branch to option-tokens-only dropped it, which silently lost
    # `git clean -fdx ~/.claude` -- a real destructive recommendation the
    # first draft caught.
    # `-n`/`--dry-run` is excluded: a dry run is non-destructive and is the
    # very look-before-you-delete step this guard promotes, so warning there
    # fires at the moment the author is complying.
    r"\bgit[ ]+clean\b(?![ ]+(?:-[-A-Za-z0-9]+[ ]+)*?(?:-[A-Za-z]*n[A-Za-z]*\b|--dry-run\b))"
    r"(?:[ ]+-[-A-Za-z0-9]+)*[ ]+[\"']?" + _ROOTS,
]
RX_DESTRUCTIVE = re.compile("(?:" + "|".join(_DESTRUCTIVE_PARTS) + ")")

# Evidence the author looked for references before proposing removal: an
# earlier command that read a manifest AND named a config root in the same
# command, in either order. Requiring both is what makes the comment true: an
# earlier draft matched any mention of `settings.json`, so
# `grep -rn 'settings.json' README.md` -- which opens no config file at all --
# discharged the guard for the rest of the session.
# Front-anchored like `_MANIFEST`: unanchored, `locate` and `duplicate`
# contain `cat` and `sbatch` contains `bat`, so each discharged the guard
# while opening nothing.
_READ = (r"(?<![-\w.])(?:grep|rg|jq|cat|sed|awk|python3?|head|less|bat"
         r"|xxd)\b")

# Front-anchored, so `tsconfig.json`, `webpack.config.json` and
# `jest.config.json` are not manifests.
_MANIFEST = (r"(?<![-\w.])(?:settings[.]json|config[.]toml|config[.]json"
             r"|[.]?mcp[.]json)")

# The discharge aims at "a read whose OPERAND is a manifest under the root",
# rather than "a read, a root and a manifest name loose in the same command".
# It gets there lexically, which is an approximation: a QUOTED search pattern
# spelling a full path --- `grep -rn '~/.claude/settings.json' README.md` ---
# still discharges, because telling a quoted pattern from a quoted operand
# needs argument-position parsing this guard does not do. Named in the limits
# above rather than chased with a wider pattern, which is what produced the
# gaps this design replaced.
#
# Earlier drafts allowed an arbitrary 200/120-character gap between the three,
# which let commands that open no manifest discharge the guard:
# `grep -rn 'settings.json' ~/.claude/hooks/` searches .py files FOR the
# string, `find ~/.claude ... -delete && cat config.json` is the deletion
# itself, and `grep -rn '~/.claude' ~/.codex/config.toml` reads a different
# root's manifest. Each paired a root with a manifest NAME rather than with a
# manifest READ.
#
# Two shapes, and nothing looser (modulo the quoted-pattern limit above):
#   1. the manifest path carries the root -- `<read> ... ~/.claude/settings.json`
#      with only path characters between them, so the root and the manifest are
#      one operand rather than two words in a line;
#   2. `cd <root> && <read> <manifest>`, where the shell supplies the prefix.
_PATHCHARS = r"[\w./~${}-]*"
# The root is CAPTURED, not merely matched. Reading it back off the whole match
# credited the wrong root whenever another root appeared earlier in the command
# --- `grep -rn '~/.claude' ~/.codex/config.toml` reads codex's manifest while
# mentioning claude as the search pattern.
_ROOTS_CAP_A = _ROOTS.replace("(?:", "(?P<root_a>", 1)
_ROOTS_CAP_B = _ROOTS.replace("(?:", "(?P<root_b>", 1)
_REF_ORDERS = [
    # No `&&`, `;` or `|` in the gap: the verb and the operand must be one
    # command. Spanning a separator let `grep -rn foo README.md && rm -f
    # ~/.claude/settings.json` discharge --- a command that DELETES the
    # manifest, the mirror of the `find ... -delete && cat config.json` case
    # the suite already pins.
    _READ + r"[^\n&;|]{0,120}?" + _ROOTS_CAP_A + r"/" + _PATHCHARS + _MANIFEST,
    r"\bcd\b[ ]+[\"']?" + _ROOTS_CAP_B + r"/?[\"']?[ ]*(?:&&|;)[ ]*" + _READ
    + r"[^\n]{0,80}?" + _MANIFEST,
]
RX_REF_CHECK = re.compile("(?:" + "|".join(_REF_ORDERS) + ")")


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


def roots_in(text):
    """The config-root names a string mentions, as a set."""
    return {m.group(1) for m in RX_ROOT_NAME.finditer(text or "")}


def read_roots(command):
    """The roots whose manifest a command actually READS.

    Scoped to each `RX_REF_CHECK` match rather than the whole command, for the
    same reason `targeted_roots` is scoped to the deletions: in
    `grep -rn '~/.claude' ~/.codex/config.toml` the `~/.claude` is the search
    PATTERN and `~/.codex` is the file opened, so a whole-command scan credits
    the read to the wrong root and discharges a `~/.claude` deletion.
    """
    found = set()
    for match in RX_REF_CHECK.finditer(command or ""):
        for group in ("root_a", "root_b"):
            hit = match.group(group)
            if hit:
                found |= roots_in(hit)
    return found


def targeted_roots(text):
    """The roots the DESTRUCTIVE commands name, not every root mentioned.

    Scoping this to the whole reply was wrong: a message that proposes deleting
    under `~/.claude` and merely mentions `~/.codex` in passing --- which this
    hook's own message text does --- widened the set to both, so a read under
    `~/.codex` discharged it. Only the matched deletions count.
    """
    found = set()
    for match in RX_DESTRUCTIVE.finditer(text or ""):
        found |= roots_in(match.group(0))
    return found


def ref_check_ran(path, wanted=None):
    """True when an earlier Bash command read a manifest under a wanted root.

    `wanted` is the set of roots the matched DELETIONS target. A read under a
    different root does not discharge: `jq . ~/.codex/config.toml` says nothing
    about what references `~/.claude/hooks`, and accepting it would clear the
    guard on evidence about an unrelated tree.

    EVERY targeted root needs evidence, not just one --- a reply proposing
    deletions under two roots is only half examined when one manifest was read,
    and the unread half is exactly the case this guard exists for. Coverage
    accumulates across commands, so two separate reads discharge a two-root
    reply.
    """
    covered = set()
    for record in transcript_records(path):
        if record.get("type") != "assistant":
            continue
        for block in (record.get("message") or {}).get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") not in {"Bash", "bash", "run_command"}:
                continue
            command = str((block.get("input") or {}).get("command") or "")
            if not RX_REF_CHECK.search(command):
                continue
            if not wanted:
                return True
            covered |= read_roots(command) & wanted
            if wanted <= covered:
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
    "Check what points at the files first: read the manifest under the same root "
    "the deletion targets and see whether it names them. For `~/.claude` that "
    "manifest is `settings.json`, so\n\n"
    "    grep -o 'hooks/[a-z0-9-]*[.]py' ~/.claude/settings.json | sort -u\n\n"
    "is the `.claude` spelling of the check; `~/.config`, `~/.codex`, `~/.gemini` "
    "and `~/.cursor` each keep their own, so repoint the grep at whichever root "
    "the deletion targets. Then recommend refresh or removal on that evidence. "
    "This warns and never "
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
    if ref_check_ran(path, targeted_roots(text)):
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
