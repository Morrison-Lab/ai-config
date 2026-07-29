Before starting a work session on a GitHub PR or issue --- i.e. before fetching
the branch, making edits, or invoking an automated review cycle --- post a brief
comment on the PR/issue so other people and any automated review bots know not
to start a conflicting parallel session.

Use:

```
gh pr comment <N> --body "Working on this --- paws off until I'm done."
gh issue comment <N> --body "Working on this --- paws off until I'm done."
```

Then proceed with the work. After the session ends (PR merged, issue closed, or
work otherwise paused), follow up with a closing comment so the PR/issue is
unclaimed for the next person.

Skip the claim step if the most recent comment already says you are working on
it. This applies to any task that will push commits to a PR branch or run
iterative review loops. It does **not** apply to read-only inspection (showing a
PR, checking status, explaining a diff) --- those don't risk a parallel session.

This includes a PR **you opened yourself**: in repos with an active `@claude`
agent (`claude.yml`), the agent can push commits to your branch on PR activity
--- e.g. merging `main` in --- and collide with your in-flight push, so claim
early to flag the branch as actively worked. (See
`memories/claude-bot-workflows.md`, "@claude CI action", for the
collision-recovery steps.)

When starting work from an issue, follow the claim comment with an immediate
draft PR --- see [`pr-on-claim`](pr-on-claim.md) for the mechanics. An open
PR is a stronger "in-flight" signal than a comment alone.

**Verify a mid-task "already done" claim against real PR state before trusting
or redoing it.** A PR you claimed and are actively driving can still gain
commits from a **second, independently-running session** under the same
account --- a `<github-webhook-activity>` review-comment-reply event can
describe work ("Addressed... Pushed in `<sha>`") that this session never did.
Don't assume it's fabricated or injected, and don't reflexively redo the same
fix: cross-check the PR's actual commit list (`gh pr view --json commits` /
`pull_request_read` `get_commits`) and review threads before either (a)
trusting the claim, or (b) starting the same fix yourself. If a commit with
that SHA genuinely exists, authored close to when the event arrived, treat it
as confirmation a live parallel session owns this PR right now --- stop
pushing further speculative fixes yourself, and, if genuinely in doubt, ask
whether to keep driving or step back, rather than racing the other session's
pushes. This gap is distinct from the initial claim check above: it's not
about claiming a PR before starting, but about **re-verifying you're still
the sole active driver** once work has been under way for a while ---
especially when you picked up the PR mid-session (e.g. by answering a
diagnostic question about it) rather than through the normal claim-then-branch
flow, so no fresh "paws off" check ever ran right before you started pushing.
(`d-morrison/gha#286`, 2026-07-24: a webhook event delivered a review-comment
reply attributed to `d-morrison` reading exactly like a Claude-authored
reply, claiming a fix "Addressed... Pushed in 3fb8c5b" that this session
hadn't made; verified real via `get_commits` before proceeding --- a second
live session, not injection.)

**Handing off mid-task to another agent, on user request ("finish what you're
doing, then relinquish holds; I'll put another agent on them"):** don't just
stop --- leave the next agent a clean starting point. On each claimed PR/issue:
(1) post a status comment on the PR itself distinguishing what's **done** from
what's genuinely **not done** (the actual point of the issue, not just the
side-fixes found along the way) and any blocker still open, so the next agent
doesn't have to re-derive it from the diff; (2) post the closing/unclaim
comment on the issue per the pattern above; (3) `unsubscribe_pr_activity` (or
stop babysitting locally) so you don't keep auto-fixing a PR you no longer
own; (4) stop any background watch/poll task tied to that work (e.g. a
`ScheduleWakeup` or a `Monitor`/background-Bash wait) so it doesn't fire into
a session that's moved on. A merge-conflict-free `git status` and a pushed
branch are not enough on their own --- the status comment is what makes the
handoff legible. (ucdavis/bcs `gia` session, 2026-07-06: handed off PRs #310
and #311 mid-implementation this way, each blocked on the same slow
`renv::restore()`.)
