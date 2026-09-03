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

Every case runs against a PINNED clock, past the Copilot moratorium the
subject now honours -- see `RUNNER` below for why the pin is injected by
import rather than by an environment variable.

Run: python3 hooks/test-no-unreviewed-pr.py hooks/no-unreviewed-pr.py
"""
import datetime
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

# The guard is inert while the Copilot moratorium stands (`MORATORIUM_END` in
# the subject), so every case below would pass vacuously against the real
# clock -- "no block" for the right reason and the wrong one are the same
# observation. So the subject is driven at a fixed post-moratorium date.
#
# The date is injected by IMPORTING the subject and overriding its `_today`,
# not by an environment variable the subject reads. A clock the subject read
# from the environment would be a one-variable bypass of the guard in
# production, which is exactly the dangerous direction its discharge paths
# already refuse; a test-side override is unavailable to any session.
RUNNER = """
import datetime, importlib.util, sys
spec = importlib.util.spec_from_file_location("_h", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m._today = lambda: datetime.date.fromisoformat(sys.argv[2])
sys.exit(m.main())
"""

# One day after the moratorium ends, so the guard is live for the cases that
# are about anything else.
#
# DERIVED from the subject's own constant rather than written out. A literal
# date here expires when `MORATORIUM_END` moves past it, putting every case
# below back inside the moratorium, where the guard returns at the first line
# of `main()`.
#
# Measured 2026-09-02, by reverting the literals and running them against the
# December constant: 92 passed, 88 failed. NOT a silent whole-file vacuum ---
# the split is what matters. Every case expecting a block FAILS loudly, since
# an inert guard blocks nothing; every true-negative case PASSES vacuously,
# for the wrong reason. So the hazard is half the suite going quiet while the
# other half screams, which is noisy enough to notice but leaves the passing
# half meaning nothing.
#
# An earlier version of this comment claimed the whole file would pass
# vacuously, on an unrun inference from a partially-fixed run. Deriving the
# date is the right fix either way; the reason it was needed is smaller and
# differently shaped than that claim said.
def _moratorium_end():
    spec = importlib.util.spec_from_file_location("_subject_const", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.MORATORIUM_END


AFTER = (_moratorium_end() + datetime.timedelta(days=1)).isoformat()


def hook_argv(when=AFTER):
    """Subject invocation with the clock pinned to `when`."""
    return [sys.executable, "-c", RUNNER, HOOK, when]

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


# One push/no-push corpus for `_argv_push`, the sole authority both this
# hook and no-push-without-self-review.py consult (ai-config#1935, #1920).
PUSH_CORPUS = [
    ("git push origin main", True),
    ("git -C /tmp/wt push origin HEAD", True),
    ("git push -o -n origin feature", True),
    ("git push --receive-pack -d origin feature", True),
    ("git push --push-option=-n origin x", True),
    ("git push -on origin x", True),
    ("git push -o ci.skip origin main", True),
    ("git push -- origin -n", True),
    # git reads the exclusions last-wins (measured on git 2.43.0: each of
    # these moves the remote ref), so a later --no- form restores the push.
    ("git push -n --no-dry-run origin main", True),
    ("git push --dry-run --no-dry-run origin main", True),
    ("git push --delete --no-delete origin main", True),
    ("git push -d --no-delete origin main", True),
    ("git push --no-dry-run -n origin main", False),
    # After an ambiguous abbreviation git refuses the command outright, so
    # the classification is immaterial; pinned so a change is deliberate.
    ("git push --rec -n origin main", False),
    ("git push --dry-run origin HEAD", False),
    ("git push origin --delete old", False),
    ("git push -qn origin x", False),
    ("git push --dry origin x", False),
    ("git push --del origin x", False),
    ("gh pr comment 1 --body 'git push'", False),
]
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
# --- the `self` (create+reviewer) discharge is guarded like pending[tid] ---
# `self` comes from request_ident over the WHOLE command, so the matched request
# may be a NON-LAST command whose own failure is masked by a trailing success.
# Here `gh pr edit --add-reviewer` (index 1 of 3) genuinely fails with GraphQL
# text matching none of RX_FAILED's alternatives, but the trailing `gh pr view`
# succeeds (is_error=False) -- so the coarse whole-body `failed` is False. The
# request is not the last simple command, so the discharge must be withheld
# (the same last-command guard the pending[tid] path uses); otherwise the PR is
# silently discharged with its reviewer-add having failed.
case([bash("gh pr create --title x --body y && "
           "gh pr edit --add-reviewer copilot-pull-request-reviewer[bot]; "
           "gh pr view --json url", tid="c"),
      res("c", "https://github.com/o/r/pull/1038\n"
               "GraphQL: Could not resolve to a User with the login of "
               "'copilot-pull-request-reviewer[bot]'\n"
               '{"url":"https://github.com/o/r/pull/1038"}', err=False),
      say("Opened, add-reviewer failed (non-last), then viewed.")], True,
     "a failed add-reviewer chained non-last in a create combo stays tracked")
# The sharper variant, needing no failure text: a request for an UNRELATED PR
# (#999) chained ahead of the create satisfies `requested=True` for the NEW PR's
# obligation. Without same-PR scoping, the new PR (#1040) self-discharges on
# ordinary success though no reviewer was ever requested FOR IT.
case([bash("gh pr edit 999 --add-reviewer someone && "
           "gh pr create --title x --body y", tid="c"),
      res("c", "https://github.com/o/r/pull/1040\n", err=False),
      say("Requested review on #999, then opened a new PR.")], True,
     "an unrelated-PR request chained with a create does not self-discharge it")
# The same-PR guard in isolation: the unrelated request for #999 is the LAST
# simple command (so the ordering guard alone would let it through), but it
# targets #999, not the created #1040 -- same-PR scoping is what keeps #1040
# tracked. This is the case the ordering guard cannot catch on its own.
case([bash("gh pr create --title x --body y && "
           "gh pr edit 999 --add-reviewer someone", tid="c"),
      res("c", "https://github.com/o/r/pull/1040\n", err=False),
      say("Opened a new PR, then requested review on unrelated #999.")], True,
     "a last request for a DIFFERENT PR does not self-discharge the created one")
# The control: the SAME shape but the request is the LAST simple command AND
# targets the created PR -- it must still discharge, so the guard does not
# over-block a genuine chained create+request.
case([bash("gh pr create --title x --body y && "
           "gh api repos/o/r/pulls/1038/requested_reviewers -X POST", tid="c"),
      res("c", "https://github.com/o/r/pull/1038\n"
               '{"requested_reviewers":[{"login":"Copilot"}]}'),
      say("Opened then requested (last) for the same PR.")], False,
     "a last, same-PR request in a create combo still discharges")
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


# --- a push re-heads the PR, so the per-head request is owed again ---------
# Case #1 is the incident itself (ai-config#1274), with its commands pasted in
# the shape the corpus actually carries -- a `cd`, a `git push ... | tail`, and
# a separate `gh workflow run` dispatch -- rather than a tidied one-liner. The
# guard is designed against a SUMMARY of the incident, so the literal text is
# what tests whether the design survives contact with it.
PUSH_CMD = ('cd /home/<user>/Projects/ai-config\n'
            'git push -q origin HEAD 2>&1 | tail -3\n'
            'echo "local:  $(git rev-parse HEAD)"')
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash(PUSH_CMD, tid="p"), res("p", "local:  76e619aa"),
                    bash("gh workflow run claude-review.yml -f pr_number=1038",
                         tid="w"), res("w", ""),
                    say("Round 2 pushed and dispatched claude-review.")], True,
     "ai-config#1274 verbatim: round 2 pushes, only claude-review dispatched")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash(PUSH_CMD, tid="p"), res("p", ""),
                    bash(REQ_CMD_Q, tid="q2"), res("q2", OK),
                    say("Pushed and re-requested at the new head.")], False,
     "a request AFTER the push discharges the re-armed obligation")
# Ordering is the whole point: the same two actions in the other order leave
# the push unanswered, which is exactly the per-head gap.
case(create("c") + [bash(PUSH_CMD, tid="p"), res("p", ""),
                    bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash(PUSH_CMD, tid="p2"), res("p2", ""),
                    say("Requested, then pushed again.")], True,
     "a request BEFORE the last push does not discharge it")

# Gate: exactly one live PR. Two open PRs make a push unattributable, and
# arming both would demand two requests for one push and wedge the session.
case([bash("gh pr create --title a", tid="c1"), res("c1", URL),
      bash(REQ_CMD_Q, tid="q1"), res("q1", OK),
      bash("gh pr create --title b", tid="c2"),
      res("c2", "https://github.com/o/r/pull/1039\n"),
      bash('gh api "repos/o/r/pulls/1039/requested_reviewers" -X POST',
           tid="q2"), res("q2", OK),
      bash(PUSH_CMD, tid="p"), res("p", ""),
      say("Pushed with two PRs open.")], False,
     "a push with TWO live PRs is unattributable and arms nothing")

# Gate: no duplicate obligation. Several pushes between two requests must
# collapse to ONE obligation, or the request the guard asks for cannot clear it.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash(PUSH_CMD, tid="p1"), res("p1", ""),
                    bash(PUSH_CMD, tid="p2"), res("p2", ""),
                    bash(PUSH_CMD, tid="p3"), res("p3", ""),
                    bash(REQ_CMD_Q, tid="q2"), res("q2", OK),
                    say("Three pushes, then one request.")], False,
     "three pushes arm ONE obligation, cleared by one request")

# Gate: a drafted PR needs no reviewer, so a push to it must not re-arm.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("gh pr ready 1038 --undo", tid="u"), res("u", "{}"),
                    bash(PUSH_CMD, tid="p"), res("p", ""),
                    say("Back to draft, then pushed.")], False,
     "a push to a PR converted back to draft does not re-arm")

# Review finding 1 (#1283). The case above uses the NUMBERED undo. A bare
# `gh pr ready --undo` is the ordinary way to draft the current branch's PR --
# the file's own comment says exactly that about bare `gh pr ready` -- so
# draft_ident yields num=None. Popping `live` only on a known number left the
# entry behind and re-armed review for a legitimately drafted PR.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("gh pr ready --undo", tid="u"), res("u", "{}"),
                    bash(PUSH_CMD, tid="p"), res("p", ""),
                    say("Drafted the current branch's PR, then pushed.")], False,
     "a numberless `gh pr ready --undo` leaves the live set, so a push "
     "does not re-arm")

# Review finding 2 (#1283). The arm fires synchronously at tool_use while the
# terminal/draft transition is DEFERRED to this same call's result, so a push
# chained with either one saw a `live` set the call was about to empty. The
# merge form is the severe one: chained ahead of the push it is not `last`, so
# its own discharge is withheld as ambiguous and the raced arm would stand
# against a merged PR that can never take a reviewer.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("gh pr merge 1038 --squash && "
                         "git push -u origin next-branch", tid="mp"),
                    res("mp", "Merged pull request o/r#1038"),
                    say("Merged and pushed the next branch in one call.")],
     False,
     "a push chained with a merge in ONE call does not arm the merged PR")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("gh pr ready 1038 --undo && "
                         "git push -u origin next-branch", tid="up"),
                    res("up", "{}"),
                    say("Drafted and pushed in one call.")], False,
     "a push chained with a draft transition in ONE call does not re-arm")

# Round-5 finding (#1283). The two cases above put the push and the transition
# in ONE chained command. A turn can carry them as separate tool_use blocks
# instead, and then the per-command check sees neither: read the push first and
# the sibling's transition is not registered yet, read it second and it is
# registered but still deferred to its own result. Both orders are tested,
# because "order does not matter" is the claim being pinned.
#
# The bare-undo form is the one that never self-heals. A merge whose result
# echoes `o/r#N` is retroactively cleaned up by _clear(), but `gh pr ready
# --undo` resolves no number from `{}`, so a wrongly-armed obligation stands.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    uses(("Bash", dict(command="gh pr ready --undo"), "u"),
                         ("Bash", dict(command="git push -u origin next"), "p")),
                    results(("u", "{}", False), ("p", "", False)),
                    say("Drafted and pushed in one turn.")], False,
     "a batched draft+push in ONE turn does not re-arm (draft block first)")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    uses(("Bash", dict(command="git push -u origin next"), "p"),
                         ("Bash", dict(command="gh pr ready --undo"), "u")),
                    results(("p", "", False), ("u", "{}", False)),
                    say("Pushed and drafted in one turn.")], False,
     "a batched push+draft in ONE turn does not re-arm (push block first)")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    uses(("Bash", dict(command="gh pr merge --squash"), "m"),
                         ("Bash", dict(command="git push -u origin next"), "p")),
                    results(("m", "{}", False), ("p", "", False)),
                    say("Merged and pushed in one turn.")], False,
     "a batched bare-merge+push in ONE turn does not re-arm")
# NOT evidence for the turn predicate, and labelled so rather than counted:
# this case passes under every mutation of it, because a structured tool always
# carries `pull_number`, so the deferred clear names 1038 and _clear() removes
# the wrongly-armed obligation retroactively. That is the self-healing the round
# 5 review describes for a merge echoing `o/r#N`. Kept as documentation that the
# structured path is not at risk -- the risk needs a transition whose result
# resolves NO number, which only the bare CLI forms produce.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    uses(("update_pull_request",
                          dict(owner="o", repo="r", pull_number=1038,
                               draft=True), "u"),
                         ("push_files",
                          dict(owner="o", repo="r", branch="next"), "p")),
                    results(("u", "{}", False), ("p", "{}", False)),
                    say("Drafted and pushed via structured tools.")], False,
     "a batched structured draft+push self-heals via its numbered clear")
# The control the finding itself names: strictly sequential, one turn each, is
# already correct and must stay correct -- otherwise the fix above is untested
# against the case it must NOT change.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("gh pr ready --undo", tid="u"), res("u", "{}"),
                    bash("git push -u origin next", tid="p"), res("p", ""),
                    say("Drafted, then pushed, in separate turns.")], False,
     "a sequential draft then push in separate turns does not re-arm")
# The mirror that keeps the fix from being vacuous: a turn that pushes and does
# NOT draft or retire anything must still arm, or the guard has been silenced
# rather than corrected.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    uses(("Bash", dict(command="git status"), "s"),
                         ("Bash", dict(command="git push -u origin next"), "p")),
                    results(("s", "", False), ("p", "", False)),
                    say("Checked status and pushed, in one turn.")], True,
     "a batched turn with a push and NO transition still arms")

# Round-6 finding (#1283). The turn predicate was a bare boolean, so ANY
# transition in the turn suppressed the arm -- including one for a different,
# untracked PR. That is the routine "merge an approved PR while still pushing
# fixes on the one I am driving" shape, and it is the DANGEROUS direction: the
# tracked PR gets a new head, nothing arms, and the guard never reports it.
# Both variants are the reviewer's own reproductions.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    uses(("Bash", dict(command="gh pr merge 2000 --squash"), "m"),
                         ("Bash", dict(command="git push -u origin next"), "p")),
                    results(("m", "Merged pull request o/r#2000", False),
                            ("p", "", False)),
                    say("Merged an unrelated PR and pushed mine.")], True,
     "an unrelated PR's merge in the same turn does not suppress the arm")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    uses(("Bash",
                          dict(command="gh pr create --title unrelated --draft"),
                          "nd"),
                         ("Bash", dict(command="git push -u origin next"), "p")),
                    results(("nd", "https://github.com/o/r/pull/2050", False),
                            ("p", "", False)),
                    say("Opened an unrelated draft and pushed mine.")], True,
     "opening a NEW draft PR in the same turn does not suppress the arm")
# The structured mirror of the same over-suppression.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    uses(("merge_pull_request",
                          dict(owner="o", repo="r", pullNumber=2000), "m"),
                         ("Bash", dict(command="git push -u origin next"), "p")),
                    results(("m", "{}", False), ("p", "", False)),
                    say("Merged an unrelated PR via the tool and pushed mine.")],
     True,
     "an unrelated structured merge in the same turn does not suppress the arm")
# The boundary the fix must NOT cross: a NUMBERED transition for the live PR
# still suppresses, so scoping by identity did not reopen rounds 3 to 5.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    uses(("Bash", dict(command="gh pr ready 1038 --undo"), "u"),
                         ("Bash", dict(command="git push -u origin next"), "p")),
                    results(("u", "{}", False), ("p", "", False)),
                    say("Drafted THIS PR by number and pushed.")], False,
     "a numbered transition for the LIVE PR still suppresses the arm")

# Round-7 finding (#1283). Rounds 4 to 6 suppressed the arm on the mere
# ATTEMPT of a same-turn transition, which is evidence of nothing: the arm
# fires while the tool_use is read, and no result exists for any block in the
# turn yet. A transition that FAILS retires nothing -- the PR stays ready, the
# push still re-headed it, and nothing ever reports it. Withholding an arm has
# the same effect as discharging one, so it owes the same positive evidence.
# Both variants are the reviewer's own reproductions.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    uses(("Bash", dict(command="gh pr ready 1038 --undo"), "u"),
                         ("Bash", dict(command="git push -u origin next"), "p")),
                    results(("u", "cannot be requested", True), ("p", "", False)),
                    say("Tried to draft, it failed, and pushed.")], True,
     "a FAILED draft in the same turn does not cancel the push's arm")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    uses(("Bash", dict(command="gh pr merge 1038 --squash"), "m"),
                         ("Bash", dict(command="git push -u origin next"), "p")),
                    results(("m", "merge conflict, cannot merge", True),
                            ("p", "", False)),
                    say("Merge hit a conflict; pushed anyway.")], True,
     "a FAILED merge in the same turn does not cancel the push's arm")
# The structured mirror: an atomic tool whose own result errored.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    uses(("update_pull_request",
                          dict(owner="o", repo="r", pull_number=1038,
                               draft=True), "u"),
                         ("push_files",
                          dict(owner="o", repo="r", branch="next"), "p")),
                    results(("u", '{"status":422}', True), ("p", "{}", False)),
                    say("Structured draft failed; pushed.")], True,
     "a FAILED structured draft does not cancel the push's arm")
# The boundary the fix must NOT cross, and a deliberate decision rather than an
# oversight: a transition chained AHEAD of the push shares ONE combined exit
# status, which belongs to the LAST command, so the call cannot attribute an
# outcome to the transition either way. The draft and terminal discharges in
# this same call already withhold on exactly this input, so the arm withholds
# too -- an ambiguous call changes nothing in either direction. The cost is
# bounded: the PR stays live (that same ambiguity withheld its own pop), so the
# next push re-arms, which the case below pins.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("gh pr ready 1038 --undo; git push -u origin next",
                         tid="x"),
                    res("x", "", False),
                    say("Chained an undo and a push in one call.")], False,
     "an AMBIGUOUS chained transition still withholds the arm")
# This began as NOT evidence -- it passed under every round-7 mutation, since
# each of them armed at one push or the other, and it was labelled so. Round 8
# made it load-bearing: it is now the only case that fails when an uncertain
# entry is made unarmable, which is the obvious wrong way to stop a stale entry
# from silencing a later PR. So it pins both the REBUTTAL's premise (withholding
# on ambiguity costs one push, not the session) and the half of the round-8 fix
# that keeps that premise true.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("gh pr ready 1038 --undo; git push -u origin next",
                         tid="x"),
                    res("x", "", False),
                    bash("git push -u origin next2", tid="p2"), res("p2", ""),
                    say("...and the next push recovers the arm.")], True,
     "the next push recovers an arm the ambiguous call withheld")

# Round-8 finding (#1283). The `live` pop is gated on the SAME attributability
# check as the discharge, so a merge chained ahead of a push never pops even
# when it plainly succeeded. That stale entry does not just affect its own PR:
# `_rearm` needs exactly one live PR, so the next PR opened in that session
# pushes the count to two and arming goes silent for EVERY PR thereafter --
# the dangerous direction, and unbounded, unlike the one-push cost of
# ambiguity. The trace is the reviewer's own, reproduced.
REQ_2000 = ('gh api "repos/o/r/pulls/2000/requested_reviewers" -X POST '
            "-f 'reviewers[]=copilot-pull-request-reviewer[bot]'")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("gh pr merge 1038 --squash && "
                         "git push -u origin next-branch", tid="mp"),
                    res("mp", "Merged pull request o/r#1038"),
                    bash("gh pr create --title next", tid="c2"),
                    res("c2", "https://github.com/o/r/pull/2000\n"),
                    bash(REQ_2000, tid="q2"), res("q2", OK),
                    bash("git push -u origin next-branch", tid="p5"),
                    res("p5", ""),
                    say("Merged 1038 in a chained call, then opened, "
                        "requested and re-headed 2000.")], True,
     "a PR retired by a chained call does not silence a LATER PR's arm")
# The draft mirror of the same stale entry, which reaches `live` by the other
# result path (_note_drafted rather than the terminal pop).
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("gh pr ready 1038 --undo && "
                         "git push -u origin next-branch", tid="up"),
                    res("up", "{}"),
                    bash("gh pr create --title next", tid="c2"),
                    res("c2", "https://github.com/o/r/pull/2000\n"),
                    bash(REQ_2000, tid="q2"), res("q2", OK),
                    bash("git push -u origin next-branch", tid="p5"),
                    res("p5", ""),
                    say("Drafted 1038 in a chained call, then opened, "
                        "requested and re-headed 2000.")], True,
     "a PR drafted by a chained call does not silence a LATER PR's arm")
# The BARE form of the same shape, which resolves no number at all. It takes
# _note_drafted's own tie-break: with one live PR the bare form is unambiguous,
# so that PR is the one marked. Without this the residual survives for exactly
# the commands most likely to be typed, since a bare `gh pr merge` is the
# ordinary way to merge the current branch's PR.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("gh pr merge --squash && "
                         "git push -u origin next-branch", tid="mp"),
                    res("mp", ""),
                    bash("gh pr create --title next", tid="c2"),
                    res("c2", "https://github.com/o/r/pull/2000\n"),
                    bash(REQ_2000, tid="q2"), res("q2", OK),
                    bash("git push -u origin next-branch", tid="p5"),
                    res("p5", ""),
                    say("Bare-merged in a chained call, then opened, "
                        "requested and re-headed 2000.")], True,
     "a BARE chained merge does not silence a LATER PR's arm either")

# Gate: a merged PR can gain no further reviewable head. Without this, the
# ordinary post-merge shape (merge, branch, push) nags about the merged PR.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("gh pr merge 1038 --squash", tid="m"),
                    res("m", "Merged pull request o/r#1038"),
                    bash(PUSH_CMD, tid="p"), res("p", ""),
                    say("Merged, then pushed the next branch.")], False,
     "a push after the PR merged does not re-arm it")
# This branch was written to assert that a merge does NOT excuse a PR that was
# never reviewed. #1287 reversed that on main, deliberately: GitHub accepts the
# reviewer POST on a merged PR with HTTP 200 and adds nobody, so the obligation
# becomes literally unsatisfiable and the guard re-fires forever (#1279, defect
# 3). An unsatisfiable guard trains everyone to narrate around it, which costs
# more than the case it was protecting. The assertion now lives one block down,
# under "a merged PR no longer demands a reviewer request", with the opposite
# expectation -- see the merge note in the PR body.

# Push detection is structural and scoped, exactly like the other detectors.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash('gh pr comment 1038 --body "then run git push"',
                         tid="p"), res("p", ""),
                    say("Commented about pushing.")], False,
     "a quoted `git push` inside another command's argument does not re-arm")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("git push --dry-run origin HEAD", tid="p"),
                    res("p", ""), say("Dry run only.")], False,
     "`git push --dry-run` re-heads nothing, so it does not re-arm")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("git push origin --delete old-branch", tid="p"),
                    res("p", ""), say("Deleted a stale branch.")], False,
     "`git push --delete` removes a ref rather than advancing one")
# The exclusion walks option VALUES (ai-config#1935): `-n` as the value of
# `-o` is a push-option, not a dry run, and `-d` after `--receive-pack` is
# that option's value -- both re-head the branch and re-arm. A clustered
# `-qn` is a dry run; `-on` is `-o` with the value `n`; `--dry` is git's
# accepted abbreviation of `--dry-run`.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("git push -o -n origin feature", tid="p"),
                    res("p", ""), say("Pushed with a push-option.")], True,
     "`-n` as the value of `-o` is not --dry-run: the push re-arms")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("git push --receive-pack -d origin feature", tid="p"),
                    res("p", ""), say("Pushed via a custom receive-pack.")], True,
     "`-d` as the value of --receive-pack is not --delete: the push re-arms")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("git push -qn origin feature", tid="p"),
                    res("p", ""), say("Quiet dry run.")], False,
     "a clustered `-qn` is a dry run and does not re-arm")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("git push -on origin feature", tid="p"),
                    res("p", ""), say("Pushed with push-option n.")], True,
     "`-on` is `-o` with the value `n`, a real push that re-arms")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("git push --dry origin feature", tid="p"),
                    res("p", ""), say("Dry run, abbreviated.")], False,
     "`--dry` is git's abbreviation of --dry-run and does not re-arm")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("git push -n --no-dry-run origin feature", tid="p"),
                    res("p", ""), say("Pushed; the later --no-dry-run wins.")], True,
     "a later --no-dry-run restores the push (git reads last-wins), so it re-arms")
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash("git -C /tmp/wt push origin HEAD", tid="p"),
                    res("p", ""), say("Pushed from a worktree.")], True,
     "`git -C <dir> push` is recognised past git's global options")
# A failed push still arms: arming is the safe over-warn direction, and a push
# is nearly always chained, so waiting for an attributable exit status would
# skip real new heads.
case(create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                    bash(PUSH_CMD, tid="p"), res("p", "rejected", err=True),
                    say("Push was rejected.")], True,
     "a failed push still arms (over-warn is the safe direction)")

# A session that opened no PR must never be nagged, however much it pushes --
# this is the bulk of all pushes and the whole reason the guard stays usable.
case([bash(PUSH_CMD, tid="p"), res("p", ""),
      bash(PUSH_CMD, tid="p2"), res("p2", ""),
      say("Pushed to a branch with no PR.")], False,
     "pushes in a session that opened no PR arm nothing")

# `live` is keyed by PR number alone, so the same number in two repositories
# would otherwise collapse to one key and report ONE live PR when there are two,
# arming a push that is genuinely unattributable.
case([bash("gh pr create --title a", tid="c1"),
      res("c1", "https://github.com/o/r1/pull/50\n"),
      bash('gh api "repos/o/r1/pulls/50/requested_reviewers" -X POST', tid="q1"),
      res("q1", OK),
      bash("gh pr create --title b", tid="c2"),
      res("c2", "https://github.com/o/r2/pull/50\n"),
      bash('gh api "repos/o/r2/pulls/50/requested_reviewers" -X POST', tid="q2"),
      res("q2", OK),
      bash(PUSH_CMD, tid="p"), res("p", ""),
      say("Pushed with #50 open in two repos.")], False,
     "the same PR number in two repos is two live PRs, so a push arms nothing")

# The push wording must be distinguishable from the open wording: it states a
# different fact (the PR WAS reviewed, at a commit that is no longer its head).
def _push_wording():
    ev = create("c") + [bash(REQ_CMD_Q, tid="q"), res("q", OK),
                        bash(PUSH_CMD, tid="p"), res("p", ""),
                        say("Pushed round 2.")]
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in ev:
            fh.write(json.dumps(e) + "\n")
    try:
        out = subprocess.run(
            hook_argv(), input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=tempfile.mkdtemp())).stdout
        return "per-HEAD" in out and "pushed a new head" in out
    finally:
        os.unlink(path)

# --- a PR that reached a terminal state cannot be discharged by complying ---
# ai-config#1279 defect 3. GitHub ACCEPTS
# `POST /pulls/{n}/requested_reviewers` on a merged PR -- HTTP 200,
# `"requested_reviewers":[]`, nobody added. So the obligation is unsatisfiable
# and the guard re-fires forever, which is how a guard stops being read.
MERGED = ('{"state":"MERGED","merged":true,'
          '"url":"https://github.com/o/r/pull/1038"}')

case(create("c") + [bash("gh pr merge 1038 --squash", tid="m"), res("m", "{}"),
                    say("Merged.")], False,
     "a merged PR no longer demands a reviewer request")
case(create("c") + [bash("gh pr close 1038", tid="m"), res("m", "{}"),
                    say("Closed it.")], False,
     "a closed PR no longer demands a reviewer request")
case(create("c") + [use("merge_pull_request", tid="m", owner="o", repo="r",
                        pullNumber=1038), res("m", "{}"), say("Merged.")], False,
     "the structured merge tool discharges too")
case(create("c") + [use("update_pull_request", tid="m", owner="o", repo="r",
                        pullNumber=1038, state="closed"), res("m", "{}"),
                    say("Closed.")], False,
     "update_pull_request(state=closed) discharges too")
# Merged OUTSIDE the session: no action in the transcript, only an observation.
case(create("c") + [bash("gh pr view 1038 --json state,merged", tid="v"),
                    res("v", MERGED), say("Someone merged it.")], False,
     "observing a terminal state on a single-PR probe discharges")

# ... and the fail-safe direction, which must survive all of the above.
case(create("c") + [bash("gh pr merge 1038 --squash", tid="m"),
                    res("m", FAIL, err=True), say("Merge failed.")], True,
     "a FAILED merge keeps the PR tracked")
case(create("c") + [bash("gh pr merge 1038 --squash; echo done", tid="m"),
                    res("m", "done"), say("Tried.")], True,
     "a merge chained AHEAD of another command is ambiguous, so it does not discharge")
case(create("c") + [bash("gh pr view 1038 --json state", tid="v"),
                    res("v", '{"state":"OPEN"}'), say("Still open.")], True,
     "a probe reporting OPEN does not discharge")
case(create("c") + [bash("gh pr list --state merged", tid="v"),
                    res("v", MERGED), say("Listed.")], True,
     "a repo-wide list naming no single PR is not a probe")
case(create("c") + [bash("gh pr merge 9999 --squash", tid="m"), res("m", "{}"),
                    say("Merged a different PR.")], True,
     "merging a DIFFERENT PR does not discharge this one")
case(create("c") + [bash('gh pr comment 1038 --body "next step: gh pr merge"',
                         tid="m"), res("m", "{}"), say("Commented.")], True,
     "the verb quoted inside a --body value is not a merge")


# --- a LANDED review at the current head satisfies the demand (#3001) ------
# A reviewer request is CONSUMED the moment Copilot posts, so "never
# requested" and "requested, reviewed, request consumed" are the same state to
# any request-keyed check -- and the second is the terminal success. Measured
# on `ucdavis/hac.sap` #25 and #37: the guard fired on four consecutive turns
# with a Copilot review sitting at each PR's exact head, and each firing bought
# another paid review of an already-reviewed diff. So a landed review at the
# current head discharges, read from the probe's own result.
#
# `HEAD_OID` differs from `STALE_OID` in more than its last character, so a
# prefix comparison cannot accidentally match the two: the discharge is
# prefix-based (the prescribed query abbreviates both sides to eight
# characters) and a fixture that differed only at the tail would pass under a
# broken comparison too.
HEAD_OID = "9eccd32ab1c4d5e6f708192a3b4c5d6e7f809a1b"
STALE_OID = "0ff0ed1122334455667788990aabbccddeeff001"
REVIEW_CMD = ("gh pr view 1038 --json headRefOid,reviews "
              "--jq '{head: .headRefOid[0:8], copilot: [.reviews[]]}'")


def digest(head, shas):
    """The DIGESTED body this guard's own recovery text prescribes."""
    return json.dumps({
        "head": head[0:8],
        "copilot": [{"sha": sha[0:8], "at": "2026-09-02T00:00:00Z"}
                    for sha in shas],
    })


def raw(head, reviews):
    """The RAW `gh pr view --json headRefOid,reviews` body."""
    return json.dumps({"headRefOid": head, "reviews": [
        {"author": {"login": login}, "commit": {"oid": oid},
         "state": "COMMENTED"} for (login, oid) in reviews]})


case(create("c") + [bash(REVIEW_CMD, tid="v"),
                    res("v", digest(HEAD_OID, [HEAD_OID])),
                    say("Copilot reviewed the current head.")], False,
     "a Copilot review at the current head discharges (digested shape)")
case(create("c") + [bash("gh pr view 1038 --json headRefOid,reviews", tid="v"),
                    res("v", raw(HEAD_OID,
                                 [("copilot-pull-request-reviewer[bot]",
                                   HEAD_OID)])),
                    say("Copilot reviewed the current head.")], False,
     "a Copilot review at the current head discharges (raw shape)")

# ... and every way the satisfaction check must NOT fire, which is what keeps
# the two true positives the guard already caught.
case(create("c") + [bash(REVIEW_CMD, tid="v"),
                    res("v", digest(HEAD_OID, [STALE_OID])),
                    say("Copilot reviewed.")], True,
     "a Copilot review one commit BEHIND the head does not discharge")
case(create("c") + [bash(REVIEW_CMD, tid="v"),
                    res("v", digest(HEAD_OID, [])),
                    say("No review yet.")], True,
     "a PR with no Copilot review at all still blocks")
case(create("c") + [bash("gh pr view 1038 --json headRefOid,reviews", tid="v"),
                    res("v", raw(HEAD_OID, [("d-morrison", HEAD_OID)])),
                    say("A human reviewed it.")], True,
     "a NON-Copilot review at the head does not discharge")
case(create("c") + [bash(REVIEW_CMD, tid="v"),
                    res("v", digest(HEAD_OID, [HEAD_OID]), err=True),
                    say("The read failed.")], True,
     "a FAILED review read does not discharge")
case(create("c") + [bash(REVIEW_CMD + "; echo done", tid="v"),
                    res("v", digest(HEAD_OID, [HEAD_OID])),
                    say("Checked.")], True,
     "a review read chained AHEAD of another command does not discharge")
case(create("c") + [bash("gh pr list --json headRefOid,reviews", tid="v"),
                    res("v", digest(HEAD_OID, [HEAD_OID])),
                    say("Listed.")], True,
     "a repo-wide list carrying a head-matching review is not a probe")
# The obligation is per-HEAD, so satisfaction is not retirement: a push after
# the review re-arms it, exactly as a push after a request does. This is the
# case a `live.pop` here would silently break, and nothing else would catch.
case(create("c") + [bash(REVIEW_CMD, tid="v"),
                    res("v", digest(HEAD_OID, [HEAD_OID])),
                    bash("git push origin HEAD", tid="p"), res("p", ""),
                    say("Pushed a fix.")], True,
     "a push AFTER a satisfying review re-arms the obligation")


# --- redaction exemption (ai-config#1392) ----------------------------------
# A redaction PR's diff carries the redacted literal on the REMOVED side of
# every hunk, so requesting a reviewer is the exposure the redaction gate
# exists to prevent (ucdavis/bcs#610/#614). Before this the guard had no
# terminating state on such a PR: refusing, recording the refusal, and the
# maintainer deciding to hold all left it firing, and its only discharges were
# the exposure itself or a false claim of draft status.
LABEL_CMD = "gh pr edit 1038 -R o/r --add-label no-ai-review"
ENV_CMD = ("ALLOW_UNREVIEWED_REDACTION_PR=1 gh pr view 1038 -R o/r "
           "--json number")

case(create("c") + [bash(LABEL_CMD, tid="x"), res("x", "{}"),
                    say("Redaction PR; held the AI review.")], False,
     "a no-ai-review label exempts a redaction PR")
case(create("c") + [bash("gh api repos/o/r/issues/1038/labels -X POST "
                         "-f 'labels[]=no-ai-review'", tid="x"),
                    res("x", '[{"name":"no-ai-review"}]'),
                    say("Labelled via the API.")], False,
     "the issue-labels endpoint exempts too")
case(create("c") + [bash(ENV_CMD, tid="x"), res("x", '{"number":1038}'),
                    say("Redaction PR; asserted the exemption.")], False,
     "an ALLOW_UNREVIEWED_REDACTION_PR=1 assertion exempts")
case(create("c") + [bash("ALLOW_UNREVIEWED_REDACTION_PR=1 gh api "
                         "repos/o/r/pulls/1038 --jq .number", tid="x"),
                    res("x", "1038"), say("Asserted.")], False,
     "the env assertion resolves identity from an API path too")
# Exemption is a property of the PR's CONTENT, not of one head: the removed
# side still carries the literal after the next push, so unlike a reviewer
# request it must survive a re-head.
case(create("c") + [bash(ENV_CMD, tid="x"), res("x", '{"number":1038}'),
                    bash("git push", tid="p"), res("p", "done"),
                    say("Pushed a fix to the redaction PR.")], False,
     "an exempted PR is not re-armed by a later push")
# The env form takes effect at tool_use time, so it must also survive a push
# CHAINED into that same call, where the arm fires synchronously.
case(create("c") + [bash(ENV_CMD + " && git push", tid="x"),
                    res("x", "1038\ndone"), say("Asserted and pushed.")], False,
     "a push chained after the assertion does not re-arm")

# ... and the discharge is narrow, since it is the DANGEROUS direction.
case(create("c") + [bash(LABEL_CMD, tid="x"),
                    res("x", "could not add label: 'no-ai-review' not found",
                        err=True),
                    say("Tried to label it.")], True,
     "a FAILED label add does not exempt (the repo has no such label)")
# Chained AHEAD of a succeeding command, the is_error belongs to that LATER
# command, so the outcome is unknowable. The body here deliberately carries no
# error-word or 4xx shape ("unable to add" matches nothing in RX_FAILED), so
# only the `last` check can withhold the exemption -- the same ordering hazard
# the draft clear above guards against.
# The same ordering rule bites the natural way to batch the exemption with a
# push, so both directions are pinned: chaining the label add BEFORE the push
# does not discharge (the push arms, and the label's result is unattributable),
# while chaining it AFTER does, since it is then last. This is why the block
# message says to run the label add on its own. Dropping the `last` requirement
# to make the forward ordering work would read `git push`'s exit status as the
# label add's own -- the silent-discharge class every releasing path here
# blocks -- so the over-warn is kept deliberately.
case(create("c") + [bash("gh pr edit 1038 -R o/r --add-label no-ai-review "
                         "&& git push", tid="x"), res("x", "done"),
                    say("Labelled and pushed.")], True,
     "a label add chained BEFORE a push does not exempt")
case(create("c") + [bash("git push && gh pr edit 1038 -R o/r "
                         "--add-label no-ai-review", tid="x"),
                    res("x", "done"), say("Pushed and labelled.")], False,
     "a label add chained AFTER a push is last, so it exempts")
case(create("c") + [bash(LABEL_CMD + "; echo done", tid="x"),
                    res("x", "unable to add label to this PR\ndone", err=False),
                    say("Tried to label it.")], True,
     "a label add chained AHEAD of a success does not exempt")
case(create("c") + [bash("gh pr comment 1038 -R o/r --body "
                         "'run: gh pr edit 1038 --add-label no-ai-review'",
                         tid="x"), res("x", "{}"), say("Explained it.")], True,
     "the label command quoted inside a --body does not exempt")
case(create("c") + [bash("echo 'ALLOW_UNREVIEWED_REDACTION_PR=1 gh pr view 1038'",
                         tid="x"), res("x", "ok"), say("Quoted it.")], True,
     "the env token quoted inside a string does not exempt")
case(create("c") + [bash("gh pr edit 1038 -R o/r --add-label needs-data",
                         tid="x"), res("x", "{}"), say("Labelled.")], True,
     "an unrelated label does not exempt")
case(create("c") + [bash("gh pr edit 1038 -R o/r --add-label no-ai-review-later",
                         tid="x"), res("x", "{}"), say("Labelled.")], True,
     "a label whose name merely CONTAINS the token does not exempt")
case(create("c") + [bash("gh api repos/o/r/issues/1038/labels", tid="x"),
                    res("x", '[{"name":"no-ai-review"}]'),
                    say("Read the labels.")], True,
     "READING the labels endpoint is not applying the label")
# `gh api` sends POST as soon as any `-f`/`-F` parameter is added, so the bare
# form IS a write and must exempt; `--method GET` sends the same parameters as
# a query string, so it is a read and must not.
case(create("c") + [bash("gh api repos/o/r/issues/1038/labels "
                         "-f 'labels[]=no-ai-review'", tid="x"),
                    res("x", '[{"name":"no-ai-review"}]'),
                    say("Labelled.")], False,
     "a bare `-f` labels call is a POST and exempts")
case(create("c") + [bash("gh api repos/o/r/issues/1038/labels --method GET "
                         "-f 'labels[]=no-ai-review'", tid="x"),
                    res("x", "[]"), say("Queried the labels.")], True,
     "`--method GET` with the same parameters is a read, not a label add")
case(create("c") + [bash("gh api repos/o/r/issues/1038/labels --method=GET "
                         "-f 'labels[]=no-ai-review'", tid="x"),
                    res("x", "[]"), say("Queried the labels.")], True,
     "the `--method=GET` equals form is a read too")
case(create("c") + [bash("gh pr edit 1039 -R o/r --add-label no-ai-review",
                         tid="x"), res("x", "{}"),
                    say("Exempted the other PR.")], True,
     "exempting a DIFFERENT PR does not exempt this one")
case(create("c") + [bash("ALLOW_UNREVIEWED_REDACTION_PR=1 echo held", tid="x"),
                    res("x", "held"), say("Asserted with no PR named.")], True,
     "the env assertion with no resolvable PR number does not exempt")
case(create("c") + [bash("ALLOW_UNREVIEWED_REDACTION_PR=0 gh pr view 1038 "
                         "-R o/r --json number", tid="x"),
                    res("x", '{"number":1038}'), say("Not asserted.")], True,
     "ALLOW_UNREVIEWED_REDACTION_PR=0 is not an assertion")


def stdout_of(events):
    """The hook's raw stdout for a transcript.

    One run-and-capture, shared by `block_of` and `reason_of`, so a later change
    to the sentinel isolation or the invocation cannot leave the two disagreeing
    about what they exercise (ai-config#3017 review).
    """
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        return subprocess.run(
            hook_argv(), input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=tempfile.mkdtemp())).stdout
    finally:
        os.unlink(path)


