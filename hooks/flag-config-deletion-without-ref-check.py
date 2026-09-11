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

The lexical path below is kept as the FALLBACK, not as the decision, and it is
narrower than it used to be. Two conditions reach it, and neither is a shape
the argv parse merely dislikes. One is an actual parse failure: `shlex` raises
on unbalanced quotes. The other is a broken install, where importing
`scripts/lib/shellcmd.py` fails and there is no argv parse to run at all --- on
that path the guard reverts wholesale to the approximation this change
replaced, including its false discharges. A command substitution does NOT fall back --- its
body is recursed through `read_roots`, so the argv path runs on the inner text
too, bounded by MAX_SUBSTITUTION_DEPTH. A heredoc body does not fall back
either; `_heredoc_free` blanks it before the scan, since its text is data for
the command rather than a command of its own.

DISCHARGE: a real manifest read can still fail to clear the guard, which warns
while the author is complying. A verb outside `READ_VERBS` (`tail`, `wc`), a
path held in a variable, a `cd` whose target is indeterminate (`cd -`, `popd`),
a wrapper carrying its own option (`sudo -u me cat ...`, `timeout 5 cat ...`),
which `strip_env` peels only when the wrapper takes no argument of its own
(ai-config#3321), and --- most likely in this harness --- a manifest opened
with the Read tool rather than Bash, since only Bash commands are scanned.

One DISCHARGE limit runs the other way and is tracked as ai-config#3564:
the parser carries no operator between simple commands, so a read the
shell never reaches --- `false && cat <manifest>` --- is credited.
Deciding it needs an exit status the text does not carry.

Two limits the argv parse RETIRED:
an already-expanded absolute path under the home directory now resolves,
and so does `cd <root>/hooks && cat ../settings.json`.
A command reading two manifests at once now credits both, since every file
operand is examined rather than only the first match.
An output redirect (`cat payload.json > ~/.claude/settings.json`) no longer
credits its target, since the shell opens that file for writing, while an
input redirect (`jq . < ~/.claude/settings.json`) still does, although a
digit pattern before one (`grep 5 < ~/.claude/settings.json`) is read as a
descriptor and under-credits, since the tokenizer drops the whitespace that
tells the two apart.
A heredoc body that merely mentions a manifest credits
nothing, since the body is blanked before either path reads the command;
a heredoc redirected into a manifest credits nothing either, since that
redirect is a write. A here-string is an operand of the opener, not a file,
so `cat <<< <manifest path>` credits nothing as well.
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
    from shellcmd import (RX_HEREDOC_OPEN, _heredoc_free, resolve_cd_target,
                          simple_commands_with_scope, strip_env)
except Exception as _exc:  # broken install; fall back to the lexical path
    print("flag-config-deletion-without-ref-check: cannot load "
          "scripts/lib/shellcmd.py ({0}); using the lexical fallback"
          .format(_exc), file=sys.stderr)
    resolve_cd_target = simple_commands_with_scope = strip_env = None
    RX_HEREDOC_OPEN = None
    _heredoc_free = None

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
# is the lexical approximation the argv parse below replaced, and it now runs
# on two conditions: `shlex` raising, which means the command does not parse at
# all, and a failed import of `scripts/lib/shellcmd.py`, which leaves no argv
# parse to attempt. A command substitution does not reach it -- `read_roots` recurses over
# each body, so the argv path runs on the inner text too. Nor does a heredoc,
# whose body `_heredoc_free` blanks before the parse. Read its comments as a
# record of which boundary each narrowing bought, not as the live decision.
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

# An interpreter opens its SCRIPT and nothing else: every later token is
# sys.argv for that script, which may never open any of them. Crediting them
# all made `python3 tidy.py <manifest>` discharge the guard over a script that
# might only delete. Only the first operand is credited.
SCRIPT_ONLY_VERBS = frozenset({"python", "python3"})

# Options that supply the pattern or script separately, so the first positional
# IS a file: `grep -e PAT file`, `awk -f prog.awk file`, `jq -f filter file`.
# Per verb for the same reason BARE_OPTS is: one spelling, several meanings.
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
    # `-c CODE` and `-m MODULE` leave no script path, so every remaining
    # token is an argument to code that may open nothing.
    "python": frozenset({"-c", "-m"}),
    "python3": frozenset({"-c", "-m"}),
}

