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
