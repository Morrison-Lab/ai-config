When an agent claims an issue it's about to work — in `gi`, `gii`, `gip`, or
`st` — open the PR **immediately**, before writing any code, and keep it a
**draft** until the implementation lands. Don't wait until the work is done to
open it.

Worked-example case records for the rules below live in
[`pr-on-claim.cases.md`](pr-on-claim.cases.md), moved out of the auto-loaded context.

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

**Marking a draft ready is a push-landed checkpoint, so verify the
implementation actually reached the branch head before `gh pr ready`.**
[`ardi`](ardi.md) already forbids claiming a fix is pushed until it is on the
PR's head commit, and its pre-push checklist makes `git rev-parse HEAD
origin/<branch>` agreeing a killer item --- but both fire *after a push* or
*before a status report*, and neither fires on the draft-to-ready transition.
That transition is where the gap bites: implementing on top of the empty
`start:` scaffold commit, running self-review, and updating the PR body all feel
like the work, so `git push` is the one step with nothing downstream to prompt
it.
The head then stays at the empty scaffold, every check is green on the empty
diff (per [`ardi`](ardi.md)'s "a PR whose branch carries no implementation is
green on every check"), and the reviewer correctly reports a zero-file diff.

So immediately before `gh pr ready`, confirm both: `git rev-parse HEAD` equals
`git ls-remote origin <branch>` (the implementation was pushed), and
`gh pr diff <N> --name-only` is non-empty (the branch carries a diff).

- **Do:** run the push-landed and non-empty-diff checks at the `gh pr ready`
  transition, exactly as before a reply asserting a push.
- **Don't:** mark a draft ready on the strength of a local commit, green checks,
  and an updated PR body --- none of those proves the branch head moved.

(Morrison-Lab/gha#427, 2026-08-06: a changelog fix was committed locally,
self-reviewed, and the PR body updated, then `gh pr ready` ran and review was
requested --- but `git push` never ran, so the branch head stayed at the empty
`start:` scaffold and the reviewer reported the diff empty and the described fix
"has not actually been committed to the branch".)

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
Use `--silent`, or `--jq` **inside** the `gh api` call, when the output needs narrowing.
Both keep the POST the last command.

- **Do:** narrow the response with a flag on the POST itself rather than a downstream pipe.
- **Don't:** pipe the POST anywhere, including to `tail`, `head`, or `jq` --- the hook cannot tell a formatting pipe from a chained verification, because the shell does not either.

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

**That blocked-request test has a false positive, and it fires on more repos than the section above describes.**
Where a ruleset auto-requests Copilot, the POST returns success naming the reviewer and `reviewRequests` reads **empty** moments later.
That is the literal signature the test above calls blocked --- request gone, no review yet --- so the two paragraphs contradict each other, and the earlier one is the one that is wrong.

The auto-requesting ruleset was offered as the likeliest reconciliation, and it is now **ruled out as the general explanation**.
`Morrison-Lab/ai-config` produces the identical signature while carrying no `copilot_code_review` rule at all, at either repository or organization scope.
Measured 2026-08-06 on PR #1219: the POST returned `HTTP/2.0 201 Created` with a `Location` header, and a read five seconds later returned `["d-morrison"]` with Copilot absent, reproduced twice.
A separately-issued `d-morrison` request persisted in that same list, so nothing is wiping the list structurally --- only Copilot's entry goes.

*Why* the entry disappears is still unexplained, and this section deliberately declines to name a replacement mechanism.
What is measured is the disappearance, and nothing yet accounts for it.
Do not upgrade a guess about it into a finding, and do not probe it harder than the question deserves --- each probe consumes the per-user Copilot quota that is usually the real reason Copilot is absent, so the experiment damages the thing it would explain.

**The operative point is that three surfaces fail to discriminate here, and only a fourth one does.**
The pending-reviewer list empties whether or not a ruleset asked.
The ruleset query comes back negative whether or not the request reached Copilot.
The reviewer's own check run goes green whether it reviewed, refused, or stayed silent, per [`fully-clean`](fully-clean.md)'s fifth case and its silent-reviewer sibling.
Only the posted review **body** distinguishes those outcomes.

So an empty pending list after a 201 supports one conclusion and not a second.
It is **not** evidence the request was blocked.
It is **also not** evidence that a review is coming, which is a separate claim and an unsupported one.
At ai-config what follows is a refusal rather than a review, so the two claims come apart there in the clearest possible way.
Note that this point is indifferent to *why* the reviewer refused --- quota, a platform incident, anything else --- because a refusal is not a verdict whatever produced it.

Route to the self-review fallback on a **read refusal body**, never on an empty pending list.
[`fully-clean`](fully-clean.md) is explicit that a refusing reviewer is not "reachable", so a refusal legitimately hands the external-verdict requirement to whichever other reviewer is working.
An empty pending list hands it to nobody, because it has established nothing either way.
Note also that a refusal body is itself proof the request **arrived**, which is the cleanest available disproof of "blocked".

Read the ruleset anyway --- it is one cheap call, and on a repo that does carry the rule it explains the disappearance outright --- but read it for what it can actually tell you.
`ucdavis/bcs` is the known example, per [`memories/github.md`](../../memories/github.md): ruleset `19248641` returns `{"review_on_push":true,"review_draft_pull_requests":true}`.
The effective-rules endpoint covers organization-level rulesets alongside the repository's own, in a single call, which the per-ruleset loop in [`memories/github.md`](../../memories/github.md) does not (that file's own note on org-level rulesets says why):

```bash
gh api "repos/<owner>/<repo>/rules/branches/<branch>" \
  --jq '[.[] | select(.type=="copilot_code_review")]'
