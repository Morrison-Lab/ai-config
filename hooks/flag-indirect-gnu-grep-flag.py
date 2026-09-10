#!/usr/bin/env python3
r"""PreToolUse guard: a GNU-only `grep` flag reached through a child-process
boundary, where the name resolves by PATH rather than to the session's own
`grep`.

## The incident

On 2026-09-10, fixing a CI check in `Morrison-Lab/qwt`, this ran on macOS:

    git ls-files -z | xargs -0 grep -lP '[\x{2014}]'

It printed `grep: invalid option -- P` to stderr and exited 1. The session
read the empty stdout as "no tracked file contains an em dash" and wrote that
claim into a commit message. Five tracked files contained one; an adversarial
reviewer caught it.

The interactive shell's `grep` was a `ugrep` shell function, per
`memories/tools.md`. A function does not survive into a child of `xargs`, so
the child got the real on-PATH binary -- BSD `grep`, which has no `-P` at all.

## Why the existing remedies do not reach it

`memories/debugging.md` already prescribes branching on the exit status
(`case $rc in 0) ...;; 1) ...;; *) echo "CHECK FAILED TO RUN";; esac`) for a
grep that never ran, and that remedy would have caught this -- BSD grep
rejects the flag with rc=**2**, exactly like the locale failure that remedy
was written for.

The indirection is what defeats it. `xargs` reports **1** for a child that
exited non-zero, laundering grep's distinguishable 2 into the one status that
also means "searched, found nothing" (measured 2026-09-10: `/usr/bin/grep
-lP x a.md` alone gives rc=2; the same through `xargs -0` gives rc=1, as does
an honest no-match through that pipe). So the single boundary that swaps the
binary also destroys the evidence it did, and after it neither stdout nor
`rc` distinguishes "searched every file, found none" from "rejected the flag
before opening one".

## Why the indirection is the trigger, not the flag

Typed directly, `grep -P` is frequently correct: the session's own `grep` may
be `ugrep` or a Homebrew `ggrep`, both of which support it. Flagging every
`grep -P` would be noise on a command that works. What changes the answer is
the child-process boundary, where the shell function or alias is gone and the
bare name resolves by PATH.

## Why this warns rather than blocks

Which `grep` actually resolves in the child is not decidable from the command
text, and on a Linux runner the command is correct as written. So this only
ever ADDS context -- `additionalContext` plus a `systemMessage`, never a
`permissionDecision`. It fails open on any parse trouble.
"""
import json
import os
import re
import sys

# Only flags MEASURED to be rejected by macOS's BSD grep belong here.
#
# An earlier draft also listed `-z`/`--null-data`, `--include`, `--exclude`
# and `--exclude-dir`, generalizing from the one flag that was actually
# tested. A reviewer checked them and all four work. Re-measured directly
# against `grep (BSD grep, GNU compatible) 2.6.0-FreeBSD` on 2026-09-10:
#
#     -P                 rc=2  grep: invalid option -- P
#     --perl-regexp      rc=2  grep: unrecognized option `--perl-regexp'
#     -z                 rc=0  (documented in its own man page)
#     --null-data        rc=0
#     --include=*.md     rc=0
#     --exclude=*.txt    rc=0
#     --exclude-dir=sub  rc=0
#
# Listing a portable flag here is worse than omitting it: the warning text
# asserts "BSD grep rejects {flag}", so a false entry makes the guard emit a
# false claim on a correct command -- the exact failure mode this whole entry
# is about. Add a flag only with a pasted measurement.
# Maps each flag to the stderr line BSD grep actually produced for THAT
# flag. They differ, so a single hard-coded quote would misreport one of
# them: the short form is rejected as an unknown character, the long form as
# an unknown word.
GNU_ONLY_FLAGS = {
    "-P": "invalid option -- P",
    "--perl-regexp": "unrecognized option " + chr(96) + "--perl-regexp'",
}

# The utilities that spawn `grep` as a fresh child, so a shell function or
# alias by that name does not reach it.
INDIRECTIONS = ("xargs", "find", "parallel", "sh", "bash", "zsh", "env")

# A quote may sit immediately before the name, as in `sh -c 'grep -P ...`,
# and the name may carry a path (`/usr/bin/grep`), which the token scan
# below strips the same way the indirection scan does.
GREP_RX = re.compile(r"(?:^|[|;&('\"]|\s)[^\s]*?(grep|egrep|fgrep)(?=\s)")

