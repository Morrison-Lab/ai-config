# Rationale: Re-check for latest review findings before reporting PR status

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#re-check-for-latest-review-findings-before-reporting-pr-status) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

[`shared/workflow/recheck-review-findings.md`](recheck-review-findings.md)

Before reporting on a PR --- and especially before calling one clean or ready --- pull the review state fresh.
Never answer from chat context or from a verdict you cached, which applies equally to any other question about that live PR ("did you fix it", "why haven't you responded").

Five traps, each of which returns something that reads exactly like good news:

- **CI green is not a review verdict.**
  `gh pr checks` reports check state and says nothing about findings.
- **The newest round is not the only unread one.**
  Several can land in one monitoring gap, and a test-only push gets a fresh clean verdict that says nothing about the earlier round's open findings.
  Diff the round list against what you last handled.
- **Filtering by author login silently returns the previous round.**
  The login varies by repo and by run (`claude`, `claude[bot]`, `github-actions[bot]` have each carried a real verdict), and the stale result is indistinguishable from "no new review yet".
  Match on the body marker `**Claude finished`.
- **A formal review's finding can sit where a comments-only scan never looks.**
  Its top-level body is often empty with the finding in an inline comment on a different endpoint, and the mirror case puts the finding in the body itself, possibly inside a collapsed `<details>`.
  A bot's `COMMENTED` review carrying a finding is blocking exactly as a human's `CHANGES_REQUESTED` is.
- **A later clean bot verdict does not clear a human's `CHANGES_REQUESTED`.**
  Only that human, or an explicit dismissal, resolves a review *state*, and an automated "Ready for merge" posted afterwards does not touch it.
  It feeds the merge gate directly, so it binds under `mwc` as much as under any other grant.

A review-gating check run can also read green over a `NOT_CLEAN` verdict, so a check named for the verdict is not the verdict --- see [`review-verdict-pitfalls`](review-verdict-pitfalls.md).

- **Do:** read every round since the one you last processed, every formal review's state and body whoever posted it, and the inline comments.
- **Don't:** treat green checks, a login-filtered query, or a named verdict-gating check as evidence the review is clean.
- **Don't:** read a `COMMENTED` state as making a review blocking on its own --- what blocks is the finding inside it.
- **Don't:** read a later clean verdict as clearing a standing `CHANGES_REQUESTED`, which blocks on its own until that human or an explicit dismissal resolves it.
  The two run opposite ways, which is why they are separate bullets: one state does not block by itself and the other does.

(A specific case of the standing **never assume;
always verify** rule in `memories/preferences.md` --- confirm the verdict with a fresh query, don't recall it.)
