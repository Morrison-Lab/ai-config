Proactively tell me --- don't wait to be asked --- when a session has grown long and hits a natural stopping point: a multi-step task or loop (GII/ARDIA/GIP, a research pass) just checkpointed or fully wrapped, a PR merged with no other in-flight work riding on this conversation, or an open question just got answered with nothing left pending.
Use the `⚠️ **FLAG** ---` tag from `CLAUDE.md`'s chat-output-tagging convention.
Place it on one line, at the natural end of that turn's recap (or immediately before a `wrap-up` report).
Don't interrupt mid-task to say it.

**Always state whether or not the session is at a clean stopping point.** The last message you post before stopping MUST explicitly state whether or not this is a clean stopping point for the session (e.g. `**Stopping Point**: Clean stopping point reached` or `**Stopping Point**: Not a clean stopping point / work remains queued: ...`). Whenever ending a session, completing a turn, or wrapping up work (whether finishing a single task, a multi-issue backlog loop like `gii`/`gia`, a PR stack sweep, or an automated session wrap-up like `mwc`/`wrap-up`), ALWAYS include an explicit `**Stopping Point**` declaration. Never leave the user guessing whether additional tasks remain queued or if a clean stopping point has been reached. (User corrections / directives, 2026-08-17, 2026-08-18.)

**The declaration is for a human reading a recap, so it does not apply where the last message is consumed by a machine instead.**
The rule says the last message MUST be the declaration.
A CI harness that posts an agent's reply to a PR or issue thread typically takes the **last assistant message** and posts that.
Two rules then claim the same slot, and the declaration wins every time, because it is by construction written last --- so the answer is replaced by a status marker and discarded.

The loss is silent and usually unrecoverable: a run log does not carry the conversation, and such workflows rarely publish the transcript as an artifact.
It is also self-concealing, because a stopping-point line reads like a completed task, so nobody looking at the thread can tell an answer went missing.

So: **when the final message is not being read by a person --- a non-interactive run whose output is posted somewhere by a harness --- put the declaration inside the substantive reply rather than after it, or omit the declaration.**
The tell is that nothing about the session resembles a terminal recap: no human is reading turn-by-turn, and the "session" is a single automated invocation whose whole output is one artifact.

- **Do:** end with the declaration in an interactive session, where a person reads the recap.
- **Do:** fold it into the substantive message, or leave it out, when a harness will post your last message verbatim.
- **Don't:** emit a bare declaration as a separate final message in a CI run --- that is the whole failure, and it looks like compliance.
- **Don't:** assume the harness concatenates your turn.
  The common implementation takes one message.

