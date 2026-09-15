#!/bin/sh
# Name the interpreter when `python3` cannot read the directory the hooks live
# in, instead of leaving every Python hook to deny tool calls anonymously.
#
# Rationale (ai-config#3624). Every Python hook is registered as
# `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/<name>.py"`. On Windows, bare `python3`
# commonly resolves to the Microsoft Store App Execution Alias, which forwards
# to a real interpreter but runs it in a packaged-app filesystem view that
# cannot see `%APPDATA%\Claude`. The plugin lives under exactly that path, so
# every hook dies on a file that is plainly there:
#
#   PreToolUse:Bash hook error: [python3 "...\hooks\flag-unmeasured-timestamp.py"]:
#   ...python.exe: can't open file '...': [Errno 2] No such file or directory
#
# A PreToolUse hook that fails to launch DENIES the call, so the outage is
# total: Bash, Edit, Write and Agent all stop working at once. It is also
# misattributed by construction. Each denial names whichever hook happened to
# match, never the interpreter, so the natural first hypothesis is a corrupt or
# partial plugin cache -- and `Test-Path` on the named file answers True, which
# makes the cache theory look confirmed rather than refuted. The interpreter is
# the last thing suspected.
#
# This hook is a shell script rather than Python for the obvious reason: in the
# failure it reports, no Python hook can run. `UserPromptSubmit` is the event
# whose plain stdout is added to context, so a diagnosis printed here reaches
# the session on the very first turn -- which is the whole remedy available,
# since nothing a hook can do repairs the harness's own PATH.
#
# The probe is `$0`: the hook asks whether `python3` can read the script file
# the harness just told the shell to run. That is the same directory every
# Python hook lives in, so it answers exactly the question that matters, and it
# needs no path manipulation at all.
#
# Passing `$0` through unchanged is load-bearing rather than merely tidy. The
# question is whether the interpreter can see the path the HARNESS names, so
# rewriting that path asks a different question -- and one that can come back
# reassuring when the real answer is not. Resolving a symlink, in particular,
# can land the probe in a directory the interpreter CAN read while the
# registered path stays invisible, which would report an all-clear over a total
# outage. (A normalised path does not, on measurement, false-alarm: MSYS
# converts a `/d/...` argument to `D:/...` before a native interpreter sees it,
# so `pwd -P` output resolves fine under Git Bash. Masking is the risk here,
# not false alarms.)
#
# Silent when the interpreter is fine. This runs on every prompt, and a
# reassurance nobody asked for would cost context on every turn forever.
set -u

REMEDY='Remedy (either one, then restart the session):
  - Windows Settings > Apps > Advanced app settings > App execution aliases:
    turn OFF the "python3" alias, so a real Python wins on PATH.
  - Put a real Python ahead of WindowsApps on PATH -- e.g. copy `python.exe` to
    `python3.exe` inside a Python install directory that already precedes it.

Until then, read every hook denial naming a missing hook file as THIS bug, not
as a corrupt plugin cache: the file is there, the interpreter cannot see it.'

if ! resolved=$(command -v python3 2>/dev/null) || [ -z "$resolved" ]; then
    printf '[ai-config] Every Python hook is inert this session: `python3` is not on PATH.\n\n'
    printf 'Hooks are registered as `python3 "<plugin root>/hooks/<name>.py"`. A PreToolUse\n'
    printf 'hook that cannot launch DENIES the tool call, so Bash, Edit, Write and Agent\n'
    printf 'will all fail with errors that name a hook rather than the missing interpreter.\n\n'
    printf 'Install Python 3, or expose it under the name `python3`.\n'
    exit 0
fi

python3 -c 'import os, sys; sys.exit(0 if os.path.exists(sys.argv[1]) else 1)' "$0" 2>/dev/null
status=$?

if [ "$status" -eq 0 ]; then
    exit 0
fi

if [ "$status" -eq 1 ]; then
    printf '[ai-config] Every Python hook is inert this session: the `python3` on PATH\n'
    printf 'cannot read the directory the hooks live in.\n\n'
    printf '  python3 resolves to: %s\n' "$resolved"
    printf '  cannot read:         %s\n\n' "$0"
    printf 'That file exists -- the interpreter is the half that cannot see it. On Windows\n'
    printf 'this is the Microsoft Store App Execution Alias, which runs Python in a\n'
    # `\\` rather than a bare `\C`: an undefined escape sequence in a printf
    # format is implementation-defined, and this one has to survive dash, bash
    # and whatever /bin/sh a consumer's machine provides.
    printf 'packaged-app filesystem view with no access to %%APPDATA%%\\Claude.\n\n'
    printf 'Every hook is registered as `python3 "<plugin root>/hooks/<name>.py"`, so all of\n'
    printf 'them fail with "[Errno 2] No such file or directory" on a file that is plainly\n'
    printf 'there. A PreToolUse hook that cannot launch DENIES the call, so Bash, Edit,\n'
    printf 'Write and Agent are all blocked, each with an error naming a hook.\n\n'
    printf '%s\n' "$REMEDY"
    exit 0
fi

printf '[ai-config] Every Python hook may be inert this session: the `python3` on PATH\n'
printf 'could not run a one-line probe.\n\n'
printf '  python3 resolves to: %s\n' "$resolved"
printf '  probe exit status:   %s\n\n' "$status"
printf 'Hooks are registered as `python3 "<plugin root>/hooks/<name>.py"`, and a\n'
printf 'PreToolUse hook that cannot launch DENIES the tool call. Run that interpreter\n'
printf 'by hand to see what it reports.\n'
exit 0
