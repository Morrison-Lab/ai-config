# Subagent worktrees are assigned, and an incident never silently repeals a decision

Moved whole from [`CLAUDE.md`](../../CLAUDE.md#subagent-worktrees-are-assigned-and-an-incident-never-silently-repeals-a-decision) to keep it out of the
always-loaded context; that section keeps the rule's one-sentence core and a
link here.

Two rules, one incident, and the second is the general form of the first.

**Assign the worktree on the `Agent` call.** Set `isolation` yourself rather than leaving each subagent to organize its own working directory, and brief every agent you isolate to stay inside the worktree it was given and to **push early** --- a pushed commit survives anything that happens to a working tree.
Deciding that a particular agent does not need one is fine.
Leaving it unmarked is what is not.
`hooks/flag-unassigned-worktree.py` mechanizes exactly this, and warns rather than blocks.

**Verify a dispatched agent's liveness before touching a worktree you did not just create --- never infer it from a snapshot.**
A clean `git status` and an unlisted agent both describe one instant.
Neither says whether the session working that worktree has actually stopped, and a quiet worktree can mean either "finished" or "between edits".
Ask the agent directly (`SendMessage` to its id, or the equivalent for a peer session) before editing or reclaiming its worktree, including one that has sat quietly for hours --- a long stretch is a reason to ask sooner, not evidence of abandonment.
[`memories/subagent-worktrees.md`](../../memories/subagent-worktrees.md) carries the case where both directions of that misreading --- read as live when quiet, read as dead when live --- happened to the same agent in one session.

**"Stay inside the worktree it was given" holds only while the agent works in the session's own repo.**
`isolation: "worktree"` places that worktree in the **session's primary repository**, never in a repository the brief happens to name --- so a dispatch into a different clone hands the agent a worktree of the wrong repo, and the instruction above is unfollowable as written.
Name the target clone by path instead, and tell the agent to create its own worktree there off `origin/<default-branch>` --- resolved from that repo, never hard-coded, per `memories/subagent-worktrees.md`'s measured `fatal: invalid reference: origin/main` failure on a repo whose default is named otherwise.
Measured 2026-08-07.
[`memories/git-worktrees.md`](../../memories/git-worktrees.md) carries the evidence.
[`shared/workflow/challenge-the-assignment.md`](challenge-the-assignment.md) covers the general form --- a brief must not assert anything about the recipient's environment, which the author cannot query even in principle.

**The general rule is the more valuable half.** When an incident makes you stop doing something you had decided to do, either re-argue the decision explicitly or fix the misuse --- never just change the behaviour.
A repealed decision changes no artifact, so review, tests, and hooks are all blind to it by construction, and the only detector is someone who remembers.
It is more dangerous than ordinary drift because the incident supplies an apparent reason, so from the inside it feels like having learned something rather than like lapsing.
If you cannot point at the message where a decision was reversed, it was not reversed.
It lapsed.

[shared/workflow/incidents-dont-repeal-decisions.md](incidents-dont-repeal-decisions.md)
