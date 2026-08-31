#!/usr/bin/env python3
"""PreToolUse guard: a branch switch and a later mutating git command, unchained.

## The incident

One Bash call carried this, on two lines:

    git checkout feat/some-branch -q && git merge --ff-only origin/feat/some-branch -q
    git merge origin/main -m "Merge branch 'main' into feat/some-branch"

The `git checkout` failed --- `fatal: 'feat/some-branch' is already checked out
at '<worktree path>'`. The `&&` protected only the command on its own line. The
SECOND line's `git merge origin/main` then ran unconditionally, against whatever
branch was actually checked out, which was `main`. Nothing errored. That time it
fast-forwarded onto an already-published commit, so nothing was lost.

In general it commits or merges onto the wrong branch, which is the failure
[`shared/workflow/incidents-dont-repeal-decisions.md`](../shared/workflow/incidents-dont-repeal-decisions.md)
records costing a commit on the wrong PR's branch --- a diff carrying a
byte-identical copy of another PR's entire change, separated only by a history
rewrite and a force-push.

## Why a hook rather than a rule

The `&&` is right there on the line, and it reads as protecting the sequence.
Nothing about the command looks wrong, and nothing after it reports a problem:
the failing `checkout` prints to stderr, the whole call still exits 0 because
the last command succeeded, and the mutation lands quietly on the wrong branch.
So there is no artifact for review, a test, or a lint to inspect --- the defect
lives in one tool call's `command` string, which is the surface none of them
read. The same reasoning that made `flag-unassigned-worktree.py` a hook applies
here.

## Why this warns rather than blocks

A multi-line git script whose later lines mutate is frequently CORRECT: the
author may know the checkout cannot fail, or may have run it already, or may
intend the mutation on the current branch regardless. Whether the sequence is
safe depends on intent, which is not observable from the command --- so a
blocking guard would refuse a large class of legitimate scripts, and per
README's "A hook that misfires is worse than a missing one" it would be worked
around rather than heeded.

So this only ever ADDS context. It emits `additionalContext` and a
`systemMessage` and nothing else; there is no code path that denies, escalates,
or auto-approves. In particular it never emits `permissionDecision: "allow"`,
which would BYPASS the normal permission prompt and leave the harness more
permissive than it was without the hook.

## The match condition

All of these must hold, and each is mutation-tested separately in
`test-flag-unchained-branch-switch.py`:

  C1  the tool is `Bash` and `tool_input.command` is a non-empty string
  C2  a SWITCHING git command sits at a command position
  C2a `git checkout` counts as switching only when its arguments carry no
      `--` separator; `git checkout -- <path>` is a file restore, not a switch
  C3  a MUTATING git command sits at a command position AFTER that switch
  C4  the separators between them are not all `&&`
  C5  heredoc bodies are removed before any of the above
  C6  quoted spans are removed, and a git invocation counts only at a command
      position, so a `grep`/`echo`/comment that merely MENTIONS one is inert
  C7  a newline directly after `&&`, `||`, or `|` is not a separator, because
      bash continues the list onto the next line there
  C8  a switch used as a conditional TEST (`if git checkout ...; then`) is
      already checked before anything depends on it, so it opens no hazard for
      a mutation INSIDE the block it governs
  C8b that exemption stops at the closing `fi`/`done`. For a mutation OUTSIDE
      the block, the same conditional switch is an ordinary unchained switch
  C9  only the NEAREST preceding switch is weighed, since a later switch
      supersedes an earlier one

C4 is stated over separators rather than over line numbers on purpose. A
newline is one such separator, which is the incident; `;` is another, and
`git checkout foo; git merge main` is the identical hazard written on one line.

C8b exists because the first version of C8 did not have it, and the gap was
found in review. C8 removed a guarded switch from consideration entirely, so
this went silent:

    if git checkout main 2>/dev/null; then git pull; fi
    git merge --no-ff feature-branch

The exemption is right inside the block and wrong after it. Note the sharp
edge, which is why the false negative mattered more than its rarity suggests:
wrapping a checkout in `if` is a MORE likely pattern after an incident like
this one, so the un-scoped C8 silenced the hook precisely where someone was
being careful.


Fails OPEN on any parse trouble. A guard that breaks every Bash call when its
input is malformed costs more than the omission it reports.
"""
import json
import re
import sys

# Subcommands that write to the repository: a wrong branch under any of these
# leaves a commit, a merge, or a published ref behind.
MUTATING = {
    "merge", "commit", "rebase", "push", "reset", "cherry-pick", "am",
}

# `git` global options that consume the NEXT token, so the subcommand is not
# simply the token after them.
GLOBAL_OPTS_WITH_ARG = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
}

# Words that can precede a real command without changing which command it is.
# `!` is here rather than below on purpose: it inverts an exit status without
# making the command conditional, so `! git checkout foo` still switches.
LEAD_WORDS = {
    "then", "do", "else", "!",
    "time", "sudo", "command", "exec", "nohup", "env",
}