# Options known to take NO value, per verb. This is the inverse of the table
# it replaced, and the inversion is the point.
#
# Listing the value-TAKING options makes an unlisted option default to bare,
# so its value falls through as a positional and is credited as a file the
# command opened. That is a false DISCHARGE, and five review rounds each found
# another spelling missing from such a list: `rg` alone grew `--pre`,
# `--replace`, `--sort`, `--type-add`, `--generate`. No curated list converges,
# because each tool's option surface is larger than the list and grows.
#
# Listing the BARE options inverts which way a gap fails. An unlisted option
# now consumes the token after it, so a forgotten spelling loses a discharge
# and WARNS rather than crediting a file nothing opened. Under-crediting is the
# direction this test wants.
#
# Per verb rather than shared, because the same spelling means different
# things: `sed -n` is `--quiet` and takes nothing, while `head -n` takes a line
# count.
BARE_OPTS = {
    "grep": frozenset({
        "-r", "-R", "--recursive", "-n", "--line-number", "-i",
        "--ignore-case", "-v", "--invert-match", "-l", "--files-with-matches",
        "-L", "--files-without-match", "-c", "--count", "-q", "--quiet",
        "-s", "--no-messages", "-w", "--word-regexp", "-x", "--line-regexp",
        "-F", "--fixed-strings", "-E", "--extended-regexp", "-P",
        "--perl-regexp", "-G", "--basic-regexp", "-o", "--only-matching",
        "-a", "--text", "-I", "-H", "--with-filename", "-h",
        "--no-filename", "-z", "--null-data", "-Z", "--null", "-U",
        "--binary", "--line-buffered", "--help", "--version", "-V",
    }),
    "rg": frozenset({
        "-i", "--ignore-case", "-S", "--smart-case", "-s", "--case-sensitive",
        "-n", "--line-number", "-N", "--no-line-number", "-v",
        "--invert-match", "-l", "--files-with-matches", "--files-without-match",
        "-c", "--count", "--count-matches", "-q", "--quiet", "-w",
        "--word-regexp", "-x", "--line-regexp", "-F", "--fixed-strings",
        "-P", "--pcre2", "-o", "--only-matching", "-a", "--text", "-u",
        "--unrestricted", "--hidden", "--no-ignore", "--follow", "-L",
        "--files", "--no-filename", "-H", "--with-filename", "--json",
        "--vimgrep", "--null", "--no-heading", "--heading", "--trim",
        "--stats", "--debug", "--help", "--version", "-V", "-p", "--pretty",
        "-z", "--search-zip", "--multiline", "-U", "--multiline-dotall",
        "--crlf", "--no-messages", "--block-buffered", "--line-buffered",
    }),
    "sed": frozenset({
        "-n", "--quiet", "--silent", "-r", "-E", "--regexp-extended",
        "-s", "--separate", "-u", "--unbuffered", "-z", "--null-data",
        "--posix", "--debug", "--help", "--version",
    }),
    "awk": frozenset({
        "--posix", "--traditional", "--re-interval", "--help", "--version",
        "-V",
    }),
    "jq": frozenset({
        "-r", "--raw-output", "-j", "--join-output", "-c", "--compact-output",
        "-n", "--null-input", "-s", "--slurp", "-e", "--exit-status",
        "-a", "--ascii-output", "-S", "--sort-keys", "-R", "--raw-input",
        "-C", "--color-output", "-M", "--monochrome-output", "--tab",
        "--seq", "--stream", "--help", "--version",
    }),
    "head": frozenset({"-q", "--quiet", "--silent", "-v", "--verbose",
                       "-z", "--zero-terminated", "--help", "--version"}),
    "cat": frozenset({
        "-n", "--number", "-b", "--number-nonblank", "-s",
        "--squeeze-blank", "-E", "--show-ends", "-T", "--show-tabs",
        "-v", "--show-nonprinting", "-A", "--show-all", "-e", "-t", "-u",
        "--help", "--version",
    }),
    "xxd": frozenset({"-r", "-p", "-b", "-u", "-i", "-E", "-h"}),
}

# The basenames that count as a manifest. Compared with `==` against a resolved
# path's basename, which is what retires `_MANIFEST`'s lookbehind: nothing can
# match `tsconfig.json` or `webpack.config.json` as a suffix.
MANIFEST_NAMES = frozenset({"settings.json", "config.toml", "config.json",
                            "mcp.json", ".mcp.json"})

# Directory-changing builtins, whose effect on later operands the scan tracks.
CD_VERBS = frozenset({"cd", "pushd", "popd"})

