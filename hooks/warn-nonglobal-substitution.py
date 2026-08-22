#!/usr/bin/env python3
"""PreToolUse guard: warn on a non-global in-place `perl`/`sed` substitution.

## The incident

Mutation-testing deliberately breaks a construct, then confirms the test that
should defend it turns red -- see `shared/workflow/algorithmatize-checks.md`.
Four measured instances, 2026-08-21, where the MUTATION itself silently
failed to apply to the intended construct, and the still-green test then
read as "the mutation survived, my test is weak" or worse "verified":

  1. `perl -0pi -e 's/OLD/NEW/'` -- non-global -- rewrote the FIRST
     occurrence of the string. That string also appeared in a nearby prose
     comment, so the comment changed and the code did not. A `diff -q`
     guard confirmed the file changed, and that was not enough to catch it.
  2. A `python3 -c` replace whose target string had 4 occurrences; an
     `assert count == 1` aborted, and the mutation silently never ran inside
     a loop that continued past the failure. A different bug shape -- see
     "What this deliberately does NOT match" below.
  3. A property enforced by TWO regexes; mutating one left the other still
     enforcing it.
  4. Same shape as 1, again.

## The check

`sed -i` and `perl -i` (any bundled form: `-pi`, `-0pi`, `-i.bak`, ...)
against an `s<delim>PATTERN<delim>REPLACEMENT<delim>FLAGS` expression whose
FLAGS carry no `g` and no digit -- the shape that changes only the first
occurrence, silently, with no error and no indication anything was skipped.

## Why this warns rather than blocks

A non-global substitution is frequently exactly what is wanted -- fixing one
known instance, or a numeric `N` flag targeting a specific occurrence on
purpose. This hook cannot tell "I meant only the first occurrence" from "I
forgot the `g`", so it only ever adds context, per README's "A hook that
misfires is worse than a missing one" -- no `permissionDecision`, ever.

## What this deliberately does NOT match, and why

  - A substitution carrying the `g` flag (already global).
  - A substitution carrying a digit flag (`s/a/b/2`) -- that targets a
    specific occurrence on purpose, and warning "only the first occurrence
    changed" would be a FALSE claim about what the command does.
  - Any command with no `-i`/`--in-place` -- a read-only scan piping to
    stdout is common and safe; this hook only cares about a WRITE.
  - `git` and every other non-`perl`/`sed` command. The leading command
    word of each shell segment must itself be `perl` or `sed`, so a
    `git commit` or `gh pr comment` whose message happens to mention
    `s/a/b/` stays silent -- the same false-positive shape
    `require-gh-repo-flag.py` avoids for `gh`.
  - A Python `str.replace(a, b)` with no `count` argument. Left out
    deliberately, and not merely because it is hard to detect cleanly:
    Python's `.replace()` with no `count` already replaces ALL occurrences
    by default, the OPPOSITE of the perl/sed bug this hook exists for.
    Incident 2 above was a different failure entirely (a swallowed
    assertion inside a loop), which no non-global-substitution check would
    catch. Warning about `.replace()` under this hook's own rationale would
    be a false claim, so it stays out rather than being force-fit in.
  - A bundled perl short-flag cluster that is actually an argument-taking
    flag with an attached value, e.g. `-Ilib` (`-I`, include path) or
    `-e'...'`/`-Fpattern`. Perl's `-i` (in-place) is recognized only among
    the no-argument flag letters `{0, n, p, i}` in a bundled short cluster
    (optionally followed by a `.SUFFIX` backup extension), which covers the
    common one-liner shapes (`-pi`, `-0pi`, `-npi`, `-i.bak`, ...) without
    mistaking a lowercase `i` inside an unrelated argument (`-Ilib`,
    `lib` itself carries an `i`) for the flag.

Fails OPEN on any parse trouble, same as every guard here.
"""
import json
import re
import shlex
import sys

RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
LEAD_WORDS = {"then", "do", "else", "!", "time", "sudo", "command", "exec",
              "nohup", "env"}

_SHELL_OPS = set("();|&")


def _simple_commands(cmd):
    """Split a shell command into simple-command argv lists; None on error.

    Same construction as `flag-reset-hard-uncommitted-work.py`'s
    `_simple_commands` (itself following `no-unreviewed-pr.py`'s pattern):
    join `\\`-continued lines, blank heredoc bodies, turn unquoted newlines
    into `;`, then let `shlex` (punctuation-aware) split and dequote.
    """
    cmd = re.sub(r"\\\r?\n", " ", cmd)
    cmd = RX_HEREDOC.sub("<<", cmd)
    cmd = cmd.replace("\n", ";")
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None
    cmds, cur = [], []
    for t in toks:
        if t and set(t) <= _SHELL_OPS:
            if cur:
                cmds.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


