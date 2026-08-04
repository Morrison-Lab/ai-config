When an agent claims an issue it's about to work — in `gi`, `gii`, `gip`, or
`st` — open the PR **immediately**, before writing any code, and keep it a
**draft** until the implementation lands. Don't wait until the work is done to
open it.

**Why up front.** The claim comment on the issue is easy to miss, and it isn't
what other sessions check. The authoritative in-flight signal is the issue's
cross-referenced **open PRs** — the check `gi` runs before grabbing an issue.
Until a PR exists, a parallel issues-sweep can grab the same issue and build a
duplicate. An open PR closes that window: it shows in `gh pr list` and the
issue's timeline, and links the issue via `Closes #N`. An open PR is the
clearest "someone is working this" signal there is — stronger than a comment.
This is the strong form of the "open and link the PR promptly" note in
[`claim-pr`](claim-pr.md).

**Mechanics.** Branch, then open the PR against an empty commit:

```bash
git fetch origin main -q
git checkout -b <type>/<slug> origin/main
git commit --allow-empty -m "start: <issue title> (closes #<N>)"
git push -u origin HEAD
gh pr create --draft --title "<title>" --body "Closes #<N>

WIP — opened up front to claim the issue; implementing now."
```

The empty commit gives the branch a diff so the PR can open with no code yet.
In a remote/web session where `gh` is absent, push the empty commit and open
the PR with the GitHub MCP tools instead (`mcp__github__create_pull_request`
with `draft: true`).

**Draft, not ready-for-review — deliberately.** A draft doesn't trigger the
`@claude` review bot, so no review round is spent on an empty or half-finished
diff. Implement on top, pushing commits to the same PR; when the change is
complete and the repo's checks pass, mark the PR **ready for review**
(`gh pr ready <N>`, or `mcp__github__update_pull_request` with `draft: false`).
Marking it ready is what kicks off ARDI.

**Request the external reviewer in the same stride.** Opening a PR or marking a draft ready can trigger the repo's own review workflow, but that does not summon every reviewer.
For a repository whose Copilot review isn't already scheduled automatically (see the caveat below), Copilot only reviews when explicitly requested with the requested-reviewers API or the equivalent UI action --- the `REQUEST_COPILOT_REVIEW` operation token (`tool-mappings.md`):

```bash
gh api -X POST "repos/<owner>/<repo>/pulls/<N>/requested_reviewers" \
  -f 'reviewers[]=copilot-pull-request-reviewer[bot]'   # REQUEST_COPILOT_REVIEW
```

Then, in a **separate** call (see the sole-command rule below), verify it landed:

```bash
gh pr view <N> --json reviewRequests,reviews
gh pr checks <N>
```

In a remote/web session without `gh`, use the equivalent tool
(`mcp__github__request_copilot_review`) instead.

**Run that `requested_reviewers` POST as the sole (or last) command in its Bash call.**
The [`no-unreviewed-pr`](../../hooks/no-unreviewed-pr.py) Stop hook discharges the reviewer-request obligation only on positive evidence the request itself succeeded, and the one reliable success signal is the whole Bash call's exit status --- which belongs to that call's **last** command.
So chaining the verification reads (`gh pr view ... --json reviews`, `gh pr checks`) *after* the POST in the same call makes the request non-last, which the hook treats as ambiguous: it keeps warning even though the POST returned 200.
Run the POST alone, then do the pending/reviews/checks verification in a **separate** later call.
This is [`fail-fast`](../principles/fail-fast.md)'s "a combined result cannot attribute a per-step outcome" applied to a review request;
the same rule governs a `gh pr ready` draft transition the hook tracks.

- **Do:** issue the Copilot-request POST as its own Bash call, with nothing chained after it.
- **Don't:** fold the `--json reviews` / `gh pr checks` verification into the same call --- that makes the request non-last, and the hook cannot discharge it.

**"Nothing chained after it" includes a pipe added purely to trim the output.**
The rule above is stated in terms of *verification reads*, which is how it is usually broken and is also the version a reader recognizes themselves in.
A formatting pipe does not feel like chaining a second step --- `| tail -3` or `| jq` is a decision about how much of one command's output to look at, not an extra command in a sequence --- so it slips past a reader who has just agreed with the rule as written.
The shell does not draw that distinction: the last command in the pipeline owns the exit status either way, so `gh api ... | tail -3` leaves the POST non-last exactly as a chained `gh pr view` does.
Use `--silent`, or `--jq` **inside** the `gh api` call, when the output needs narrowing; both keep the POST the last command.

- **Do:** narrow the response with a flag on the POST itself rather than a downstream pipe.
- **Don't:** pipe the POST anywhere, including to `tail`, `head`, or `jq` --- the hook cannot tell a formatting pipe from a chained verification, because the shell does not either.