def reason_of(events):
    """The block `reason` text for a transcript, or "" when it does not block.

    `block_of` answers only whether the hook blocked; a wording assertion needs
    the text itself.
    """
    out = stdout_of(events)
    return json.loads(out).get("reason", "") if out.strip() else ""


def _chained_request_wording():
    """A request chained AHEAD of another command must be NAMED as such.

    ai-config#3017, measured on ai-config#3010: eight successive POSTs each
    returned 200 and three Copilot reviews landed, while every call chained the
    hook's own prescribed verification after the request -- so `rlast` was
    False every time, nothing discharged, and the block text named only failure
    as the cause. From inside the turn the two are indistinguishable, so the
    reader re-issues the same shape and the guard re-fires unchanged.

    The negative half is the load-bearing one: a session that made NO request
    must not be told a request is in the transcript.
    """
    chained = reason_of(create("c") + [
        bash(REQ_CMD_Q + " && gh pr view 1038 --json reviews", tid="q"),
        res("q", OK), say("Requested.")])
    none_made = reason_of(create("c") + [say("Opened it.")])
    # A `gh pr create --reviewer` chained ahead of another command resolves no
    # number on either side, so the number-matched marking cannot reach it and
    # it needs its own path (ai-config#3017 review). Without that path this arm is
    # the pre-fix message, naming only failure as the cause.
    chained_create = reason_of([
        bash("gh pr create --base main --title x --body y --reviewer "
             "copilot-pull-request-reviewer[bot] && gh pr view 1038 "
             "--json reviews", tid="c"),
        res("c", URL), say("Created with a reviewer.")])
    # The needle must be unique to the new paragraph. "chained AHEAD" is NOT:
    # the pre-existing label-exemption text already carries that exact phrase,
    # so a needle keyed on it matches the no-request case too and the negative
    # half passes vacuously (caught by running it).
    # Several PRs can be outstanding with only one carrying a chained request,
    # so the paragraph names the flagged number rather than saying "this PR"
    # over a mixed set (ai-config#3017 review round 4). The mixed case is the
    # one that discriminates: aggregating with any() passes every other arm.
    mixed = reason_of([
        bash("gh pr create --base main --title x --body y", tid="c1"),
        res("c1", URL),
        bash(REQ_CMD_Q + " && gh pr view 1038 --json reviews", tid="q"),
        res("q", OK),
        bash("gh pr create --base main --title y --body z", tid="c2"),
        res("c2", "https://github.com/o/r/pull/2222\n"),
        say("Opened a second, unrequested.")])
    needle = "A reviewer request for #1038 appears in the transcript"
    # A request chained ahead of a ready for a DIFFERENT PR must not mark
    # this one: the direct marking is restricted to the create form, whose
    # request resolves no number (ai-config#3017 review round 2).
    # A push re-arms its obligation AFTER the marking loop runs, so a call
    # chaining a push with a non-last request must still be marked
    # (claude-review on ai-config#3024).
    pushed_chain = reason_of(create("c") + [bash(REQ_CMD_Q, tid="q0"),
                                            res("q0", OK),
                                            say("Requested.")] + [
        bash("git push origin HEAD && " + REQ_CMD_Q
             + " && gh pr view 1038 --json reviews", tid="p"),
        res("p", OK), say("Pushed and requested.")])
    # Two number-less commands naming DIFFERENT repos must not mark either.
    # The result must RESOLVE a number, or `flagged`'s own `and o["num"]`
    # filter drops the obligation and the needle is absent either way -- the
    # vacuous-needle shape this suite has hit before.
    cross_repo = reason_of([
        bash("gh pr edit -R o/repoA --add-reviewer "
             "copilot-pull-request-reviewer[bot] && gh pr ready -R o/repoB",
             tid="rr"),
        res("rr", "https://github.com/o/repoB/pull/77\n"),
        say("Different repos.")])
    # A `&&` chain can short-circuit before the request runs, so the paragraph
    # must not assert it executed or returned anything (Copilot on
    # ai-config#3024). It is still named -- the transcript cannot tell the
    # cases apart, which is the point -- but the wording stays agnostic.
    short_circuit = reason_of(create("c") + [
        bash("false && " + REQ_CMD_Q + " && gh pr view 1038", tid="sc"),
        res("sc", "", True), say("Short-circuited.")])
    # A chained request SUPERSEDED by a credited standalone one must not mark an
    # obligation the later push re-armed: without the seq/tid ordering the
    # end-of-scan sweep loses, the block would blame chaining for a moved head
    # (adversarial review on ai-config#3024).
    superseded = reason_of(create("c") + [
        bash(REQ_CMD_Q + " && gh pr view 1038", tid="s1"), res("s1", OK),
        bash(REQ_CMD_Q, tid="s2"), res("s2", OK),
        bash("git push origin HEAD", tid="s3"), res("s3", ""),
        say("Superseded, then pushed.")])
    # A bare `gh pr ready` backfills its number from the RESULT, which arrives
    # after the marking site runs, so only an end-of-scan sweep sees it
    # (Copilot on ai-config#3024).
    backfilled = reason_of([
        bash("gh pr ready && " + REQ_CMD_Q + " && gh pr view 1038", tid="bf"),
        res("bf", URL), say("Readied and requested.")])
    # The same cross-repo overclaim on the NUMBER-MATCHED path, which the
    # cross_repo arm above cannot reach -- it pins the direct marking only
    # (adversarial review on ai-config#3024).
    cross_repo_numbered = reason_of([
        bash("gh pr ready 42 -R o/repoB", tid="b"),
        res("b", "https://github.com/o/repoB/pull/42\n"),
        bash('gh api "repos/o/repoA/pulls/42/requested_reviewers" -X POST '
             "-f 'reviewers[]=copilot-pull-request-reviewer[bot]' "
             "&& gh pr view 42", tid="n"),
        res("n", OK), say("Requested against another repo.")])
    # `gh pr ready <N>` names a PR that need not be this branch's, so a
    # current-branch numberless add-reviewer chained ahead of it targets a
    # DIFFERENT PR and must not mark <N> (Copilot on ai-config#3024).
    ready_named = reason_of([
        bash("gh pr edit --add-reviewer copilot-pull-request-reviewer[bot] "
             "&& gh pr ready 1038", tid="r"),
        res("r", OK), say("Readied a named PR.")])
    # Two flagged PRs get the plural sentence, not a singular one over a list.
    two = reason_of([
        bash("gh pr create --base main --title x --body y --reviewer "
             "copilot-pull-request-reviewer[bot] && gh pr view", tid="d1"),
        res("d1", URL),
        bash("gh pr create --base main --title y --body z --reviewer "
             "copilot-pull-request-reviewer[bot] && gh pr view", tid="d2"),
        res("d2", "https://github.com/o/r/pull/2222\n"),
        say("Two creates, each chained.")])
    cross_pr = reason_of([
        bash("gh api \"repos/o/r/pulls/42/requested_reviewers\" -X POST "
             "-f 'reviewers[]=copilot-pull-request-reviewer[bot]' "
             "&& gh pr ready 1038", tid="x"),
        res("x", OK), say("Readied a different PR.")])
    # The remedy sentence lives in the generic recovery paragraph, not in the
    # chained one -- duplicating it there was dropped as redundant, so assert
    # it where it actually is (adversarial review on ai-config#3024).
    return (needle in chained and "only command in this call" in chained
            and needle in chained_create
            and none_made and needle not in none_made
            and cross_pr and needle not in cross_pr
            # Decisive over a mixed set: the SINGULAR branch must render, which
            # it does only when `flagged` holds one number. Asserting the
            # absence of a "#2222 appears" phrase decided nothing -- that
            # phrase exists only when 2222 is flagged ALONE, a world the
            # positive needle has already excluded (adversarial review).
            and needle in mixed and "Reviewer requests for" not in mixed
            and ready_named and needle not in ready_named
            and "Reviewer requests for #1038, #2222 appear" in two
            and needle in pushed_chain
            and cross_repo and "#77 appears in the transcript" not in cross_repo
            and cross_repo_numbered
            and "#42 appears in the transcript" not in cross_repo_numbered
            and needle in backfilled
            and superseded and needle not in superseded
            # The needle is the ASSERTIVE old phrasing, not the substring the
            # new hedged sentence still contains ("it may have returned 200
            # with a review landing"). A needle matching both tests nothing.
            and "The POST may well have returned 200" not in chained
            and "short-circuited before it ran" in chained
            # The intended fact stated directly. The former disjunction drew
            # both operands from one string literal, so it held whether or not
            # a short-circuited chain was flagged (adversarial review).
            and needle in short_circuit)


