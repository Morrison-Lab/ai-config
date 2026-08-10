Proactively tell me --- don't wait to be asked --- when a session has grown long and hits a natural stopping point: a multi-step task or loop (GII/ARDIA/GIP, a research pass) just checkpointed or fully wrapped, a PR merged with no other in-flight work riding on this conversation, or an open question just got answered with nothing left pending.
Use the `⚠️ FLAG` tag from `CLAUDE.md`'s chat-output-tagging convention, one line, at the natural end of that turn's recap --- don't interrupt mid-task to say it.

Don't suggest it when there's still live state only this conversation holds: a background agent or CI run still in flight that I'm tracking, **any PR this session opened or pushed to that has not yet merged or closed**, an unanswered question, or a mid-investigation train of thought that would be expensive to reconstruct.
`/clear` wipes conversation state outright (unlike compaction, which summarizes) --- anything not already durable (in `CLAUDE.md`, a memory file, or a tracked issue/PR) is gone.
If UMS hasn't run recently, run it *before* raising the flag rather than disclosing the debt inside it, per [`run-ums-proactively`](run-ums-proactively.md)'s "Recommending that the session end is itself a UMS trigger" section.

**That PR clause is a bright line, not a judgment call, and it was narrowed deliberately.**
It used to read "a PR I'm actively babysitting", which invites the question of whether *this* PR still counts as active --- and the answer always sounds like no.
A PR whose checks are green and whose review has not come back yet feels finished: there is nothing to do, so there is nothing live.
That reading is what the rule has to rule out, because "waiting on a review round" is the single most common state for a PR to be in when a session reaches a natural pause, and it is exactly when the flag is most tempting.

Two things make an unmerged PR live regardless of how quiet it looks.
[`ardi`](ardi.md) obliges the session to keep monitoring it until it merges or closes, so proposing a stop proposes abandoning that loop mid-flight.
And a review can still come back with findings, which is work only this conversation has the context to address cheaply.

Open PRs belonging to *other* sessions do not trigger this --- `wrap-up`'s sweep surfaces them, and they are worth reporting, but they are not this conversation's live state.

- **Do:** hold the flag until every PR this session opened or pushed to has merged or closed.
- **Do:** report an unmerged PR's status plainly instead, with no stopping-point suggestion attached.
- **Don't:** treat "green checks, just awaiting review" as not-live --- it is the archetypal live PR.
- **Don't:** flag a stopping point and disclose the open PR in the same breath, which is the same too-early flag [`run-ums-proactively`](run-ums-proactively.md)'s "Recommending that the session end is itself a UMS trigger" section rejects.

**Run `wrap-up`'s state sweep *before* flagging a stopping point, not after the user asks for one.**
The paragraph above says not to flag while live state remains; it doesn't say how to know.
Answering that from memory only covers the PRs and branches *this conversation* created, which is exactly the blind spot: a bot-opened PR, a leftover branch from the harness or an earlier session in the same container, or another session's PR in the same repo never entered the conversation, so nothing about them feels outstanding.
Run the sweep --- open PRs and issues per repo, `git status`, local branches, worktrees --- and let its output decide, the same way [`fully-clean`](fully-clean.md) insists a PR's readiness comes from a fresh query rather than a cached verdict.

**Two mechanical details about that leftover-branch case, one of which reads as the opposite of what it is.**
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

- **Do:** run the sweep across every scoped repo, not only the ones this session worked in.
- **Do:** settle liveness first, then `git checkout main` in that repo, then `git branch -D`.
- **Don't:** read `used by worktree` as evidence that a separate live worktree exists.
- **Don't:** assume a repo the session never opened is on `main`.

**When flagging a good moment to `/clear`, offer archiving as the default alternative.**
Whenever there's a meaningful chance I'd want to come back to this conversation later, recommend leaving the session alone and starting a fresh one for the next task, instead of `/clear`ing it -- the old session stays fully retrievable (nothing to lose), at the cost of a small navigation step to reopen it.
Reserve a bare `/clear` recommendation for when nothing in the session is worth revisiting; when in doubt, default to the archive-and-start-new option since it's strictly safer.