# Constructs whose argv is not what the shell would pass: the value of a
# command substitution is unknown here, and a PROCESS substitution splits into
# an argv whose `argv[0]` is the outer program, so
# `diff <(cat <manifest>) <(cat other)` presents `diff` where `cat` ran. The
# lexical scan runs over the text INSIDE each such construct and nothing else
# (see `substitution_bodies`), per the issue's "fall back to the lexical path
# rather than to silence". A heredoc is NOT in this set: its body is never
# executed, so nothing inside it is a read, and the argv path sees the command
# with the body blanked by `shellcmd._heredoc_free`.
RX_SUBSTITUTION_OPEN = re.compile(r"[$][(]|`|[<>][(]")
# How far `read_roots` follows a substitution nested inside a substitution.
# Deep nesting is vanishingly rare and the bound only ever under-credits,
# which is the direction that warns.
MAX_SUBSTITUTION_DEPTH = 8
# A redirect operand is not a file the command READS. `> file` and `>> file`
# name a file the shell opens for writing, so overwriting a manifest must not
# discharge the guard; `< file` names one the command reads, so its target
# stays an operand. `shlex` with `punctuation_chars=True` never fuses a
# descriptor digit with the operator, so `2>&1` arrives as `2`, `>&`, `1`:
# the loop below joins a bare all-digit token to the operator that follows it
# rather than letting the digit fall through as a positional. The tokenizer
# also drops the whitespace that distinguishes `5<file` (descriptor 5) from
# `grep 5 < file` (pattern 5, then stdin), so the second shape loses its
# pattern. It no longer loses the FILE with it: a redirect target is collected
# apart from the positionals, so the PATTERN drop below cannot reach it.
# `<>` opens for reading as well as writing and is credited like `<`.
RX_OUT_REDIRECT = re.compile(r"^(?:>>?[|&]?|&>>?)(.*)$")
RX_IN_REDIRECT = re.compile(r"^<(&?)>?(.*)$")
# A here-string (`<<<`) is followed by its literal text, which names no file
# the command opens; the tokenizer always splits the text from the operator,
# attached or not, so both are skipped. A heredoc opener (`<<`, `<<-`) reaches
# this parser with its delimiter and body already blanked by
# `shellcmd._heredoc_free`, so only the operator itself is skipped.
RX_HERE_STRING = re.compile(r"^<<<$")
RX_HERE_DOC = re.compile(r"^<<-?$")

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
    bare_opts = BARE_OPTS.get(verb, frozenset())
    pair_opts = PAIR_OPTS.get(verb, frozenset())
    no_file_opts = NO_FILE_OPTS.get(verb, frozenset())
    pattern_opts = PATTERN_OPTS.get(verb, frozenset())
    positional = []
    redirected = []
    no_positionals = False
    pattern_supplied = False
    end_of_opts = False
    index = 1
    while index < len(argv):
        token = argv[index]
        if not end_of_opts and token == "--":
            end_of_opts = True
            index += 1
            continue
        if token.isdigit() and index + 1 < len(argv) and argv[index + 1][:1] in "<>":
            index += 1
            token = argv[index]
        if RX_HERE_STRING.match(token):
            index += 2
            continue
        if RX_HERE_DOC.match(token):
            index += 1
            continue
        out_redirect = RX_OUT_REDIRECT.match(token)
        if out_redirect:
            index += 1 if out_redirect.group(1) else 2
            continue
        in_redirect = RX_IN_REDIRECT.match(token)
        if in_redirect:
            dup, target = in_redirect.groups()
            if dup:
                index += 1 if target else 2
                continue
            if not target:
                # Detached form: the target is the NEXT token. Consuming it
                # here is what keeps it out of `positional`, where the
                # PATTERN drop below could reach it.
                if index + 1 < len(argv):
                    redirected.append(argv[index + 1])
                index += 2
                continue
            # Kept apart from `positional`: a redirect may appear anywhere
            # in a simple command, so `grep < README.md '<manifest>'` would
            # otherwise put the target at index 0 and the PATTERN drop below
            # would remove the file actually opened and credit the pattern.
            redirected.append(target)
            index += 1
            continue
        if not end_of_opts and token.startswith("-") and token != "-":
            name = token.split("=", 1)[0]
            if cluster_supplies_pattern(name, pattern_opts):
                pattern_supplied = True
            if name in no_file_opts:
                # No POSITIONAL operand is a file this command opens, but a
                # redirect still is: `python3 -c '...' < <manifest>` opens it
                # on stdin. Returning here dropped the targets collected so
                # far and skipped any that follow, which under-credits.
                no_positionals = True
            if "=" in token:
                index += 1
            elif name in pair_opts:
                index += 3
            elif takes_no_value(name, bare_opts):
                index += 1
            else:
                # Unknown option: assume it consumes the next token. A wrong
                # guess here loses a discharge and warns; the opposite guess
                # credits a file nothing opened.
                index += 2
            continue
        positional.append(token)
        index += 1
    if verb in PATTERN_FIRST_VERBS and not pattern_supplied and positional:
        positional = positional[1:]
    if verb in SCRIPT_ONLY_VERBS:
        positional = positional[:1]
    if no_positionals:
        positional = []
    return positional + redirected