def _request_ordering_wording():
    """The recovery text must tell the reader to run the request alone.

    The message used to present the request and its verification together
    under "in this same message", which is exactly the shape `request_ident`
    refuses to credit -- so following the instruction reproduced the block.
    """
    text = reason_of(create("c") + [say("Opened it.")])
    return all(t in text for t in ("only command in this call", "SEPARATE call",
                                   "per-PR, not per-head",
                                   "`sha` equals `head`"))


def _review_query_null_safe():
    """The prescribed review-check `jq` must survive a null review author.

    A GitHub review author is nullable -- a deleted account reports
    `"author": null` -- and `null | startswith(...)` is a hard `jq` error
    rather than a false. So the unguarded filter aborts the WHOLE query
    instead of skipping that one review, and the reader sees a jq usage error
    where the hook promised them a way to confirm their review landed
    (Copilot on ai-config#3024).

    The guard is already in place; this pins it, because it survived a
    mutation otherwise. Pinned two ways, since the lexical half alone would
    pass on a filter that merely mentions the guard somewhere harmless. When
    `jq` is on PATH the extracted filter is RUN against a fixture whose first
    review has a null author and whose second is a real Copilot review: it
    must not error, and must still find the Copilot one.
    """
    text = reason_of(create("c") + [say("Opened it.")])
    match = re.search(r"--jq '(\{head:.*?\})'", text, re.S)
    if not match:
        return False
    filt = match.group(1)
    if "(.author.login // \"\")" not in filt:
        return False

    if not shutil.which("jq"):
        # The lexical half above already fails without the guard, so an
        # absent `jq` weakens this check rather than voiding it.
        return True

    fixture = json.dumps({
        "headRefOid": "deadbeefcafe",
        "reviews": [
            {"author": None, "commit": {"oid": "1111111111"},
             "submittedAt": "2026-01-01T00:00:00Z"},
            {"author": {"login": "copilot-pull-request-reviewer"},
             "commit": {"oid": "2222222222"},
             "submittedAt": "2026-01-02T00:00:00Z"},
        ],
    })
    proc = subprocess.run(["jq", filt], input=fixture, capture_output=True,
                          text=True)
    if proc.returncode != 0:
        return False
    try:
        got = json.loads(proc.stdout)
    except ValueError:
        return False
    return [c["sha"] for c in got.get("copilot", [])] == ["22222222"]