**`/compact` is a third alternative, for weak continuity rather than a clean break.**
When the next move is to keep working on *loosely related* things in the same window -- no concrete open item, so not the live state that triggers the `compress-session` flag, but enough of a thread that a clean slate would lose something worth keeping -- recommend `/compact` instead of archive-and-start-new.
It carries a lossy summary forward in place, keeping the gist and skipping the reopen step, at the cost of a session that keeps growing and detail that is lost.
Pick among the options by what the *next* work needs from this session.
Nothing, and unrelated to what's next, is archive-and-start-new by default, or a bare `/clear` only when nothing is worth revisiting;
the gist in the same window is `/compact`;
the full live task state is the `compress-session` flag, not this one.
Archive still beats compact for pure *reference*, since a retrievable full thread dominates a lossy summary, so reserve the compact recommendation for continuation rather than preservation.

**Starting a new PR is itself a moment to weigh compacting, clearing, or a fresh session -- not only a natural stopping point is.**
The options above all fire on a *stopping* point: a task wrapped, a PR merged, a question answered.
Opening a new PR is a *starting* point, and it feels the opposite -- momentum rather than pause -- which is exactly why the consideration gets skipped.
But a new PR is where a fresh chunk of context begins accumulating, so it is the cleanest seam at which to decide whether to carry this session forward or reset, and deciding *before* the new state exists is cheaper than untangling it after.

So before opening a new PR, pause and pick from the same menu, by what the *new* PR needs from this session:

- Unrelated to everything in the current window, and nothing here is worth revisiting -> archive-and-start-new (the default), or a bare `/clear` only when nothing is worth revisiting.
- Builds loosely on the current thread -> `/compact`.
- Small, fresh context -> do nothing and open the PR.

The bright line still governs, and it changes what "reset" can even mean here.
If this session has an unmerged PR it opened or pushed to, it owes that PR active monitoring (per [`ardi`](ardi.md)), so *this* session must not be `/clear`ed or walked away from -- the new PR either rides along in the same window (where `compress-session` or `/compact` can still lighten the carried context), or goes to a genuinely separate fresh session while this one keeps monitoring.
Only when no such live PR remains is the full menu (archive-and-start-new, `/clear`, `/compact`, or nothing) open, chosen by the criteria above.
Run UMS first if it is owed, per [`run-ums-proactively`](run-ums-proactively.md)'s "Recommending that the session end is itself a UMS trigger" section -- not disclosed inside the flag.

- **Do:** pause at the new-PR boundary and recommend the fitting session-management option, before opening the PR.
- **Do:** keep monitoring an unmerged PR in the session that owns it -- send only the *new* PR to a fresh session, rather than resetting the one that owes monitoring.
- **Don't:** barrel into a new PR carrying a long, unrelated session by reflex, just because opening a PR feels like forward motion rather than a stopping point.
- **Don't:** `/clear` or abandon a session while a PR it opened is still unmerged -- that drops the monitoring loop the bright line protects.

## Flag good moments to run `compress-session`, too

The mid-task counterpart to the section above: don't wait for the automatic compaction to guess what matters, and don't wait to be asked.
Proactively flag (same `⚠️ FLAG` tag) when a session is still mid-task but has grown large --- many tool calls, long tool outputs (test/CI logs, big diffs) no longer needed once their conclusions are captured, or a session that's already been through one automatic compaction and is heading for another.
Then run `compress-session` yourself: write the focused distillation and, if compaction looks imminent, trigger `/compact focus on <what matters>` rather than leaving it to the automatic pass.

Use this instead of the `/clear` flag above when there's still live state worth carrying forward: an unfinished task, an unmerged PR this session opened or pushed to, or an open question.
`/clear` is for a clean task boundary with nothing left to carry.
This is for continuing the same work with a lighter context.
That middle item uses the same bright line as the section above, deliberately: the two are complements, so a PR that disqualifies the `/clear` flag is exactly what makes `compress-session` the right tool instead.
