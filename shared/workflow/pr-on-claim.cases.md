# Case records: pr-on-claim

Worked-example case records for the rules in
[`pr-on-claim.md`](pr-on-claim.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## Run the reviewer POST as the sole (or last) command

(Morrison-Lab/rpt#181, 2026-08-03: the POST was chained ahead of `gh pr view`/`gh pr checks` in one call across six turns, so the hook re-fired every Stop;
running the POST bare discharged it.
The failure was misread as the hook not recognizing a Copilot quota refusal, which it was not about.)

## "Nothing chained after it" includes a formatting pipe

(Morrison-Lab/ai-config#1139, 2026-08-04: the pipe variant, in a session that had already cited this rule's reasoning aloud earlier in the same hour.
The request was written `gh api -X POST .../requested_reviewers -f 'reviewers[]=...' 2>&1 | tail -3`, and it genuinely succeeded --- the response named `Copilot` in `requested_reviewers`, and Copilot posted its quota refusal at `07:22:15Z`.
The hook still fired at Stop, correctly, because `tail` owned the exit status.
Re-running the POST bare discharged it and produced a second, identical refusal at `07:53:03Z`.)

## The blocking message prescribes a non-dischargeable shape

(Morrison-Lab/ai-config#3010, 2026-09-02, and the third occurrence of the chained-request mistake after rpt#181 and ai-config#1139 above.
The session ran the request across a run of successive turns, chaining the block message's own verify command after the POST each time, which is what left the request non-last;
the hook fired after every one of them, and the loop ended on the first turn that ran the POST as the sole command in its call.
Four Copilot reviews landed on the PR while this was going on, at `15:51:54Z`, `16:43:37Z`, `16:47:16Z`, and `17:00:45Z`.

**Take the turn and POST counts from the timeline, not from the session's own narration, because the two disagree.**
That session reported eight POSTs across nine turns.
`gh api repos/Morrison-Lab/ai-config/issues/3010/timeline` carries four `review_requested` events, at `15:47:51Z`, `16:39:35Z`, `16:43:40Z`, and `16:56:17Z`.
A POST that adds a reviewer emits such an event, so at most four of the claimed eight demonstrably added anyone, and the discrepancy is unexplained.
That gap is itself the lesson the record is about: a session in this loop cannot tell a request that failed from one that was not last, and it cannot reliably count its own either.

The first two occurrences were a session composing the wrong shape on its own.
This one had the rule written down twice already, in `pr-on-claim.md` and in `pr-on-claim.rationale.md`, while the message a blocked session actually reads stated it for `gh pr edit --add-label` and not for the request.
That is why #3017 proposes fixing the message rather than adding another sentence of prose.

One smaller finding from the same turns: the message's verification query counts Copilot reviews on the PR rather than on the head, and returned 1 over a review that predated a force-push.

Tracked as [ai-config#3017](https://github.com/Morrison-Lab/ai-config/issues/3017), open at the time of writing.
The PR was open when this was written, so its review and event counts drift;
the figures above are what the endpoints returned on 2026-09-02.)

## The blocked-request test's false positive on auto-requesting repos

(Morrison-Lab/ai-config#1077, 2026-08-03: two explicit requests each returned `["Copilot"]` and each left `reviewRequests` empty within a minute, and both were reported as a possible blocked/silent reviewer.
The repo's `main` ruleset carried `copilot_code_review` with `review_on_push: true` and `review_draft_pull_requests: false` as of 2026-08-03, so neither request was ever needed.
Copilot separately did stay silent on that PR, which is the distinct third state [`review-verdict-pitfalls`](review-verdict-pitfalls.md) records --- the point here is that the empty pending-list was not the evidence for it.
**This does not describe the repo's current state.**
Re-measured 2026-08-04, the rule was absent: `main`'s ruleset carried only `deletion`, `non_fast_forward`, and `pull_request`, no org-level parent ruleset supplied it either, and the change happened in the one day between the two measurements.
Re-read the ruleset before trusting this record for `copilot_code_review`'s presence, per [`timestamp-volatile-claims`](../writing/timestamp-volatile-claims.md) --- the query in the "Three surfaces fail to discriminate a vanished pending request" case record just below reconfirmed the same absence on 2026-08-06, two days later.
Tracked as [ai-config#1148](https://github.com/Morrison-Lab/ai-config/issues/1148).)

## Request the reviewer in the same step; don't leave it "review owed"

(Morrison-Lab/ai-config #1038 and #1040, 2026-08-02: both PRs were opened around 07:00Z and then reported as still owing review requests.
They had zero Copilot reviews until the user asked why no review had been requested about ten minutes later.
The repo's `claude-review` workflow was failing for the same context-closure limit that made #1029's review fail on every attempt, so a PR without the explicit Copilot request had no working reviewer despite review-shaped checks.)

## Do not `Closes` a parent issue on a partial ship

(Morrison-Lab/gha#373 / #516 / #517, 2026-08-19: `gi` opened the draft with
`Closes #373` and shipped only Case B of a later A/B split. The merge
closed #373, so Case A --- a human security decision the issue itself
said not to fold into an unrelated PR --- left the tracker until wrap-up
filed #517. File the leftover issue before merge and drop `Closes` on the
parent.)

## Verify you switched branches before the second issue's code

(ucdavis/bcs `gia` session, 2026-07-06: SLURM-hardening changes for issue #286
were written while still on issue #281's `chore/renv-explicit-snapshot`
branch --- caught before pushing, but only by re-checking `git status`/`git
diff --stat` against expectations, not because anything failed.)

## Marking a draft ready is a push-landed checkpoint

(Morrison-Lab/gha#427, 2026-08-06: a changelog fix was committed locally,
self-reviewed, and the PR body updated, then `gh pr ready` ran and review was
requested --- but `git push` never ran, so the branch head stayed at the empty
`start:` scaffold and the reviewer reported the diff empty and the described fix
"has not actually been committed to the branch".)

## The reviewer-request POST must be the sole command in its call

(Morrison-Lab/ai-config#1367, 2026-08-09: investigated after chaining `gh api ".../requested_reviewers" -X POST ... --silent && echo "requested"` in one Bash call on a `Lacaedemon/sparta` PR; the Stop hook correctly flagged it, and recovery was one extra Bash call.)

## Three surfaces fail to discriminate a vanished pending request

(Measured 2026-08-06 on `Morrison-Lab/ai-config`.
The repository's only ruleset is named `main` and carries rule types
`deletion,non_fast_forward,pull_request`, and the effective-rules endpoint
returns zero `copilot_code_review` entries, so the org scope is covered too.
The second query returned
`{"total":39,"refusals":39,"substantive":0,"since_override":39,"before_incident":39,"latest":"2026-08-06T09:14:23Z"}`.
Read `substantive: 0` as the finding, and the two timestamp aggregates as what
rules the 2026-08-06 Actions incident out as a rival cause for *this* set, per
`Morrison-Lab/ai-config#1223`, which owns that discrimination.
Treat the counts themselves as volatile: the `last:60` window slides as PRs
merge, so two runs minutes apart returned 40 and then 39 without anything about
Copilot having changed.
An earlier reading of this same evidence counted reviewer *logins* rather than
review *bodies*, saw `copilot-pull-request-reviewer` as the only reviewer, and
concluded Copilot was active here --- which inverted the finding, since every
one of those review objects is the refusal string quoted in
[`memories/gh-cli.md`](../../memories/gh-cli.md).
That is the login-versus-body distinction
[`review-verdict-pitfalls`](review-verdict-pitfalls.md)'s fifth case already
warns about, met in the direction that flatters the repo.)

## Requesting Copilot discharges nothing on a dispatch-only repo

(`Morrison-Lab/ai-config#1235`, 2026-08-06: opened by a subagent that correctly requested Copilot, which was quota-exhausted and refused.
The PR then read 4 check runs, 0 pending and 0 failing, with zero Claude reviews, because nothing had dispatched one.
`claude-review.yml` there carries `workflow_dispatch` and nothing else, while `ucdavis/bcs`'s `claude-code-review.yml` carries `pull_request: [opened, synchronize, ready_for_review, reopened]` --- and the session had spent the day in the second repo, where every push fired a review and no one ever had to ask.
`hooks/no-unreviewed-pr.py` had fired correctly on #1222 earlier in that same session and stayed silent here, discharged by the Copilot POST exactly as its contract says.
The user's correction was "you should be requesting ai bot reviews on prs when you think they're ready", followed immediately by "(if github actions isn't triggering one for you)".
A second correction was needed before this pass ran at all: the first response was to dispatch the missing review and carry on, where `CLAUDE.md`'s "Correcting your own understanding of a technical issue is itself a trigger" puts the pass at the correction rather than after the work the correction unblocked.)

## A redaction PR must not get an AI reviewer

(Morrison-Lab/ai-config#1392, from `ucdavis/bcs#615`, which removed 47 real participant identifiers.
`redaction-gate` passed and `ai-review` reported `skipping`, as designed, and the guard then fired on six consecutive turns demanding a request whose only correct response was to refuse.
Refusing did not discharge it, recording the refusal on the PR did not, and the maintainer deciding "hold, no AI reviewer" did not --- which is the shape [`algorithmatize-checks`](algorithmatize-checks.md) warns about, reached by an unusual route: the threshold was sharp and the **discharge set was incomplete**.)

## A caller's `on:` block is not the workflow's trigger conditions

(`Morrison-Lab/wai#54`, 2026-08-09: wai's `claude-code-review.yml` carries
`types: [opened, synchronize, ready_for_review, reopened]` and no draft
filter, which was read as this repo burning a review round on every draft
scaffold PR.
It does not.
The caller is a 90-line delegation to
`Morrison-Lab/gha/.github/workflows/claude-code-review.yml@v2`, whose
`gather-context` and review jobs both gate on
`github.event.pull_request.draft == false` at lines 185 and 346.
The false premise reached a UMS brief as a candidate learning and was caught
only by cloning gha and grepping it.)
