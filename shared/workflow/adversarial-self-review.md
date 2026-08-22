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

## Its findings are findings

[`self-review-fallback`](self-review-fallback.md) already rules out surfacing a defect in your own review and closing it on your own estimate of its blast radius.
A dispatched reviewer makes that concrete, because the finding now has an author who is not you: give each one Address, Rebut, or Defer-to-a-tracked-issue per [`ard`](../../skills/ard/SKILL.md), in writing, exactly as for a finding from the PR's own reviewer.
"I know why that is fine" is a Rebut, and a Rebut is something you would be willing to post.

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
- **Don't:** count a subagent's clean verdict as the external verdict [`fully-clean`](fully-clean.md) requires; it is a self-review, performed properly.
