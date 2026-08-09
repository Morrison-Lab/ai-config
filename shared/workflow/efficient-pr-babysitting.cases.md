# Case records: efficient-pr-babysitting

Worked-example case records for the rules in
[`efficient-pr-babysitting.md`](efficient-pr-babysitting.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## "That saving presupposes that a push triggers a review"

(`Morrison-Lab/ai-config`, 2026-08-09: a finished, tested, committed fix was
deliberately held back from `git push` and reported as such, to batch it with
whatever the in-flight review round returned so the round would cost one review
run instead of two.
A **user-level** `Stop` hook flagged the unpushed commit ---
`~/.claude/stop-hook-git-check.sh`, which is not in this repo's `hooks/` and is
not registered in its `hooks.json` --- and the hook was right.
That distinction is load-bearing rather than pedantic: a user-level hook
protects the machine it was written on and no other, so the same withheld
commit on a colleague's checkout would have gone unflagged.
This repo's `.github/workflows/claude-review.yml` carries `workflow_dispatch`
and nothing else, so a push there schedules no review, and the review-run half
of the batching saving was zero while the commit sat only in an ephemeral
container's working tree.
The CI half was not zero: `validate.yml` carries
`on: [push, pull_request, workflow_dispatch]`, so the withheld push really would
have saved a `validate` run.
Review round 1 caught the first draft of this record claiming batching bought
"exactly zero", which was falsifiable against the unchanged text of the very
rule it amends, four lines above it.
The dispatch-only fact was already recorded in
[`ardi.md`](ardi.md), [`pr-on-claim.md`](pr-on-claim.md), and
[`memories/claude-bot-workflows.md`](../../memories/claude-bot-workflows.md),
so the gap was in the trigger rather than in the knowledge: every existing
statement of it fires around a push, and none fires when the batching rule is
invoked to withhold one.)

## "A reviewer's 'considered but declined to raise' note is not an open item"

(Morrison-Lab/ai-config#1115, 2026-08-04: a 23-line CLAUDE.md addition earned **Ready for merge** on round one, with one optional cross-link the reviewer noted but declined to raise.
Acting on it drew a second clean verdict plus a fresh declined note -- a forward-pointing phrase the added cross-link introduced -- and acting on that drew a third: three review rounds for a change mergeable after the first.
Copilot's check went green with `get_reviews` empty on every head, including #1118's stable single-push head, so its silence was its no-findings behavior rather than anything the pushes caused -- an earlier version of this entry wrongly called that silence self-inflicted.)

## "Merge first, then commit the fix, then push once"

(ai-config#700: pushed the review fix, then merged `main` and pushed again about a minute later; the first review run was cancelled mid-flight and the round cost an extra cycle.)

## "Run the behind-check as its own step, before composing the push"

(Morrison-Lab/ai-config#957, 2026-07-31: the behind-check was folded into the
same command as the `git push`, so "3 behind" was read only once the push had
gone out.
The follow-up merge push then cancelled review run `30614715159`, in flight on
the commit it superseded.)
