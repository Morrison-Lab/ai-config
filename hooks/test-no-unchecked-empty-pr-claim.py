"""Test the no-unchecked-empty-pr-claim guard.

Case one is the reported incident in its own words, copied from the session
transcript that produced it (record 3266, 2026-09-17):

    "Re-deriving the open set rather than reusing my remembered list surfaced
     a fifth PR -- #3737, a draft from another thread with zero changed files.
     Not mine to drive, and closing it needs Ezra's word, so I've left it."

#3737 was a live claim PR for #3707 carrying one commit, whose body opened
with a bolded callout saying fourteen finished commits could not be pushed.

Two drafts of this guard were silent on messages of that shape, each for its
own reason, and both are reproduced below as cases rather than as prose.
The measured facts about that session, since the fixtures encode them:

    553 non-sidechain tool calls before the claim;
    323 Bash, 44 update_status, 39 pull_request_read, 23 reply;
    ZERO Read, Grep or Glob calls;
    of the 39 pull_request_read calls: 13 method `get`, 20 `get_check_runs`,
      2 `get_comments`, 2 `get_files`, 2 `get_status`;
    ZERO commit-list reads of any kind.

Draft one accepted the method-`get` mergeability query as evidence, so the 13
discharged it. Draft two allowed evidence from any non-file tool call, so the
session's own `reply` and `update_status` prose discharged it. Neither failure
is visible in a fixture that carries only the sentence, which is
`shared/workflow/fixtures-are-not-evidence.md`'s point; the guard was also run
against the real 12 MB transcript truncated at that record, where it fires.

The negative cases are what decide whether this guard survives. This corpus
explains `pr-on-claim`'s empty-commit convention constantly -- the hook's own
docstring does -- so a reply correcting the reading must stay silent, and so
must a close whose own sentence states another basis.

Run: python3 hooks/test-no-unchecked-empty-pr-claim.py \
         hooks/no-unchecked-empty-pr-claim.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
SUBJECT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    HERE, "no-unchecked-empty-pr-claim.py")

SENTINEL_PREFIX = ".claude-empty-pr-claim-"

# Payloads a fire produced that the harness would discard; see run().
SHAPE_ERRORS = []


def say(text, sidechain=False):
    """An assistant text turn, which is what the guard reads."""
    record = {"type": "assistant", "message": {
        "role": "assistant",
        "content": [{"type": "text", "text": text}]}}
    if sidechain:
        record["isSidechain"] = True
    return record


def call(name, tool_input):
    """A tool call. Only a query-bearing one counts as evidence."""
    return {"type": "assistant", "message": {
        "role": "assistant",
        "content": [{"type": "tool_use", "name": name, "input": tool_input}]}}


def result(text):
    """A tool result, which is content and never counts."""
    return {"type": "user", "message": {
        "role": "user",
        "content": [{"type": "tool_result", "content": text}]}}


def pr_read(method, number):
    return call("mcp__github__pull_request_read",
                {"method": method, "owner": "Morrison-Lab", "repo": "ai-config",
                 "pullNumber": number})


# --- the incident -----------------------------------------------------------
INCIDENT = say(
    "Re-deriving the open set rather than reusing my remembered list surfaced "
    "a fifth PR -- #3737, a draft from another thread with zero changed "
    "files. Not mine to drive, and closing it needs Ezra's word, so I've "
    "left it.")

# The session's real pull-request traffic before that message, in the measured
# proportions. The commit-list reads on OTHER pull requests are what make this
# fixture test SCOPING: without them the case passes even with scoping removed,
# which is how an earlier version of this suite let the flagship narrowing go
# unexercised.
PRIOR_PR_TRAFFIC = (
    [pr_read("get_check_runs", n) for n in (3690, 3692, 3745, 3750) * 5]
    + [pr_read("get", n) for n in (3690, 3692, 3745) + (3750,) * 10]
    + [pr_read("get_comments", 3690), pr_read("get_files", 3692),
       pr_read("get_status", 3745)]
    + [pr_read("get_commits", 3690), pr_read("get_commits", 3692)]
)

# The session's own outgoing prose, which quotes the discharging token. Draft
# two treated these as evidence.
OWN_REPLY = call("mcp__hearthbot__reply",
                 {"text": "I have not run get_commits for #3737 yet."})
OWN_STATUS = call("mcp__hearthbot__update_status",
                  {"text": "PR triage\n\n- get_commits on 3737\n"})
OWN_COMMENT = call("Bash", {
    "command": "gh pr comment 3755 --body 'the guard wants a get_commits "
               "read for 3737'"})
OWN_ISSUE_COMMENT = call("mcp__github__add_issue_comment",
                         {"body": "no get_commits for 3737 yet"})

# --- plainer phrasings of the same defect ----------------------------------
PLAIN_EMPTY = say("PR #3737 is empty, so I closed it.")
BATCH_PLURAL = say("Closing the abandoned PRs #3737 and #3740.")
STALE_PLURAL = say("These are abandoned PRs: #3737, #3740. Closing them.")
FIELD_STATED = say("PR #3737: changed_files is 0, so this is an abandoned PR. "
                   "Closing it in this sweep.")
READ_NOT_DONE = say("I have not run get_commits, but PR #3737 is empty "
                    "with no activity -- closing.")
NOT_A_CLAIM = say("PR #3737 is not a claim PR; it is an abandoned draft. "
                  "Closing.")
NO_COMMITS = say("PR #3737 carries no commits at all, so I closed it.")
NOTHING_IN_IT = say("I read #3737's diff and there is nothing in it that "
                    "would break the build, so I dropped my objection.")
NEVER_IMPLEMENTED = say("PR #3737 was opened and never implemented, so I "
                        "closed it.")
CAMEL_FIELD = say("PR #3737 reports changedFiles: 0, so it is dead weight. "
                  "Closing.")

# --- the reads that settle it ----------------------------------------------
RIGHT_PR_COMMITS = pr_read("get_commits", 3737)
OTHER_PR_COMMITS = pr_read("get_commits", 9999)
MERGEABILITY = pr_read("get", 3737)
REST_COMMITS = call("Bash", {
    "command": "curl -s https://api.github.com/repos/Morrison-Lab/"
               "ai-config/pulls/3737/commits"})
PAYLOAD_BUILDER = call("Bash", {
    "command": "python3 scripts/build-pr-payload.py Morrison-Lab/ai-config "
               "3737 /tmp/p.json"})
GIT_LOG = call("Bash", {
    "command": "git log --oneline origin/main..origin/claude/pr-3737"})
BARE_HTTPS_COMMITS = call("Bash", {
    "command": "python3 -c \"import urllib.request; urllib.request.urlopen("
               "'https://api.github.com/repos/Morrison-Lab/ai-config/pulls/"
               "3737/commits')\""})

# A shell read of a PATH that looks like the commit endpoint. A path is not a
# query, so it is not evidence.
BASH_CAT_PATH = call("Bash", {"command": "cat /tmp/pulls/3737/commits.json"})
FILE_TOOL_READ = call("Read", {"file_path": "/tmp/pulls/3737/commits.json"})

# Content carrying the discharging tokens. Results are never evidence --
# including a read of this hook's own README row, which is how a guard gets
# disabled by its own documentation.
README_ROW = result(
    "| `no-unchecked-empty-pr-claim.py` | `Stop` | ... commit-list query "
    "... get_commits ... #3737 ...")
LIST_ENDPOINT = result(
    '[{"number": 3737, "url": "https://api.github.com/repos/Morrison-Lab/'
    'ai-config/pulls/3737"}]')

# --- what must stay silent -------------------------------------------------
CORRECTING = say(
    "#3737 is a live claim PR for #3707; pr-on-claim makes zero changed files "
    "the expected reading, so closing it would be wrong.")
DESCRIBING_GUARD = say(
    "Opened the guard PR. It warns when a reply calls something an abandoned "
    "PR near a number, so #3755 should be clean once CI is green.")
STATUS_LINE = say(
    "#3737 shows zero changed files; I am still working the implementation.")
SUPERSEDED = say(
    "Dependabot's stale PR #2200 was superseded by #2210, so I closed it.")
ALREADY_MERGED = say(
    "I closed the stale PR #1234 after confirming its branch had already "
    "merged.")
MIXED_RECAP = say(
    "#3700 was superseded by #3702 so I closed it. Separately, PR #3737 is an "
    "abandoned PR with no commits, so I closed that too.")
COMPOUND_NOUN = say(
    "I cleared the stale PR-status cache before re-checking #3745.")
COMPOUND_DRAFT = say(
    "The stale drafting workflow in #3745 needs a pass.")
DEADLINE = say(
    "PR #3737 is an empty PR; the CI deadline passed while we waited.")
CLOSELY = say(
    "I looked closely at #3737, which has zero changed files, before moving "
    "on.")
DROPDOWN = say(
    "#3737 has zero changed files and the dropdown in the docs is stale too.")
ISSUE_NUMBER = say(
    "Issue #3707 is done. The draft is empty, so I dropped it.")
GENERIC_PROSE = say(
    "In general an abandoned pull request should be closed after ninety days.")
DEAD_PATTERN = say(
    "The vendored upstream project is effectively a dead PR pattern we should "
    "avoid.")
ORDINARY = say(
    "#3745 is green on its current head and #3750 carries a standing "
    "not-clean verdict from a push made under a human account.")

# A claim and a PR number far enough apart that the phrase is about neither.
FAR_APART = say(
    "#3737 came up in the sweep and I have left it alone for now.\n\n"
    + ("Separately, the release notes for the analysis helper needed a pass "
       "this morning, and the figure captions in the methods chapter were "
       "still carrying the old numbering scheme from before the renumber, "
       "which took a while to reconcile against the rendered output. "
       "None of that touched the queue at all, and the render came back "
       "clean on the second attempt once the cache was dropped.\n\n")
    + "The vendored copy of the parser was never filled in, so I dropped it.")


def clear_sentinels():
    tmp = tempfile.gettempdir()
    for name in os.listdir(tmp):
        if name.startswith(SENTINEL_PREFIX):
            try:
                os.remove(os.path.join(tmp, name))
            except OSError:
                pass


def invoke(events, hook=None, clear=True):
    """Run the hook over a synthesized transcript; return its parsed payload."""
    if clear:
        clear_sentinels()
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")
    try:
        out = subprocess.run(
            [sys.executable, hook or SUBJECT],
            input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
        ).stdout.strip()
    finally:
        os.remove(path)
    return json.loads(out) if out else {}


def run(events):
    """True when the guard fired AND the warning reaches the harness.

    `bool(out)` alone would score any output as a fire, including output the
    harness discards: a `Stop` hook's `reason` is read only alongside
    `"decision": "block"`, so a warn-only hook emitting `reason` by itself is
    valid JSON that reaches nobody (ai-config#1566, #1582).
    """
    payload = invoke(events)
    if not payload:
        return False
    if not payload.get("systemMessage"):
        SHAPE_ERRORS.append(sorted(payload))
    return True


# (events, should_fire, label)
CASES = [
    # --- the incident, and the two session shapes that hid it --------------
    ([INCIDENT], True, "#3755: the incident, in its own words"),
    (PRIOR_PR_TRAFFIC + [INCIDENT], True,
     "the session's real prior PR traffic, commit reads included, does not "
     "discharge a claim about a DIFFERENT PR"),
    ([OWN_REPLY, READ_NOT_DONE], True,
     "the session's own reply quoting the token is not a read"),
    ([OWN_STATUS, PLAIN_EMPTY], True,
     "a status checklist quoting the token is not a read"),
    ([OWN_COMMENT, PLAIN_EMPTY], True,
     "a PR comment body quoting the token is not a read"),
    ([OWN_ISSUE_COMMENT, PLAIN_EMPTY], True,
     "an issue comment body quoting the token is not a read"),

    # --- plainer phrasings of the same defect ------------------------------
    ([PLAIN_EMPTY], True, "the plainest phrasing: empty, so I closed it"),
    ([BATCH_PLURAL], True, "a plural batch close"),
    ([STALE_PLURAL], True, "a plural abandoned list"),
    ([FIELD_STATED], True, "the inference stated outright from the field"),
    ([READ_NOT_DONE], True,
     "naming the read you did NOT perform buys no exemption"),
    ([NOT_A_CLAIM], True, "denying it is a claim PR is not correcting"),
    ([NO_COMMITS], True, "no commits at all"),
    ([NOTHING_IN_IT], False,
     "'nothing in it' is an idiom about content, not an emptiness claim"),
    ([NEVER_IMPLEMENTED], True, "opened and never implemented"),
    ([CAMEL_FIELD], True, "the gh --json spelling, changedFiles"),

    # --- discharge, scoped to every PR the claim names ---------------------
    ([RIGHT_PR_COMMITS, PLAIN_EMPTY], False,
     "a commit-list read on THIS PR discharges it"),
    ([REST_COMMITS, PLAIN_EMPTY], False,
     "the REST commits endpoint on THIS PR discharges it"),
    ([PAYLOAD_BUILDER, PLAIN_EMPTY], False,
     "this repo's own build-pr-payload.py discharges it"),
    ([GIT_LOG, PLAIN_EMPTY], False,
     "a local git log over the PR's branch discharges it"),
    ([BARE_HTTPS_COMMITS, PLAIN_EMPTY], False,
     "a bare-https urllib read of the commits endpoint discharges it, with no "
     "gh/curl/wget/git token on the line"),
    ([OTHER_PR_COMMITS, PLAIN_EMPTY], True,
     "a commit-list read on ANOTHER PR does not"),
    ([pr_read("get_commits", 3740), BATCH_PLURAL], True,
     "one PR of a batch checked leaves the other unchecked"),
    ([pr_read("get_commits", 3740), pr_read("get_commits", 3737),
      BATCH_PLURAL], False,
     "every PR of a batch checked discharges it"),
    ([MERGEABILITY, PLAIN_EMPTY], True,
     "the mergeability query returning changed_files is not evidence"),
    ([BASH_CAT_PATH, PLAIN_EMPTY], True,
     "a shell read of a path that looks like the endpoint is not a query"),
    ([FILE_TOOL_READ, PLAIN_EMPTY], True,
     "a file tool reading that same path is not a query either"),
    ([README_ROW, PLAIN_EMPTY], True,
     "reading this hook's own README row does not disarm it"),
    ([LIST_ENDPOINT, PLAIN_EMPTY], True,
     "a PR-list result naming the PR does not discharge it"),

    # --- what must stay silent ---------------------------------------------
    ([CORRECTING], False, "a reply correcting the reading"),
    ([DESCRIBING_GUARD], False, "a recap describing this guard"),
    ([STATUS_LINE], False, "reporting the field with no disposition"),
    ([SUPERSEDED], False, "a close whose sentence states supersession"),
    ([ALREADY_MERGED], False, "a close whose sentence states a merged branch"),
    ([MIXED_RECAP], True,
     "a justified close does not exempt an unjustified one beside it"),
    ([COMPOUND_NOUN], False, "'stale PR-status cache' names no pull request"),
    ([COMPOUND_DRAFT], False, "'stale drafting workflow' names none either"),
    ([DEADLINE], False, "'deadline' is not a disposition"),
    ([CLOSELY], False, "'closely' is not a disposition"),
    ([DROPDOWN], False, "a stale dropdown is not a disposed-of pull request"),
    ([ISSUE_NUMBER], False, "an issue number is not the claim's subject"),
    ([GENERIC_PROSE], False, "prose about pull requests in the abstract"),
    ([DEAD_PATTERN], False, "'dead PR pattern' naming no pull request"),
    ([FAR_APART], False, "a PR number far from the phrase is not its subject"),
    ([ORDINARY], False, "negative control: ordinary triage prose"),

    # --- transcript handling ------------------------------------------------
    ([say("PR #3737 is empty, so I closed it.", sidechain=True),
      ORDINARY], False,
     "a subagent's turn is not this session's last assistant text"),
    ([PLAIN_EMPTY, ORDINARY], False,
     "a claim superseded by a later, clean message is not re-flagged"),
]

failures = 0


def check(label, got, want):
    global failures
    ok = got == want
    if not ok:
        failures += 1
    print(f"{'ok  ' if ok else 'FAIL'}  got={got!s:5} want={want!s:5}  {label}")


def matrix():
    for events, want, label in CASES:
        check(label, run(events), want)


def dedupe_check():
    first = bool(invoke([INCIDENT]))
    second = bool(invoke([INCIDENT], clear=False))
    check("dedupe: the first run on a message fires", first, True)
    check("dedupe: an identical second run is silent", second, False)


def shape_check():
    payload = invoke([INCIDENT])
    check("the warning is emitted in a field the harness surfaces "
          f"(keys={sorted(payload)})",
          bool(payload.get("systemMessage")), True)
    check("the warning names the PR it is about",
          "#3737" in payload.get("systemMessage", ""), True)
    batch = invoke([pr_read("get_commits", 3740), BATCH_PLURAL])
    message = batch.get("systemMessage", "")
    check("the warning names only the UNCHECKED PR of a batch",
          ("#3737" in message, "#3740" in message), (True, False))


def fail_open_check():
    out = subprocess.run(
        [sys.executable, SUBJECT],
        input="not json at all",
        capture_output=True, text=True,
    )
    check("fails open on an unparseable payload (exit)", out.returncode, 0)
    check("fails open on an unparseable payload (silent)",
          bool(out.stdout.strip()), False)
    missing = subprocess.run(
        [sys.executable, SUBJECT],
        input=json.dumps({"transcript_path": "/nonexistent/path.jsonl"}),
        capture_output=True, text=True,
    ).stdout.strip()
    check("a missing transcript is silent", bool(missing), False)


# --------------------------------------------------------------------------
# Mutation checks: each disables one narrowing and names the case that flips.
# --------------------------------------------------------------------------

MUTATIONS = [
    ("NEARBY_WINDOW = 240", "NEARBY_WINDOW = 100000",
     [FAR_APART], True,
     "the proximity window keeps a distant PR number out of the claim"),
    ("n = re.escape(number)", 'n = "[0-9]+"',
     [OTHER_PR_COMMITS, PLAIN_EMPTY], False,
     "scoping the read to the claimed PR is what rejects another PR's read"),
    ("if not any(pattern.search(call) for call in calls):",
     "if True or not any(pattern.search(call) for call in calls):",
     [RIGHT_PR_COMMITS, PLAIN_EMPTY], True,
     "the evidence gate discharges a sweep that read the commits"),
    ("if not RX_QUERY_TOOL.match(name):",
     "if False and not RX_QUERY_TOOL.match(name):",
     [OWN_REPLY, READ_NOT_DONE], False,
     "the query-tool allowlist is what stops the session's own prose "
     "counting as a read"),
    ("and not RX_MESSAGE_BODY.search(line)]",
     "and True]",
     [OWN_COMMENT, PLAIN_EMPTY], False,
     "the message-body filter is what stops a comment counting as a read"),
    ("if RX_QUERY_COMMAND.search(line)", "if True",
     [BASH_CAT_PATH, PLAIN_EMPTY], False,
     "the shell-client requirement is what stops a file path counting as a "
     "query"),
    ('command = tool_input.get("command")', 'command = json.dumps(tool_input)',
     [call("Bash", {"command": "git log --oneline -5",
                    "description": "state check before closing PR 3737"}),
      PLAIN_EMPTY], False,
     "reading only the command is what stops a free-prose description "
     "supplying the number"),
    ("if RX_CORRECTING_GLOBAL.search(text):",
     "if False and RX_CORRECTING_GLOBAL.search(text):",
     [DESCRIBING_GUARD], True,
     "the global correction gate keeps prose about the guard silent"),
    ("if RX_CORRECTING_LOCAL.search(_sentence(text, match)):",
     "if RX_CORRECTING_LOCAL.search(text):",
     [MIXED_RECAP], False,
     "scoping the basis exemption to its sentence is what stops one "
     "justified close covering an unjustified one"),
    ("if RX_DISPOSITION.search(window):",
     "if True or RX_DISPOSITION.search(window):",
     [STATUS_LINE], True,
     "the disposition cue separates reporting the field from acting on it"),
]


def mutation_checks():
    source = open(SUBJECT, encoding="utf-8").read()
    for anchor, replacement, events, want_fire, label in MUTATIONS:
        if source.count(anchor) != 1:
            check(f"mutation anchor {anchor!r} is unique",
                  source.count(anchor), 1)
            continue
        tmp = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                          encoding="utf-8")
        tmp.write(source.replace(anchor, replacement))
        tmp.close()
        try:
            fired = bool(invoke(events, hook=tmp.name))
        finally:
            os.unlink(tmp.name)
        check(f"mutation {anchor!r}: {label}", fired, want_fire)

    # The output-shape mutation README's "Writing a warn-only hook" names: the
    # guard still fires, but its warning stops reaching anyone.
    anchor = '"systemMessage"'
    if source.count(anchor) != 1:
        check(f"mutation anchor {anchor!r} is unique", source.count(anchor), 1)
        return
    tmp = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                      encoding="utf-8")
    tmp.write(source.replace(anchor, '"reason"'))
    tmp.close()
    try:
        payload = invoke([INCIDENT], hook=tmp.name)
    finally:
        os.unlink(tmp.name)
    check("mutation systemMessage->reason drops the surfaced field",
          "systemMessage" in payload, False)


def main():
    shape_check()
    matrix()
    dedupe_check()
    fail_open_check()
    mutation_checks()
    if SHAPE_ERRORS:
        print(f"FAIL  {len(SHAPE_ERRORS)} fire(s) emitted a payload the "
              f"harness would discard: {SHAPE_ERRORS[0]}")
        return 1
    if failures:
        print(f"\n{failures} failure(s)")
        return 1
    print("\nall no-unchecked-empty-pr-claim checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