# Perl's -i (in-place), bundled only among these NO-ARGUMENT flag letters, so
# an argument-taking flag's ATTACHED value (`-Ilib`, `-e'...'`) is never
# mistaken for the flag itself. See "What this deliberately does NOT match".
_PERL_INPLACE_CLUSTER = re.compile(r"^-[0np]*i[0npi]*(\.\S*)?$")

# sed's -i, optionally bundled with -n (quiet). BSD sed's mandatory backup-
# extension argument, when given as a separate empty-string token
# (`sed -i '' ...`), needs no special handling here -- the bare `-i` token
# alone already carries the flag.
_SED_INPLACE_CLUSTER = re.compile(r"^-[n]*i[n]*(\.\S*)?$")
_SED_INPLACE_LONG = re.compile(r"^--in-place(=.*)?$")


def _has_inplace_flag(cmd_word, args):
    if cmd_word == "perl":
        return any(_PERL_INPLACE_CLUSTER.match(a) for a in args)
    if cmd_word == "sed":
        return any(_SED_INPLACE_CLUSTER.match(a) or _SED_INPLACE_LONG.match(a)
                    for a in args)
    return False


# Common substitution delimiters. `/` covers the vast majority of real
# one-liners; the rest are the other conventional choices (used to avoid
# escaping a literal `/`, e.g. in a path). Deliberately NOT exhaustive --
# under-matching an exotic delimiter is far cheaper than a false positive.
_DELIMS = "/|#,~^!@"
_SUBST_RE = re.compile(
    r"\bs(?P<delim>[" + _DELIMS + r"])"
    r"(?:\\.|(?!(?P=delim)).)*"
    r"(?P=delim)"
    r"(?:\\.|(?!(?P=delim)).)*"
    r"(?P=delim)"
    r"(?P<flags>[A-Za-z0-9]*)",
    re.S,
)


def _non_global_matches(text):
    """Every substitution in TEXT whose flags carry neither `g` nor a digit
    -- the shape that silently changes only the first occurrence.

    Returns a list of (matched_text, flags).
    """
    out = []
    for m in _SUBST_RE.finditer(text):
        flags = m.group("flags")
        if "g" not in flags and not any(c.isdigit() for c in flags):
            out.append((m.group(0), flags))
    return out


def find_offenses(command):
    """[(cmd_word, segment_text, matched_subst, flags), ...] for every
    perl/sed -i invocation in COMMAND carrying a non-global substitution."""
    cmds = _simple_commands(command)
    if cmds is None:
        return []
    out = []
    for argv in cmds:
        i = 0
        while i < len(argv) and (ASSIGNMENT.match(argv[i])
                                  or argv[i] in LEAD_WORDS):
            i += 1
        rest = argv[i:]
        if not rest:
            continue
        cmd_word = rest[0].split("/")[-1]
        if not _has_inplace_flag(cmd_word, rest[1:]):
            continue
        segment_text = " ".join(rest)
        for matched, flags in _non_global_matches(segment_text):
            out.append((cmd_word, segment_text, matched, flags))
    return out


NOTE = (
    "This `{cmd_word} -i` command runs a NON-GLOBAL substitution:\n\n"
    "    {matched}\n\n"
    "(flags: {flags_display})\n\n"
    "A substitution with no `g` flag changes only the FIRST occurrence per "
    "line (sed) or in the target text (perl) -- which may not be the "
    "occurrence you meant, especially when the same string also appears in "
    "a nearby comment or an unrelated line.\n\n"
    "This bites hardest in MUTATION TESTING: a mutation that silently "
    "failed to apply reads as a surviving mutation, or worse as a verified "
    "one -- the test stays green because nothing changed, not because the "
    "code is correct.\n\n"
    "Confirm the intended CONSTRUCT changed, not merely that the file "
    "changed: print back the specific line or function you meant to "
    "mutate, rather than trusting a byte count or `diff -q`.\n\n"
    "If every occurrence should change, add `g`. If only one specific "
    "occurrence should, scope the pattern so it can only match there, and "
    "confirm which one changed.\n\n"
    "    command:  {cmd_word} -i ...\n"
    "    segment:  {segment}"
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # fail open, but say so
        print(f"warn-nonglobal-substitution: unreadable hook input ({exc})",
              file=sys.stderr)
        return 0

    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return 0

    try:
        offenses = find_offenses(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"warn-nonglobal-substitution: could not parse command "
              f"({exc})", file=sys.stderr)
        return 0

    if not offenses:
        return 0

    cmd_word, segment, matched, flags = offenses[0]
    flags_display = flags if flags else "(none)"

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(
                cmd_word=cmd_word, matched=matched,
                flags_display=flags_display, segment=segment,
            ),
        },
        "systemMessage": (
            f"`{cmd_word} -i` runs a non-global substitution ({matched}); "
            "it changes only the first occurrence -- confirm that is what "
            "you meant, and print back the changed construct rather than "
            "trusting the file diff alone."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