(Morrison-Lab/rpt#181, 2026-08-03: the POST was chained ahead of `gh pr view`/`gh pr checks` in one call across six turns, so the hook re-fired every Stop;
running the POST bare discharged it.
The failure was misread as the hook not recognizing a Copilot quota refusal, which it was not about.)

(Morrison-Lab/ai-config#1139, 2026-08-04: the pipe variant, in a session that had already cited this rule's reasoning aloud earlier in the same hour.
The request was written `gh api -X POST .../requested_reviewers -f 'reviewers[]=...' 2>&1 | tail -3`, and it genuinely succeeded --- the response named `Copilot` in `requested_reviewers`, and Copilot posted its quota refusal at `07:22:15Z`.
The hook still fired at Stop, correctly, because `tail` owned the exit status.
Re-running the POST bare discharged it and produced a second, identical refusal at `07:53:03Z`.)

**Some repos schedule Copilot automatically, and this step is redundant there.**
A repository ruleset can carry a `copilot_code_review` rule with
`review_on_push: true` (and optionally `review_draft_pull_requests: true`),
which re-requests Copilot on every push with no explicit request from anyone
--- see [`memories/github.md`](../../memories/github.md)'s "Required checks are
not the only thing a ruleset carries" section for how to read that off a
repo's rulesets.
When that applies, an explicit request lands while Copilot is already a
pending reviewer, which the API can (unreliably) answer with either `201` or
`422` --- don't spend a call resolving which; either response is consistent
with the ruleset already having asked.
Where you can't tell whether the repo has such a ruleset, request explicitly
anyway --- a redundant request costs nothing, while skipping it on a repo
without automatic review leaves Copilot unrequested.

Run that request immediately after `gh pr create` for a non-draft PR, or immediately after `gh pr ready` for a draft PR, before writing any status report.
Verify the request landed: the POST response should include the requested reviewer, then a fresh read should show either a pending review request or a new review/check from that reviewer on the current head.
A POST response alone is not enough; if the pending request disappears and no current-head review appears after a short poll, treat the reviewer request as blocked and start the documented fallback.
Do not leave it as "review owed".

**That blocked-request test has a false positive, and it is on exactly the repos the section above describes.**
Where a ruleset auto-requests Copilot, the POST returns success naming the reviewer and `reviewRequests` reads **empty** moments later.
That is the literal signature the test above calls blocked --- request gone, no review yet --- so the two paragraphs contradict each other on any repo with `review_on_push: true`, and the earlier one is the one that is wrong there.

The empty read is observed, on two repos; *why* it comes back empty is not.
[`memories/github.md`](../../memories/github.md) records the same
201-then-empty sequence and offers auto-requesting as the **likeliest
reconciliation, explicitly untested** --- deliberately so, since probing it
consumes the per-user quota that is usually the real reason Copilot is absent.
Keep that hedge: what matters operationally is that an empty pending-list is
uninformative on such a repo, which holds whatever the mechanism turns out to
be.

Reading it as blocked costs more than a wasted call.
It routes you to the self-review fallback while a working reviewer is queued, which [`fully-clean`](fully-clean.md) treats as a fallback for when *no* external reviewer is reachable --- so the PR ends up carrying a weaker verdict than it could have.

Settle it by reading the ruleset rather than by polling harder.
[`memories/github.md`](../../memories/github.md) gives the single-ruleset form;
this loop is the same query when you do not already know the id, so keep the
two in sync if either changes:

```bash
for id in $(gh api "repos/<owner>/<repo>/rulesets" --jq '.[].id'); do
  gh api "repos/<owner>/<repo>/rulesets/$id" \
    --jq '.rules[]? | select(.type=="copilot_code_review") | .parameters'
done
```

A `review_on_push: true` result means the disappearance is expected,
and that the next push re-requests automatically.
Only then does an absent review become a question about the reviewer rather
than about the request.

- **Do:** check for a `copilot_code_review` rule before concluding a vanished pending request means a blocked one.
- **Don't:** re-POST the request on such a repo --- it is auto-requested on every push, so the retry changes nothing and the empty read repeats.

(Morrison-Lab/ai-config#1077, 2026-08-03: two explicit requests each returned `["Copilot"]` and each left `reviewRequests` empty within a minute, and both were reported as a possible blocked/silent reviewer.
The repo's `main` ruleset carries `copilot_code_review` with `review_on_push: true` and `review_draft_pull_requests: false`, so neither request was ever needed.
Copilot separately did stay silent on that PR, which is the distinct third state [`fully-clean`](fully-clean.md) records --- the point here is that the empty pending-list was not the evidence for it.)

