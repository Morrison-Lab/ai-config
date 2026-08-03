"""Test the no-unreviewed-pr guard.

The guard's value is concentrated in the negative cases: a draft PR
legitimately defers review, and a session that already requested a reviewer
must not be nagged. A guard that fires on correct behaviour gets disabled,
and then the case it exists for goes unprotected too.

Fixtures mirror real transcripts: every tool_use carries an `id`, and every
tool_result references it via `tool_use_id`, because the guard correlates a
result to its own call by identity. Crucially, a `gh pr create` command does
NOT embed its PR number -- the number arrives only in the command's result --
so the create fixtures deliberately keep the number OUT of the command and
put it in the result, the shape the position/number-in-command model got
wrong.

Run: python3 hooks/test-no-unreviewed-pr.py hooks/no-unreviewed-pr.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

_n = [0]


def _id():
    _n[0] += 1
    return f"t{_n[0]}"


def use(name, tid=None, **inp):
    """One assistant message with a single tool_use block."""
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tid or _id(), "name": name, "input": inp}]}}


def bash(cmd, tid=None):
    return use("Bash", tid=tid, command=cmd)


def res(tid, body, err=False):
    """One user message with a single tool_result block for `tid`."""
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tid, "content": body,
         "is_error": err}]}}


def results(*pairs):
    """One user message with several tool_result blocks (a batched turn)."""
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tid, "content": body,
         "is_error": err} for (tid, body, err) in pairs]}}


def uses(*triples):
    """One assistant message with several tool_use blocks (a batched turn)."""
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tid, "name": name, "input": inp}
        for (name, inp, tid) in triples]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


URL = "https://github.com/o/r/pull/1038\n"          # a `gh pr create` result
OK = '{"requested_reviewers":[{"login":"Copilot"}]}'  # a successful request
FAIL = '{"status":422,"message":"Review cannot be requested"}'
REQ_CMD = ("gh api repos/o/r/pulls/1038/requested_reviewers -X POST "
           "-f 'reviewers[]=copilot-pull-request-reviewer[bot]'")
# The hook's OWN recovery text quotes the URL (an unquoted `<N>` placeholder is
# a shell redirect), so the single commonest real request shape has the
# `requested_reviewers` endpoint INSIDE double quotes. This must still discharge
# -- blanking every quoted span (not just free-text payload values) erases it.
REQ_CMD_Q = ('gh api "repos/o/r/pulls/1038/requested_reviewers" -X POST '
             "-f 'reviewers[]=copilot-pull-request-reviewer[bot]'")


def create(tid, result=URL, err=False):
    """A realistic `gh pr create`: number in the RESULT, never the command."""
    return [bash("gh pr create --base main --title x --body y", tid=tid),
            res(tid, result, err)]


CASES = []


def case(events, expected, label):
    CASES.append((events, expected, label))


# --- opens with no request block ---
case(create("c") + [say("Opened. Review owed.")], True,
     "gh pr create with no reviewer request blocks")
case([use("create_pull_request", tid="c", title="x", body="y"),
      res("c", '{"number":1038,"html_url":"https://github.com/o/r/pull/1038"}'),
      say("Opened.")], True,
     "the harness create tool with no request blocks")
case([bash("gh pr ready 1038", tid="c"), res("c", "{}"), say("Ready.")], True,
     "gh pr ready with no request blocks")

# --- a successful request discharges; a failed one does not ---
case(create("c") + [bash(REQ_CMD, tid="q"), res("q", OK),
                    say("Opened and requested.")], False,
     "a create keyed from its result is cleared by a numbered request")
case([bash("gh pr create --base main --title x --reviewer "
           "copilot-pull-request-reviewer", tid="c"), res("c", URL),
      say("Opened with a reviewer.")], False,
     "gh pr create --reviewer self-discharges")
case([use("create_pull_request", tid="c", title="x",
          reviewers=["copilot-pull-request-reviewer"]),
      res("c", '{"number":1038}'), say("Opened with a reviewer.")], False,
     "the harness create tool with a reviewers field self-discharges")
# `update_pull_request` marking a PR ready AND requesting reviewers, whose
# reviewer-add fails with a bare `{"status":422}` (no PR number echoed -- the
# ordinary error shape). The PR number is known from the INPUT (`pull_number`),
# so the "failed + no identity in the result" drop must NOT fire: the PR was
# genuinely marked ready with no reviewer, and dropping it would silently
# discharge exactly the dangerous false-negative every round has blocked on.
case([use("update_pull_request", tid="u", owner="o", repo="r",
          pull_number=1038, draft=False,
          reviewers=["copilot-pull-request-reviewer"]),
      res("u", '{"status":422,"message":"Reviewers could not be requested"}',
          err=True),
      say("Marked ready and tried to add a reviewer; it 422'd.")], True,
     "a ready+reviewers edit whose reviewer-add fails keeps the PR tracked")
# The SAME `update_pull_request(draft=False, reviewers=[...])` shape, but the
# reviewer-add fails with PLAIN-LANGUAGE text ("failed"/"error"/"not found") and
# NO 4xx/HTTP shape, with is_error UNSET. The `draft:false` branch appends a
# `self` obligation, kept correctly by the BROAD RX_FAILED. Registering
# `pending[tid]` too (the old code did, unconditionally on `reviewers`) added a
# second, NARROWER (RX_REQ_FAILED) discharge path that runs AFTER the obligations
# loop and `_clear()`s the very obligation the broad check just kept -- silently
# discharging a genuinely-unreviewed PR. The pending path is now withheld when
# draft is False, so only the self path (broad, fail-safe) tracks it.
case([use("update_pull_request", tid="u", owner="o", repo="r",
          pull_number=1038, draft=False,
          reviewers=["copilot-pull-request-reviewer"]),
      res("u", '{"message":"Adding reviewer failed"}', err=False),
      say("Marked ready; the reviewer-add failed in plain language.")], True,
     "a ready+reviewers edit whose reviewer-add fails in plain language tracks")
# The success mirror: the SAME shape whose reviewer-add SUCCEEDS must still
# discharge -- via the self-obligation path (`self and not failed`), now that the
# redundant pending path is gone -- so the fix does not over-block a real success.
case([use("update_pull_request", tid="u", owner="o", repo="r",
          pull_number=1038, draft=False,
          reviewers=["copilot-pull-request-reviewer"]),
      res("u", '{"number":1038,"requested_reviewers":[{"login":"Copilot"}]}'),
      say("Marked ready and added the reviewer.")], False,
     "a ready+reviewers edit whose reviewer-add succeeds discharges")
# The RESERVED case: a pure reviewer-add via update_pull_request with NO draft
# transition is a genuine request that discharges an ALREADY-tracked PR. The
# pending path must still fire here (it is withheld ONLY for draft:false), so a
# prior open is cleared by a later reviewers-only edit.
case([use("create_pull_request", tid="c", owner="o", repo="r", title="x",
          body="y"),
      res("c", '{"number":1038,"html_url":"https://github.com/o/r/pull/1038"}'),
      use("update_pull_request", tid="u", owner="o", repo="r",
          pull_number=1038, reviewers=["copilot-pull-request-reviewer"]),
      res("u", '{"requested_reviewers":[{"login":"Copilot"}]}'),
      say("Opened, then added a reviewer.")], False,
     "a reviewers-only update_pull_request discharges an already-open PR")
# The create counterpart: a create whose reviewer step fails but whose result
# DOES echo the PR number is real and must stay tracked (identity known from
# the result rather than the input).
case([use("create_pull_request", tid="c", owner="o", repo="r", title="x",
          reviewers=["copilot-pull-request-reviewer"]),
      res("c", '{"number":1038,"errors":[{"message":"cannot be requested"}]}',
          err=True),
      say("Opened with a reviewer; the reviewer step failed.")], True,
     "a create+reviewers whose reviewer step fails but echoes the number tracks")
# And when the failure body does NOT echo the number (the ordinary error shape),
# a create+reviewers (`self`) obligation must STILL stay tracked: its number is
# never known at append time, so a numberless failure cannot tell "the create
# failed, no PR" from "the PR was created and only the reviewer step failed".
# Dropping it would silently discharge a genuinely-created, unreviewed PR -- the
# dangerous direction. It stays tracked (unclearable, a safe over-warn), for both
# the structured tool and the `gh pr create --reviewer` shell form.
case([use("create_pull_request", tid="c", owner="o", repo="r", title="x",
          reviewers=["copilot-pull-request-reviewer"]),
      res("c", '{"status":422,"message":"Reviewers could not be requested"}',
          err=True),
      say("Opened with a reviewer; the reviewer step failed.")], True,
     "a create+reviewers reviewer-fail with NO number in the body still tracks")
case([bash("gh pr create --reviewer copilot-pull-request-reviewer[bot] "
           "--base main --title x", tid="c"),
      res("c", '{"status":422,"message":"Reviewers could not be requested"}',
          err=True),
      say("Opened via gh with a reviewer; the reviewer step failed.")], True,
     "a `gh pr create --reviewer` numberless reviewer-fail still tracks")
case(create("c") + [bash(REQ_CMD, tid="q"), res("q", FAIL, err=True),
                    say("Requested.")], True,
     "a FAILED (422) request does not discharge it")

# --- create and request CHAINED into one Bash call (one tool_use_id) ---
# `failed` is one flag over the whole result body, so a trailing request's 422
# must NOT be read as the create failing and silently drop the (real,
# unreviewed) PR. This is the dangerous direction -- a genuinely-opened PR the
# guard goes silent about.
case([bash("gh pr create --title x --body y && "
           "gh api repos/o/r/pulls/1038/requested_reviewers -X POST", tid="c"),
      res("c", "https://github.com/o/r/pull/1038\n"
               '{"status":422,"message":"cannot be requested"}'),
      say("Opened then tried to request in one call; the request 422'd.")],
     True, "a chained create + FAILED request in one call keeps the PR tracked")
# The realistic form: `gh pr create --reviewer` creates the PR, then its
# reviewer step 422s -- gh prints the URL and exits non-zero. The PR is real
# and unreviewed, so the obligation must stay.
case([bash("gh pr create --base main --title x --reviewer "
           "copilot-pull-request-reviewer", tid="c"),
      res("c", "https://github.com/o/r/pull/1038\n"
               '{"status":422,"message":"Reviewers could not be requested"}',
          err=True),
      say("Created, but the reviewer step failed.")], True,
     "create --reviewer whose reviewer step 422s still blocks (PR created)")
# The mirror: both halves succeed in one call -> discharged.
case([bash("gh pr create --title x --body y && "
           "gh api repos/o/r/pulls/1038/requested_reviewers -X POST", tid="c"),
      res("c", "https://github.com/o/r/pull/1038\n"
               '{"requested_reviewers":[{"login":"Copilot"}]}'),
      say("Opened and requested in one call; both succeeded.")], False,
     "a chained create + successful request in one call discharges")
# A create that itself fails carries NO PR URL/number, so no PR was opened.
case([bash("gh pr create --title x --body y", tid="c"),
      res("c", '{"status":422,"message":"validation failed"}', err=True),
      say("The create itself failed.")], False,
     "a create that itself fails opens no PR")

# --- request discharge is scoped to the REQUEST's own outcome ---
# An UNRELATED failing command chained (via `;`) with a genuinely successful
# request in one call must still discharge: the request exits 0 and the only
# failure text (`command not found: error`) belongs to the other command, not
# to an API failure. Gating the discharge on the whole-body `failed` flag would
# nag forever after a real, successful request (the safe-but-real bug).
case(create("c") + [
    bash("some_check.sh; gh api repos/o/r/pulls/1038/requested_reviewers "
         "-X POST", tid="q"),
    res("q", "some_check.sh: command not found: error\n"
             '{"requested_reviewers":[{"login":"Copilot"}]}'),
    say("Ran an unrelated check, then requested, in one call.")], False,
     "an unrelated failing command chained with a successful request discharges")
# The mirror: a chained request that ITSELF 422s (a real API failure shape,
# even with is_error unset) must NOT discharge -- the narrow request-failure
# signal still catches a genuine 4xx.
case(create("c") + [
    bash("some_check.sh; gh api repos/o/r/pulls/1038/requested_reviewers "
         "-X POST", tid="q"),
    res("q", "some_check.sh: ok\n"
             '{"status":422,"message":"cannot be requested"}'),
    say("Ran a check, then a request that 422'd.")], True,
     "a chained request that itself 422s does not discharge")

# --- the discharge fires only on POSITIVE success of the request's OWN result,
# which is reliable only when the request is the last/sole simple command ---
# A genuinely-FAILED request whose failure is NOT 4xx-shaped -- a network error,
# a 5xx, a timeout, a bare auth message -- must still block. `is_error` is the
# only signal that catches these, and it is authoritative because the request
# is the sole command in the call. (Dropping is_error for the api form, as an
# earlier revision did, silently discharged exactly this case -- the dangerous
# direction, since no reviewer was ever actually requested.)
case(create("c") + [
    bash("gh api repos/o/r/pulls/1038/requested_reviewers -X POST", tid="q"),
    res("q", "gh: Could not resolve host: api.github.com\n"
             "curl: (6) Could not resolve host", err=True),
    say("Opened and tried to request; the request failed to connect.")], True,
     "a sole api request that fails without a 4xx body does not discharge")
# A sole successful api request MUST still discharge (guards against the
# fail-safe rule over-blocking everything).
case(create("c") + [
    bash("gh api repos/o/r/pulls/1038/requested_reviewers -X POST", tid="q"),
    res("q", '{"requested_reviewers":[{"login":"Copilot"}]}'),
    say("Requested a reviewer, successfully.")], False,
     "a sole successful api request discharges")
# A request chained AHEAD of another command is AMBIGUOUS: is_error belongs to
# the trailing command, and no other signal recovers the request's own outcome
# from the single combined result blob. The guard fails toward NOT discharging
# (it keeps blocking -- the safe over-warn direction) rather than risk clearing
# a request that may have failed. Here the request actually succeeded, so the
# block is a deliberate over-warn, not a false positive about failure.
case(create("c") + [
    bash("gh api repos/o/r/pulls/1038/requested_reviewers -X POST "
         "-f reviewers=x; gh pr view 1038 --jq .nonexistent", tid="q"),
    res("q", '{"requested_reviewers":[{"login":"Copilot"}]}\n'
             "jq: error: nonexistent field", err=True),
    say("Requested a reviewer, then a verify step that errored.")], True,
     "an api request chained ahead of a failing command does not discharge")
# The DANGEROUS variant, and why the chained-ahead case must block regardless
# of `is_error`: a request that itself FAILED non-4xx, chained ahead of a
# command that SUCCEEDED, leaves is_error=False (the trailing success) with no
# 4xx body -- so `err`/RX_REQ_FAILED alone would silently discharge a genuinely
# failed request. The ambiguity guard (a chained-ahead request never
# discharges) is the only thing that blocks it.
case(create("c") + [
    bash("gh api repos/o/r/pulls/1038/requested_reviewers -X POST "
         "|| echo continuing", tid="q"),
    res("q", "curl: (6) Could not resolve host\ncontinuing"),
    say("The request failed to connect, but a trailing echo succeeded.")],
     True,
     "a failed request whose trailing command succeeds does not discharge")
# A CLI `--add-reviewer` request can fail through GraphQL with NO 4xx body, so
# `is_error` is what catches it -- a genuinely failed sole CLI request must
# still block, since RX_REQ_FAILED alone would not.
case(create("c") + [
    bash("gh pr edit 1038 -R o/r --add-reviewer baduser", tid="q"),
    res("q", "GraphQL: Could not resolve to a User with the login of "
             "'baduser'", err=True),
    say("A CLI add-reviewer that failed without a 4xx body.")], True,
     "a failed CLI add-reviewer with no 4xx body does not discharge")

# --- draft carve-out ---
case([bash("gh pr create --draft --base main --title x", tid="c"),
      res("c", URL), say("Draft.")], False,
     "a draft PR does not block")
case([use("create_pull_request", tid="c", title="x", draft=True),
      res("c", '{"number":1038}'), say("Draft.")], False,
     "the harness draft flag does not block")
case([bash("gh pr create --draft --title x", tid="c"), res("c", URL),
      bash("gh pr ready 1038", tid="r"), res("r", "{}"), say("Ready now.")],
     True, "readying a draft later re-arms the guard")
case(create("c") + [bash("gh pr ready 1038 --undo", tid="u"), res("u", "{}"),
                    say("Held as a draft.")], False,
     "gh pr ready --undo is a draft action, not an open one")
case([use("create_pull_request", tid="c", title="x", body="y"),
      res("c", '{"number":1038,"html_url":"https://github.com/o/r/pull/1038"}'),
      use("update_pull_request", tid="u", owner="o", repo="r",
          pull_number=1038, draft=True), res("u", "{}"),
      say("Converted back to draft.")], False,
     "update_pull_request draft:true defers review again")
# A draft transition clears its PR only on a NON-failed result: a `draft:true`
# edit whose conversion 422s leaves the PR ready, so the obligation must stay
# outstanding rather than be cleared at tool_use time (the dangerous direction).
case([use("update_pull_request", tid="o", owner="o", repo="r",
          pull_number=1038, draft=False), res("o", '{"number":1038}'),
      use("update_pull_request", tid="d", owner="o", repo="r",
          pull_number=1038, draft=True),
      res("d", '{"status":422,"message":"could not convert"}', err=True),
      say("Tried to hold it as a draft; the conversion failed.")], True,
     "a failed draft:true conversion keeps the ready PR tracked")
case(create("c") + [bash("gh pr ready 1038 -R o/r --undo", tid="d"),
                    res("d", "failed to convert PR to draft", err=True),
                    say("Tried to undo ready; it failed.")], True,
     "a failed gh pr ready --undo keeps the ready PR tracked")
# A draft transition chained AHEAD of a succeeding command has an is_error that
# belongs to the LATER command, so the clear cannot trust it -- exactly the
# ordering hazard the reviewer-request discharge already guards against. Here
# the `--undo` genuinely fails ("cannot revert to draft state") but `echo done`
# succeeds (is_error=False) and the failure text carries no error-word/4xx, so
# the broad whole-body flag alone would wrongly read success. The clear must
# NOT fire: silently dropping this leaves a ready, unreviewed PR unguarded.
case(create("c") + [bash("gh pr ready 1038 --undo; echo done", tid="u"),
                    res("u", "pull request cannot revert to draft state\ndone",
                        err=False),
                    say("Tried to undo ready; unclear if it worked.")], True,
     "a failed --undo chained ahead of a success keeps the PR tracked")
case(create("c") + [bash("gh pr ready 1038 --undo || echo done", tid="u"),
                    res("u", "could not convert\ndone", err=False),
                    say("Tried to undo ready with a fallback.")], True,
     "a failed --undo with a `|| echo` fallback keeps the PR tracked")
# The ordering guard is about POSITION, not about forbidding chaining: a draft
# action that IS the last simple command (even preceded by another command)
# still has an authoritative is_error, so a genuine success still clears.
case(create("c") + [bash("echo start; gh pr ready 1038 --undo", tid="u"),
                    res("u", "start\n{}", err=False),
                    say("Held as a draft after a preamble.")], False,
     "a successful --undo as the last command still clears")
# The `last` check must find the ACTUAL draft transition structurally, not just
# inspect whichever command happens to be last. A failed `--undo` chained ahead
# of an UNRELATED command whose argv merely contains a `--draft`/`draft=true`
# token -- a `gh pr comment` whose --body is `draft=true`, or a follow-up
# `gh pr create --draft` that succeeds -- must NOT be read as the transition
# being last. Both would silently discharge #1038 (still ready, never reviewed)
# if `_argv_draft` matched a bare token or `_draft_last` looked only at cmds[-1].
case(create("c") + [bash('gh pr ready 1038 --undo; gh pr comment 42 '
                         '--body "draft=true"', tid="u"),
                    res("u", "pull request cannot revert to draft state\n"
                        "posted comment 42", err=False),
                    say("Tried to undo; also commented.")], True,
     "a failed --undo ahead of a draft-token-bearing command keeps it tracked")
case(create("c") + [bash("gh pr ready 1038 --undo; gh pr create --draft "
                         "--title y --body z", tid="u"),
                    res("u", "pull request cannot revert to draft state\n"
                        "https://github.com/o/r/pull/1099", err=False),
                    say("Tried to undo; opened a fresh draft.")], True,
     "a failed --undo ahead of a successful `create --draft` keeps it tracked")
# The gh-scope must not OVER-match: a draft-token inside an unrelated command
# that PRECEDES a genuine successful `--undo` (the real last command) must still
# let the undo clear -- the scope drops the decoy, so the undo is found last.
case(create("c") + [bash('gh pr comment 42 --body "draft=true"; '
                         "gh pr ready 1038 --undo", tid="u"),
                    res("u", "posted comment 42\n{}", err=False),
                    say("Commented, then held as a draft.")], False,
     "a successful --undo last, after a draft-token decoy, still clears")
# A `gh api ... -f draft=true` is NOT a draft transition: REST PATCH /pulls/{n}
# does not accept `draft` (title/body/state/base/maintainer_can_modify only), so
# the call does not convert the PR -- it stays ready. Treating it as a draft
# conversion would DISCHARGE on the no-op's success, silently clearing a
# still-ready PR. It must keep the PR tracked, whether the field is quoted (the
# gate's _scrub_all blanks it) or not (matched by the gate but draft_ident finds
# no structural transition, so `last` is False and the clear is withheld).
case(create("c") + [bash("gh api repos/o/r/pulls/1038 -f 'draft=true' -X PATCH",
                         tid="u"),
                    res("u", '{"number":1038,"draft":false}', err=False),
                    say("Tried to draft via the REST API.")], True,
     "a quoted `gh api -f draft=true` does not clear (REST cannot draft)")
case(create("c") + [bash("gh api repos/o/r/pulls/1038 -f draft=true -X PATCH",
                         tid="u"),
                    res("u", '{"number":1038,"draft":false}', err=False),
                    say("Tried to draft via the REST API.")], True,
     "an unquoted `gh api -f draft=true` does not clear (REST cannot draft)")

# --- per-PR identity: one request does not clear another PR ---
case([bash("gh pr create --title a", tid="a"), res("a", URL),
      bash("gh pr create --title b",
           tid="b"), res("b", "https://github.com/o/r/pull/1040\n"),
      bash("gh api repos/o/r/pulls/1040/requested_reviewers -X POST", tid="q"),
      res("q", OK), say("Opened both, requested one.")], True,
     "requesting for one PR does not clear another's obligation")
case([bash("gh pr create --title a", tid="a"), res("a", URL),
      bash("gh api repos/o/r/pulls/1038/requested_reviewers -X POST", tid="q"),
      res("q", OK),
      bash("gh pr create --draft --title b",
           tid="b"), res("b", "https://github.com/o/r/pull/1040\n"),
      say("One reviewed, one draft.")], False,
     "a later draft does not silence an already-satisfied PR")

# --- multi-repository identity (same PR number, two repos) ---
case([bash("gh pr create -R o1/r --title a", tid="a"),
      res("a", "https://github.com/o1/r/pull/10\n"),
      bash("gh pr create -R o2/r --title b", tid="b"),
      res("b", "https://github.com/o2/r/pull/10\n"),
      bash("gh api repos/o1/r/pulls/10/requested_reviewers -X POST", tid="q"),
      res("q", OK), say("Opened in two repos, requested one.")], True,
     "same PR number in two repos: requesting one leaves the other")
# Requesting the SAME repo's PR twice must not discharge the OTHER repo's
# same-numbered PR. A number-only identity would clear both here; owner/repo
# in the identity is what keeps o2/r#10 outstanding.
case([bash("gh pr create -R o1/r --title a", tid="a"),
      res("a", "https://github.com/o1/r/pull/10\n"),
      bash("gh pr create -R o2/r --title b", tid="b"),
      res("b", "https://github.com/o2/r/pull/10\n"),
      bash("gh api repos/o1/r/pulls/10/requested_reviewers -X POST", tid="q1"),
      res("q1", OK),
      bash("gh api repos/o1/r/pulls/10/requested_reviewers -X POST", tid="q2"),
      res("q2", OK), say("Requested o1's PR twice.")], True,
     "requesting one repo's PR twice does not clear the other repo's")

# --- open IDENTITY is structural: a decoy verb in a chained open does not
# misattribute the obligation ---
# `gh pr view 42 && gh pr ready` checks an unrelated PR #42, then readies the
# CURRENT branch's own PR (#1038, learned from the ready result). A whole-string
# identity scan matched the decoy `pr view 42` and mislabeled the obligation as
# #42 -- so a later, entirely unrelated request for #42 discharged the (real,
# unreviewed) #1038. open_ident scopes identity to the `gh pr ready` command
# itself, so the obligation is #1038 (backfilled from its result) and the #42
# request cannot clear it.
case([bash("gh pr view 42 && gh pr ready", tid="c"),
      res("c", 'Pull request o/r#1038 is marked as "ready for review"'),
      bash("gh api repos/o/r/pulls/42/requested_reviewers -X POST", tid="q"),
      res("q", OK),
      say("Checked #42, readied the current PR, later requested on #42.")], True,
     "a decoy verb before a chained open does not misattribute the obligation")
# The mirror control: the SAME open, but the later request targets the ACTUAL
# readied PR (#1038) -- it must discharge, proving identity resolved to #1038.
case([bash("gh pr view 42 && gh pr ready", tid="c"),
      res("c", 'Pull request o/r#1038 is marked as "ready for review"'),
      bash("gh api repos/o/r/pulls/1038/requested_reviewers -X POST", tid="q"),
      res("q", OK),
      say("Checked #42, readied #1038, then requested on #1038.")], False,
     "a chained open resolves its own PR identity (a request for it discharges)")
# An explicit `gh pr ready <N>` chained after a decoy verb takes ITS OWN number,
# not the decoy's: `gh pr checks 1029 && gh pr ready 1038` opens #1038, so a
# request for the decoy #1029 must not discharge it.
case([bash("gh pr checks 1029 && gh pr ready 1038", tid="c"), res("c", "{}"),
      bash("gh api repos/o/r/pulls/1029/requested_reviewers -X POST", tid="q"),
      res("q", OK),
      say("Checked #1029, readied #1038, requested on #1029.")], True,
     "a decoy verb does not override an explicit `gh pr ready <N>` identity")

# --- id-correlated results: an unrelated batched result must not mislead ---
case(create("c") + [
    uses(("Bash", {"command": "gh pr checks 1038"}, "chk"),
         ("Bash", {"command": REQ_CMD}, "q")),
    results(("chk", '{"conclusion":"failure"}', False), ("q", OK, False)),
    say("Checked and requested.")], False,
     "a batched unrelated failing result does not block a real request")
case(create("c") + [
    uses(("Bash", {"command": REQ_CMD}, "q"),
         ("Bash", {"command": "gh pr checks 1038"}, "chk")),
    results(("q", OK, False), ("chk", '{"conclusion":"failure"}', False)),
    say("Requested and checked.")], False,
     "request success is read from its own result regardless of batch order")
# The sharp case: an unrelated call in the batch returns a genuine 4xx/error.
# Positional correlation would attribute that failure to the real request and
# block; id-correlation reads only the request's OWN (successful) result.
case(create("c") + [
    uses(("Bash", {"command": "gh pr view 1038 --json state"}, "v"),
         ("Bash", {"command": REQ_CMD}, "q")),
    results(("v", '{"status":404,"message":"not found error"}', False),
            ("q", OK, False)),
    say("Viewed then requested.")], False,
     "an unrelated 4xx result in the batch does not fail the real request")

# --- a read-only GET of the endpoint is NOT a request ---
case(create("c") + [
    bash("gh api repos/o/r/pulls/1038/requested_reviewers", tid="g"),
    res("g", OK), say("Checked who is requested.")], True,
     "a read-only GET of requested_reviewers does not discharge")

# --- a gh action QUOTED inside another command's argument is not an action ---
# This repo's docs and this hook's own recovery text quote these strings, so a
# comment/body containing them must neither forge nor discharge an obligation.
case([bash('gh pr comment 1038 --body "next time run gh pr create first"',
           tid="m"), res("m", "{}"), say("Reminded someone.")], False,
     "a quoted 'gh pr create' in a --body forges no obligation")
case(create("c") + [
    bash('gh pr comment 42 --body "fix: run gh api '
         'repos/o/r/pulls/1038/requested_reviewers -X POST"', tid="m"),
    res("m", "{}"), say("Opened 1038, commented on 42.")], True,
     "a quoted requested_reviewers -X POST does not discharge a real PR")
case(create("c") + [
    bash("gh pr comment 42 --body-file - <<'EOF'\n"
         "run gh api repos/o/r/pulls/1038/requested_reviewers -X POST\nEOF",
         tid="m"), res("m", "{}"), say("Opened 1038, heredoc comment on 42.")],
     True, "a heredoc body quoting the recovery snippet does not discharge")
# A REAL create whose --body is a heredoc must still be detected as an open.
case([bash("gh pr create --title x --body \"$(cat <<'EOF'\n"
           "the body\nEOF\n)\"", tid="c"), res("c", URL),
      say("Opened with a heredoc body.")], True,
     "a real create with a heredoc body still blocks")
# The mirror of the two above: the hook's OWN recovery command quotes its URL,
# so a GENUINE quoted request must still discharge. A blanket blank of every
# quote (the round-4 over-correction) would erase `requested_reviewers` from
# the URL and leave the obligation standing forever after the user runs exactly
# the command the hook printed -- the single most common real request shape.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    say("Opened and requested with the quoted recovery cmd.")],
     False, "the quoted-URL recovery command still discharges")
# A quoted-URL GET (no POST) still must NOT discharge: the URL survives the
# payload-only scrub, so is_request must still gate on the mutating method.
case(create("c") + [
    bash('gh api "repos/o/r/pulls/1038/requested_reviewers"', tid="g"),
    res("g", OK), say("Checked who is requested, quoted URL.")], True,
     "a quoted-URL read-only GET does not discharge")
# A bare `echo` of the create string (an example NOT in a --body/heredoc) must
# still forge nothing: open-detection blanks every quote, so the leading word
# is `echo`, not `gh pr create`.
case([bash('echo "gh pr create"', tid="e"), res("e", ""),
      say("Just echoed an example.")], False,
     "a quoted create outside any payload flag forges no obligation")

# --- request detection is STRUCTURAL: an embedded example never discharges ---
# Round 5's payload-flag scrub blanked quoted text only next to six named
# flags, but is_request/cmd_ident scanned the whole string -- so ANY other
# embedding mechanism (a bare echo, a herestring, `gh pr edit` quoted, ...)
# still discharged a real obligation. Request detection now parses argv per
# simple command, so the request tokens count only as the argv of an actual
# gh api / gh pr edit invocation.
case(create("c") + [
    bash('echo "run gh api repos/o/r/pulls/1038/requested_reviewers -X POST"',
         tid="e"), res("e", ""), say("Just echoed the recovery snippet.")],
     True, "a bare echo of the recovery snippet does not discharge")
case(create("c") + [
    bash("gh pr comment 42 --body-file - <<< "
         '"see repos/o/r/pulls/1038/requested_reviewers -X POST"', tid="m"),
    res("m", "{}"), say("Opened 1038, herestring comment on 42.")], True,
     "a herestring quoting the recovery snippet does not discharge")
case(create("c") + [
    bash('echo "gh pr edit 1038 --add-reviewer bob"', tid="e"), res("e", ""),
    say("Echoed an add-reviewer example.")], True,
     "a quoted 'gh pr edit --add-reviewer' does not discharge")
# The mirror: a GENUINE `gh pr edit --add-reviewer` (an inherently mutating
# request form, no separate POST) must still discharge.
case(create("c") + [
    bash("gh pr edit 1038 --add-reviewer copilot-pull-request-reviewer",
         tid="q"), res("q", "{}"), say("Requested via edit.")], False,
     "a real gh pr edit --add-reviewer discharges")
# The hook's own recovery command spans two lines with a `\` continuation. The
# structural parser must join it, not split it into a URL-only command and a
# POST-only command (which would leave the obligation standing forever after
# the user runs exactly what the hook printed).
case(create("c") + [
    bash('gh api "repos/o/r/pulls/1038/requested_reviewers" \\\n'
         "  -X POST -f 'reviewers[]=copilot-pull-request-reviewer[bot]'",
         tid="q"), res("q", OK), say("Ran the multi-line recovery command.")],
     False, "the multi-line (\\-continued) recovery command still discharges")

# --- separator set: newline separates, redirects attach ---
# A NEWLINE separates two commands exactly as `;` does. shlex drops `\n` as
# whitespace, so without converting it to a separator the two commands merge
# into one, the request registers as `last`, and its own genuine failure is
# masked by the trailing command's success -- a SILENT DISCHARGE. Mirrors the
# `;` case at "a failed request whose trailing command succeeds" above.
case(create("c") + [
    bash("gh api repos/o/r/pulls/1038/requested_reviewers -X POST\necho done",
         tid="q"),
    res("q", "curl: (6) Could not resolve host\ndone", err=False),
    say("Requested (failed) then echoed, on two lines.")], True,
     "a newline-joined failed request whose trailing command succeeds tracks")
# The mirror: a newline-joined SUCCESSFUL request followed by a command is still
# ambiguous (the request is not the last simple command), so it over-warns
# rather than risk a silent discharge -- the same rule the `;`-joined case uses.
case(create("c") + [
    bash("gh api repos/o/r/pulls/1038/requested_reviewers -X POST\necho done",
         tid="q"),
    res("q", '{"requested_reviewers":[{"login":"Copilot"}]}\ndone', err=False),
    say("Requested (ok) then echoed, on two lines.")], True,
     "a newline-joined request ahead of another command does not discharge")
# A trailing REDIRECT (`> /dev/null`, `2>&1`) attaches to the command, it does
# not start a new one. Treating `<`/`>` as separators split a genuinely sole,
# successful request into two "commands", so it never registered as `last` and
# never discharged -- a permanent nag. A redirect must leave the request as the
# sole/last command so it discharges normally.
case(create("c") + [
    bash('gh api "repos/o/r/pulls/1038/requested_reviewers" -X POST '
         "-f 'reviewers[]=copilot' > /dev/null", tid="q"),
    res("q", "", err=False),
    say("Requested with output redirected to /dev/null.")], False,
     "a sole successful request with a trailing > redirect still discharges")
case(create("c") + [
    bash("gh pr edit 1038 --add-reviewer copilot 2>&1", tid="q"),
    res("q", "{}", err=False),
    say("Added a reviewer with 2>&1.")], False,
     "a sole add-reviewer with a 2>&1 redirect still discharges")

# --- a bare `gh pr ready` (no number) must be dischargeable ---
# `gh pr ready` with no argument readies the current branch's PR -- ordinary
# usage. RX_CMD_VERB needs a digit, so the command yields no number and the
# obligation is appended with num=None. gh's success line is `Pull request
# owner/repo#N is marked as "ready for review"` -- an owner/repo#N shape
# result_ident must recognize, or the number never backfills and _clear() (which
# will not touch a num=None obligation) can NEVER discharge it: the guard would
# then block every message for the rest of the session (a wedge).
READY_OUT = 'Pull request o/r#1038 is marked as "ready for review"'
case([bash("gh pr ready", tid="r"), res("r", READY_OUT),
      bash(REQ_CMD, tid="q"), res("q", OK),
      say("Readied the current branch's PR, then requested.")], False,
     "a bare `gh pr ready` is discharged by a later request (num backfilled)")
case([bash("gh pr ready", tid="r"), res("r", READY_OUT),
      say("Readied the current branch's PR; no reviewer yet.")], True,
     "a bare `gh pr ready` with no request still blocks (num resolved)")

# --- a 4xx failure body survives json.dumps' escaping ---
# A string tool-result body is `json.dumps()`-wrapped in scan(), so a `{"status":
# 422}` body arrives as `\"status\":422`. The failure regexes must match that
# escaped shape, not only a bare `"status":422` -- otherwise a sole request that
# failed with a 4xx body but is_error UNSET (no `HTTP 4xx` text) would discharge.
case(create("c") + [
    bash("gh api repos/o/r/pulls/1038/requested_reviewers -X POST", tid="q"),
    res("q", '{"status":422,"message":"nope"}', err=False),
    say("Requested; it 422'd with is_error unset.")], True,
     "a sole request 422ing with is_error unset (escaped body) does not discharge")

# --- non-shell tools must never be text-matched ---
case([use("create", tid="w", path="hooks/no-unreviewed-pr.py",
          file_text="matches gh pr create and requested_reviewers"),
      res("w", "ok"), say("Wrote the hook file.")], False,
     "writing a file mentioning the CLI strings creates no obligation")
case(create("c") + [
    use("create", tid="w", path="doc.md",
        file_text="see requested_reviewers"), res("w", "ok"),
    say("Documented.")], True,
     "a file mentioning requested_reviewers does not discharge")

# --- sessions that opened no PR, and a bare re-request ---
case([bash("git status --short", tid="g"), res("g", ""), say("All clean.")],
     False, "a session that opened no PR does not block")
case([bash("gh api repos/o/r/pulls/1029/requested_reviewers -X POST", tid="q"),
      res("q", OK), say("Re-requested on #1029.")], False,
     "a bare re-request with no open does not block")

# The draft-before-open ordering is load-bearing: `gh pr ready --undo` matches
# RX_OPEN too, so only checking RX_DRAFT first keeps it a draft action. Inspect
# the actual obligation state, not just the block decision.
case(create("c") + [bash("gh pr ready 1038 --undo", tid="u"), res("u", "{}")],
     "ordering", "RX_DRAFT must be checked before RX_OPEN")


def block_of(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        out = subprocess.run(
            [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=tempfile.mkdtemp()),
        ).stdout
        return '"decision": "block"' in out or '"decision":"block"' in out
    finally:
        os.unlink(path)


def obligations_of(events):
    spec = importlib.util.spec_from_file_location("_h", HOOK)
    hookmod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hookmod)
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        obs, _ = hookmod.scan(path)
        return obs
    finally:
        os.unlink(path)


def main():
    passes = failures = 0
    for events, expected, label in CASES:
        if expected == "ordering":
            obs = obligations_of(events)
            ok = "1038" not in {o["num"] for o in obs}
            if ok:
                print(f"PASS: {label}")
                passes += 1
            else:
                print(f"FAIL: {label} (#1038 still open after --undo)")
                failures += 1
            continue
        got = block_of(events)
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected block={expected}, got {got})")
            failures += 1

    # Recovery commands must be copy-pasteable: an unquoted `<` is a shell
    # redirect, so a placeholder-bearing argument has to be quoted.
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in create("c") + [say("Opened it.")]:
            fh.write(json.dumps(e) + "\n")
    out = subprocess.run(
        [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
        capture_output=True, text=True,
        env=dict(os.environ, TMPDIR=tempfile.mkdtemp()),
    ).stdout
    os.unlink(path)
    reason = json.loads(out).get("reason", "") if out.strip() else ""
    bad = [ln for ln in reason.splitlines()
           if ln.strip().startswith("gh ") and "<" in ln
           and '"' not in ln and "'" not in ln]
    if not bad:
        print("PASS: recovery commands quote their placeholders")
        passes += 1
    else:
        print(f"FAIL: unquoted placeholder in recovery command: {bad[:1]}")
        failures += 1

    out = subprocess.run(
        [sys.executable, HOOK], input='{"transcript_path": "/nonexistent"}',
        capture_output=True, text=True,
    )
    if out.returncode == 0 and "block" not in out.stdout:
        print("PASS: fails open on an unreadable transcript")
        passes += 1
    else:
        print("FAIL: should fail open on an unreadable transcript")
        failures += 1

    # Sentinel scope: within ONE transcript the guard fires at most once per
    # message, but a DIFFERENT transcript ending with the same recap must not
    # inherit that suppression. Share one TMPDIR so the sentinel files persist
    # across runs, the way they do within a real machine's temp dir.
    tmp = tempfile.mkdtemp()
    env = dict(os.environ, TMPDIR=tmp)

    def once(events, transcript_name):
        p = os.path.join(tmp, transcript_name)
        with open(p, "w") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")
        out = subprocess.run(
            [sys.executable, HOOK], input=json.dumps({"transcript_path": p}),
            capture_output=True, text=True, env=env).stdout
        return "block" in out

    ev = create("c") + [say("Opened it.")]
    first = once(ev, "sessionA.jsonl")
    repeat = once(ev, "sessionA.jsonl")
    other = once(ev, "sessionB.jsonl")
    if first and not repeat and other:
        print("PASS: sentinel is per-message and per-transcript")
        passes += 1
    else:
        print(f"FAIL: sentinel scope wrong "
              f"(first={first} repeat={repeat} other={other})")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
