When your fix is superseded --- someone else's landed first, or landed a better
version of the same thing --- closing your PR is not the whole disposition.
Diff what you had against what landed, and land the part the winner lacks.

Two independent fixes for one defect rarely have the same *coverage*.
The winning fix discharges the bug.
Whether it also carries a regression guard is a separate question with a
separate answer, and the guard is what stops the class recurring rather than
the instance ([`algorithmatize-checks`](algorithmatize-checks.md)).
That part is orthogonal to whose fix won, so it can survive the supersession
even when your fix does not.

**Verify the supersession before acting on it.**
"This is already fixed, close yours" is a factual assertion like any other, and
the cost of accepting it wrongly is a defect left open under the belief that it
is closed ([`dont-take-my-word-for-it`](../principles/dont-take-my-word-for-it.md)).
Read the merged tree, not the report: the claimed fix, at the ref consumers
actually resolve.
[`keep-checkouts-fresh`](keep-checkouts-fresh.md) governs how to read that ref
without a stale local copy answering for it.

**Then check the merged fix for the guard rather than assuming either way.**
Assuming it has one closes a real gap silently;
assuming it lacks one re-lands a test that already exists.
Grep the merged tree for an assertion naming the thing that broke.

Once the gap is real, the order matters:

1. Rebase onto the merged state, so your diff is stated against what shipped.

2. Drop the now-redundant part of your change *entirely*, rather than leaving a
   variant of a fix that already landed.

3. Confirm what remains **passes** against the merged fix.
   A guard that fails there is a competing opinion about the right fix, not a
   guard for the one that won.

4. Mutation-confirm it still catches the original defect when applied on top of
   the merged fix --- a guard that no longer discriminates is
   [`fixtures-are-not-evidence`](fixtures-are-not-evidence.md) with extra steps.

5. Rewrite the PR body to say what you dropped and why.
   A reviewer who arrives at a title describing a fix, and a diff containing
   only a test, will otherwise reconstruct the reason wrongly or ask.

- **Do:** treat "superseded" as a question about *coverage*, not a verdict on
  the whole branch.

- **Do:** say plainly, in the PR and to the user, which part you dropped and
  which part you kept, so the narrowed scope is a decision rather than a
  silent leftover.

- **Don't:** keep your version of the fix alongside the merged one to preserve
  authorship --- that is the competing-opinion case, and it belongs in a review
  comment on the merged PR if you think the other fix is wrong.

- **Don't:** close the PR reflexively either.
  Both reflexes skip the diff, and the diff is the only thing that answers the
  question.

(Morrison-Lab/gha#816, 2026-09-02: a `post-review` job reached a helper script
by repo-relative path in a job that checks nothing out, so every consumer review
exited 127 after posting its comment and two `require-` gates cascaded red off a
clean verdict.
A parallel session had already tracked it as #812 and fixed it in #813, merged
and tag-slid while the duplicate PR was open.
The report of that was verified from the remote rather than taken on trust ---
`git ls-remote` for the tag, and `main`'s own copy of the workflow --- and held.
What did not hold was the implied disposition: `run-review-job-split-tests.py`
on the merged `main` contained no assertion naming `workflows/scripts/` at all,
so #813 shipped no regression guard, and the script's own 114-case suite
structurally could not supply one --- it passes its own `$SCRIPTS_DIR` from a
job that *does* check the repo out, which is why it stayed green throughout the
incident.
The workflow fix was dropped, the branch rebased onto the merged state, and the
guard alone kept: an assertion that no step in a checkout-less job may name a
repo-relative script path, stated over every such job rather than the one that
broke.
It passes against `main` as merged and turns red when the pre-fix invocation is
restored on top of it, which is the pair of checks step 3 and step 4 name.)