def cluster_supplies_pattern(name, pattern_opts):
    """True when `name` supplies the pattern, whole or as a clustered letter.

    `takes_no_value` already decomposes a short cluster letter by letter, and
    this has to as well: `sed -ne '1,5p' <manifest>` carries `-e` inside `-ne`,
    so testing the whole token left `pattern_supplied` false and the PATTERN
    drop then took the one real file operand.
    """
    if name in pattern_opts:
        return True
    if not name.startswith("-") or name.startswith("--") or len(name) < 3:
        return False
    return any("-" + letter in pattern_opts for letter in name[1:])


def takes_no_value(name, bare_opts):
    """True when `name` is known to take no value.

    A short-option CLUSTER counts when every letter in it does, so `grep -rn`
    stays bare rather than swallowing the pattern that follows it. An unknown
    spelling is not bare, which is what makes a gap in the table warn rather
    than discharge.
    """
    if name in bare_opts:
        return True
    if not name.startswith("-") or name.startswith("--") or len(name) < 3:
        return False
    return all("-" + letter in bare_opts for letter in name[1:])


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


BACKSLASH = chr(92)


# What a quoted expansion trigger is rewritten to before the argv parse. A
# character no rule recognises, so the operand arrives naming a path that
# resolves under no config root and credits nothing.
INERT = chr(2)


def _inert_regions(command):
    """{start: end} for each span this walk must not read as shell text.

    A `#` comment runs to the newline. A heredoc body runs from the line after
    its opener to its terminator. Both are data the shell never parses for
    quoting, and reading them desynchronizes a quote-tracking scan.
    """
    regions = {}
    quote = None
    index = 0
    while index < len(command):
        char = command[index]
        if char == BACKSLASH and quote in (None, '"'):
            index += 2
            continue
        if quote is None and char in ("'", '"'):
            quote = char
        elif quote == char:
            quote = None
        elif quote is None and char == "#" and (
                index == 0 or command[index - 1] in " \t\n;&|()"):
            newline = command.find("\n", index)
            end = len(command) if newline == -1 else newline
            regions[index] = end
            index = end
            continue
        elif quote is None and command.startswith("<<", index):
            match = RX_HEREDOC_OPEN.match(command, index)
            if match:
                body = command.find("\n", match.end())
                if body != -1:
                    terminator = command.find(
                        "\n" + match.group(3), body)
                    end = len(command) if terminator == -1 else terminator + 1
                    regions[body + 1] = end
                index = match.end()
                continue
        index += 1
    return regions


def neutralize_quoted_expansions(command):
    """`command` with every QUOTED expansion trigger made inert.

    `shlex` strips quotes before the argv parse sees a token, and the quoting
    is what decides whether the shell expanded it. Measured against bash: a
    tilde expands in neither quote, and `$HOME` expands in double quotes but
    not single. So `cat '<tilde>/.claude/settings.json'` opens a file named
    literally with a tilde, and crediting the home manifest there is a false
    discharge.

    Done by rewriting the raw text POSITIONALLY rather than by recovering the
    quoted spans and matching operands against them by content. That earlier
    approach produced four separate defects in three review rounds --- a
    split-quoted trigger it could not see, an escaped quote that desynchronized
    it, and two operands with identical text but different quoting that it
    conflated --- because text content cannot distinguish one occurrence from
    another. Here each trigger is decided where it sits, so there is nothing to
    reconcile.
    """
    out = list(command)
    quote = None
    index = 0
    skip_to = _inert_regions(command)
    while index < len(command):
        # A comment body and a heredoc body are DATA, and an apostrophe in one
        # is not a quote. Scanning them flipped this walk's quote state, so the
        # real opening quote of a later operand read as a close and its trigger
        # survived un-neutralized: a false discharge from the word "it's".
        if index in skip_to:
            index = skip_to[index]
            continue
        char = command[index]
        # A backslash escapes at top level and inside double quotes, where a
        # backslash-quote is a literal quote rather than the span's close.
        if char == BACKSLASH and quote in (None, '"'):
            index += 2
            continue
        if quote is None and char in ("'", '"'):
            quote = char
            index += 1
            continue
        if quote == char:
            quote = None
            index += 1
            continue
        if quote is not None and _trigger_at(command, index, quote):
            out[index] = INERT
        index += 1
    return "".join(out)