def _no_attribution_overclaim():
    """The block must not claim the exit status BELONGS to the later command.

    It does not, in either direction. `false && <request> && gh pr view`
    leaves the status with `false`; `<request> && gh pr view` where the
    request fails leaves it with the request. The only sound claim is the
    negative one -- the combined status cannot be attributed to the request
    -- and the paragraph's own later hedge ("a `&&` chain may have
    short-circuited before it ran at all") contradicted the unconditional
    attribution it opened with (Copilot on ai-config#3024, round 4).

    Checked over BOTH the chained paragraph and the always-rendered recovery
    paragraph, since the overclaim appeared in three places and a needle over
    only one of them would pass while the others still asserted it.
    """
    chained = reason_of(create("c") + [
        bash(REQ_CMD_Q + " && gh pr view 1038 --json reviews", tid="q"),
        res("q", OK), say("Requested.")])
    two = reason_of([
        bash("gh pr create --base main --title x --body y --reviewer "
             "copilot-pull-request-reviewer[bot] && gh pr view", tid="d1"),
        res("d1", URL),
        bash("gh pr create --base main --title y --body z --reviewer "
             "copilot-pull-request-reviewer[bot] && gh pr view", tid="d2"),
        res("d2", "https://github.com/o/r/pull/2222\n"),
        say("Two creates, each chained.")])
    plain = reason_of(create("c") + [say("Opened it.")])
    banned = "belongs to that later command"
    return (banned not in chained and banned not in two and banned not in plain
            and "cannot be attributed to the request" in chained
            and "cannot be attributed to any one of them" in two
            and "cannot be attributed to it" in plain)