# Two templates, because the two shapes have different causes and only one of
# them is about PATH resolution. Neither names a binary the hook has not seen
# in the command text.
NOTE_RESOLVED = """`{invoked} {flag}` is reached through `{via}`, which spawns it as a fresh
child process.

    {command}

In that child the bare name `{invoked}` resolves by PATH, NOT to this
session's own `{invoked}` -- a shell function or alias does not cross a
child-process boundary. On macOS the PATH answer is typically
`/usr/bin/grep`, which has no `{flag}`: measured 2026-09-10 against
`grep (BSD grep, GNU compatible) 2.6.0-FreeBSD`, it prints
`{stderr}` and exits 2.

The failure then mimics a pass. The usage error goes to **stderr** while
**stdout is empty**, and `{via}` reports **1** for a child that exited
non-zero -- laundering grep's distinguishable 2 into the one status that
means "searched, found nothing". An honest no-match through the same pipe
also gives 1. So the boundary that swapped the binary also destroyed the
evidence it did, which is why branching on `rc` alone does not separate them
here.

Measured 2026-09-10: a false "no tracked file contains an em dash" reached a
commit message this way.

Two ways out:

  * Pin a binary you have checked, rather than relying on the name:
        GREP=$(command -v ggrep || command -v grep); ... | {via} ... "$GREP" {flag} ...
  * Better, for a content scan whose answer you will act on: replace the
    pipeline with a script that reports the POPULATION it examined alongside
    the hit count, so a zero carries evidence the scan ran. See
    `shared/workflow/algorithmatize-checks.md` and
    `memories/debugging.md`'s "A zero is not a pass" entries.

Either way, read stderr before reporting a zero.
"""

NOTE_PINNED = """`{invoked} {flag}` runs through `{via}`, and the path is pinned rather than
resolved.

    {command}

So nothing about a shell function or alias applies here -- the question is
only whether `{invoked}` is a grep that supports `{flag}`. If it is macOS's
own `/usr/bin/grep`, it is not: measured 2026-09-10 against
`grep (BSD grep, GNU compatible) 2.6.0-FreeBSD`, `{flag}` prints
`{stderr}` and exits 2. A Homebrew `ggrep` or a Linux GNU grep
accepts it, in which case this warning is noise -- check which one
`{invoked}` is.

If it is the BSD one, the failure mimics a pass: the usage error goes to
**stderr**, **stdout is empty**, and `{via}` reports **1** for a non-zero
child, which is also what an honest no-match returns. So read stderr, and
prefer a scan that reports the population it examined over one whose only
output is the hits.
"""


def _tokens(command):
    """Cheap whitespace split, with quotes stripped. Good enough to spot a
    flag token; this hook never needs to understand the shell's grammar."""
    out = []
    for raw in command.split():
        # Strip surrounding quotes AND any backslash the shell would have
        # eaten, so `sh -c \\\'grep ...` still yields a bare `grep` token.
        out.append(raw.strip("'" + '"' + chr(92)))
    return out


# Tokens an indirection may place before the utility it runs: its own flags,
# and `xargs -I`'s replacement placeholder. Skipped when locating the utility.
PLACEHOLDERS = {"{}", "{}" + ";", "()"}


def _utility_after(toks, vi):
    """Index of the utility `toks[vi]` will actually run, or None.

    `grep` appearing anywhere after an indirection is NOT enough: in
    `xargs -0 python3 script.py grep -P f` the utility is `python3` and
    `grep -P` is a pair of plain arguments, so warning there is noise on a
    command that never runs grep. So locate the utility slot and check only
    that.

    Heuristic, deliberately: the shell's grammar is not reimplemented here.
    Flags and `xargs -I`'s placeholder are skipped, and the first remaining
    token is taken as the utility. A flag that takes a SEPARATE value
    (`xargs -n 4`) would leave that value in the utility slot and suppress a
    warning -- a false negative, which is the safe direction for a guard
    that only ever adds context.
    """
    base = toks[vi].rsplit("/", 1)[-1]
    if base == "find":
        # `find` runs its utility only after -exec/-execdir.
        for j in range(vi + 1, len(toks)):
            if toks[j] in {"-exec", "-execdir"}:
                return j + 1 if j + 1 < len(toks) else None
        return None
    for j in range(vi + 1, len(toks)):
        t = toks[j]
        if t.startswith("-") or t in PLACEHOLDERS:
            continue
        return j
    return None