This is part of opening the PR, not a follow-up task.
A status sentence like "review owed on #N" is the anti-pattern: it names a debt that should already have been discharged, the same way an offer to file an issue names work instead of doing it.
The sentence is the trigger to request the review now.

- **Do:** request the reviewer explicitly in the same step that opens the PR or marks it ready.
- **Do:** verify the request landed from the API response plus a fresh pending-request or current-head-review read.
- **Don't:** treat a PR's auto-triggered checks as evidence that every reviewer is engaged.
- **Don't:** write "review owed" or "still need to request review" into a status report; go request it instead.

(Morrison-Lab/ai-config #1038 and #1040, 2026-08-02: both PRs were opened around 07:00Z and then reported as still owing review requests.
They had zero Copilot reviews until the user asked why no review had been requested about ten minutes later.
The repo's `claude-review` workflow was failing for the same context-closure limit that made #1029's review fail on every attempt, so a PR without the explicit Copilot request had no working reviewer despite review-shaped checks.)

**Don't mark ready within seconds of the final push — the two review runs race
and the WRONG one can get cancelled.** On repos whose review workflow runs on
`pull_request` (`synchronize`, `ready_for_review`) with `concurrency:
cancel-in-progress`, a push followed immediately by `gh pr ready` fires two
runs a second apart: the ready-event run (recorded against the pre-push head)
and the push's synchronize run (recorded against the new head). The
cancellation can land on the **newer** run, leaving the current head with a
cancelled review job and a red require-review check — while the surviving
older run can still post a genuine, current verdict: a reviewer that fetches
the PR's diff at review time (sparta's does, via `gh pr diff` per its own run
transcript) sees the pushed code even though the run is nominally tied to the
pre-push head. Read the posted review and confirm it actually discusses the
current head's changes before trusting it. If this happens, don't push or
re-mention: `gh run rerun <cancelled-run-id>` re-reviews the same head and
turns the head's own checks green. Prevention: push the implementation first,
wait until the synchronize-triggered review run appears in GitHub Actions,
then mark ready as its own later step.
(Hit on `Lacaedemon/sparta#898`, 2026-07-15.)

**Check whether the race can even arise before paying for that wait --- on
many repos it cannot, and the check is one field.**
The race needs *two live runs*.
But the paragraph above sits in tension with this fragment's own
premise that "a draft doesn't trigger the `@claude` review bot": where that
holds, the push's synchronize run **skips** rather than running, so there is
nothing in flight for the `ready_for_review` run to cancel.
Which way a given repo behaves is visible directly --- read the review job's
conclusion on the push's own run before marking ready:

- `skipped` -> no live run, mark ready immediately, no wait needed.
- `in_progress`/`queued` -> the sparta case; wait for it to finish first.

Read it with `gh pr checks <N>`, or `pull_request_read` `get_check_runs` in a
session without `gh` (see [`tool-mappings.md`](../../tool-mappings.md)).
Mind the casing split [`fully-clean`](fully-clean.md) warns about: REST
returns lowercase `status`/`conclusion` (`completed`, `skipped`), while
`gh pr checks`/GraphQL return uppercase `state` values.

Don't generalize from either repo. sparta#898 is real, and so is the opposite;
the deciding factor is whether that repo's review workflow gates on
`github.event.pull_request.draft`, which is a property of the workflow, not
something to assume. (d-morrison/altdoc#55, 2026-07-25: the draft's
synchronize-triggered `review / claude-review` reported `skipped`, so marking
ready seconds after the push was safe and the subsequent `ready_for_review`
run posted a normal verdict.)
`d-morrison/ai-config` behaves the same way: its draft synchronize run
reports `review / claude-review` and `review / require-review` as `skipped`,
so no wait is needed there either.
(ai-config#754, 2026-07-28.)

So the per-issue order becomes: claim → branch → **open the draft PR now** →
implement → mark ready-for-review → ARDI.

**Working several issues in one session? Verify you actually switched branches
before writing the second issue's code.** The `git checkout -b <type>/<slug>
origin/main` you ran for issue 1 doesn't carry over to issue 2 --- you have to
run it again with a new branch name for each new issue. Forgetting leaves the
working tree on issue 1's branch, so issue 2's edits land in the same
commit/PR as issue 1's --- silently, since nothing errors (there's no reused
branch name here to trigger `git checkout -b`'s own "already exists" error).
Run `git branch --show-current` immediately
before the first edit for every new issue, not just the first one in the
session, and confirm it matches the branch you just created for *this* issue.
(ucdavis/bcs `gia` session, 2026-07-06: SLURM-hardening changes for issue #286
were written while still on issue #281's `chore/renv-explicit-snapshot`
branch — caught before pushing, but only by re-checking `git status`/`git
diff --stat` against expectations, not because anything failed.)