def _trigger_at(command, index, quote):
    """True when an expansion trigger starts at `index` under `quote`.

    A tilde only triggers at the start of a word, which inside a quoted span
    means the character before it opened the span or is a separator. `$HOME`
    triggers anywhere, and only single quotes suppress it.
    """
    char = command[index]
    if char == "~" and (index == 0 or command[index - 1] in "'\" /:= 	"):
        return True
    if char != "$" or quote != "'":
        return False
    return command.startswith("$HOME", index) or command.startswith("${HOME}", index)


def argv_read_roots(command):
    """Roots whose manifest `command` reads, or `None` when it cannot parse."""
    parsed = simple_commands_with_scope(
        neutralize_quoted_expansions(command))
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


def read_roots(command, depth=0):
    """The roots whose manifest a command actually READS.

    The argv parse decides. A substitution's body is itself a shell command,
    so it is parsed the same way rather than handed to the regex: scanning it
    lexically reinstated the argument-position blindness this hook exists to
    remove, and `echo $(grep -rn '<manifest path>' README.md)` credited a
    manifest that only ever appeared as a grep PATTERN (CI review of
    c4dd08a2). The lexical scan survives for the two cases the argv path cannot
    reach: a `shlex` failure, and a broken install where `shellcmd` did not
    import at all. The fail-open direction is what a warn-only DISCHARGE test
    wants in both. `depth` bounds the recursion, since a substitution can nest.
    """
    command = command or ""
    # The outer parse sees the raw command with its substitutions blanked.
    # NOT the heredoc-free text: `_heredoc_free` blanks from the opener, so a
    # file operand sitting after `<<-EOF` on the same line would go with it,
    # and `simple_commands_with_scope` applies that blanking itself anyway.
    outer = blank_substitutions(command, substitution_spans(command))
    parsed = argv_read_roots(outer) if simple_commands_with_scope else None
    if parsed is None:
        return lexical_read_roots(command)
    if depth >= MAX_SUBSTITUTION_DEPTH:
        return parsed
    # Recursion reads the heredoc-free text, so an opener inside a heredoc
    # BODY is data rather than a substitution to follow.
    scanned = _heredoc_free(command) if _heredoc_free else command
    for start, end in substitution_spans(scanned):
        parsed = parsed | read_roots(scanned[start:end], depth + 1)
    return parsed


def blank_substitutions(command, spans):
    """Replace each substitution, delimiters and all, with a single space.

    The argv parse must not see a substitution's inner tokens. `shlex` opens a
    fresh scope for `$(` only, an accident of how `punctuation_chars` splits
    that into two tokens, so a backtick or `<( )` body stayed glued into the
    enclosing command's own argv. `cat <(grep -rn '<manifest>' README.md)`
    then credited a manifest that appears only as a grep PATTERN, which is the
    exact false discharge this hook exists to close.

    A space rather than a filler word, so a substitution embedded in a word
    splits that word rather than producing a plausible-looking operand: the
    result credits nothing, and under-crediting is the direction a DISCHARGE
    test wants.
    """
    if not spans:
        return command
    out = []
    cursor = 0
    for start, end in spans:
        opener = command.rfind("`", cursor, start)
        if opener == -1:
            opener = max(command.rfind("$(", cursor, start),
                         command.rfind("<(", cursor, start),
                         command.rfind(">(", cursor, start))
        out.append(command[cursor:opener])
        out.append(" ")
        cursor = min(end + 1, len(command))
    out.append(command[cursor:])
    return "".join(out)


