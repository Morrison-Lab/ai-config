#!/usr/bin/env python3
"""PreToolUse reminder: a diff range whose base is a bare local ref.

`shared/workflow/verify-the-right-artifact.md`'s "A comparison's base is an
artifact too" says to resolve a review diff's base from a *remote-tracking*
ref after fetching that remote.
`shared/workflow/adversarial-self-review.md` names the same thing at the point
of dispatch: `<base>` in "hand over `git diff <base>...HEAD`" is a claim, not a
label.

WHAT HAPPENED
-------------
Measured 2026-09-02 while reviewing ucdavis/matt.contracts#98.
The PR head was fetched as a local branch `pr-98`, and an adversarial reviewer
was dispatched against `git diff main...pr-98` using the worktree's local
`main`, 128 commits behind the remote --- `git rev-list --count
43d59cc..7ec49fe`, or 28 with `--first-parent`, and 0 ahead by the reversed
range:

    base                     files  insertions
    stale local `main`          53        2999
    true merge-base 6345e92     14        1584

The 39 extra files were already-merged work from other pull requests.
Every finding the reviewer returned was individually well-formed and quoted a
real line; the scope was wrong and nothing in the output said so.

WHY THIS IS MECHANIZABLE
------------------------
The rule is not "was the local ref fresh", which no hook can know.
The rule is "name a remote-tracking ref", which is lexical: a base token
carrying no remote prefix is a local branch name, and that is the whole
condition.
A base that is strictly BEHIND its remote moves the merge-base earlier, so the
diff grows and the review returns confident false findings about already-merged
work. A base carrying local commits the remote lacks --- ahead, or diverged ---
where the head branch also carries them, moves the merge-base later, so the diff
shrinks and part of the change is silently never reviewed. The second is the
worse of the two: an over-wide diff produces findings the author will dispute,
while an under-wide one produces a clean verdict nobody questions.

WHY WARN RATHER THAN BLOCK
--------------------------
Deliberate, and the asymmetry is one-sided.
The hook cannot tell a review diff from an ordinary local comparison, and a
bare local base is entirely correct for plenty of them --- inspecting your own
work in progress, comparing two feature branches you just built.
Blocking those would refuse a correct command on a heuristic.
A missed reminder costs a review round; a false block costs every local `git
diff` with a range in it.
So this only ever adds context.

It also fires on `Agent`, `Task` and `SendMessage` prompts, because the measured failure was a
brief handed to a subagent rather than a command run directly, and the
recipient cannot check a premise about the author's own environment.

There is deliberately no session-level discharge. An earlier `git fetch` was
the obvious candidate and is worthless here: `keep-checkouts-fresh.md` mandates
a fetch at session start, which is exactly the reading that had already expired
in the measured case, so keying on one would silence the hook on its own
motivating incident.

Fails open everywhere: an unreadable payload, an unreadable git checkout, or
any unexpected exception returns 0 silently.
"""

import json
import os
import re
import subprocess
import sys

# A git range: <base>..<head> or <base>...<head>.
# `.` is inside the class because it is legal in a ref name, which means this
# pattern DOES match documentation placeholders: `origin/<default-branch>...HEAD`
# matches with base `.`, since `>` is outside the class and the separator dots
# are all that is left. `is_local_branch_base` rejects that, not this pattern.
RX_RANGE = re.compile(
    r"(?<![A-Za-z0-9._/@^~-])"
    r"([A-Za-z0-9._/@^~-]+)"
    r"(\.\.\.?)"
    r"([A-Za-z0-9._/@^~-]+)"
)

# Only these subcommands take a range whose base is a review scope. `git
# rebase`, `git merge`, and friends are excluded on purpose.
# The option repetition is BOUNDED. Unbounded, the optional value group makes
# each token ambiguous --- consumable as `option value` or as two options --- so
# an outer `*` admits 2^N parses whenever the overall match fails: measured
# 8.4s at 34 tokens, growing ~2.7x per token, against a 10s timeout. Requiring
# `=` would remove the ambiguity but break `git -C <path> diff`, which this
# hook needs. The cutoff costs a missed reminder past 13 `-c k=v` options (or
# 25 bare flags, since one repetition can swallow two tokens), and a missed
# reminder is the cheaper side of this trade.
_GIT_RANGE_CMD = (
    r"git\b(?:\s+-[-A-Za-z0-9]+(?:[= ](?:'[^']*'|\"[^\"]*\"|\S+))?){0,12}\s+"
    r"(diff|log|shortlog|merge-base|rev-list|range-diff)\b"
)