def _redaction_wording():
    """The block text must NAME the redaction deferral and both escapes.

    Point 3 of ai-config#1392: enumerating the draft carve-out as though it
    were exhaustive is what left a correctly-refusing session with no
    sanctioned way to record why, and the next one liable to comply.
    """
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in create("c") + [say("Opened it.")]:
            fh.write(json.dumps(e) + "\n")
    try:
        out = subprocess.run(
            hook_argv(), input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=tempfile.mkdtemp())).stdout
        reason = json.loads(out).get("reason", "") if out.strip() else ""
        return all(t in reason for t in
                   ("REDACT", "no-ai-review", "ALLOW_UNREVIEWED_REDACTION_PR=1"))
    finally:
        os.unlink(path)


def block_of(events):
    out = stdout_of(events)
    return '"decision": "block"' in out or '"decision":"block"' in out


def load_hook():
    spec = importlib.util.spec_from_file_location("_h", HOOK)
    hookmod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hookmod)
    return hookmod


def blocks_at(when, events):
    """Does the subject block on `events`, with its clock pinned to `when`?"""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        out = subprocess.run(
            hook_argv(when), input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True,
            env=dict(os.environ, TMPDIR=tempfile.mkdtemp()),
        ).stdout
        return "block" in out
    finally:
        os.unlink(path)


