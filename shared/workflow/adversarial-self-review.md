Every self-review is an **adversarial review by a separate subagent**.
Whenever this corpus calls for reviewing your own work --- before a push, as the fallback when the external reviewer is down, or the project-conventions pass a clean verdict does not discharge --- dispatch it to a reviewer with its own context and an adversarial brief, and take its findings as findings.
The authoring session never reviews its own diff inline.

[`self-review-fallback`](self-review-fallback.md) governs *when* a self-review is owed and to what standard.
This governs *who performs it*, which that fragment left to the author by default.

## Why the authoring session cannot be the reviewer

A reviewer's job is to read what the diff **says**.
The author knows what it was **meant** to say, and that knowledge is not removable by care --- it is the context the session is made of.
So the author reads the artifact and recovers the intent, which is confirmation rather than review.

This corpus already names the shape.
[`verify-the-right-artifact`](verify-the-right-artifact.md) is about verifying an adjacent artifact thoroughly instead of the target one, and the adjacent artifact here is the intent in your own head --- the one artifact that is never wrong, because it is what the diff was written from.
Nothing about the check feels skipped: the reading is real, the standards are applied, and the answer comes back clean.

Two consequences worth stating separately, because they are easy to run together.

**A subagent buys independence of intent, not independence of vendor.**
A Claude subagent reviewing a Claude diff shares the training and therefore the blind spots, exactly as [`self-review-fallback`](self-review-fallback.md)'s cross-vendor section says.
What it does not share is the account of what the change was for.
Those are different independences, and this rule buys the second one only.

