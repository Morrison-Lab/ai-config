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
`main`, two commits behind the remote:

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
A stale base can only move the merge-base earlier, so the error is
single-signed --- the diff only ever grows --- which is why an over-wide scope
produces confident false findings rather than an obvious failure.

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

It also fires on `Agent`/`Task` prompts, because the measured failure was a
brief handed to a subagent rather than a command run directly, and the
recipient cannot check a premise about the author's own environment.

Fails open everywhere: an unreadable payload, an unreadable transcript, or any
unexpected exception returns 0 silently.
"""

import json
import os
import re
import sys

# A git range: <base>..<head> or <base>...<head>. The character class
# deliberately excludes `<` and `>` so documentation placeholders such as
# `origin/<default-branch>...HEAD` cannot match.
RX_RANGE = re.compile(
    r"(?<![A-Za-z0-9._/@^~-])"
    r"([A-Za-z0-9._/@^~-]+)"
    r"(\.\.\.?)"
    r"([A-Za-z0-9._/@^~-]+)"
)

# Only these subcommands take a range whose base is a review scope. `git
# rebase`, `git merge`, and friends are excluded on purpose.
RX_GIT_RANGE_CMD = re.compile(
    r"(?<![A-Za-z0-9-])git\b(?:\s+-[-A-Za-z0-9]+(?:[= ]\S+)?)*\s+"
    r"(diff|log|shortlog|merge-base|rev-list|range-diff)\b"
)

# A fetch anywhere earlier in the session discharges the reminder: the session
# has already demonstrated it is thinking about ref freshness.
RX_DISCHARGE = re.compile(
    r"(?<![A-Za-z0-9-])git\b[^\n;|&]*\b(fetch|ls-remote|remote\s+update)\b"
)

# Refs that are not local branch names, so cannot be the failure this catches.
SYMBOLIC = {
    "HEAD", "@", "FETCH_HEAD", "ORIG_HEAD", "MERGE_HEAD", "CHERRY_PICK_HEAD",
    "REVERT_HEAD", "BISECT_HEAD", "AUTO_MERGE",
}

RX_SHA = re.compile(r"\A[0-9a-f]{7,40}\Z")
# A version tag is immutable, so it cannot go stale the way a branch does.
RX_TAG = re.compile(r"\A[vV]?\d+(\.\d+)*\Z")
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

NOTE = """\
A diff range in this call names a bare local branch as its base: {bases}

`verify-the-right-artifact.md`'s "A comparison's base is an artifact too"
covers why that is a claim rather than a label. A local branch is a cached copy
of a remote one, and `A...B` computes from the merge-base of the refs you
supplied -- so the three-dot form is not self-correcting. It is only as fresh
as the local ref.

The error is single-signed: a stale base moves the merge-base earlier, so the
diff only ever gets BIGGER. The extra content is already-merged work by other
people, and a review run on it returns findings against code this branch never
touched. Nothing in the output announces it -- a 53-file diff and a 14-file
diff look equally plausible, and every finding is individually well-formed.

Resolve the base from a remote-tracking ref, after fetching that remote:

    git -C <repo> fetch -q <remote>
    BASE=$(git -C <repo> merge-base <remote>/<default-branch> <head-ref>)
    git -C <repo> diff --shortstat "$BASE" <head-ref>
    gh pr view <N> --json changedFiles,additions,deletions

The last two readings must agree; a mismatch means the base is wrong.
Resolve the default branch from the repo rather than assuming `main`, and note
the remote is not always `origin`.

If the base is deliberately local -- comparing two branches you just built, or
inspecting your own work in progress -- carry on. This is a reminder, not a
refusal.
"""


def strip_heredocs(command):
    """Drop heredoc bodies, so writing a file about this rule does not trip it."""
    if not isinstance(command, str):
        return ""
    return RX_HEREDOC.sub("<<HEREDOC", command)


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


def is_local_branch_base(token):
    """True when `token` looks like a bare local branch name.

    A remote-tracking ref carries a remote prefix, so it contains `/`. A
    symbolic ref, a raw SHA, and a version tag each name something a fetch
    cannot make staler.
    """
    token = normalize_base(token)
    if not token or "/" in token:
        return False
    # A run of dots is the separator itself, reached when the text before it
    # ends in a character the ref class excludes --- as `origin/<default-
    # branch>...HEAD` does. It names no ref.
    if not re.search(r"[A-Za-z0-9]", token):
        return False
    # Strip revision suffixes: `main~2`, `main^`, `main@{u}`.
    stem = re.split(r"[~^@]", token, 1)[0]
    if not stem or stem in SYMBOLIC:
        return False
    if RX_SHA.match(stem) or RX_TAG.match(stem):
        return False
    return True


def stale_bases(text):
    """Return the bare-local-branch bases of any git range in `text`."""
    if not isinstance(text, str) or not text:
        return []
    body = strip_heredocs(text)
    found = []
    for match in RX_GIT_RANGE_CMD.finditer(body):
        # Look only at the remainder of that command, up to a separator.
        tail = re.split(r"[\n;|&]", body[match.end():], 1)[0]
        for base, _dots, _head in RX_RANGE.findall(tail):
            if not is_local_branch_base(base):
                continue
            base = normalize_base(base)
            if base not in found:
                found.append(base)
    return found


def _tool_uses(entry):
    """Yield (name, payload_dict) for each tool_use in a transcript entry."""
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else entry.get("content")
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name")
            payload = block.get("input")
            yield (name if isinstance(name, str) else ""), (payload if isinstance(payload, dict) else {})

    calls = entry.get("tool_calls")
    if isinstance(calls, list):
        for call in calls:
            if not isinstance(call, dict):
                continue
            name = call.get("name") or (call.get("function") or {}).get("name") or ""
            payload = (call.get("args") or call.get("input")
                       or (call.get("function") or {}).get("arguments") or {})
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except ValueError:
                    payload = {"command": payload}
            yield name, (payload if isinstance(payload, dict) else {})


def _payload_text(payload):
    """Yield the command-ish and brief-ish strings from a tool input dict."""
    for key in ("command", "cmd", "CommandLine") + BRIEF_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value:
            yield value


def transcript_has_fetch(transcript_path):
    """True when some earlier command fetched or queried a remote.

    Returns True (discharged, silent) on any read failure --- fail open.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return True
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                for _name, payload in _tool_uses(entry):
                    for text in _payload_text(payload):
                        if RX_DISCHARGE.search(strip_heredocs(text)):
                            return True
    except OSError:
        return True
    return False


def _emit(note):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        }
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
        elif tool_name in BRIEF_TOOLS:
            texts = [tool_input.get(k) for k in BRIEF_KEYS]
        else:
            return 0

        bases = []
        for text in texts:
            for base in stale_bases(text):
                if base not in bases:
                    bases.append(base)
        if not bases:
            return 0

        if transcript_has_fetch(payload.get("transcript_path") or ""):
            return 0

        _emit(NOTE.format(bases=", ".join("`%s`" % b for b in bases)))
    except Exception as exc:  # noqa: BLE001 --- a reminder must never break a tool
        print(f"warn-stale-review-diff-base: could not evaluate ({exc})",
              file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