(Measured 2026-08-19 on `d-morrison/rme`.
Installing this corpus as a plugin in that repo's `@claude` workflow ([rme#1076](https://github.com/d-morrison/rme/pull/1076)) made every prose reply collapse to a one-line declaration.
The pre-plugin reply was 1182 characters and substantive.
The three post-plugin replies were 233, 356, and 501 characters, and each began with the marker.
One run diagnosed the bug itself and had its diagnosis swallowed by the bug.
Tracked as [rme#1081](https://github.com/d-morrison/rme/issues/1081).
[rme#1082](https://github.com/d-morrison/rme/pull/1082) is the consumer-side workaround, and this section is the upstream fix that stops it recurring in every other repo installing the plugin.)

Don't suggest it when there's still live state only this conversation holds: a background agent or CI run still in flight that I'm tracking, **any PR this session opened or pushed to that has not yet merged or closed**, an unanswered question, or a mid-investigation train of thought that would be expensive to reconstruct.
`/clear` wipes conversation state outright (unlike compaction, which summarizes) --- anything not already durable (in `CLAUDE.md`, a memory file, or a tracked issue/PR) is gone.
If UMS hasn't run recently, run it *before* raising the flag rather than disclosing the debt inside it, per [`run-ums-proactively`](run-ums-proactively.md)'s "Recommending that the session end is itself a UMS trigger" section.

**A clean stopping point requires that something finished, and the disqualifier list above cannot tell you whether anything did.**
The rule's two halves read as one test and are not.
The opening paragraph defines a stopping point by **completion** --- a task checkpointed or fully wrapped, a PR merged, an open question answered with nothing left pending.
The paragraph beginning "Don't suggest it" lists what **disqualifies** one.
Nothing marks that second list as necessary rather than sufficient, so "none of these apply" gets read as "clean", and the completion half is never consulted at all.

The gap opens on the commonest turn shape there is: the one that only explored.
A turn that answered a question conversationally, ran diagnostics, read code, or made a change it never committed has finished nothing by construction --- and it trips none of the disqualifiers either, because a session with no PR has no unmerged PR and a session with no CI run has nothing in flight.
Absence of live state and presence of a completion are different facts about a session.
A turn that produced neither is where the first gets read as the second, which is why this misreads in exactly the case where it is least deserved.

So name the thing that finished, in the declaration itself.
"No PR opened or pushed to by this session" is a true sentence answering the wrong question, and enumerating the disqualifiers that way is what makes the declaration read as checked.
That is the near-miss: the check *looks* performed, in the specific vocabulary of the rule, while the question the rule exists to answer went unasked.

**Two mechanical checks refute it, so run them instead of judging.**
Both are negative tests: each can show a declaration is wrong, and neither can establish that it is right.
That is the same necessary-versus-sufficient shape as the disqualifier list, so passing both is not a verdict either --- naming what finished is the positive half, and nothing mechanical can supply it.

**A boxed marker in the same turn contradicts the declaration.**
A `QUESTION`, `OFFER`, or `BLOCKER` box is by definition something the user has not answered yet, which the disqualifier list already covers under "an unanswered question".
The contradiction is invisible from the inside when both land in one message, because posing the question and declaring the stop feel like separate acts performed at different moments.
They are not separate to the reader, who gets a request for input and a claim that nothing is pending in the same breath.

**`git log origin/<default-branch>..HEAD` plus `git status --short` decides whether the session produced anything durable.**
An empty range and a clean tree mean this branch carries nothing.
That is not the same as the session having produced nothing: one that merged its own PR and then ran [`post-merge`](../../skills/post-merge/SKILL.md)'s cleanup leaves an identical reading while having finished the most a session can finish.
So establish what merged before reading an empty range as an empty session.
Resolve the default branch from the repo rather than assuming `main`.
An untracked local change --- a dotfile repaired, a scratch script written --- is real work and still not a completion, because nothing another session or another person could find records that it happened.
The remedy converts it rather than excusing it: file it or commit it, and it becomes something nameable.

- **Do:** name the specific thing that finished, in the declaration itself.
- **Do:** run both checks --- boxed markers in this turn, and the commit range plus tree state --- before writing the word clean.
- **Don't:** read "none of the disqualifiers apply" as "clean" --- that list is necessary and not sufficient.
- **Don't:** declare a clean stopping point in a turn that also posts a `QUESTION`, `OFFER`, or `BLOCKER` box.
- **Don't:** count exploration, diagnosis, or an uncommitted local change as a completion.

(Directive from the user, 2026-08-19:
"cai: that wasn't a real stopping point; you haven't finished anything".
See [`flag-session-boundaries.cases.md`](flag-session-boundaries.cases.md), "A clean declaration over a session that committed nothing".)

**That unmerged-PR clause in the disqualifier list above is a bright line, not a judgment call, and it was narrowed deliberately.**
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
First, fast-forwarding `main` quietly does nothing in those repos because `main` is not checked out.
Second, `git branch -D` refuses with `cannot delete branch 'X' used by worktree`, which is almost always just that repo's ordinary checkout on that branch.
Settle liveness from the branch's commits (`origin/main..<branch>` having zero commits plus absence from remote), resist adding a redundant `--is-ancestor` check, switch that repo to `main`, and delete the branch.

- **Do:** run the sweep across every scoped repo, not only the ones this session worked in.
- **Do:** settle liveness first, then `git checkout main` in that repo, then `git branch -D`.
- **Don't:** read `used by worktree` as evidence that a separate live worktree exists.
- **Don't:** assume a repo the session never opened is on `main`.

See [`flag-session-boundaries.cases.md`](flag-session-boundaries.cases.md), "Leftover harness branches in scoped repositories".

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

**Check for a stopping point instead of asking for more tasks.**
Never ask for more tasks.
Never say "what would you like me to do next?"
When a session has grown long and hits a natural stopping point,
run the `wrap-up` skill to sweep for pending work.
After executing `wrap-up`,
use the live state you observed and the criteria in this file to determine if a session-management recommendation applies.
Since this file's criteria supersede `wrap-up`'s default assessment (e.g., allowing a `/clear` when open work belongs to another session),
adjust `wrap-up`'s stopping point declaration to clean if the criteria here permit it.
If a recommendation applies,
prefix your recommendation with the `⚠️ **FLAG** ---` tag and present it.
Regardless of whether a recommendation applies,
output `wrap-up`'s full report.
Ensure the (possibly adjusted) stopping point declaration remains the final thing in your response (subject to the CI exception above).

- **Do:** run `wrap-up` when a session hits a natural stopping point.
- **Do:** prefix any recommendation with the flag, instead of offering to take on more tasks.
- **Don't:** ask "what next?" when you just finished a task.

## Flag good moments to run `compress-session`, too

The mid-task counterpart to the section above: don't wait for the automatic compaction to guess what matters, and don't wait to be asked.
Proactively flag (using the same `⚠️ **FLAG** ---` tag) when a session is still mid-task but has grown large.
This applies when there are many tool calls, or long tool outputs (test/CI logs, big diffs) no longer needed once their conclusions are captured.
It also applies to a session that's already been through one automatic compaction and is heading for another.
Then run `compress-session` yourself: write the focused distillation and, if compaction looks imminent, trigger `/compact focus on <what matters>` rather than leaving it to the automatic pass.

Use this instead of the `/clear` flag above when there's still live state worth carrying forward: an unfinished task, an unmerged PR this session opened or pushed to, or an open question.
`/clear` is for a clean task boundary with nothing left to carry.
This is for continuing the same work with a lighter context.
That middle item uses the same bright line as the section above, deliberately: the two are complements, so a PR that disqualifies the `/clear` flag is exactly what makes `compress-session` the right tool instead.