# Words that turn the command after them into a TEST rather than an action.
# `if git checkout foo; then git merge ...; fi` is genuinely guarded, so the
# switch there does not open the hazard -- warning on it would be the misfire
# README calls worse than a missing hook.
CONDITION_WORDS = {"if", "elif", "while", "until"}

# Compound-command boundaries. The guard a conditional switch provides reaches
# exactly as far as the block it governs, so the block has to be tracked; see
# C8b in the module docstring for what goes wrong without it.
OPENERS = {"if", "while", "until", "for"}
CLOSERS = {"fi", "done"}

# Returned in place of an index when the nearest switch is a conditional test
# whose block ENCLOSES the mutation: the mutation runs only if that switch
# succeeded, so there is nothing to warn about.
PROTECTED = object()

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# `<<TAG` / `<<-TAG` / `<<'TAG'`, but never `<<<` (a herestring, which has no
# body to strip).
HEREDOC = re.compile(r"(?<!<)<<(?P<dash>-?)\s*(?P<q>['\"]?)"
                     r"(?P<tag>[A-Za-z_][A-Za-z0-9_]*)(?P=q)(?!<)")

CONTINUING = ("&&", "||", "|")

NOTE = (
    "This Bash call switches branches and then runs a mutating git command "
    "that is NOT chained to it.\n\n"
    "  switch:   {switch}\n"
    "  mutation: {mutation}\n\n"
    "`&&` binds only within its own list. A `git checkout` on one line and a "
    "`git merge`/`git commit` on the next are two separate commands, so the "
    "mutation runs even when the checkout fails -- against whatever branch is "
    "actually checked out. A checkout can fail for ordinary reasons: the "
    "branch is already checked out in another worktree, the name is wrong, the "
    "tree is dirty.\n\n"
    "Nothing reports this. The failing checkout writes to stderr, the call "
    "still exits 0 because the last command succeeded, and the mutation lands "
    "quietly on the wrong branch.\n\n"
    "Either chain the whole sequence with `&&` (a trailing `&&` or a `\\` "
    "continuation both work across lines), or confirm the switch landed before "
    "the mutation runs. If the mutation is meant to run on the current branch "
    "regardless, say so -- that is a fine answer, and it is not what an "
    "unchained sequence expresses."
)


def _strip_heredocs(command):
    """C5: drop heredoc bodies, so a documented command is not a real one."""
    lines = command.split("\n")
    kept = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        i += 1
        match = HEREDOC.search(line)
        if not match:
            continue
        tag = match.group("tag")
        dash = match.group("dash")
        while i < len(lines):
            probe = lines[i].strip() if dash else lines[i].rstrip()
            i += 1
            if probe == tag:
                break
    return "\n".join(kept)


def _segments(script):
    """Split into (command_text, separators_before_it) at command positions.

    C6 lives here: quoted spans and comments are dropped, so text that merely
    mentions a git command never reaches the classifier. C7 lives here too.
    """
    segments = []
    current = []
    separators = []
    i = 0
    n = len(script)

    def flush():
        text = "".join(current).strip()
        del current[:]
        if text:
            segments.append((text, list(separators)))
            del separators[:]

    def push_separator(sep):
        # C7: bash continues the list across a newline that follows `&&`, `||`,
        # or `|`, so that newline separates nothing.
        if sep == "\n" and separators and separators[-1] in CONTINUING:
            return
        separators.append(sep)

    while i < n:
        char = script[i]

        if char == "\\" and i + 1 < n:
            # A line continuation joins the lines; any other escape hides
            # whatever follows from separator detection.
            current.append(" ")
            i += 2
            continue

        if char == "'":
            end = script.find("'", i + 1)
            i = n if end == -1 else end + 1
            current.append(" ")
            continue

        if char == '"':
            j = i + 1
            while j < n:
                if script[j] == "\\":
                    j += 2
                    continue
                if script[j] == '"':
                    break
                j += 1
            i = n if j >= n else j + 1
            current.append(" ")
            continue

        if char == "#" and not "".join(current).strip():
            while i < n and script[i] != "\n":
                i += 1
            continue

        if script[i:i + 2] in ("&&", "||", ";;"):
            pair = script[i:i + 2]
            flush()
            push_separator(pair)
            i += 2
            continue

        if char in ";|&\n(){}":
            flush()
            push_separator("\n" if char == "\n" else char)
            i += 1
            continue

        current.append(char)
        i += 1

    flush()
    return segments


def _subcommand(text):
    """The git subcommand this segment invokes, its arguments, and whether it
    sits in a conditional test rather than running unconditionally."""
    tokens = text.split()
    guarded = False
    while tokens and (tokens[0] in LEAD_WORDS
                      or tokens[0] in CONDITION_WORDS
                      or ASSIGNMENT.match(tokens[0])):
        # C8
        if tokens[0] in CONDITION_WORDS:
            guarded = True
        tokens.pop(0)
    if not tokens or tokens[0] != "git":
        return None, [], guarded
    i = 1
    while i < len(tokens) and tokens[i].startswith("-"):
        i += 2 if tokens[i] in GLOBAL_OPTS_WITH_ARG else 1
    if i >= len(tokens):
        return None, [], guarded
    return tokens[i], tokens[i + 1:], guarded