# On a shell command line, require the invocation to sit at a COMMAND position:
# the start of the string, or after a separator or an opening paren. That is
# what distinguishes a command git will run from one quoted inside another
# command's argument --- `git commit -m "...git diff main...HEAD"`,
# `grep -rn 'git diff main...pr-98'`, `gh pr comment --body "..."`.
#
# Stripping quoted spans instead would be wrong in both directions: it silences
# `git diff "main...pr-98"`, which git really does run, and it mangles ordinary
# English, where an apostrophe in "the branch's diff" opens a span that swallows
# everything up to the next contraction.
# `(` is deliberately NOT in the separator class. A bare parenthesis occurs
# inside quoted prose constantly --- `gh pr comment --body "the base was local
# (git diff main...pr-98), so the scope grew"` is the very comment a session
# writes when reporting this rule --- and admitting it would re-arm the pattern
# inside the strings the anchor exists to exclude. `$(` is admitted explicitly,
# since a command substitution really is a command position.
#
# The same reasoning excludes a bare backtick and a bare `then`/`do`. A
# backtick code span is how this corpus writes a command inside a comment body,
# and "fetch first, then git diff main...pr-98" is ordinary English --- so
# admitting either re-arms the pattern inside exactly the strings this anchor
# exists to exclude. The loop keywords are recognized only where a shell would
# treat them as such, immediately after a separator.
#
# This anchor UNDER-approximates on purpose. `bash -c "git diff main...HEAD"`,
# a backtick substitution, and any wrapper word outside the list below stay
# silent. A missed reminder costs a review round; a reminder fired on quoted
# prose trains everyone to ignore it, which is the failure README calls worse
# than a missing hook.
RX_GIT_RANGE_CMD_SHELL = re.compile(
    r"(?:\A|[\n;|&]|&&|\|\||\$\()\s*(?:(?:then|do)\s+)?"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"(?:(?:sudo|env|time|nohup|xargs|command)\s+"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*)*"
    + _GIT_RANGE_CMD
)

# A brief is prose, not a shell line, so the invocation is quoted or inline by
# construction and no command position exists to anchor to.
RX_GIT_RANGE_CMD_PROSE = re.compile(r"(?<![A-Za-z0-9-])" + _GIT_RANGE_CMD)

# Refs that are not local branch names, so cannot be the failure this catches.
# Remote names to fall back on when `git remote` cannot be read. A local branch
# may contain `/` too --- `feature/foo`, `release/2.0`, this repo's own
# `ums/...` and `fix/...` --- so a slash alone says nothing, and treating it as
# a remote prefix is what would blind the hook to a stacked-PR base.
FALLBACK_REMOTES = frozenset({
    "origin", "upstream", "github", "gitlab", "fork", "downstream",
})

SYMBOLIC = {
    "HEAD", "@", "FETCH_HEAD", "ORIG_HEAD", "MERGE_HEAD", "CHERRY_PICK_HEAD",
    "REVERT_HEAD", "BISECT_HEAD", "AUTO_MERGE",
}

RX_SHA = re.compile(r"\A[0-9a-f]{7,40}\Z")
# Options taking a SEPARATE argument, whose value must not be read as a ref:
# `git log --grep main...HEAD` searches for a pattern, it does not take a
# range. Membership is by real git behaviour, not by shape --- `-L` and `-O`
# genuinely require a separate value, while `-C` (find-copies) never takes one,
# and listing `-C` here ate the real range of `git diff -C main...HEAD`.
VALUE_OPTIONS = frozenset({
    "--grep", "--author", "--committer", "--since", "--until", "--before",
    "--after", "--format", "--pretty", "--output", "-S", "-G", "-L",
    "-O", "--git-dir", "--work-tree",
})

