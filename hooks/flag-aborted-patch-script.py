#!/usr/bin/env python3
r"""PreToolUse guard: committing after a multi-edit patch script raised.

## The incident

Morrison-Lab/ai-config#3320 (2026-09-07). A UMS pass had three review
findings to address, and applied them with one heredoc'd Python script
shaped like this:

    patch('memories/gh-cli.md',  old_a, new_a)   # anchor did not match
    patch('CLAUDE.md',           old_b, new_b)   # never ran
    patch('skills/.../SKILL.md', old_c, new_c)   # never ran

The first `patch()` asserted its anchor was present, the anchor had been
mangled by the backslash collapse `CLAUDE.md` documents under "Tool
transport collapses doubled backslashes", and the assert raised. Python
exits at the raise, so edits two and three never happened.

The session read the traceback, fixed the FIRST edit, and committed -- with
a message stating all three findings were addressed. Two of the three claims
were false. The next adversarial round caught it and returned "Needs more
work" over exactly the findings the message claimed were closed.

## Why the traceback is not the signal it looks like

A traceback reads as "that command failed", which invites re-running the
failed part. It is really "that command STOPPED", and everything after the
raise silently did not happen. Those are different, and only the second
explains why edits nobody re-examined are missing. Nothing later in the
session distinguishes them: the file that WAS edited looks right, `git
status` shows a real modification, and the diff of that one file is correct.
The absent edits leave no trace at all -- there is no error, no empty diff,
no failing check. They are invisible except by going back and asking, per
file, whether the edit landed.

That makes it the shape `shared/workflow/verify-the-right-artifact.md`
names: the artifact in hand (a correct-looking diff for one file) cannot
show the claim false, because the claim is about files the diff does not
mention.

## Why a hook rather than a rule

The corpus already forbids the resulting behaviour twice over.
`shared/writing/fact-check-prose.md` says to verify a claim before writing
it, and `CLAUDE.md`'s "Tool transport collapses doubled backslashes" section
ends with "Knowing this rule does not stop you tripping it, so add a check
rather than trusting recall" -- written after the same collapse was tripped
while that very section was loaded.

Both are read at a moment other than the one where this breaks. The claim is
composed at commit time, minutes after the traceback scrolled past, and by
then the traceback feels handled because the visible half of it was.

The condition, by contrast, is decidable from the transcript with no
semantics: a Bash result carried a Python traceback, its command wrote
files, and a commit follows with no intervening re-run.

## Why this warns rather than blocks

The hook cannot tell a partially-applied patch from a traceback that was
fully understood and correctly handled -- which is the common case, since
most tracebacks are from exploratory scripts that changed nothing, or from
a script whose edits were all re-applied afterwards. Blocking would refuse a
large class of correct commits, and per README's "A hook that misfires is
worse than a missing one" it would be switched off, taking the real cases
with it. So it only ever adds context.

## The match condition

  M1  the tool is `Bash` and the command runs `git commit`, decided from
      ARGV via `scripts/lib/shellcmd.py` rather than by a regex -- `\b` sits
      happily between `commit` and `-`, so a `git\s+commit\b` scan matches
      `git commit-tree` and `git commit-graph write`, and a quoted mention
      inside an `echo` matches too
  M2  scanning back to the previous SUCCESSFUL `git commit` (or the start of
      the transcript), some tool RESULT contains a Python traceback. No
      tool-NAME filter is applied to the historical scan -- correlation is by
      `tool_use_id` to a block carrying a command-shaped input, which in
      practice means Bash, but a different tool exposing a `command` or
      `script` field would be scanned identically.
      A commit that was rejected -- by a pre-commit hook, a lint gate --
      does not close the window: the partial patch is exactly as unresolved
      afterwards, and the retry is where this guard is worth most
  M3  that traceback's own command looks like an in-place file editor: it
      writes (`.write(`, `open(...,"w")`, `writelines`, `Path.write_text`)
      or is an explicit patch/sed-in-place invocation -- AND is not composed
      entirely of known read-only programs. The write patterns are matched
      against the command's own TEXT, so without that second half a `grep`
      for `.write(` over a source file counts as a write, and in this repo
      auditing hook sources for exactly these strings is routine
  M4  no later Bash command in the window re-ran an equivalent edit AND
      completed without a traceback

M4 compares TARGETS, not merely liveness. A patch script names its files as
string literals in its own text, so the failed command records approximately
what it meant to edit -- and clearing on any later write let the motivating
incident through, since repairing one of three files discharged the warning
for the other two. Only paths named by the later command's WRITING segments
count, so an `echo` summary listing the files it believes were fixed does
not clear anything: a command containing ANY announcing segment never takes
the heredoc fallback, whatever its writer's own target looks like.

Two approximations are deliberate. A path is recognized by its file
EXTENSION, so a failed command naming only extensionless targets
(`Makefile`, `LICENSE`) records no targets and then clears on the next
write. And the heredoc fallback reads the whole command, so a
non-announcing script that merely mentions an unrelated path counts it.
Both err toward clearing, which for a warn-only guard is the cheaper
direction than warning forever.

Fires once per (transcript, traceback position), so re-committing after
reading the warning is silent.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

TRACEBACK = "Traceback (most recent call last):"

# A command that modifies files in place. Kept deliberately narrow: a bare
# `python3 -c "print(1)"` that raised is not a partial patch, and warning on
# it would train the reader to ignore this.
WRITES = re.compile(
    r"""\.write\(|\.write_text\(|\.writelines\(|"""
    r"""open\s*\([^)]*['"][wa]['"]|"""
    r"""\bsed\s+-i\b|\bpatch\s+(-p\d|<)|\btee\b""",
    re.VERBOSE,
)

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (COMMAND_WRAPPERS, SHELL_KEYWORDS,
                          git_subcommand, simple_commands)
except Exception as _exc:  # broken install; fail open and say so
    print(f"flag-aborted-patch-script: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not evaluating", file=sys.stderr)
    git_subcommand = simple_commands = None
    COMMAND_WRAPPERS = SHELL_KEYWORDS = frozenset()


def is_commit(command):
    r"""True when `command` actually runs `git commit`.

    argv-based rather than a regex, because `\b` sits happily between
    `commit` and `-`: a `git\s+commit\b` scan matches `git commit-tree` and
    `git commit-graph write`, and a quoted mention inside an `echo` matches
    too. `scripts/lib/shellcmd.py` exists because this repo already paid for
    that bug once (no-unshipped-commit.py).
    """
    if simple_commands is None:
        return False
    argvs = simple_commands(command)
    if argvs is None:
        return False
    for argv in argvs:
        got = git_subcommand(argv)
        if got and got[0] == "commit":
            return True
    return False


# Commands that only READ. The write patterns below are matched against a
# command's own TEXT, so a grep or a cat whose subject happens to contain
# `.write(` or `sed -i` would otherwise be classed as a writer -- and in this
# repo, auditing hook sources for exactly these patterns is routine.
# How far past a wrapper to look for a read-only program. Matches
# `scripts/lib/shellcmd.py`'s own WRAPPER_ARG_WINDOW, which bounds the
# same scan for the same reason: a wrapper's options are unbounded in
# principle, and an unbounded search would reach the next command's words.
WRAPPER_ARG_WINDOW = 6

READ_ONLY = {
    "grep", "rg", "egrep", "fgrep", "cat", "bat", "head", "tail", "less",
    "more", "find", "ls", "wc", "diff", "git", "awk", "sort", "uniq", "jq",
}


def writes(command):
    """True when `command` plausibly edits a file in place."""
    if not WRITES.search(command):
        return False
    if simple_commands is None:
        return True
    argvs = simple_commands(command)
    if argvs is None:
        return True
    # A command every one of whose simple commands is a known reader cannot
    # have written anything, whatever its text quotes.
    for argv in argvs:
        head = _program(argv)
        if head is None:
            continue
        if head not in READ_ONLY:
            return True
    return False


def _program(argv):
    """The program `argv` actually runs, past wrappers and shell keywords.

    `git_subcommand` already strips `COMMAND_WRAPPERS` before reading the
    program name; this check reimplemented that comparison without the
    stripping, so `env grep`, `sudo grep` and `timeout 5 grep` -- ordinary
    forms in this repo's own hooks and CI -- read as writers on the strength
    of the text they were grepping FOR.
    """
    # `for`/`case`/`select` open a HEADER, not a command: their next token is
    # a loop variable or a subject word, never a program. Skipping the
    # keyword the way a wrapper is skipped returns that variable as the
    # program -- `for f in *.py` resolves to `f`, which is in no read-only
    # set, so an audit loop over source files reads as a writer.
    if argv and argv[0] in ("for", "case", "select"):
        return None
    # `find -exec <prog>` RUNS <prog>, so the head token lies about what
    # the command does. `find` is in READ_ONLY, and the whole invocation
    # is one simple command -- the `;` terminator is escaped, so the
    # splitter never separates it -- which made
    # `find . -name '*.md' -exec sed -i ... {} ;` read as a pure reader.
    # A bulk fix across several files is an ordinary way to repair what a
    # patch script half-applied, so that verdict cleared nothing and the
    # guard kept warning after the work was genuinely done.
    for flag in ("-exec", "-execdir", "-ok", "-okdir"):
        if flag in argv:
            k = argv.index(flag) + 1
            if k < len(argv):
                return _program(argv[k:])
            return None
    i = 0
    while i < len(argv):
        tok = argv[i]
        # A leading `VAR=value` assignment is not the program.
        if "=" in tok and not tok.startswith("=") and "/" not in tok.split("=")[0]:
            i += 1
            continue
        if tok in SHELL_KEYWORDS or os.path.basename(tok) in COMMAND_WRAPPERS:
            i += 1
            # A wrapper may take its own options or operands first
            # (`timeout 5 grep`), so skip those before the real program.
            #
            # Skipping only dash-led and numeric tokens is not enough: a
            # short option can take a SEPARATE value, so `sudo -u me grep`
            # stopped at `me` and returned that as the program. `me` is in
            # no read-only set, so an audit grep for these very patterns
            # read as a writer -- the exact false positive M3 promises
            # cannot happen, on the example M3 itself uses.
            #
            # Enumerating each wrapper's option grammar would be its own
            # parser, which `scripts/lib/shellcmd.py` explicitly declines
            # to write; it looks a bounded distance ahead for the token it
            # wants instead. Same technique here, with one asymmetry that
            # keeps an unparsed grammar safe: the lookahead may only ever
            # find a READ-ONLY program. It can therefore clear a command
            # this scan would have called a writer, and can never do the
            # reverse -- so a wrapper we cannot parse still costs at worst
            # the warning it already cost, and never silences one.
            window = argv[i:i + WRAPPER_ARG_WINDOW]
            hit = next((k for k, t in enumerate(window)
                        if os.path.basename(t) in READ_ONLY), None)
            if hit is not None:
                return os.path.basename(window[hit])
            while i < len(argv) and (argv[i].startswith("-")
                                     or argv[i].isdigit()):
                i += 1
            continue
        return os.path.basename(tok)
    return None


def _text(block):
    """Flatten one content block to searchable text."""
    if isinstance(block, str):
        return block
    if not isinstance(block, dict):
        return ""
    if "text" in block and isinstance(block["text"], str):
        return block["text"]
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_text(c) for c in content)
    return ""


# A path-shaped token: something with a directory separator, or a bare name
# with a file extension. Good enough to recover the targets a patch script
# names as string literals, which is all this is for.
PATHISH = re.compile(r"[\w.-]+(?:/[\w.-]+)*\.[A-Za-z]{1,6}\b")


def _paths(command):
    """Path-shaped tokens in `command`, as a set."""
    return {m.group(0) for m in PATHISH.finditer(command or "")}


# Programs that only ANNOUNCE. A status line naming the files it believes
# were fixed is exactly what this hook's own warning text asks for, so
# counting those mentions as coverage would let the summary discharge the
# warning it was written in response to.
#
# Just the two, NOT all of READ_ONLY. Every reader was in here once, on
# the reasoning that a reader cannot have written anything -- true, and
# not what this set decides. Presence of an announcer also disables the
# heredoc fallback, so a `grep -q` PRECONDITION guarding a re-run
# (`grep -q x a.md && python3 - <<'PY' ... PY`) made a genuine multi-file
# fix recover no targets at all and read as unresolved. A reader is not
# an announcement; only a program whose whole output IS the claim is.
ANNOUNCERS = {"echo", "printf"}


def _writing_paths(command):
    """Paths named by the parts of `command` that could actually edit.

    Segments whose program only reads or prints are dropped first, so
    `echo "fixed a.md b.md c.md" | tee log` contributes `log` and not the
    three files it merely names.
    """
    if simple_commands is None:
        return _paths(command)
    argvs = simple_commands(command)
    if argvs is None:
        return _paths(command)
    out = set()
    saw_writer = False
    saw_announcer = False
    for argv in argvs:
        head = _program(argv)
        if head is None:
            continue
        if head in ANNOUNCERS:
            saw_announcer = True
            continue
        # A READER contributes nothing and is not a writer. It used to do
        # both, because READ_ONLY sat inside ANNOUNCERS; taking it out
        # left readers falling through to here, where a `grep -q a.md`
        # precondition put its own subject into `out` and the non-empty
        # `out` then blocked the fallback -- so a guarded heredoc re-run
        # recovered the grep's file and none of its own.
        if head in READ_ONLY:
            continue
        saw_writer = True
        out |= _paths(" ".join(argv))
    if saw_writer and not out and not saw_announcer:
        # A heredoc body is BLANKED by the splitter, so a
        # `python3 - <<'PY' ... PY` patch script contributes no paths at
        # segment level even though its text names every target. Falling
        # back to the whole command recovers them.
        #
        # The gate is the ABSENCE OF AN ANNOUNCER, not an empty `out`. An
        # earlier version gated on `out` alone and reasoned that
        # `echo ... | tee log` could not reach here because its `tee`
        # segment names a path. It does not: `PATHISH` requires a file
        # extension, and `log`, `/dev/null` and `build-log` have none, so
        # `out` was empty and the echoed text was recovered whole --
        # clearing the warning for files nobody touched. Any announcer in
        # the command now blocks the fallback outright.
        return _paths(command)
    return out


def _covers(later, failed):
    """True when `later` names every path-shaped token `failed` did.

    The clearing rule used to accept ANY later clean write, on the reasoning
    that the transcript does not record which edits were intended. It does,
    approximately: a patch script names its targets as string literals in its
    own text. Without this, the incident the hook exists for slips straight
    through -- the failed script names three files, the session repairs only
    the first with a narrow `sed -i`, and that single-file fix clears the
    warning for the two files nobody touched.

    Falls back to clearing when the failed command named no paths at all:
    there is then nothing to compare, and staying pending forever is the
    worse error.
    """
    want = _paths(failed)
    if not want:
        return True
    return want <= _writing_paths(later)


def _failed(block, out):
    """True when a tool_result reports failure.

    `is_error` is authoritative where the harness sets it; the text fallback
    covers shapes that do not.
    """
    if isinstance(block, dict) and block.get("is_error"):
        return True
    return TRACEBACK in out


def _command(block):
    inp = block.get("input") if isinstance(block, dict) else None
    if not isinstance(inp, dict):
        return ""
    return str(inp.get("command") or inp.get("CommandLine") or inp.get("cmd")
               or inp.get("script") or "")


def scan(path):
    """Return (traceback_cmd, traceback_index) for an unresolved partial patch.

    Walks the transcript once, tracking the most recent traceback whose own
    command wrote files, and clearing it when a later writing command runs
    clean. Returns (None, -1) when nothing is outstanding at the commit.
    """
    pending_cmd = None
    pending_at = -1
    commit_pending_id = None
    # Map a tool_use id to its command, so a tool_result can be attributed.
    cmd_by_id = {}

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")

                if btype == "tool_use":
                    cmd = _command(block)
                    if not cmd:
                        continue
                    cmd_by_id[block.get("id")] = cmd
                    # A commit CLOSES the window. Whatever was pending was
                    # that commit's problem and was warned about then, so it
                    # must not re-warn on the next one -- otherwise a single
                    # traceback follows the session for every later commit.
                    # Substring prefilter before the shlex parse. `is_commit`
                    # requires the literal word, so this cannot change the
                    # answer -- and it is what keeps a long session's repeated
                    # full-transcript walk off this hook's 10s timeout, since
                    # `simple_commands` dominated that cost at roughly 70%.
                    if "commit" in cmd and is_commit(cmd):
                        # Recorded, not cleared: the window only closes if
                        # the commit SUCCEEDS. A commit rejected by a
                        # pre-commit hook or a lint gate leaves the partial
                        # patch just as unresolved as before, and the retry
                        # is exactly where this guard is worth most (F3).
                        commit_pending_id = block.get("id")

                elif btype == "tool_result":
                    out = _text(block)
                    cmd = cmd_by_id.get(block.get("tool_use_id"), "")
                    if not cmd:
                        continue
                    if block.get("tool_use_id") == commit_pending_id:
                        commit_pending_id = None
                        if not _failed(block, out):
                            # A commit that landed closes the window.
                            pending_cmd, pending_at = None, -1
                        continue
                    if TRACEBACK in out and writes(cmd):
                        pending_cmd, pending_at = cmd, i
                    elif (pending_cmd is not None
                          and TRACEBACK not in out
                          and writes(cmd)
                          and _covers(cmd, pending_cmd)):
                        # A later writing command completed cleanly: treat the
                        # partial patch as re-applied. Weak by design -- see
                        # the module docstring's M4.
                        pending_cmd, pending_at = None, -1

    # Whatever is still pending at end-of-transcript belongs to the commit
    # now being attempted, which has not been recorded yet.
    return pending_cmd, pending_at


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name") != "Bash":
        return 0
    ti = payload.get("tool_input") or {}
    cmd = str(ti.get("command") or ti.get("CommandLine") or ti.get("cmd")
              or ti.get("script") or "")
    if not is_commit(cmd):
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    try:
        tb_cmd, tb_at = scan(path)
    except Exception:
        return 0
    if tb_cmd is None:
        return 0

    key = hashlib.sha256(f"{path}:{tb_at}".encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(),
                            f".claude-aborted-patch-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        with open(sentinel, "w") as fh:
            fh.write(str(tb_at))
    except Exception:
        pass

    snippet = tb_cmd.strip().splitlines()[0][:120]
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                "[flag-aborted-patch-script] A file-writing command in this "
                "commit's window ended in a Python traceback, and no later "
                "writing command has run clean since:\n\n"
                f"    {snippet}\n\n"
                "A traceback means the script STOPPED, not merely that it "
                "failed: every edit after the raise silently did not happen, "
                "and leaves no trace -- no error, no empty diff, no failing "
                "check. The edits that DID land look correct, which is what "
                "makes the message about to be committed feel verified.\n"
                "Before committing, confirm each intended edit is present by "
                "reading the file (grep for the new text), not by re-reading "
                "the script that was supposed to make it. If the commit "
                "message claims a set of fixes, check the set, not the one "
                "you just repaired.\n"
                "Disregard this if the traceback was from a script that "
                "changed nothing, or if every edit was re-applied since. "
                "This fires once per traceback per session."
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
