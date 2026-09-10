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

THE DISCHARGE SIDE IS PARSED, NOT MATCHED (ai-config#3126). Whether an earlier
command READ a manifest is a parsing question --- "is this path the operand of
a reading command?" --- and a regex has no notion of argument position, so each
narrowing traded one boundary case for another over eight rounds on #3101. The
question is now asked of an argv: `scripts/lib/shellcmd.py` splits the command
into simple commands, `read_operands` drops each verb's options and its
pattern/script argument, and a discharge needs a FILE operand that both
resolves under a targeted root and is named like a manifest. `argv[0]`
membership replaces front-anchoring, so `locate` cannot match through `cat`; a
quoted pattern is a distinct argv element from the file operand, so
`grep -rn '~/.claude/settings.json' README.md` opens nothing and discharges
nothing; and the split means a verb and an operand in different commands cannot
pair.

The lexical path below is kept as the FALLBACK, not as the decision. `shlex`
raises on unbalanced quotes, and a command substitution or a heredoc body does
not parse into the operands the shell would pass, so those fall back to the
regex rather than to silence.

DISCHARGE: a real manifest read can still fail to clear the guard, which warns
while the author is complying. A verb outside `READ_VERBS` (`tail`, `wc`), a
path held in a variable, a `cd` whose target is indeterminate (`cd -`, `popd`),
a wrapper carrying its own option (`sudo -u me cat ...`, `timeout 5 cat ...`),
which `strip_env` peels only when the wrapper takes no argument of its own
(ai-config#3321), and --- most likely in this harness --- a manifest opened
with the Read tool rather than Bash, since only Bash commands are scanned. Two limits the argv
parse RETIRED: an already-expanded absolute path under the home directory now
resolves, and so does `cd <root>/hooks && cat ../settings.json`.
A command reading two manifests at once now credits both, since every file
operand is examined rather than only the first match.
An output redirect (`cat payload.json > ~/.claude/settings.json`) no longer
credits its target, since the shell opens that file for writing, while an
input redirect (`jq . < ~/.claude/settings.json`) still does. A heredoc body
redirected into a manifest still takes the regex fallback and is credited
there: a remaining limit.
Fires once per distinct message (sentinel keyed by content hash).
"""
import hashlib
import json
import os
import re
import sys
import tempfile

try:
    # `globals().get` rather than a bare `__file__`, because the test suite
    # `exec`s this module to read `REASON` and to time the regexes, and in
    # that namespace `__file__` is unbound -- so a bare reference reported a
    # broken install on every run of a suite whose subject imports fine.
    _SELF = globals().get("__file__") or sys.argv[0]
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(_SELF))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (resolve_cd_target, simple_commands_with_scope,
                          strip_env)
except Exception as _exc:  # broken install; fall back to the lexical path
    print("flag-config-deletion-without-ref-check: cannot load "
          "scripts/lib/shellcmd.py ({0}); using the lexical fallback"
          .format(_exc), file=sys.stderr)
    resolve_cd_target = simple_commands_with_scope = strip_env = None

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

# FALLBACK ONLY, since ai-config#3126. Everything from here to `RX_REF_CHECK`
# is the lexical approximation the argv parse below replaced; it still runs
# when `shlex` cannot parse the command, or when a command substitution or a
# heredoc means the argv is not what the shell would pass. Read its comments as
# a record of which boundary each narrowing bought, not as the live decision.
#
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

# ---------------------------------------------------------------------------
# The argv path (ai-config#3126). Everything below decides "is this manifest
# path the operand of a reading command?" from argument position rather than
# from the shape of the surrounding text.
# ---------------------------------------------------------------------------

# Programs that OPEN their file operands. Membership is tested on
# `os.path.basename(argv[0])`, which is what retires the front-anchoring the
# `_READ` pattern needed: `locate` is simply not in this set, so the `cat`
# inside its name can never match.
READ_VERBS = frozenset({
    "grep", "egrep", "fgrep", "rg", "jq", "yq", "cat", "sed", "awk", "gawk",
    "mawk", "python", "python3", "head", "less", "bat", "xxd",
})
# `egrep`/`fgrep`/`gawk` take the option grammar of the program they alias.
VERB_ALIASES = {"egrep": "grep", "fgrep": "grep", "gawk": "awk",
                "mawk": "awk", "yq": "jq"}

# Verbs whose FIRST positional argument is a PATTERN or a SCRIPT rather than a
# file. Dropping it is what stops `grep -rn '~/.claude/settings.json' README.md`
# discharging: `shlex` dequotes the pattern into an argv element that looks
# exactly like a path, and only its POSITION says it is not one.
PATTERN_FIRST_VERBS = frozenset({"grep", "rg", "jq", "sed", "awk"})

# Options that supply the pattern or script separately, so the first positional
# IS a file: `grep -e PAT file`, `awk -f prog.awk file`, `jq -f filter file`.
# Per verb for the same reason VALUE_OPTS is: one spelling, several meanings.
# `jq -e` is --exit-status, a boolean with nothing to do with the filter, so a
# shared set marked the filter as already supplied and left a quoted path
# spelling a manifest sitting in file position -- a FALSE DISCHARGE, which is
# the one direction this guard must not fail in.
PATTERN_OPTS = {
    "grep": frozenset({"-e", "--regexp", "-f", "--file"}),
    "rg": frozenset({"-e", "--regexp", "-f", "--file"}),
    "sed": frozenset({"-e", "--expression", "-f", "--file"}),
    "awk": frozenset({"-f", "--file"}),
    "jq": frozenset({"-f", "--from-file"}),
}

# Options consuming the NEXT TWO tokens: `jq --arg NAME VALUE`. Skipping only
# one leaves the other in positional position, where a value that happens to
# spell a manifest path is read as a file operand the command never opens.
PAIR_OPTS = {
    "jq": frozenset({"--arg", "--argjson", "--slurpfile", "--rawfile"}),
}

# Options after which the remaining positionals are NOT input files: jq's
# `--args`/`--jsonargs` rebind them to $ARGS. Which of them the filter still
# consumes is not decidable from argv alone, so credit no operand at all --
# the fail-toward-warning direction.
NO_FILE_OPTS = {
    "jq": frozenset({"--args", "--jsonargs"}),
}

# Options taking the NEXT token as their value, per verb. Per verb rather than
# shared, because the same spelling means different things: `sed -n` is
# `--quiet` and takes nothing, while `head -n` takes a line count. A shared set
# would consume `sed -n '1,5p' <manifest>`'s script as `-n`'s value, leaving the
# manifest as the dropped first positional and losing a real discharge.
VALUE_OPTS = {
    "grep": frozenset({
        "-e", "--regexp", "-f", "--file", "-m", "--max-count",
        "-A", "--after-context", "-B", "--before-context", "-C", "--context",
        "--include", "--exclude", "--exclude-dir", "--exclude-from", "--label",
        "-d", "--directories", "-D", "--devices", "--binary-files",
        "--color", "--colour",
    }),
    "rg": frozenset({
        "-e", "--regexp", "-f", "--file", "-m", "--max-count",
        "-A", "--after-context", "-B", "--before-context", "-C", "--context",
        "-g", "--glob", "-t", "--type", "-T", "--type-not", "--color",
        "--colors", "-M", "--max-columns", "--max-depth", "--iglob",
    }),
    "sed": frozenset({"-e", "--expression", "-f", "--file",
                      "-l", "--line-length"}),
    "awk": frozenset({"-f", "--file", "-v", "--assign",
                      "-F", "--field-separator"}),
    # `--arg` and friends live in PAIR_OPTS, and `--jsonargs` in NO_FILE_OPTS;
    # neither takes exactly one value, which is all this table can express.
    "jq": frozenset({"-f", "--from-file", "--indent"}),
    "head": frozenset({"-n", "--lines", "-c", "--bytes"}),
    "xxd": frozenset({"-l", "-s", "-c", "-g"}),
}

# The basenames that count as a manifest. Compared with `==` against a resolved
# path's basename, which is what retires `_MANIFEST`'s lookbehind: nothing can
# match `tsconfig.json` or `webpack.config.json` as a suffix.
MANIFEST_NAMES = frozenset({"settings.json", "config.toml", "config.json",
                            "mcp.json", ".mcp.json"})

# Directory-changing builtins, whose effect on later operands the scan tracks.
CD_VERBS = frozenset({"cd", "pushd", "popd"})

# Constructs whose argv is not what the shell would pass: the value of a
# command substitution is unknown here, a heredoc BODY is blanked by
# `shellcmd._heredoc_free` before `shlex` ever sees it, and a PROCESS
# substitution splits into an argv whose `argv[0]` is the outer program, so
# `diff <(cat <manifest>) <(cat other)` presents `diff` where `cat` ran. Union
# the argv verdict with the lexical one for all three, per the issue's "fall
# back to the lexical path rather than to silence".
RX_UNPARSEABLE = re.compile(r"[$][(]|`|<<|[<>][(]")
# A redirect operand is not a file the command READS. `> file` and `>> file`
# (with or without a leading descriptor, attached or separate) name a file the
# shell opens for writing, so overwriting a manifest must not discharge the
# guard; `< file` names one the command reads, so its target stays an operand.
RX_OUT_REDIRECT = re.compile(r"^(?:[0-9]*>>?[|]?|&>>?)(.*)$")
RX_IN_REDIRECT = re.compile(r"^[0-9]*<(.*)$")

HOME = os.path.expanduser("~")


def config_root_of(abs_path):
    """The config root `abs_path` lies under, or `None`.

    An exact match or a `<root>/...` prefix only, so `~/.config-notes` is not
    under `~/.config` --- the same boundary `RX_ROOT_NAME`'s lookahead draws,
    here as a path comparison rather than a character class.
    """
    for name in CONFIG_ROOTS:
        root = os.path.normpath(os.path.join(HOME, "." + name))
        if abs_path == root or abs_path.startswith(root + os.sep):
            return name
    return None


def expand_path(path, cwd):
    """`path` as a normalized absolute path, or `None` when indeterminate.

    `~`, `$HOME` and `${HOME}` expand; any other `$` or a backtick makes the
    value unknowable without running the shell, and `None` means exactly that
    rather than "no root". A relative path needs a known `cwd`, which is why
    `cat config.json` after an untracked `cd` credits nothing.
    """
    if not path:
        return None
    if path == "~":
        path = HOME
    elif path.startswith("~/"):
        path = os.path.join(HOME, path[2:])
    elif path in ("$HOME", "${HOME}"):
        path = HOME
    elif path.startswith("$HOME/"):
        path = os.path.join(HOME, path[len("$HOME/"):])
    elif path.startswith("${HOME}/"):
        path = os.path.join(HOME, path[len("${HOME}/"):])
    elif "$" in path or "`" in path or path.startswith("~"):
        return None
    if not os.path.isabs(path):
        if cwd is None:
            return None
        path = os.path.join(cwd, path)
    return os.path.normpath(path)


def read_operands(argv):
    """The FILE operands of a reading command, or `None` when argv is not one.

    Options are dropped, an option's separate value is skipped, and a
    pattern-first verb loses its first positional unless an `-e`/`-f`-style
    option already supplied the pattern. What is left is the set of paths the
    command actually opens.
    """
    if not argv:
        return None
    verb = os.path.basename(argv[0])
    verb = VERB_ALIASES.get(verb, verb)
    if verb not in READ_VERBS:
        return None
    value_opts = VALUE_OPTS.get(verb, frozenset())
    pair_opts = PAIR_OPTS.get(verb, frozenset())
    no_file_opts = NO_FILE_OPTS.get(verb, frozenset())
    pattern_opts = PATTERN_OPTS.get(verb, frozenset())
    positional = []
    pattern_supplied = False
    end_of_opts = False
    index = 1
    while index < len(argv):
        token = argv[index]
        if not end_of_opts and token == "--":
            end_of_opts = True
            index += 1
            continue
        out_redirect = RX_OUT_REDIRECT.match(token)
        if out_redirect:
            index += 1 if out_redirect.group(1) else 2
            continue
        in_redirect = RX_IN_REDIRECT.match(token)
        if in_redirect:
            target = in_redirect.group(1)
            if not target:
                index += 1
                continue
            if target.startswith("&"):
                index += 1
                continue
            positional.append(target)
            index += 1
            continue
        if not end_of_opts and token.startswith("-") and token != "-":
            name = token.split("=", 1)[0]
            if name in pattern_opts:
                pattern_supplied = True
            if name in no_file_opts:
                return []
            if "=" in token:
                index += 1
            elif name in pair_opts:
                index += 3
            elif name in value_opts:
                index += 2
            else:
                index += 1
            continue
        positional.append(token)
        index += 1
    if verb in PATTERN_FIRST_VERBS and not pattern_supplied and positional:
        positional = positional[1:]
    return positional


def scope_cwd(cwd_by_scope, scope):
    """The directory a command in `scope` runs in, inherited from its parents.

    A subshell starts where its parent stood, so the lookup walks outward from
    the command's own scope. A sibling subshell carries a different id, which
    is what keeps `(cd ~/.claude) && cat settings.json` from crediting a read.
    """
    for depth in range(len(scope), 0, -1):
        key = scope[:depth]
        if key in cwd_by_scope:
            return cwd_by_scope[key]
    return None


def argv_read_roots(command):
    """Roots whose manifest `command` reads, or `None` when it cannot parse."""
    parsed = simple_commands_with_scope(command)
    if parsed is None:
        return None
    found = set()
    cwd_by_scope = {}
    for scope, argv in parsed:
        cwd = scope_cwd(cwd_by_scope, scope)
        _env, rest = strip_env(argv)
        if not rest:
            continue
        if os.path.basename(rest[0]) in CD_VERBS:
            cwd_by_scope[scope] = resolve_cd_target(rest, cwd)
            continue
        for operand in read_operands(rest) or ():
            resolved = expand_path(operand, cwd)
            if resolved is None:
                continue
            if os.path.basename(resolved) not in MANIFEST_NAMES:
                continue
            root = config_root_of(resolved)
            if root:
                found.add(root)
    return found


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


def lexical_read_roots(command):
    """`read_roots`'s fallback: the roots `RX_REF_CHECK` credits.

    Scoped to each match rather than the whole command, for the same reason
    `targeted_roots` is scoped to the deletions: in
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


def read_roots(command):
    """The roots whose manifest a command actually READS.

    The argv parse decides, and the lexical scan is consulted only where the
    argv cannot be trusted: a `shlex` failure returns `None` here, and a
    command substitution or heredoc means the tokens are not the ones the shell
    would pass. Unioning in those two cases keeps the guard's behaviour where
    it was rather than dropping to silence, which for a DISCHARGE test is the
    fail-open direction a warn-only guard wants.
    """
    command = command or ""
    parsed = argv_read_roots(command) if simple_commands_with_scope else None
    if parsed is None:
        return lexical_read_roots(command)
    if RX_UNPARSEABLE.search(command):
        return parsed | lexical_read_roots(command)
    return parsed


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
            # A read is now DEFINED by the roots it credits, so the separate
            # `RX_REF_CHECK.search` gate this replaced would have re-admitted
            # every case the argv parse exists to reject.
            roots = read_roots(command)
            if not roots:
                continue
            if not wanted:
                return True
            covered |= roots & wanted
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