def _classify(text):
    """("switch" | "mutate" | None, whether it sits in a conditional test)."""
    subcommand, args, guarded = _subcommand(text)
    if subcommand is None:
        return None, guarded
    if subcommand == "switch":
        return "switch", guarded
    if subcommand == "checkout":
        # C2a: `git checkout -- <path>` (or `git checkout <ref> -- <path>`)
        # restores files and never moves HEAD.
        if "--" in args:
            return None, guarded
        return "switch", guarded
    if subcommand in MUTATING:
        # A MUTATION inside a test still mutates, so `guarded` never exempts one.
        return "mutate", guarded
    return None, guarded


def _records(segments):
    """Annotate each segment with the conditional blocks enclosing it.

    Returns (kind, separators_before, guard_block, scope, text) per segment.
    `scope` is the tuple of block ids enclosing that segment; `guard_block` is
    the block a conditional switch GOVERNS, and is None for every other segment.
    """
    out = []
    stack = []
    blocks = 0
    for text, seps in segments:
        tokens = text.split()
        first = tokens[0] if tokens else ""

        if first in CLOSERS and stack:
            stack.pop()
        scope = tuple(stack)

        opened = None
        if first in OPENERS:
            blocks += 1
            opened = blocks
            stack.append(opened)

        kind, guarded = _classify(text)
        guard_block = None
        if guarded and kind == "switch":
            # `if`/`while`/`until` govern the block they open; `elif` continues
            # the block already open around it.
            guard_block = opened if opened is not None else (
                scope[-1] if scope else None)

        out.append((kind, seps, guard_block, scope, text))
    return out


def _separators_between(records, i, j):
    """Every separator crossed going from segment i to segment j."""
    low, high = (i, j) if i < j else (j, i)
    crossed = []
    for k in range(low + 1, high + 1):
        crossed.extend(records[k][1])
    return crossed


def _nearest_switch(records, j):
    """The switch that decides which branch segment j runs on.

    C3: only a switch BEFORE the mutation can decide its branch.
    C9: only the NEAREST one. A later switch supersedes an earlier one, so in
        `git checkout a && git merge x` / `git checkout b && git merge y` the
        second merge's branch is set by the second checkout, which is chained
        to it -- warning there on the strength of the FIRST checkout would
        misfire on an ordinary cascade.
    C8: a conditional switch whose block ENCLOSES j protects it -- the mutation
        runs only if that switch succeeded. Returns PROTECTED.
    C8b: the same conditional switch is an ORDINARY unchained switch for a
        mutation OUTSIDE its block. Once `fi` closes, whether the switch
        happened is exactly the open question, so an unconditional mutation
        after it is the original incident wearing a defensive wrapper.
    """
    scope_j = records[j][3]
    for i in range(j - 1, -1, -1):
        if records[i][0] != "switch":
            continue
        guard_block = records[i][2]
        if guard_block is not None and guard_block in scope_j:
            return PROTECTED
        return i
    return None


def unchained(payload):
    """Return (switch_text, mutation_text) to warn about, or None."""
    # C1
    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        return None

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None

    command = tool_input.get("command") or tool_input.get("CommandLine") or tool_input.get("cmd") or tool_input.get("script")
    if not isinstance(command, str) or not command.strip():
        return None

    records = _records(_segments(_strip_heredocs(command)))

    for j, record in enumerate(records):
        if record[0] != "mutate":
            continue
        # C2 (with C2a inside _classify), C3, C9, C8, C8b
        i = _nearest_switch(records, j)
        if i is None or i is PROTECTED:
            continue
        # C4
        if any(sep != "&&" for sep in _separators_between(records, i, j)):
            return records[i][4], records[j][4]
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # fail open, but say so
        print(f"flag-unchained-branch-switch: unreadable hook input ({exc})",
              file=sys.stderr)
        return 0

    if not isinstance(payload, dict):
        print("flag-unchained-branch-switch: hook input was not an object",
              file=sys.stderr)
        return 0

    try:
        found = unchained(payload)
    except Exception as exc:  # fail open on any parse trouble
        print(f"flag-unchained-branch-switch: could not parse command ({exc})",
              file=sys.stderr)
        return 0

    if found is None:
        return 0

    switch, mutation = found

    # No `permissionDecision` key at all: an absent decision defers to the
    # normal permission flow, which is exactly the intent. Naming "allow" here
    # would suppress a prompt the user would otherwise have seen.
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(switch=switch, mutation=mutation),
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            "Unchained branch switch: `{switch}` is not joined by `&&` to the "
            "later `{mutation}`, which runs even if the switch fails."
        ).format(switch=switch, mutation=mutation)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