**So the subagent is the floor, not the ceiling.**
Where a cross-vendor reviewer is reachable --- [`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.md), or the repo's own configured reviewer --- it is still worth chasing, and its clean verdict is still not the one a PR is reported ready on while Claude is reachable (see [`fully-clean`](fully-clean.md)).

## What "separate" requires

**Its own context window.**
The near-miss is the pass performed in the same turn under a reviewer framing --- "now let me look at this adversarially" --- and it reads as compliance, because the prose that comes out is adversarial in tone and nothing in the output distinguishes it from a dispatched review.
The test is mechanical rather than tonal: an `Agent` call was made, or it was not.

**Foreground, not background.**
A background dispatch returns an agent id rather than a report, so the verdict is not the call's result and the work you are gating cannot wait on it.
This is the Agent tool's own criterion for `run_in_background: false` --- the very next action depends on the answer.

**Read-only.**
The reviewer reports; the author disposes.
A reviewer that can edit turns a finding into a silent fix, which loses the finding and the disposition together.

**No Agent tool, or no reviewer registered here?**
A separate CLI is the same move and a stronger one --- [`delegate-to-codex`](../../skills/delegate-to-codex/SKILL.md) or [`delegate-to-opencode`](../../skills/delegate-to-opencode/SKILL.md).
The `adversarial-reviewer` persona also lives at `.claude/agents/` and `.opencode/agents/`, which are project agents: a session rooted in another repo may not be able to resolve it at all ([ai-config#1921](https://github.com/Morrison-Lab/ai-config/issues/1921) tracks shipping it alongside the guard).

Note what that does to the pre-push guard, since the two rules meet here and pull opposite ways.
A CLI's verdict never becomes an `Agent` call's `tool_result`, so the guard cannot see it however real the review was.
Prefix the push itself with `ALLOW_UNREVIEWED_PUSH=1` there, and say in the same reply which reviewer produced the verdict and why the subagent route was unavailable --- the override covers a push whose verdict the guard cannot check, not only a push with nothing to check.
The same applies to a session whose reviewer is registered from a stale definition, which is the case on any rollout of a change to the persona itself.
Where no second context is reachable at all, say so in the review itself rather than letting an inline pass be reported as a dispatched one.

## Brief it with the diff and the standards, never with your rationale

The instinct on writing the brief is to supply the context that makes the change make sense --- what the problem was, why this approach, what the alternatives were.
That re-imports precisely what dispatching was meant to exclude.
A reviewer holding your account of the change checks the diff against **it** rather than against the repo, and agrees, because the two were written by the same session minutes apart.

Give it the base ref, the paths, the standards that apply, and the question.
Where the change's own reasoning matters, it is in the diff --- a comment, a docstring, a fragment --- and the reviewer should be reading it there, where a later reader will.
Scope is not rationale: which branch, which base, where the tests live, and what is out of scope are facts the reviewer cannot derive and must be told.

- **Do:** hand over `git diff <base>...HEAD`, the applicable rules, and the question.
- **Don't:** hand over the case for the change.
  If it is not persuasive from the diff alone, that is the finding.

### The PR's own review history is rationale you cannot withhold

The rule above governs the brief you write.
A reviewer reading the **PR** gets a second channel you never chose to open: the claim comment saying how many rounds ran, the round-by-round commit messages, and the `# round-2 review finding 8` markers a fix left behind in the test file.
Each of those is a true record, and none of them was written as an argument, which is why the effect is invisible from both ends --- nothing in the artifact reads as persuasion, and nothing in the verdict reads as deference.

Measured 2026-08-24 Pacific on [ai-config#2131](https://github.com/Morrison-Lab/ai-config/pull/2131).
The repo's own reviewer returned **Ready for merge** and named the history in its own justification: the PR's history and the round markers baked into the test file "show the near-misses I would normally look for [...] were already found and fixed in earlier rounds, and my independent probing did not surface anything beyond that."
A cross-vendor pass on that same head then returned 11 findings, 8 of them blocking (see [`self-review-fallback.cases.md`](self-review-fallback.cases.md), "A clean same-vendor verdict over eight blocking cross-vendor findings").

**State what is observable, which is narrower than it first looks.**
That verdict also lists nine verification steps it ran, so "it probed less" is a claim about effort that those steps weigh against, and at least one other explanation fits --- the reviewer probed normally and the diff was, in its own words, "almost entirely prose/documentation plus one well-isolated, warn-only hook with unusually thorough self-testing".
What is observable is that **the history entered the justification**: a reason for finding nothing was supplied by the artifact rather than derived from the diff.
That is enough, because a verdict resting partly on prior rounds is partly a re-reading of those rounds, so it is worth less as corroboration than its independence suggests --- however hard it worked.

**A `# round-N` marker is a changelog of past MISSES, not a certificate of coverage.**
It records that one defect was found there once.
It says nothing about the family that defect belonged to, and reading it as evidence of scrutiny inverts its meaning: the marker points at a line that was wrong, and a reader who takes it as a coverage claim reads it as a line that has been checked.

**The loop is self-reinforcing, which is what makes it a rule rather than a matter of care.**
More rounds produce a more reassuring history, which is available as a reason to stop, and a diff that accumulates many rounds is often one complex enough to need more.
So the effect is strongest exactly where it is most costly.
That is [`learn-from-review-findings`](learn-from-review-findings.md)'s convergence rule reaching a reviewer who never ran the earlier rounds: there a series narrows its own search space by inheriting findings, and here a *fresh* reviewer inherits the narrowing from the artifact instead.

- **Do:** quote back the sentences in a verdict that cite the PR's history rather than the diff, and say what independent evidence is left once they are set aside.
- **Do:** label a regression case with the property it pins rather than the round that found it, so the comment is a specification a reviewer can check instead of a report that scrutiny already happened.
- **Don't:** read a long visible review history as coverage --- it is a record of what was found, and every entry marks a place a defect once lived.
- **Don't:** count a verdict that cites prior rounds in its justification as a fully independent round;
  that much of it is a re-reading of the rounds it names, however hard the rest of it worked.

## Its findings are findings

[`self-review-fallback`](self-review-fallback.md) already rules out surfacing a defect in your own review and closing it on your own estimate of its blast radius.
A dispatched reviewer makes that concrete, because the finding now has an author who is not you: give each one Address, Rebut, or Defer-to-a-tracked-issue per [`ard`](../../skills/ard/SKILL.md), in writing, exactly as for a finding from the PR's own reviewer.
"I know why that is fine" is a Rebut, and a Rebut is something you would be willing to post.

## The posted fallback comment is the reviewer's report, not an author composite

When the self-review is posted as a PR comment, the comment body **is**
the dispatched reviewer's structured report, then the required
disclosure marker from
[`disclose-agent-authorship`](disclose-agent-authorship.md).
The marker is forge attribution, not author recap.
Dispatching the reviewer and then writing a different review body is the
same failure as reviewing inline, one step later: the authoring session
still composed the text that readers treat as the review.

Measured 2026-08-25 on
[ai-config#2234](https://github.com/Morrison-Lab/ai-config/pull/2234#issuecomment-5415839535).
A foreground `Task` dispatch
(`bc-61fbadd0-7970-5b2d-8775-4924a28e09a1`, catalog name
"Final review HEAD f71c02ea") ran on `f71c02ea`.
The posted comment was author-assembled, labeled
"Fallback self-review", copied the child's
`### Verdict: Ready for merge` and `Reviewed-Commit` lines, and wrapped
them in a 16-item
"Round history that was Addressed, Rebutted, or Deferred" ledger.
That comment is the wrap, not the parent `Task` JSON.
How Cursor Cloud obtains the child's structured report is in
[`memories/cursor.md`](../../memories/cursor.md).

- **Do:** post the dispatched reviewer's structured report
  (Summary / Findings / Verdict / Reviewed-Commit) as the fallback comment,
  then append the required disclosure marker.
  How Cursor Cloud obtains that report is in
  [`memories/cursor.md`](../../memories/cursor.md).
- **Don't:** wrap the verdict in the authoring session's ARD round-history
  recap in the same comment.
- **Don't:** omit the disclosure marker, or treat that marker as license to
  add an ARD ledger.
- **Don't:** paraphrase a missing reviewer body as Ready for merge.

## The mechanism

[`hooks/no-push-without-self-review.py`](../../hooks/no-push-without-self-review.py) gates the pre-push case, per [`algorithmatize-checks`](algorithmatize-checks.md).
It answers three questions rather than one, because provenance alone is not enough.

*Who said it*: a verdict is admitted only from the `tool_result` of an `Agent` call whose `subagent_type` is the reviewer, and only when that result is not an error.
So an inline pass, a verdict quoted out of a file, the guard's own denial message, and a clean report from some other subagent all fail.

*What it said*: restricting provenance does not make a phrase search sound **inside** the admitted body, which is the same failure one layer in --- a review whose closing note quotes the clean verdict it is withholding would read as clean.
So the verdict is the last line that **is** a verdict line, anchored at line start, and a quotation mid-sentence is not one.

*What it was about*: the reviewer states the commit it read as a `Reviewed-Commit: <sha>` line after its verdict, and the guard resolves what the push would actually ship --- reading the refspec, not just `HEAD` --- and compares.
A push ships commits, so anything that changes what would be shipped --- a later commit, a `main` merge, a rebase, a commit a subagent made in a transcript the guard cannot see, or a branch other than the reviewed one --- fails the comparison.
That is also why the review comes **after** committing, which is where [`ardi`](ardi.md) already puts the pause point.

The other cases have no guard and are prose rules here.

- **Do:** dispatch [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md) (foreground, read-only) for every self-review, and report which agent produced the verdict.
- **Do:** re-dispatch after fixing findings, so the clean verdict describes the tree you are shipping.
- **Do:** chase a cross-vendor reviewer on top of it wherever one is reachable.
- **Don't:** perform a self-review inline under a reviewer framing --- that is the move this rule replaces, and it is indistinguishable from compliance in the output.
- **Don't:** brief the reviewer with the rationale for the change.
- **Don't:** count a subagent's clean verdict as the external verdict [`fully-clean`](fully-clean.md) requires.
  It is a self-review, performed properly.

## The review gates the push, not the work --- and it is one round, not a loop

The rule above is a gate on a **push**.
It is not a rule that the work must stop moving until the reviewer is happy,
and reading it that way turns one gate into an unbounded loop.

The failure runs like this.
A review returns findings, you fix them, and the fix needs its own review ---
correctly, since a fix is a diff nobody has read.
So far so good.
The trap is treating each round's fix as something that must clear review
*before the branch can be pushed at all*, because that condition never
arrives: every round produces new code, new code owes a review, and the
commits pile up locally while the loop runs.
Measured on [ai-config#1911](https://github.com/Morrison-Lab/ai-config/pull/1911):
five rounds on one file, every round finding something real, and nothing
pushed for hours.

It reads as rigour from the inside, which is what makes it worth a rule.
Each individual decision to hold is defensible, and the loop is invisible
because no single round is the one that went wrong.

**Pushing is not merging, and the costs run the other way.**
A pushed branch is where CI and the repo's own reviewer can see the code, so
pushing *adds* scrutiny rather than skipping it.
Holding subtracts it, and adds costs of its own: the work is invisible to
other sessions, it is unbacked-up, and its merge conflict with a moving base
grows the whole time.

So the gate is per push and the review is of what that push ships.
Once a round's fix is verified --- its own tests, its own mutation control,
its own measurement --- push it, and let the next review run against the
pushed head, which is the head that matters.

- **Do:** push a verified round and let the reviewer read the pushed head.
- **Do:** batch a round's fixes into one push, per
  [`efficient-pr-babysitting`](efficient-pr-babysitting.md), rather than
  trickling or hoarding.
- **Don't:** hold a branch until some future round returns clean --- that
  condition recedes with every fix.
- **Don't:** read a gate on pushing as a gate on shipping any of the work.

(Directive from the user, 2026-08-22, mid-session on #1911: "what are you
waiting for?".
Five commits were sitting unpushed behind a self-imposed review queue while
the branch's conflict with `main` had to be re-resolved twice.
The honest answer to the question was "nothing".)

## Query all available providers sequentially

When obtaining adversarial reviews, we need a clean verdict from **every** available provider.
(e.g. Cursor, Antigravity (`agy`), OpenCode, Codex, and Claude --- when Claude is not quota-blocked).
Do not stop after one provider returns clean.
Query them sequentially, one at a time.
Once one provider gives a clean review, move on to the next one.
Repeat this until all available providers have signed off with a clean verdict on the exact same commit.

The set of required providers must be pinned at the start of the review cycle.
If a pinned provider drops offline during a subsequent round, you must wait for it to return or explicitly request user permission to drop it from the quorum.
If zero providers are available at the start of the cycle, you must fail closed and wait until at least one becomes reachable, or request explicit user permission to proceed.
If any provider (or combination of providers) creates an unbounded loop --- whether through irreconcilably contradictory requirements, self-contradictory oscillation, or endless non-contradictory goalpost-moving --- halt the review process and escalate to the user for a tie-breaking decision.