# A tag is immutable, so it cannot go stale the way a branch does. But a tag
# and a branch are lexically indistinguishable, so this exempts only the two
# unambiguous forms: a `v`-prefixed dotted version (`v1.2`, `v1.2.0`), and an
# unprefixed one of at least three components (`1.2.0`). Both may carry a
# pre-release suffix or build metadata.
#
# A bare two-component name is NOT exempt: `3.11` and `2.0` are the standard
# maintenance-branch convention (CPython's live branches are literally `3.11`,
# `3.12`, `3.13`), so exempting them would take the missed base over the false
# positive, which is the opposite of the policy below.
#
# Deliberately NOT exempted: a bare integer or integer-dash form. `123-fix`,
# `2261-ums`, and `2026-08-01` are all far likelier to be branches --- issue
# numbers are the commonest branch prefix in this corpus --- and a warn-only
# reminder should take the false positive over the missed base.
# The suffix is a recognized pre-release or build-metadata form, not any word:
# a bare `-[0-9A-Za-z]+` exempted `v2-rewrite` and `v3-api`, which are feature
# branches. A dot is required throughout, so a bare `v1` warns too.
RX_TAG = re.compile(r"\A(?:[vV]\d+(?:\.\d+)+|\d+(?:\.\d+){2,})"
                    r"(?:-(?:rc|alpha|beta|pre|dev|snapshot)[0-9.]*)?"
                    r"(?:\+[0-9A-Za-z][0-9A-Za-z.]*)?\Z")
# `[^\n]*` after the delimiter is load-bearing: `cat <<'EOF' > f.md` puts a
# redirection between the delimiter and the newline, and a pattern anchored
# straight to `\n` misses exactly the form used to write a file.
RX_HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n.*?^\s*\2\s*$",
    re.DOTALL | re.MULTILINE,
)

# Tool names whose free-text payload is a brief that may carry the command.
BRIEF_TOOLS = {"Agent", "Task", "SendMessage"}
BRIEF_KEYS = ("prompt", "message", "description", "summary")

SUMMARY = ("warn-stale-review-diff-base: diff base {bases} is a bare local "
           "branch. Resolve it from a remote-tracking ref after a fetch, and "
           "cross-check the counts against `gh pr view --json changedFiles`.")

NOTE = """\
A diff range in this call names a bare local branch as its base: {bases}

`verify-the-right-artifact.md`'s "A comparison's base is an artifact too"
covers why that is a claim rather than a label. A local branch is a cached copy
of a remote one, so both range forms inherit whatever revision it is parked at:
`A..B` reads the base you named, and `A...B` computes a merge-base FROM the
base you named, which is what makes the three-dot form feel self-correcting
when it is not.

A base that is BEHIND its remote widens the diff, so a review runs on
already-merged work by other people and returns findings against code this
branch never touched. A base carrying local commits the remote lacks --- ahead,
or diverged --- where the head branch also carries them, narrows it, so part of
the change is never reviewed at all and the verdict comes back clean. Neither
is announced: a 53-file diff and a 14-file diff look equally plausible, and
every finding either produces is individually well-formed.

Resolve the base from a remote-tracking ref, after fetching that remote:

    git -C <repo> fetch -q <remote>
    BASE=$(git -C <repo> merge-base <remote>/<default-branch> <head-ref>)
    git -C <repo> diff --shortstat "$BASE" <head-ref>
    gh pr view <N> --json changedFiles,additions,deletions

The last two readings must agree. A mismatch means one of the two refs is
wrong -- re-fetch the head before concluding it was the base.
Resolve the default branch from the repo rather than assuming `main`, and note
the remote is not always `origin`.

If the base is deliberately local -- comparing two branches you just built, or
inspecting your own work in progress -- carry on. This is a reminder, not a
refusal, and it does not know which kind of comparison this is.
"""


