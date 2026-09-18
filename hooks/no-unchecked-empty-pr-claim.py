#!/usr/bin/env python3
"""Stop-hook guard: catch calling a PR empty or abandoned from `changed_files`.

`pr-on-claim.md` has this repo open a PR against an EMPTY COMMIT before
implementing, deliberately, as the in-flight signal that stops parallel
duplicates. So `changed_files: 0` is the expected reading on three states the
field cannot tell apart:

    a live claim whose implementation has not landed;
    a thread whose commits exist but cannot be pushed (#3739 / #3045 / #3743);
    a genuinely abandoned branch.

Only the third is closeable, and the repo's own convention manufactures the
reading for the other two. That is what makes this a hook rather than a rule:
the trap is set by the convention, so every triage sweep meets it, and nothing
about the number announces which state produced it.

`memories/github.md`'s triage step already says to read the commit list before
closing an empty PR, and the miss happened anyway -- the sweep never reached
for it, it reached for the field already in hand from a mergeability query. A
rule is consulted at read time and broken at composition time.

The condition is decidable from the transcript:

    the message characterizes a PR as abandoned, or as empty AND disposable
      AND a PR number sits within NEARBY_WINDOW characters
      AND that claim is not locally justified on some other basis
      AND no commit-list QUERY naming that number was issued this session

Every clause above is a narrowing some draft of this guard got wrong, and each
one failed the same way: the guard went quiet, which is indistinguishable from
a guard that never ran.

**Evidence must be a QUERY, not merely a tool call.** Round 2 drew the line at
calls versus results, which does not hold: a `Bash` call carries a path and a
`reply` / `add_issue_comment` / `update_status` call carries the agent's own
prose, so writing "I have not run get_commits for #3737" into a PR comment
discharged the guard. Measured over the session that produced the incident,
those two families were 401 of 553 calls (323 `Bash`, 44 `update_status`,
23 `reply`, 11 `add_issue_comment`) while the file tools the denylist named
were zero. So the evidence set is an ALLOWLIST of reads, a command carrying a
message body is never one, and a `Bash` call contributes its command's lines
rather than its serialized input --- see `query_lines`.

**Evidence must name the PR the claim is about, and every PR it names.** A
sweep reads many PRs; an unscoped test is discharged by the first. Returning
on the first number that has evidence repeats that one level down, silencing
a batch close because one of its PRs was checked.

**The mergeability query is not evidence.** `pull_request_read` with method
`get`, and a bare `repos/O/R/pulls/N` read, are the queries that return
`changed_files`. Measured on the real transcript at the incident: 39
`pull_request_read` calls preceded it (13 method `get`, 20 `get_check_runs`,
2 each `get_comments` / `get_files` / `get_status`) and ZERO commit-list reads
of any kind. Counting the mergeability query is what silenced the first draft;
scoping alone would also have fixed it, and so would this exclusion alone.

Warns, never blocks: "abandoned" is partly a judgment, and a blocking guard on
a judgment gets switched off, taking the real cases with it. Fails OPEN on any
parse trouble, and fires at most once per distinct message.

Two known limits, both accepted rather than unnoticed.

A bare `#N` that names neither a PR nor an issue (a numbered list item,
"Option #2") is read as a PR reference.

And the disposition cue is a proxy for the claim being consequential, not a
reading of its polarity: it fires on "closing it needs Ezra's word, so I've
left it", which declines to close, and it would miss a close phrased with no
cue word near the emptiness statement. The incident is of the first kind, so
the guard catches it while the sentence disposes of nothing --- worth stating,
because the proxy is what makes the condition decidable at all, and a reader
who assumes polarity handling will misjudge what the guard covers.

Morrison-Lab/ai-config#3755. Measured on #3737, 2026-09-17.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# How far a PR number may sit from the phrase for the phrase to be a claim
# about that PR.
NEARBY_WINDOW = 240

# How far a disposition cue, or a locally-stated basis, may sit from the
# phrase it qualifies.
CUE_WINDOW = 200

# How far a PR number may sit from a commit-list token inside one tool call's
# input for that call to be a read of that PR. A separate knob from the two
# above: it measures a distance in a serialized query, not in prose.
CALL_WINDOW = 200

# Family A: the PR characterized as ABANDONED. This is the claim
# `changed_files` cannot support, and it is not how anyone describes the
# convention working, so it fires on its own.
#
# `stale`, `dead`, `orphaned` and `forgotten` are deliberately NOT triggers.
# This corpus uses "stale" for a PR whose base moved --- `CLAUDE.md`'s
# batch-merge section says so outright --- so a repo running `sync-pr-branch`
# meets that phrase in correct prose far more often than in the defect, and a
# warn-only guard that fires there trains its reader to ignore it.
#
# `s?(?![\w-])` rather than a bare word boundary: every noun here pluralizes,
# and "the abandoned PRs #1 and #2" is the natural phrasing of a batch triage
# close, so a trailing boundary misses the defect in the place it most often
# appears. Dropping the boundary entirely is the other error -- it matches
# "stale PR-status cache" and "stale drafting workflow", neither of which
# names an abandoned pull request.
RX_ABANDON = re.compile(
    r"(?:"
    r"never (?:filled|worked on|pushed to|implemented|started|touched"
    r"|got any (?:code|commits))"
    r"|(?:opened|created) (?:it )?and (?:never|then) (?:filled|abandoned|forgot)"
    r"|nobody (?:ever )?filled"
    r"|(?:(?:an?|the) )?abandoned (?:PR|MR|pull request|draft|branch)s?(?![\w-])"
    r"|(?:PR|MR|pull request|draft)s?(?![\w-]) (?:that |which )?"
    r"(?:was |is |were |are )?abandoned"
    r")",
    re.I,
)

# Family B: the PR characterized as EMPTY. On its own this is ordinary,
# correct reporting -- "#3737 shows zero changed files; I am still working the
# implementation" states the field and claims nothing. It becomes the defect
# only when a disposition rides on it, so family B fires only alongside a cue
# from RX_DISPOSITION within CUE_WINDOW characters.
RX_EMPTY = re.compile(
    r"(?:"
    r"(?:zero|no|0) changed ?[fF]iles"
    r"|changed_?[fF]iles(?:\s*[:=]\s*|\s+is\s+|\s+of\s+)0\b"
    r"|(?:zero|no) commits"
    r"|(?:PR|MR|pull request|draft)s?(?![\w-]) (?:with|has|have|carrying) "
    r"(?:zero|no|0) (?:changed )?(?:files|commits)"
    r"|empty (?:PR|MR|pull request|draft)s?(?![\w-])"
    r"|(?:PR|MR|pull request|draft)s?(?![\w-])(?: #?\d+)? "
    r"(?:is|are|was|were) empty"
    r")",
    re.I,
)

# What turns an emptiness reading into a claim worth checking. Two
# constraints, each of which a draft got wrong. Every literal is
# boundary-anchored, since an unanchored alternation matches inside
# "deadline", "closely", "disclosed", "dropdown" and "reapply". And every
# literal is an ACTION: the adjectives ("dead", "stale", "forgotten") are
# family-A triggers in their own right when they qualify a PR, and as cues
# they fire on prose that disposes of nothing -- "#N has zero changed files
# and the dropdown in the docs is stale too".
RX_DISPOSITION = re.compile(
    r"\b(?:"
    r"clos(?:e|es|ed|ing|eable|able)"
    r"|safe to close|not planned|reap|prune"
    r"|delet(?:e|es|ed|ing)|drop(?:s|ped|ping)?"
    r"|abandon(?:ed|ing)?"
    r")\b",
    re.I,
)

# A concrete PR NUMBER, which is what the gate requires -- not a PR noun.
# Several trigger alternatives contain the word "PR" themselves, so a gate
# accepting a bare noun is satisfied by its own trigger, and generic prose
# about stale pull requests in the abstract fires on nothing at all. The
# number may sit inside the matched phrase ("PR #3737 is empty"), which is the
# commonest place for it.
RX_PR_NUMBER = re.compile(r"#(\d+)\b|/pull/(\d+)|/merge_requests/(\d+)")

# `#N` that a PR noun introduces, and `#N` that an ISSUE noun introduces. A
# number the message itself calls an issue is not the subject of a claim about
# a pull request, and naming it in the warning sends the reader to the wrong
# object.
RX_PR_QUALIFIED = re.compile(
    r"(?:PR|MR|pull request)s?[^\w#]{0,12}#?(\d+)\b|/pull/(\d+)", re.I)
RX_ISSUE_QUALIFIED = re.compile(r"issues?[^\w#]{0,12}#(\d+)\b|/issues/(\d+)",
                                re.I)

# A reply that CORRECTS this reading is not a reply that commits it, and
# neither is a close whose basis is stated. Split in two because the scopes
# differ: naming the convention is a statement about the whole message, while
# "superseded by #N" justifies the ONE close it sits next to. Searching a
# per-close basis over the whole message lets one correctly-justified close in
# a batch recap exempt every unjustified one beside it.
RX_CORRECTING_GLOBAL = re.compile(
    r"pr-on-claim"
    r"|no-unchecked-empty-pr-claim|empty-pr-claim"
    r"|changed_files (?:cannot|can't|lies|says nothing|is not|does not)"
    r"|expected reading"
    r"|manufactures that reading"
    r"|not evidence (?:that|it|of)"
    # Prose about a guard rather than about a pull request. A recap of this
    # very PR otherwise fires on its own subject matter, which is the hazard
    # shared/writing/examples-are-scanned.md names.
    r"|(?:warns|fires) when (?:a|the) reply",
    re.I,
)
RX_CORRECTING_LOCAL = re.compile(
    r"(?:is|was|being) a (?:live |legitimate )?claim (?:PR|commit)"
    r"|supersed(?:e|es|ed)|already merged|branch had (?:already )?merged"
    r"|duplicate of|duplicates #",
    re.I,
)

# Tool calls whose input is a QUERY. Anything not matched here is not
# evidence, however its input reads: an allowlist, because the families that
# defeat a denylist (a shell command carrying a path, a message-posting call
# carrying prose) are the ones a real session uses most.
RX_QUERY_TOOL = re.compile(
    r"^(?:bash|mcp__github__pull_request_read|mcp__github__list_commits"
    r"|mcp__github__search_pull_requests)$", re.I)

# A command that carries a message body is authoring prose, not querying. Its
# body can say anything, including the guard's own warning quoted back.
RX_MESSAGE_BODY = re.compile(
    r"--body|--body-file|-F body=|-f body=|\bcomment\b|\bissue create\b"
    r"|\bpr create\b|\breview\b", re.I)

# A shell command is a query only when it invokes something that talks to the
# forge or to git. Without this, `cat /tmp/pulls/3737/commits.json` reads as a
# commit-list query because the PATH contains the endpoint's shape -- the same
# path-is-not-a-query confusion the denylist draft made, one level down.
RX_QUERY_COMMAND = re.compile(
    r"\b(?:gh|glab|curl|wget|http|https?ie|git)\b|build-pr-payload", re.I)


def commit_read_pattern(number: str) -> re.Pattern:
    """Reads that settle whether PR `number` carries commits.

    A claim PR has one commit and a truly empty branch has none, so the commit
    list separates the two states the field cannot. The mergeability query is
    excluded on purpose; see the module docstring. `build-pr-payload.py` is
    included because it is this repo's own way to gather a PR's full state
    without `gh`, and it fetches `pulls/<n>/commits`.
    """
    n = re.escape(number)
    w = CALL_WINDOW
    return re.compile(
        rf"pulls/{n}/commits"
        rf"|merge_requests/{n}/commits"
        rf"|get_commits[^\n]{{0,{w}}}\b{n}\b"
        rf"|\b{n}\b[^\n]{{0,{w}}}get_commits"
        rf"|list_commits[^\n]{{0,{w}}}\b{n}\b"
        rf"|gh pr view {n}\b[^\n]{{0,{w}}}commits"
        rf"|glab mr view {n}\b[^\n]{{0,{w}}}commits"
        rf"|build-pr-payload[^\n]{{0,{w}}}\b{n}\b"
        rf"|git (?:log|rev-list)[^\n]{{0,{w}}}\b{n}\b",
        re.I,
    )


def _sentence(text: str, match: re.Match) -> str:
    """The sentence the match sits in.

    A stated basis -- "superseded by #N", "its branch had already merged" --
    justifies the ONE close it belongs to. Searched over a character window
    instead, a single correctly-justified close in a batch recap exempts every
    unjustified one beside it, which is the modal shape of the message this
    guard exists for.
    """
    dot = text.rfind(". ", 0, match.start())
    line = text.rfind("\n", 0, match.start())
    start = max(dot + 2 if dot != -1 else 0,
                line + 1 if line != -1 else 0)
    ends = [e for e in (text.find(". ", match.end()),
                        text.find("\n", match.end())) if e != -1]
    return text[start:min(ends) if ends else len(text)]


def claim_numbers(text: str, match: re.Match):
    """PR numbers this claim is about.

    The union of the ones a PR noun introduces and the bare ones, minus any a
    noun calls an issue. Preferring the qualified set over the bare one drops
    the second number of every list, since "PRs #1 and #2" qualifies only the
    first -- which silences exactly the batch close this guard is about.
    """
    window = text[max(0, match.start() - NEARBY_WINDOW):
                  match.end() + NEARBY_WINDOW]
    qualified = [n for group in RX_PR_QUALIFIED.findall(window)
                 for n in group if n]
    issues = {n for group in RX_ISSUE_QUALIFIED.findall(window)
              for n in group if n} - set(qualified)
    bare = [n for group in RX_PR_NUMBER.findall(window)
            for n in group if n and n not in issues]
    return list(dict.fromkeys(qualified + bare))


def find_claims(text: str):
    """Every claim in the message about a named PR, in order.

    All of them, not the first: `main` warns when ANY claim names a PR nothing
    read, and stopping at the first means a checked close early in a recap
    covers an unchecked one later in it. That is the same wrong-subject
    discharge one level up from the per-number loop.
    """
    claims = []
    for match in _candidates(text):
        if RX_CORRECTING_LOCAL.search(_sentence(text, match)):
            continue
        numbers = claim_numbers(text, match)
        if numbers:
            claims.append((match, numbers))
    return claims


def _candidates(text: str):
    """Abandonment matches, plus emptiness matches carrying a disposition."""
    for match in RX_ABANDON.finditer(text):
        yield match
    for match in RX_EMPTY.finditer(text):
        window = text[max(0, match.start() - CUE_WINDOW):
                      match.end() + CUE_WINDOW]
        if RX_DISPOSITION.search(window):
            yield match


def query_lines(name: str, tool_input):
    """The query text a tool call contributes, as one entry per real line.

    Two things this must not do, each measured on the real transcript.

    It must not serialize the whole input dict: a `Bash` call carries a free-
    prose `description` beside its command, and a PR number mentioned there
    then discharges the guard as if a query had named it.

    And it must not treat the serialization as text: `json.dumps` writes a
    newline as the two characters backslash and `n`, so a pattern written with
    `[^\n]` never terminates at a line and spans the whole script, while a
    `\b` before a command name is defeated by the `n` that escaping glues to
    it. One produces a false discharge and the other a false warning on a
    genuine read. Splitting the command into real lines first removes both.
    """
    if not isinstance(tool_input, dict):
        return []
    if name.lower() == "bash":
        command = tool_input.get("command")
        if not isinstance(command, str):
            return []
        lines = command.splitlines() or [command]
        return [line for line in lines
                if RX_QUERY_COMMAND.search(line)
                and not RX_MESSAGE_BODY.search(line)]
    try:
        blob = json.dumps(tool_input)
    except Exception:
        return []
    if RX_MESSAGE_BODY.search(blob):
        return []
    return [name + " " + blob]


def scan(path: str):
    """Return (query lines, last assistant text) from the transcript."""
    calls = []
    text = ""
    if not path or not os.path.isfile(path):
        return calls, text
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:
                continue
            # A subagent's turns are not this session's own. Peer transcript
            # readers all skip them; see memories/hooks.md.
            if record.get("isSidechain"):
                continue
            message = record.get("message") or {}
            role = message.get("role") or record.get("role") or ""
            blocks = message.get("content")
            if isinstance(blocks, str):
                if role == "assistant" and blocks.strip():
                    text = blocks
                continue
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                kind = block.get("type")
                if kind == "tool_use":
                    name = (block.get("name") or "")
                    if not RX_QUERY_TOOL.match(name):
                        continue
                    calls.extend(query_lines(name, block.get("input")))
                elif kind == "text" and role == "assistant":
                    if block.get("text", "").strip():
                        text = block["text"]
    return calls, text


def unchecked_numbers(numbers, calls):
    """The claimed PRs no commit-list query in this session named."""
    missing = []
    for number in numbers:
        pattern = commit_read_pattern(number)
        if not any(pattern.search(call) for call in calls):
            missing.append(number)
    return missing


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        calls, text = scan(payload.get("transcript_path") or "")
    except Exception:
        return 0  # fail open

    if not text:
        return 0
    claims = find_claims(text)
    if not claims:
        return 0
    # Naming the convention corrects the reading for the whole message.
    if RX_CORRECTING_GLOBAL.search(text):
        return 0
    for hit, numbers in claims:
        missing = unchecked_numbers(numbers, calls)
        if missing:
            break
    else:
        return 0

    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(),
                            f".claude-empty-pr-claim-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        with open(sentinel, "w"):
            pass
    except Exception:
        pass

    named = ", ".join("#" + n for n in missing)
    print(json.dumps({
        "systemMessage": (
            f"Empty-PR check: your message characterizes {named} as abandoned "
            f"or as empty and disposable (\"{hit.group(0).strip()}\"), and no "
            "commit-list query naming it was issued this session. pr-on-claim "
            "opens PRs against an empty commit on purpose, so changed_files: "
            "0 reads the same way on a live claim and on a thread whose "
            "commits cannot be pushed. The mergeability query that returns "
            "that field cannot tell those apart -- read the commit list (a "
            "claim PR has 1, not 0) and the PR body before reporting it as "
            "abandoned (ai-config#3755)."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
