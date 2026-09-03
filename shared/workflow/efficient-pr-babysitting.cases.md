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
[`memories/claude-review-dispatch.md`](../../memories/claude-review-dispatch.md),
so the gap was in the trigger rather than in the knowledge: every existing
statement of it fires around a push, and none fires when the batching rule is
invoked to withhold one.)

## "A reviewer's 'considered but declined to raise' note is not an open item"

(Morrison-Lab/ai-config#1115, 2026-08-04: a 23-line CLAUDE.md addition earned **Ready for merge** on round one, with one optional cross-link the reviewer noted but declined to raise.
Acting on it drew a second clean verdict plus a fresh declined note -- a forward-pointing phrase the added cross-link introduced -- and acting on that drew a third: three review rounds for a change mergeable after the first.
Copilot's check went green with `get_reviews` empty on every head, including [#1118](https://github.com/Morrison-Lab/ai-config/pull/1118)'s stable single-push head.
That silence carried no verdict, and its cause is unresolved.
The single-push head shows the trickled pushes were not necessary for it, and nothing measured says whether they contributed -- an earlier version of this entry wrongly called it self-inflicted, and a later one wrongly called it Copilot's no-findings behavior.)

## "A caveat reporting that the reviewer could not check is not a declined note"

(`Morrison-Lab/ai-config`, 2026-08-09: both shapes occurred hours apart in one
session, and the correct responses diverged.

[#1345](https://github.com/Morrison-Lab/ai-config/pull/1345)'s round-2 review
closed with a **ranking**: "One purely optional, non-blocking observation: the
corrected text prices the CI cost as 'one `validate` run,' which is technically
a slight undercount (it's actually two, per the check-run evidence above) ...
so it isn't worth another round."
That reviewer had checked the fact itself, so the note was weighed and ranked
low, and holding it was right.

[#1347](https://github.com/Morrison-Lab/ai-config/pull/1347)'s round-2 review
closed with an **inability**: "One claim I could not independently verify: the
PR body's/new content's statement that '4 of the 5 most recent squash merges on
that repo carry zero preserved bullets in their bodies.'
Repeated attempts to fetch individual squash-commit message bodies via
`gh api repos/.../commits/<sha>` were denied by this session's tool-approval
gate (while `gh pr list`/`gh pr view`/`gh pr diff` worked fine).
This is an illustrative, non-load-bearing detail ... so I'm not treating this as
a finding, just noting it as unverified."
Both verdicts read **Ready for merge**, and the second caveat was held as though
it were the first.

The blocked check ran fine from the driving session, which is the sandbox
asymmetry the rule names: `gh api` was gated for the reviewer while plain
`git log` was never gated for the author.
It refuted the claim.
The five most recent first-parent commits at that moment returned three carrying
zero bullets, not four:

```bash
for sha in $(git log origin/main --format=%H -5); do
  printf '%s bullets=%s\n' "$(git log -1 --format=%h "$sha")" \
    "$(git log -1 --format=%b "$sha" | grep -c '^\* ' || true)"
done
```

The false ratio merged into
[`fail-fast`](../principles/fail-fast.md) and needed
[#1351](https://github.com/Morrison-Lab/ai-config/pull/1351) to correct it,
which is the whole cost of reading an inability as a ranking: a command before
the merge, or a PR after it.

Re-running that same loop later on 2026-08-09, after #1351 merged, returns 3 of
5 again over an entirely different five commits ---
`1ab91d69 0`, `f9884cc5 0`, `165d8a96 2`, `02146f6d 2`, `2b368175 0` --- which
is why #1351's fix published the loop rather than refreshing 4 to 3.
"The N most recent" is a sliding window, so a bare count is stale on arrival,
per [`avoid-hardcoding-external-data`](../coding/avoid-hardcoding-external-data.md)'s
rule that refreshing a drifted figure only resets the clock.)

## "Merge first, then commit the fix, then push once"

(ai-config#700: pushed the review fix, then merged `main` and pushed again about a minute later; the first review run was cancelled mid-flight and the round cost an extra cycle.)

## "Run the behind-check as its own step, before composing the push"

(Morrison-Lab/ai-config#957, 2026-07-31: the behind-check was folded into the
same command as the `git push`, so "3 behind" was read only once the push had
gone out.
The follow-up merge push then cancelled review run `30614715159`, in flight on
the commit it superseded.)