def quote_state_map(body):
    """Per-offset quote state for `body`, computed in a single pass.

    Why quote state is tracked at all: the separator class admits a newline,
    because a multi-line shell script's second line really is a command
    position. But a newline also occurs inside a quoted argument --- a
    `gh pr comment --body` or `git commit -m` body of more than one line ---
    and there the anchor would re-arm inside exactly the string it exists to
    exclude. Dropping the newline from the class instead would blind the hook
    to every multi-line script, so the state is tracked rather than the
    separator narrowed. This subsumes the special cases the anchor was patched
    for one at a time: `(`, a backtick, and the words `then` and `do` were each
    excluded because each occurs inside quoted prose, and asking whether an
    offset is quoted answers that question directly.

    Why one pass: a per-match rescan from index 0 would be quadratic. A 44 KB
    command carrying 2000 ranges took 11.7 s against the 10 s timeout
    `hooks.json` declares. One pass makes it linear, and the per-match lookup
    an index.
    """
    states = [False] * (len(body) + 1)
    single = double = False
    i = 0
    while i < len(body):
        states[i] = single or double
        ch = body[i]
        if ch == "\\" and not single:
            states[min(i + 1, len(body))] = single or double
            i += 2
            continue
        if ch == "'" and not double:
            single = not single
        elif ch == '"' and not single:
            double = not double
        i += 1
    states[len(body)] = single or double
    return states


def strip_heredocs(command):
    """Drop heredoc bodies, so writing a file about this rule does not trip it."""
    if not isinstance(command, str):
        return ""
    return RX_HEREDOC.sub("<<HEREDOC", command)