def indirect_gnu_grep(payload):
    """Return (flag, via, command) when a GNU-only grep flag is reached
    through a child-process boundary, else None."""
    tool = payload.get("tool_name") or payload.get("toolName") or ""
    if tool != "Bash":
        return None
    tin = payload.get("tool_input") or payload.get("toolInput") or {}
    command = (tin.get("command") or "").strip()
    if not command:
        return None

    if not GREP_RX.search(command):
        return None

    toks = _tokens(command)

    # Which indirection, if any, introduces the grep. Require the indirection
    # to appear BEFORE the grep token, so `grep xargs` in a pattern does not
    # count.
    grep_at = None
    for i, t in enumerate(toks):
        # `/usr/bin/grep` and `grep` are the same utility for this purpose,
        # and an absolute path is MORE exposed rather than less: it pins the
        # binary past any function or alias. Mirrors the `rsplit` the
        # indirection scan below already does.
        # `ggrep` is deliberately absent: it is GNU grep (Homebrew), where
        # `-P` genuinely works, so warning on it would assert a rejection
        # that does not happen. `egrep` and `fgrep` stay because BSD ships
        # both and both reject `-P` -- measured 2026-09-10,
        # `/usr/bin/egrep -lP` and `/usr/bin/fgrep -lP` each print
        # "invalid option -- P". `egrep` is additionally an alias in this
        # session (`grep -E`), so the boundary argument applies to it too.
        if t.rsplit("/", 1)[-1] in {"grep", "egrep", "fgrep"}:
            grep_at = i
            break
    if grep_at is None:
        return None

    # Pair the indirection with the utility it actually runs, and require
    # that utility to BE the grep found above. Checking the two
    # independently is what let `xargs -0 python3 script.py grep -P f`
    # through: an indirection was present, a grep token was present, and
    # nothing established that the second was what the first ran.
    via = None
    for i, t in enumerate(toks[:grep_at]):
        base = t.rsplit("/", 1)[-1]
        if base not in INDIRECTIONS:
            continue
        # A bare `find ... | grep` is a pipe, where grep is the shell's own
        # child and the function DOES apply; only -exec/-execdir spawns it.
        if _utility_after(toks, i) == grep_at:
            via = base
            break
    if via is None:
        return None

    # The flag must belong to the grep, so only look after it.
    # An explicit path is a different situation from a bare name, and the
    # warning has to say which: a bare name RESOLVES in the child (so the
    # session's function or alias is what goes missing), while a path PINS a
    # specific binary (so nothing resolves, and the question is only whether
    # that binary is BSD grep). Asserting the PATH story over a pinned path
    # would be a false claim of exactly the kind the flag table above
    # already warns about.
    invoked = toks[grep_at]
    pinned = "/" in invoked

    for t in toks[grep_at + 1:]:
        # `--perl-regexp=x` carries its value on the same token.
        bare = t.split("=", 1)[0]
        if bare in GNU_ONLY_FLAGS:
            return bare, via, command, invoked, pinned, GNU_ONLY_FLAGS[bare]
        # Clustered short flags: -lP, -rlP, etc.
        if re.fullmatch(r"-[A-Za-z]{2,}", t) and "P" in t[1:]:
            return "-P", via, command, invoked, pinned, GNU_ONLY_FLAGS["-P"]
    return None


def main():
    raw = sys.stdin.read()
    is_dry_run = os.environ.get("HOOK_DRY_RUN") == "1"
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception as exc:  # fail open
        print("flag-indirect-gnu-grep-flag: unparseable payload (%s)" % exc,
              file=sys.stderr)
        return 0

    try:
        found = indirect_gnu_grep(payload)
    except Exception as exc:  # fail open
        print("flag-indirect-gnu-grep-flag: could not parse command (%s)" % exc,
              file=sys.stderr)
        return 0

    if found is None:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    flag, via, command, invoked, pinned, stderr = found
    template = NOTE_PINNED if pinned else NOTE_RESOLVED
    # No `permissionDecision` key: an absent decision defers to the normal
    # permission flow. Naming "allow" would suppress a prompt the user would
    # otherwise see.
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": template.format(
                flag=flag, via=via, command=command, invoked=invoked,
                stderr=stderr),
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        if pinned:
            out["systemMessage"] = (
                "`%s %s` via `%s` pins that binary: if it is macOS's BSD grep "
                "the flag is rejected, with empty stdout and rc=1 -- "
                "indistinguishable from no match." % (invoked, flag, via)
            )
        else:
            out["systemMessage"] = (
                "`%s %s` via `%s` resolves by PATH in the child, past this "
                "session's own `%s`: BSD grep rejects the flag, with empty "
                "stdout and rc=1 -- indistinguishable from no match."
                % (invoked, flag, via, invoked)
            )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
