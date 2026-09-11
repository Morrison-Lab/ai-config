# Re-check for latest review findings before reporting PR status

Moved out of the auto-loaded `CLAUDE.md` (ai-config#3568), which keeps the rule and its pattern/anti-pattern pairs;
this file carries the queries, the login-versus-body-marker trap, the formal-review blind spots and the cases.
Nothing here was rewritten in the move.


**Before** reporting status on a PR (especially "clean" / "ready to merge"), re-read the **most recent** review comment on the PR.
The same fetch applies to any other question about that live PR ("why didn't you wait", "did you fix it", "why haven't you responded").
Don't answer from chat context alone.
Don't trust an earlier "verdict" you've cached --- a new review may have been posted since (by the @claude bot, by a human, or by a re-trigger), and that newer review may contain findings the old one missed.

Specifically: when scanning checks (`gh pr checks`) shows green or "no failures", that's about CI state, **not** review verdict.
Always pull the latest review comment and parse it for any "Findings", "Issues", "Remaining" sections before declaring a PR ready.

**Read every round since the one you last processed, not only the newest.**
Several rounds can land during a monitoring gap, and "read the latest" alone fails exactly then.
A test-only push between two substantive rounds gets a fresh verdict that says nothing about the earlier round's unaddressed findings, so the latest comment reads clean while older findings sit open (measured 2026-08-24 on sparta#1375 --- three rounds landed in one gap, and acting on the newest alone would have reported clean over an open regression finding).
Diff the round list against what you last handled: fetch all `**Claude finished` comments, note each `Reviewed commit:` SHA, and treat any round newer than your last processed one as unread input.

**Filter on the body marker, not on an author login.**
The login a review posts under varies by repo and by run --- `claude`, `claude[bot]`, and `github-actions[bot]` have each been observed carrying a real, complete verdict --- so a login-filtered query silently returns the *previous* round's comment and reads exactly like "no new review yet".
That is a false negative on the one question this section exists to answer, and nothing in the output announces it.
Completed runs start the body with `**Claude finished`, so match that instead:

```bash
gh api repos/<owner>/<repo>/issues/<N>/comments --paginate \
  | jq -s '[.[][] | select(.body | test("\\*\\*Claude finished|### Verdict"))] | last | .body'
```

`memories/gh-cli.md` carries the full statement, including the placeholder-wording trap when polling a run still in flight.

**Also check formal GitHub reviews, not just issue-style comments --- a review's findings can sit where a comments-only scan never looks, whoever posted it and whatever state it carries.**
A review submitted via GitHub's review UI (as opposed to a plain PR comment) shows up in `gh pr view N --json reviews`, and its top-level `body` is frequently **empty** --- the actual finding lives entirely in a per-line inline comment, which only appears via `gh api repos/<owner>/<repo>/pulls/N/comments` (a different endpoint from issue comments).
The mirror case is a finding in the top-level `body` itself, plainly or inside a collapsed `<details>` suppression block: neither shape produces a comment object, so `pulls/N/comments` and a thread query both return nothing over it.
[`fully-clean`](fully-clean.md) carries the matcher for the collapsed block, and what fails that bar is the finding rather than the state.
So a bot's `COMMENTED` review carrying a finding fails that bar exactly as a human's `CHANGES_REQUESTED` does.
Checking `--json comments` alone can miss the review's existence entirely.
Before declaring a PR ready, also run:
```
gh pr view N --json reviews --jq '.reviews[] | [.state, .author.login, .submittedAt, ((.body // "") | split("\n") | map(select(length > 0)) | .[0] // "(empty body)")] | @tsv'
gh pr view N --json reviews --jq '.reviews[] | select(.state == "CHANGES_REQUESTED") | "\(.author.login) \(.submittedAt)"'
gh api repos/<owner>/<repo>/pulls/N/comments --jq '.[] | "\(.path):\(.line // .original_line // "?") \(.user.login) \(.body)"'
```
A `CHANGES_REQUESTED` state is blocking regardless of whether an automated re-review later says "Ready for merge" --- that bot verdict doesn't clear a human's own review state, which only the human (or an explicit dismissal) can resolve.
The unfiltered listing comes first: the state filter answers only whether a review *state* blocks the merge button, which the forge lets `CHANGES_REQUESTED` alone do.

- **Do:** read every formal review's state and body, whoever posted it, and treat a finding in a review body --- a collapsed suppression block included --- as blocking.
- **Don't:** pass over a review because its author is a bot or its state is `COMMENTED`, nor read that state as blocking on its own.

See [`CLAUDE.cases.md`](../../CLAUDE.cases.md), "A bot's `COMMENTED` review is the same blind spot".

**The review's own required check run can itself read green over a `NOT_CLEAN` verdict --- a distinct failure from "CI green isn't the review verdict".**
The `gh pr checks` paragraph at the top of this section treats check state and the review verdict as two signals that both need checking.
This one says the review's *own* gate, e.g. `review / require-clean-verdict`, does not always track the outcome it is named for.
[`review-verdict-pitfalls`](review-verdict-pitfalls.md) carries the measured case and the analysis, and is where further cases go.

- **Do:** treat a green review-gating check run as unverified until the latest review comment's own verdict field confirms it, even when that check run's name implies it enforces the verdict directly.
- **Don't:** read a named review-verdict check (e.g. `require-clean-verdict`) as SUCCESS meaning the review is clean --- name and outcome can disagree.

(A specific case of the standing **never assume;
always verify** rule in `memories/preferences.md` --- confirm the verdict with a fresh query, don't recall it.)