def remote_names(cwd):
    """Remote names for `cwd`, falling back to a small set on any failure."""
    # No `os.path.isdir` pre-check: `subprocess.run` on a missing cwd raises
    # `FileNotFoundError`, an `OSError`, which the handler below already answers
    # with the same fallback. A guard whose deletion changes no behaviour is one
    # the suite cannot pin, so it is not written.
    #
    # `cwd=None` is never passed: that would run `git remote` wherever the hook
    # process happens to sit and report a third repository's remotes as this
    # one's.
    try:
        proc = subprocess.run(
            ["git", "remote"], cwd=cwd or os.curdir,
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return FALLBACK_REMOTES
    if proc.returncode != 0:
        return FALLBACK_REMOTES
    names = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    # Not unioned with the fallback: doing that would exempt a LOCAL branch
    # named `upstream/foo` in every repository, including ones with no
    # `upstream` remote. The fallback is for when the real list is unavailable.
    return names or FALLBACK_REMOTES


def normalize_base(token):
    """Trim the separator dots the range pattern leaves on a greedy base.

    `.` is a legal character in a ref name, so the base group is greedy over
    it and `a...b` backtracks to base `a.` rather than to base `a`. Left as
    is, `6345e92.` fails the SHA test and `v1.2.0.` fails the tag test, so
    both would warn --- the two cases most obviously exempt.
    """
    if not isinstance(token, str):
        return ""
    return token.strip(".")


def local_branch_stem(token):
    """The plain branch name a local-ref spelling denotes.

    `refs/heads/main` -> `main`; `main~2` and `main^` -> `main`. The file
    already knows both normalizations --- `is_local_branch_base` treats a
    `refs/heads/` prefix as proof of a local branch and splits on `[~^@]` ---
    so any comparison against a base has to apply them too, or the
    fully-qualified spelling of an exempt idiom warns.
    """
    token = normalize_base(token)
    if token.startswith("refs/heads/"):
        token = token[len("refs/heads/"):]
    return re.split(r"[~^@]", token, maxsplit=1)[0]


def remote_prefix(token, remotes):
    """The remote whose name prefixes `token`, longest first, or None.

    Git permits a `/` in a remote name, so testing only the first segment
    misreads `my/remote/main` as a local branch called `my`.
    """
    for name in sorted(remotes, key=len, reverse=True):
        if token.startswith(name + "/"):
            return name
    return None


def remote_tracking_branch(token, remotes):
    """The branch part of a remote-tracking ref, or None.

    `origin/main` -> `main`; `refs/remotes/origin/main` -> `main`; a local
    branch, a tag or a SHA -> None.
    """
    token = normalize_base(token)
    if not token:
        return None
    if token.startswith("refs/remotes/"):
        rest = token[len("refs/remotes/"):]
        name = remote_prefix(rest, remotes)
        if name:
            return rest[len(name) + 1:]
        return rest.split("/", 1)[1] if "/" in rest else None
    name = remote_prefix(token, remotes)
    return token[len(name) + 1:] if name else None


def is_local_branch_base(token, remotes):
    """True when `token` looks like a bare local branch name.

    A remote-tracking ref is `<remote>/<branch>` for a remote this repository
    actually has, or an explicit `refs/remotes/...`. A slash on its own proves
    nothing: `feature/foo` and `release/2.0` are local.

    A symbolic ref, a raw SHA, and a version tag each name something a fetch
    cannot make staler.
    """
    token = normalize_base(token)
    if not token:
        return False
    # A run of dots is the separator itself, reached when the text before it
    # ends in a character the ref class excludes. `.` normalizes to empty and
    # is caught above; `-...HEAD` reaches here. Neither names a ref.
    if not re.search(r"[A-Za-z0-9]", token):
        return False
    if token.startswith("refs/remotes/"):
        return False
    if token.startswith("refs/heads/"):
        # The prefix is unambiguous proof this is a local branch, so return
        # before the tag test: `refs/heads/v1.2.0` is a branch, not a tag.
        return True
    if "/" in token and remote_prefix(token, remotes):
        return False
    # Strip revision suffixes: `main~2`, `main^`, `main@{u}`.
    stem = re.split(r"[~^@]", token, maxsplit=1)[0]
    if not stem or stem in SYMBOLIC:
        return False
    if RX_SHA.match(stem) or RX_TAG.match(stem):
        return False
    return True


RX_DASH_C = re.compile(r"(?<![A-Za-z0-9-])git\s+-C\s+('[^']*'|\"[^\"]*\"|\S+)")


def target_repo(command, session_cwd):
    """The repository a `git -C <path> ...` command names, or None.

    Without this, a `git -C /other/repo diff feature/x...HEAD` is classified
    against the SESSION's remote list rather than that repository's --- which
    is this fragment's own substitution, committed by its own instrument.

    Returns None rather than a fallback so the caller can distinguish "this
    text names a repository" from "it does not", which the two call sites
    answer differently.

    `--git-dir=` is NOT handled: it names a git directory rather than a working
    tree, so recovering the repository from it is a second lookup. Such a
    command is classified against the session repository, which is the
    unresolved half of this function.
    """
    if not isinstance(command, str):
        return None
    match = RX_DASH_C.search(command)
    if not match:
        return None
    path = os.path.expanduser(match.group(1).strip("'\""))
    if not os.path.isabs(path):
        # Relative to the SESSION's cwd, not to wherever the hook process
        # happens to sit --- resolving it against the latter would classify
        # the base against a third repository.
        path = os.path.join(session_cwd or os.curdir, path)
    return path if os.path.isdir(path) else None


def stale_bases(text, remotes, pattern, quote_aware=False):
    """Return the bare-local-branch bases of any git range in `text`."""
    if not isinstance(text, str) or not text:
        return []
    body = strip_heredocs(text)
    states = quote_state_map(body) if quote_aware else None
    found = []
    for match in pattern.finditer(body):
        if states is not None and states[min(match.start(), len(body))]:
            continue
        # Only this command's own arguments, up to a separator.
        tail = re.split(r"[\n;|&]", body[match.end():], maxsplit=1)[0]
        skip_next = False
        for token in tail.split():
            # `--` ends the ref arguments; everything after it is a pathspec.
            if token == "--":
                break
            # An option is not a ref, and neither is the value of one that
            # takes a separate argument --- `git log --grep main...HEAD`
            # searches for a pattern, it does not read a range.
            if token.startswith("-"):
                skip_next = token in VALUE_OPTIONS
                continue
            if skip_next:
                skip_next = False
                continue
            for rng in RX_RANGE.finditer(token):
                base, _dots, head = rng.groups()
                # A shell expansion is not a ref name. `$BASE...HEAD` matches
                # with base `BASE` because `$` is outside the ref class, and
                # warning there would fire on the NOTE's own recommended
                # remediation. The quoted and braced spellings already miss.
                start = rng.start(1)
                if start and token[start - 1] in "${":
                    continue
                if not is_local_branch_base(base, remotes):
                    continue
                # `main..origin/main` measures THAT branch's staleness --- the
                # idiom `post-merge` prescribes --- rather than claiming a
                # review scope, so naming a remote-tracking base would defeat
                # the measurement. The exemption has to be this narrow: it is
                # only safe when the head names the SAME branch as the base.
                # `main...origin/feature` is an ordinary review diff, and its
                # remote-tracking head says nothing about the base's freshness
                # --- exempting it would blind the hook to this incident's own
                # shape, one fetch removed.
                if remote_tracking_branch(head, remotes) == local_branch_stem(base):
                    continue
                base = normalize_base(base)
                if base not in found:
                    found.append(base)
    return found


def _emit(note, summary):
    """Emit both channels.

    `additionalContext` reaches the model; `systemMessage` reaches the user's
    terminal. This hook exists to correct a premise the AUTHOR asserted, so
    the human-visible channel is the one that closes the loop.

    `check-hook-output-shape.py` does not require it here: its emit rule is
    scoped to `Stop` hooks, and its PreToolUse rule governs the test rather
    than the hook. So the convention is the reason, and it is derivable ---
    of the 16 `warn-`/`flag-`/`remind-` hooks registered under PreToolUse
    besides this one, 14 emit `systemMessage` (measured 2026-09-02; the two
    that do not are `warn-pr-create-without-dupe-check.py` and
    `flag-cd-into-main-checkout.py`).
    """
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        },
        "systemMessage": summary,
    }))