```

A `review_on_push: true` result means the disappearance is expected on that repo, and that the next push re-requests automatically.
An empty result means only that no ruleset explains the disappearance.

- **Do:** decide whether a reviewer is engaged by reading its posted review body, since the pending list, the ruleset, and the check run each fail to discriminate.
- **Do:** check for a `copilot_code_review` rule before concluding that a vanished pending request means a blocked one.
- **Don't:** read an empty pending list as evidence the request was blocked, nor as evidence a review is on its way.
- **Don't:** treat a negative ruleset result as establishing that the request failed --- ai-config returns exactly that while the request still reaches Copilot.
- **Don't:** re-POST on a repo whose ruleset auto-requests --- the retry changes nothing and the empty read repeats.

The deriving queries, so a later reader re-measures rather than inheriting this:

```bash
# No copilot_code_review rule, at either scope (returns an empty array here).
gh api "repos/Morrison-Lab/ai-config/rules/branches/main" \
  --jq '[.[] | select(.type=="copilot_code_review")]'

# Every Copilot review is a refusal (returns 0 substantive here).
gh api graphql -f query='{search(query:"repo:Morrison-Lab/ai-config is:pr is:merged", type:ISSUE, last:60){nodes{... on PullRequest{reviews(first:20){nodes{author{login} body}}}}}}' \
  --jq '[.data.search.nodes[].reviews.nodes[]
         | select(.author.login=="copilot-pull-request-reviewer")]
        | {total: length,
           refusals: ([.[] | select(.body | test("unable to review|quota limit"; "i"))] | length),
           substantive: ([.[] | select(.body | test("unable to review|quota limit"; "i") | not)] | length)}'
```

(Measured 2026-08-06 on `Morrison-Lab/ai-config`.
The repository's only ruleset is named `main` and carries rule types
`deletion,non_fast_forward,pull_request`, and the effective-rules endpoint
returns zero `copilot_code_review` entries, so the org scope is covered too.
The second query returned `substantive: 0` against every Copilot review object
in its window, with `total` and `refusals` equal to each other at around 40.
Read `substantive: 0` as the finding and treat the total as volatile: the
`last:60` window slides as PRs merge, so two runs minutes apart returned 40 and
then 39 without anything about Copilot having changed.
An earlier reading of this same evidence counted reviewer *logins* rather than
review *bodies*, saw `copilot-pull-request-reviewer` as the only reviewer, and
concluded Copilot was active here --- which inverted the finding, since every
one of those review objects is the refusal string quoted in
[`memories/github.md`](../../memories/github.md).
That is the login-versus-body distinction
[`fully-clean`](fully-clean.md)'s fifth case already warns about, met in the
direction that flatters the repo.)

This is part of opening the PR, not a follow-up task.
A status sentence like "review owed on #N" is the anti-pattern: it names a debt that should already have been discharged, the same way an offer to file an issue names work instead of doing it.
The sentence is the trigger to request the review now.

- **Do:** request the reviewer explicitly in the same step that opens the PR or marks it ready.
- **Do:** verify the request landed from the API response plus a fresh pending-request or current-head-review read.
- **Don't:** treat a PR's auto-triggered checks as evidence that every reviewer is engaged.
- **Don't:** write "review owed" or "still need to request review" into a status report; go request it instead.

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