def substitution_bodies(command):
    """The text INSIDE each command or process substitution in `command`.

    The argv parse cannot see what runs inside `$( )`, backticks, `<( )` or
    `>( )`, so `read_roots` recurses over exactly that text and nothing
    else. Scanning the whole segment instead handed the regex the outer
    command too, which the argv parse had already decided: a grep whose
    PATTERN spells a manifest path, with a substitution among its arguments,
    credited the manifest (review rounds on #3469). A manifest path that a
    substitution merely PRODUCES (`jq . $(echo <manifest>)`) is not credited
    either, since its value is unknown here; that under-credits, which for a
    DISCHARGE test is the direction that warns. An opener inside a
    single-quoted span is text the shell never expands, so it opens nothing;
    inside double quotes it does expand, and is followed. The scan resumes
    AFTER each body rather than inside it, since `read_roots` recurses into
    the body and would otherwise re-extract every nested substitution once
    per enclosing level, which is exponential in the nesting depth (CI
    review of a60a5f1a: 15 seconds on a 187-character command). The walk tracks
    which quote is open, so an apostrophe inside a double-quoted word does
    not start a single-quoted span (twelfth review round). A backtick body
    is closed by the first backtick outside its own quotes, so a quoted
    backtick inside it does not end it early. A command whose quotes never
    close never reaches here: shlex rejects it and the whole-command lexical
    fallback runs instead.
    """
    return [command[start:end] for start, end in substitution_spans(command)]


def substitution_spans(command):
    """[(body_start, body_end), ...] for each substitution in `command`.

    The walk is `substitution_bodies`' own, factored out so the same pass can
    both recurse into a body and blank it out of the text the argv parse sees.
    """
    bodies = []
    quote = None
    index = 0
    while index < len(command):
        char = command[index]
        # An unquoted `#` at a word boundary starts a comment, and bash
        # expands nothing after it: `echo ok # $(cat <manifest>)` runs no
        # `cat`, so following that substitution credited a read that never
        # happens.
        if (quote is None and char == "#"
                and (index == 0 or command[index - 1] in " \t\n;&|()")):
            newline = command.find("\n", index)
            if newline == -1:
                break
            index = newline + 1
            continue
        if quote == "'":
            if char == "'":
                quote = None
            index += 1
            continue
        if char == "\\":
            index += 2
            continue
        if quote == '"' and char == '"':
            quote = None
            index += 1
            continue
        if quote is None and char in ("'", '"'):
            quote = char
            index += 1
            continue
        match = RX_SUBSTITUTION_OPEN.match(command, index)
        if not match:
            index += 1
            continue
        # `$( )` and a backtick expand inside double quotes; `<( )` and `>( )`
        # do not -- bash leaves them as literal text there, so scanning one
        # credited a read the shell never performs.
        if quote == '"' and match.group(0) in ("<(", ">("):
            index += 1
            continue
        if match.group(0) == "`":
            close = matching_backtick(command, match.end())
            bodies.append((match.end(), close))
            index = close + 1
            continue
        close = matching_paren(command, match.end())
        bodies.append((match.end(), close))
        index = close + 1
    return bodies


def matching_backtick(text, start):
    """Index of the backtick closing the body that opened before `start`.

    Quote-aware like `matching_paren`, so a backtick inside a quoted argument
    of the body does not end it early. A backslash escapes nothing inside
    single quotes, so a single-quoted span ending in one still closes at
    its quote (CI review of 85aa774e). Runs to the end of the text when no
    close exists, which shlex has already ruled out for a parsed command.
    """
    quote = None
    index = start
    while index < len(text):
        char = text[index]
        if quote == "'":
            if char == "'":
                quote = None
            index += 1
            continue
        if char == "\\":
            index += 2
            continue
        if quote:
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char == "`":
            return index
        index += 1
    return len(text)


def matching_paren(text, start):
    """Index of the `)` closing the group that opened just before `start`.

    Quote-aware, since a parenthesis inside a quoted argument of the
    substitution is text rather than structure: counting it would carry the
    body past the real close and into a later, unrelated command, which the
    lexical scan would then read (review round on #3469). A single-quoted
    span ends at the next quote; a double-quoted span ends at the next quote
    that is not backslash-escaped; a backslash outside quotes escapes the
    character after it.
    """
    depth = 1
    quote = None
    index = start
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\" and quote == '"':
                index += 2
                continue
            if char == quote:
                quote = None
        elif char == "\\":
            index += 2
            continue
        elif char in ("'", '"'):
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return len(text)


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
