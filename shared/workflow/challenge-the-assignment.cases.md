# Case records: challenge-the-assignment

Worked-example case records for the rules in
[`challenge-the-assignment.md`](challenge-the-assignment.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## "The authoring side" --- an unqueried brief premise

(2026-08-04, this fragment's own subject: a brief asserted that `CLAUDE.md`
carries a review-quota carve-out phrased as "`total_cost` 0 at `num_turns` 1",
written from recollection and never queried.
`grep -nE "total_cost|num_turns" CLAUDE.md` returns nothing, and
`git grep -n 'total_cost` 0 at' -- '*.md'` returns exactly one hit,
`shared/workflow/review-verdict-pitfalls.md:29` (moved there from
`fully-clean.md` per ai-config#1236), which is where that carve-out actually
lives.
`CLAUDE.md`'s quota material is about a bot comment stating that the review
was skipped for an exhausted quota --- a signal the bot posts, rather than an
inference drawn from a zero cost.
The receiving agent checked and pushed back, which is the discretionary
detector working rather than a mechanism.
The brief written to record this entry then repeated the shape at smaller
scale, saying `CLAUDE.md` had "five quota mentions" where `grep -ci quota`
returns 6 lines and `grep -oi quota | wc -l` returns 7 occurrences.)

## "the SAS source is the spec" convention-document premise

(2026-07-30, `ucdavis/bcs`: that repo's `CLAUDE.md` asserts, as a section
heading, "the SAS source is the spec".
The maintainer's correction was that the SAS programs are a proposal rather
than a specification.
By then the assertion had been treated as background fact by several agents and
had propagated into issues and briefs, which is the convention-document shape
[`challenge-the-assignment.md`](challenge-the-assignment.md) describes: no
single reader invented it, and each one found it corroborated.)

## A brief's own command contradicted its own disclaimer

(2026-08-12, a brief dispatched into a `Morrison-Lab/gha` clone: the prose said
"Do NOT assume anything about its checked-out branch or worktree layout ---
establish your own working state", and the command block directly beneath it
assumed both.
Its two `git worktree add` forms, joined by `||`, differed on whether to create
the branch or reuse it, and both failed because the branch was already checked
out in that clone --- so the chain enumerated two states and the real one was a
third.
The recipient recovered by detaching the existing checkout and using `-B`.

The same block resolved the default branch with a piped
`git symbolic-ref --short refs/remotes/origin/HEAD`, falling back to
`|| echo main` inside the substitution.
That ref is unset in the clones this corpus is developed in, so the fallback was
the only thing that could have supplied a value.

**It could not have.**
An earlier version of this record said `DEF` came from the literal, right by
luck.
That was wrong, and wrong in the direction that made the example fit the
argument, which is why it survived a self-review and was caught in review on
`Morrison-Lab/ai-config#1408`.
The `||` does sit inside the substitution here, but the pipe in front of it
discards the failing command's status and `sed` exits 0 on empty input, so the
fallback never fires.
`DEF` ends up **empty**, and `git worktree add` against `origin/` then errors.

Measured, 2026-08-12, with `false` standing in for the failing lookup:

| form | `DEF` |
|---|---|
| `DEF=$(false \|\| echo main)` | `main` |
| `DEF=$(false) \|\| echo main` | *empty* |
| `DEF=$(false \| sed ... \|\| echo main)` | *empty* |
| the same, under `set -o pipefail` | `main` |

So the brief carried an inert fallback, and neither its author nor its recipient
ran it.
The recipient sidestepped it by resolving the branch with `git remote show
origin` instead, which is why the inertness surfaced only in review.

The resolution that does answer, derivable in any of these clones:
`git symbolic-ref --short refs/remotes/origin/HEAD` exits non-zero with
`fatal: ref refs/remotes/origin/HEAD is not a symbolic ref`, while
`git remote show origin | sed -n 's/.*HEAD branch: //p'` returns `main`.
Measured in `/home/user/ai-config` on 2026-08-12, and the recipient reported the
same result for the `gha` clone the brief targeted.

Two further premises in the same brief were the sections above, unchanged:
`python3 -m pytest check-phi/tests/ -q` was instructed into an environment whose
default interpreter has no pytest module (it is a `uv tool install` at
`/root/.local/bin/pytest`), which is the environment case; and
`Morrison-Lab/gha#445` was described as an open issue when it is a merged pull
request, `merged_at` 2026-08-12T07:35:21Z, which is the corpus-state case that
one `issue_read` call would have settled.
The recipient caught all three and reported them back, which is again the
discretionary detector rather than a mechanism.)

## This fragment's own brief overstated coverage

(2026-07-31, this fragment's own brief: it named four areas as likely
uncovered.
Two --- a premise handed down as settled, and a default nobody chose --- had
been closed hours earlier, both of them in
[`metacognitive-monitoring`](metacognitive-monitoring.md): the unexamined
default by ai-config#947, merged 06:28Z, and the handed premise by
ai-config#955, merged 07:13Z.
The brief also pointed at a checkout that was 37 commits behind `origin/main`,
so every search run there would have understated coverage.
The brief asked to be questioned, which is why this was caught; the general
case is a brief that does not.)

## A recurring brief re-asserted a blocker nobody re-tested

(Morrison-Lab/ai-config#1439, 2026-08-13: a session spent roughly 8 hours
reporting three of its PRs blocked because no external reviewer was reachable,
citing four gates.
One of them was "`claude-review` dispatch returns 403 (token lacks
`actions: write`)".
At 2026-08-13T04:11Z that exact dispatch was retried and returned HTTP 204,
"Workflow run has been queued", producing live run 31666212015 on branch
`ums/claude-settings-scope-precedence`.
So the claim was false at the time of retry.

Why the two attempts differed was not established, and no mechanism is named
here.
Three candidates went untested: the token's permissions may have changed, the
original 403 may have been misdiagnosed, and the branch was 6 commits behind
`main` at the first attempt and had just been merged forward at the retry.
Recording the disagreement is the finding, and naming a cause would be the guess
this corpus keeps warning against.

What kept the claim alive was the session's own scheduled check-in brief, which
restated the four gates as established fact every time it fired, and whose step
4 read "If still nothing, do NOT re-post the request".
[`self-review-fallback`](self-review-fallback.md)'s "Re-check reachability every
round" was loaded in context throughout.
[#902](https://github.com/Morrison-Lab/ai-config/issues/902) is the adjacent
open issue, covering a one-shot wakeup whose named PR merged underneath it
rather than a recurring brief carrying a capability claim forward.)

## A supplied measurement carried a status-code confound

(ucdavis/bcs, 2026-08-20: a session was handed "four POSTs, HTTP 200, zero
Copilot reviews resulted" as evidence that requesting a reviewer buys
nothing on that repo.
The number was accurate and the conclusion drawn from it was not fully
supported: `hooks/no-unreviewed-pr.py`'s `_argv_close` docstring documents
that `POST /pulls/{n}/requested_reviewers` returns HTTP 200, rather than
the success code, exactly when the PR was already merged or closed --- and
adds nobody in that case, by design, not by failure.
So a 200 across all four calls is at least partly explained by PR state
rather than by the request mechanism being broken.

Checking settled it only partway: ucdavis/bcs #648 closed at
`2026-08-20T01:33:34Z` and #649 merged at `01:40:47Z`, both plausibly before
the POSTs ran, while #650 stayed open throughout the window.
Per-POST timings were never recorded, so the confound is confirmed to apply
to some of the four calls, not shown to explain all of them.
The brief's author had no way to see this from the count alone --- reading
the status code as a confound required already knowing what it encodes,
which is exactly why a supplied number needs re-deriving rather than only
re-reading.)

## A run-level conclusion stood in for a job-level one

(`Morrison-Lab/ai-config#2019`, measured 2026-08-23.
A brief handed a UMS agent the premise that `R CMD check` "never completed on
this PR", offered as measurement rather than as inference.
What had actually been queried was `ucdavis/bcs#732`'s five `R-CMD-check.yaml`
runs, four of which concluded `cancelled`.
Nobody queried the jobs inside them.

Run `32610472088` had already answered the question.
Its `macos-latest (release)` job concluded `success` at 01:58:32Z and its
`ubuntu-latest (release)` job at 02:01:21Z, about half an hour after the PR
opened;
only `windows-latest (release)` was cancelled.
So the package had checked green on two platforms while the brief was
asserting the check had produced nothing.

The premise is what makes this a case record rather than a stray error.
It was load-bearing: the agent built a `fully-clean.md` subsection on it, and
that subsection's own prescribed test --- "confirm at least one run reached a
conclusion" --- is satisfied vacuously by a `cancelled` conclusion, so the
instrument inherited the premise's defect and failed toward "clean" in exactly
the state it was written to catch.
An adversarial review found it, and the subsection was deleted rather than
patched.

The transferable half is narrower than "verify your premises".
A run-level `cancelled` says the run stopped;
it says nothing about which of that run's jobs had already finished.
"The run was cancelled" and "the check never ran" are different claims, and the
brief measured the first while asserting the second, which is why running a
query did not protect it.
`list_workflow_jobs` on any one of those four runs settles it.)
