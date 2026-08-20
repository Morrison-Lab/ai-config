# Case records: flag-session-boundaries

Worked-example case records for the rules in
[`flag-session-boundaries.md`](flag-session-boundaries.md), moved here verbatim to
keep them out of the auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## Leftover harness branches in scoped repositories

The harness assigns its branch name in *every* scoped repo and leaves each one checked out on it, including repos the session never opens.
So the sweep finds the branch sitting in places nothing in the conversation points at, and two things follow from that.

Point 3 of [`keep-checkouts-fresh`](keep-checkouts-fresh.md)'s "The working repo's main checkout" step quietly does nothing in those repos.
It fast-forwards `main` only when `main` is the checked-out branch, and here it never is, so a repo you never opened stays as stale as the container left it.

And `git branch -D` refuses, with `cannot delete branch 'X' used by worktree at '<path>'`.
That message names a worktree, which reads as a second checkout holding live parallel work --- the one condition that would genuinely make deleting the branch unsafe.
It is almost always just that repo's ordinary checkout sitting on the branch.
So the cautious reading is the wrong one here, and acting on it leaves a dead branch in place for the next session to re-discover and re-adjudicate.

Settle liveness from the branch's own commits rather than from the error text, and settle it before deleting anything.
Zero commits in `origin/main..<branch>`, plus absence from the remote, together mean there is nothing to lose.
Resist adding an ancestry check beside the first of those.
An empty `origin/main..<branch>` range is the same fact as `git merge-base --is-ancestor <branch> origin/main` succeeding, so running both confirms one thing twice rather than two things once.
Once liveness is settled, switch that repo to `main` --- which is what the refusal is really asking for --- and then delete.

## A clean declaration over a session that committed nothing

A session was asked whether opencode's free models could be used as subagents.
It answered the question, discovered that the user's `~/.config/opencode/opencode.jsonc` was invalid and repaired it, verified two models end to end, posted a `💡 OFFER` to build a delegation skill, and closed with `**Stopping Point**: Clean stopping point reached --- no PR opened or pushed to by this session`.

The user's reply:

> that wasn't a real stopping point; you haven't finished anything

Two rules failed at once, and they failed differently.

The `OFFER` was an unanswered question, which the disqualifier list has covered since the rule was written.
That rule was loaded and simply did not fire.
Posing the offer and declaring the stop happened in the same message, and from the inside those read as two unrelated acts rather than as a contradiction --- the offer feels like generosity appended to a finished report, not like a question left open.

The second failure had no rule pointed at it.
`git log origin/main..HEAD` was empty and `git status --short` clean.
The branch carried nothing at all, and the session's whole durable output was one untracked edit to a dotfile outside any repository.
Every *remaining* disqualifier was genuinely absent, because a session that opens no PR cannot have an unmerged one.
Strike the offer from the record and the declaration is still wrong, which is what makes this a second failure rather than a restatement of the first.
The declaration even enumerated that absence as its justification, which is what made it read as a check rather than as an omission.

The repair is the completion half of the test, now stated explicitly in the fragment: name what finished.
Applying it here yields nothing --- and "nothing finished" was available from the same two commands that produced "no PR opened", which is the point.
The evidence was never missing.
Only the question was.

The follow-through matters as much as the rule.
The offer was filed as [#1693](https://github.com/Morrison-Lab/ai-config/issues/1693) rather than left as chat prose, and that issue carries the dotfile repair as a Troubleshooting item for whatever implements it.
Filing is what makes the difference here, not shipping: an issue is findable by a later reader whether or not the work it describes has landed yet, which is precisely the property the untracked dotfile edit lacked.