def _read_payload():
    """Parse the payload from argv (--dry-run) or stdin."""
    args = sys.argv[1:]
    if "--dry-run" in args or "--simulate" in args:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw = positional[0].strip()
            if raw.startswith("{") and raw.endswith("}"):
                try:
                    return json.loads(raw)
                except ValueError:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw}}
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # noqa: BLE001 --- fail open, but say why
        print(f"warn-stale-review-diff-base: unreadable hook input ({exc})",
              file=sys.stderr)
        return {}
    return payload if isinstance(payload, dict) else {}


def main():
    payload = _read_payload()
    if not payload:
        return 0

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    try:
        if tool_name == "Bash":
            texts = [tool_input.get("command")]
            pattern = RX_GIT_RANGE_CMD_SHELL
        elif tool_name in BRIEF_TOOLS:
            texts = [tool_input.get(k) for k in BRIEF_KEYS]
            pattern = RX_GIT_RANGE_CMD_PROSE
        else:
            return 0

        if not any(isinstance(t, str) and ".." in t for t in texts):
            return 0

        cwd = payload.get("cwd") or os.getcwd()
        source = tool_input.get("command") if tool_name == "Bash" else " ".join(
            t for t in texts if isinstance(t, str))
        resolved = target_repo(source, cwd)
        remotes = remote_names(resolved or cwd)
        if tool_name in BRIEF_TOOLS and resolved is None:
            # A brief routinely describes ANOTHER repository, and nothing in it
            # says which. Classifying `github/main` or `hc2-gitlab/main`
            # against the session's remote list would warn on a correct
            # remote-tracking base --- on the measured incident's own fix, since
            # `github/main` is the right answer there and this repository has no
            # `github` remote. So a brief that names no `-C` path is judged
            # permissively, accepting the extra false negatives.
            remotes = remotes | FALLBACK_REMOTES

        bases = []
        quote_aware = tool_name == "Bash"
        for text in texts:
            for base in stale_bases(text, remotes, pattern, quote_aware):
                if base not in bases:
                    bases.append(base)
        if not bases:
            return 0

        named = ", ".join("`%s`" % b for b in bases)
        _emit(NOTE.format(bases=named), SUMMARY.format(bases=named))
    except Exception as exc:  # noqa: BLE001 --- a reminder must never break a tool
        print(f"warn-stale-review-diff-base: could not evaluate ({exc})",
              file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