def obligations_of(events):
    hookmod = load_hook()
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
    hookmod = load_hook()
    for cmd, want in PUSH_CORPUS:
        got = hookmod._argv_push(cmd.split())
        if got is want:
            passes += 1
            print(f"PASS: _argv_push({cmd!r}) is {want}")
        else:
            failures += 1
            print(f"FAIL: _argv_push({cmd!r}) is {got}, want {want}")
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
    reason = reason_of(create("c") + [say("Opened it.")])
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
        hook_argv(), input='{"transcript_path": "/nonexistent"}',
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
            hook_argv(), input=json.dumps({"transcript_path": p}),
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

    # --- the Copilot moratorium suspends the whole guard -------------------
    # ai-config#1709. While the standing directive forbids the Copilot
    # request, every discharge this guard offers is the one action forbidden,
    # so the guard has to be inert rather than merely quieter. Same
    # transcript, two clocks: the ONLY difference between these two is the
    # date, which is what makes the second one evidence the first is silent
    # for the moratorium's sake and not because the fixture stopped arming.
    #
    # Both clocks are DERIVED from the subject's constant. Written out, they
    # drift the moment the moratorium is extended: a literal "day before" and
    # "end date" from an earlier window both fall INSIDE the new one, the
    # guard is inert on both, and the pair stops testing the boundary it
    # exists for. Measured 2026-09-02, when extending the window to December
    # turned the literals 2026-08-31 and 2026-09-01 into two dates on the
    # same side of the line.
    _end = _moratorium_end()
    _during = (_end - datetime.timedelta(days=1)).isoformat()
    _on_end = _end.isoformat()
    armed = create("c") + [say("Opened it.")]
    if blocks_at(_during, armed):
        print("FAIL: the guard still fires during the Copilot moratorium")
        failures += 1
    elif not blocks_at(_on_end, armed):
        print("FAIL: the guard stays inert on the moratorium's end date")
        failures += 1
    else:
        print("PASS: inert during the moratorium, live again on its end date")
        passes += 1

    hookmod = load_hook()
    import datetime as _dt
    bounds = (
        hookmod.moratorium_active(hookmod.MORATORIUM_END - _dt.timedelta(days=1)),
        not hookmod.moratorium_active(hookmod.MORATORIUM_END),
        not hookmod.moratorium_active(hookmod.MORATORIUM_END + _dt.timedelta(days=31)),
    )
    if all(bounds):
        print("PASS: moratorium_active is half-open -- live ON the end date")
        passes += 1
    else:
        print(f"FAIL: moratorium_active boundaries wrong {bounds}")
        failures += 1

    # The subject's own clock must be the real one. A clock it read from the
    # environment would let any session silence the guard by exporting a date,
    # so the test's injection has to be a test-side override and nothing the
    # subject itself offers.
    if hookmod._today() == _dt.date.today():
        print("PASS: the subject's default clock is the real date")
        passes += 1
    else:
        print("FAIL: the subject's default clock is not date.today()")
        failures += 1

    if _redaction_wording():
        print("PASS: the block text names the redaction deferral and both "
              "escapes")
        passes += 1
    else:
        print("FAIL: the block text does not name the redaction deferral")
        failures += 1

    if _chained_request_wording():
        print("PASS: a chained request is named as chained, and a session "
              "that made none is not")
        passes += 1
    else:
        print("FAIL: the block text does not distinguish a chained request "
              "from no request")
        failures += 1

    if _no_attribution_overclaim():
        print("PASS: the block does not claim the exit status belongs "
              "to the later command")
        passes += 1
    else:
        print("FAIL: the block overclaims exit-status attribution")
        failures += 1

    if _review_query_null_safe():
        print("PASS: the prescribed review query survives a null review "
              "author")
        passes += 1
    else:
        print("FAIL: the prescribed review query aborts on a null review "
              "author")
        failures += 1

    if _request_ordering_wording():
        print("PASS: the recovery text says to run the request alone and "
              "verify separately")
        passes += 1
    else:
        print("FAIL: the recovery text does not state the ordering rule")
        failures += 1

    if _push_wording():
        print("PASS: a push re-arm says the head moved, not that the PR is "
              "unreviewed")
        passes += 1
    else:
        print("FAIL: push re-arm reuses the open wording")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
