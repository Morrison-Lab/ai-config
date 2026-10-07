Proactively tell me --- don't wait to be asked --- when a session has grown long and hits a natural stopping point: a multi-step task or loop (GII/ARDIA/GIP, a research pass) just checkpointed or fully wrapped, a PR merged with no other in-flight work riding on this conversation, or an open question just got answered with nothing left pending.
Use the `⚠️ **FLAG** ---` tag from `CLAUDE.md`'s chat-output-tagging convention.
Place it on one line, at the natural end of that turn's recap (or immediately before a `wrap-up` report).
Don't interrupt mid-task to say it.

**Always state whether or not the session is at a clean stopping point.**
The last message you post before stopping MUST explicitly state whether or not this is a clean stopping point for the session (though for non-clean stopping points, the declaration need not be the absolute final line of the message) (e.g. `**Stopping Point**: Clean stopping point reached --- session done; UMS executed; no follow-up items pending` or `**Stopping Point**: Not a clean stopping point / work remains queued: session not done; ...`).
Whenever ending a session, completing a turn, or wrapping up work (whether finishing a single task, a multi-issue backlog loop like `gii`/`gia`, a PR stack sweep, or an automated session wrap-up like `mwc`/`wrap-up`), ALWAYS include an explicit `**Stopping Point**` declaration that says whether the session is done or not.
When reporting stopping point status:
- Explicitly state whether the session is done or not.
  Never say a session is done when there are uncommitted, unpushed, or un-PRed changes,
  or open PRs authored by that session ---
  even after delivering completed implementation work (opening the PR),
  work remains to monitor CI and drive the review to clean or merge.
- Include running UMS (or confirming no new learnings accumulated since the last pass).
- Confirm that any follow-up items noticed during the turn or task have been filed.
Never leave the user guessing whether additional tasks remain queued or if a clean stopping point has been reached.
(User corrections / directives, 2026-08-17, 2026-08-18, 2026-09-29, 2026-10-06;
[#4328](https://github.com/Morrison-Lab/ai-config/issues/4328).)

**A conversational question-answering reply concluding a turn is a stopping point.**
When answering a question at the end of a session or turn (e.g. explaining a diagnosis, answering "why not?", or clarifying why a branch was deleted), that reply is the stopping point of the turn.
Phrasing about the user's tasks (such as "Nothing is left for you to do" or "Nothing further is needed from you") is about the user's workload, not the session's state, and does not substitute for explicitly stating whether the session is done (`session is done` or `session not done`).
State explicitly whether the session is done or not on that final reply, exactly as on any other turn-concluding message.
(User directive, 2026-10-05, Morrison-Lab/lbt; [#4308](https://github.com/Morrison-Lab/ai-config/issues/4308).)

**Arm resumption before every non-clean pause.**
Whenever work remains at a pause, create a timer or equivalent wake mechanism
that will resume the next concrete step before ending the turn.
Report what will fire and its clock time.
Use an active background monitor or a durable scheduled trigger when the harness
does not provide a reliable timer.
A verified clean stopping point needs no timer because no work remains to resume.
This requirement depends on session state, not on whether a human-facing
stopping-point declaration is emitted.

- **Do:** arm and report a resumption mechanism before every non-clean pause.
- **Do:** omit the timer after a verified clean stopping point.
- **Don't:** end at a non-clean stopping point with only a promise to return.
- **Don't:** create a pointless timer after the work has reached a clean stop.

**The declaration is for a human reading a recap, so it does not apply where the last message is consumed by a machine instead.**
The rigid interpretation of the rule says the last separate message MUST be the declaration.
A CI harness that posts an agent's reply to a PR or issue thread typically takes the **last assistant message** and posts that.
Two rules then claim the same slot, and the declaration wins every time, because it is by construction written last --- so the answer is replaced by a status marker and discarded.

The loss is silent and usually unrecoverable: a run log does not carry the conversation, and such workflows rarely publish the transcript as an artifact.
It is also self-concealing, because a stopping-point line reads like a completed task, so nobody looking at the thread can tell an answer went missing.

So: **when the final message is not being read by a person --- a non-interactive run whose output is posted somewhere by a harness --- put the declaration inside the substantive reply rather than after it, or omit the declaration.**
The tell is that nothing about the session resembles a terminal recap: no human is reading turn-by-turn, and the "session" is a single automated invocation whose whole output is one artifact.

- **Do:** end with the declaration in an interactive session, where a person reads the recap (though for non-clean stopping points, pending work may follow the declaration).
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

An unboxed question or offer in prose is just as open, and harder to spot because nothing marks it --- "I can file an issue on that if you want" is an offer whether or not it sits in a box.
[`tag-chat-output`](../writing/tag-chat-output.md) says how to mark them in the first place;
this check catches the ones that were not.
(Measured 2026-10-05 in a Morrison-Lab/lbt session: a reply ended with that unboxed offer and then "The session is done", and the user answered that open questions for them mean the session is not done.)

**`git log origin/<default-branch>..HEAD` plus `git status --short` decides whether the session produced anything durable.**
An empty range and a clean tree mean this branch carries nothing.
That is not the same as the session having produced nothing: one that merged its own PR and then ran [`post-merge`](../../skills/post-merge/SKILL.md)'s cleanup leaves an identical reading while having finished the most a session can finish.
So establish what merged before reading an empty range as an empty session.
Resolve the default branch from the repo rather than assuming `main`.
An untracked local change --- a dotfile repaired, a scratch script written --- is real work and still not a completion, because nothing another session or another person could find records that it happened.
The remedy converts it rather than excusing it: file it or commit it, and it becomes something nameable.

- **Do:** name the specific thing that finished, in the declaration itself.
- **Do:** state explicitly whether the session is done or not, including running UMS and filing any noticed follow-up items.
- **Do:** run both checks --- questions, offers, and blockers put to the user in this turn, boxed or not, and the commit range plus tree state --- before writing the word clean.
- **Don't:** read "none of the disqualifiers apply" as "clean" --- that list is necessary and not sufficient.
- **Don't:** declare a clean stopping point in a turn that also puts a question, offer, or blocker to the user, whether in a `QUESTION`, `OFFER`, or `BLOCKER` box or in plain prose.
- **Don't:** count exploration, diagnosis, or an uncommitted local change as a completion.
- **Don't:** end a turn without declaring whether the session is done or ongoing.
- **Don't:** declare a clean completed stopping point or report that the session is done when there are uncommitted, unpushed, or un-PRed changes, or open PRs authored by that session.
- **Do:** include the explicit stopping-point and session-done declaration on conversational and question-answering replies concluding a turn.
- **Don't:** substitute user-workload phrasing like "Nothing is left for you to do" for an explicit declaration of whether the session is done.

(Directive from the user, 2026-08-19:
"cai: that wasn't a real stopping point; you haven't finished anything".
See [`flag-session-boundaries.cases.md`](flag-session-boundaries.cases.md), "A clean declaration over a session that committed nothing".)

**Never say a session is done when there are uncommitted, unpushed, or un-PRed changes, or open PRs authored by that session.**
A declaration that a session is done means no further action is owed by or in-flight for this session.
Four conditions strictly disqualify declaring that the session is done:
1. **Uncommitted changes:** the git working tree or index has modified, staged, or untracked changes (`git status --porcelain` is not empty).
2. **Unpushed changes:** commits exist locally that have not been pushed to the remote tracking branch (`git log @{u}..HEAD` or `git status` shows unpushed commits).
3. **Un-PRed changes:** a feature branch has been pushed or worked on without opening a pull request to deliver the change.
4. **Open PRs authored by that session:** any PR opened or pushed to by this session remains open (unmerged and unclosed).
Even after delivering completed implementation work (opening the PR), work remains to monitor CI, run automated reviews, and drive the review to clean or merge.
(User directive, 2026-10-06, [#4328](https://github.com/Morrison-Lab/ai-config/issues/4328).)

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

**When you recommend a new session, offer to start it yourself.**
A recommendation to start fresh leaves the user to open the session and type out what it should do, and the second half is the part that needs this session's context.
So write the next session's opening prompt yourself and make it self-contained: the repo, the issue or PR numbers, what to skip and why, and any uncommitted or unpushed work, since a session spawned in a fresh worktree cannot see it.
Then offer to start the session with that prompt already in it, by whatever this harness provides:

- **Claude desktop app:** post a `spawn_task` chip (`mcp__ccd_session__spawn_task`) carrying the prompt.
  The session starts only when the user clicks the chip, in a fresh worktree, so the chip is the offer and the click is the yes.
  The tool is described for out-of-scope follow-up work, and a session handoff is a second use of the same mechanism.
- **Terminal, or any harness with no one-click mechanism:** give the prompt in a fenced block and ask plainly whether to open a terminal tab running `claude` on it.
  Open it only on a yes.
- **Nothing can start a session:** give the prompt in a fenced block ready to paste, and say that this harness cannot start the session for them.

The user has not authorized starting a session, so asking is correct here, and [`no-cop-out-offers`](no-cop-out-offers.md) agrees, since it governs only actions already authorized.
Where a one-click mechanism exists, attach it as the ask rather than writing "want me to start it?" in prose.
Archiving the current session stays with the user.

- **Do:** attach the way to start the session (the chip, the terminal offer, or the paste-ready prompt) in the same reply that recommends it.
- **Don't:** recommend a fresh session and leave the user to open it and reconstruct the next prompt.

(User directive, 2026-10-03, Morrison-Lab/mds: "when you recommend a new session, you should offer to start it yourself";
[#4270](https://github.com/Morrison-Lab/ai-config/issues/4270).)

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
run `wrap-up`'s state sweep to gather the live state,
per this file's own "Run `wrap-up`'s state sweep" instruction above,
rather than invoking the full `wrap-up` skill.
The full skill's own UMS step is not owed at every task boundary:
per [`run-ums-proactively`](run-ums-proactively.md),
a learning gets recorded the moment it surfaces,
so the pass should already be current by the time one task ends.
Use the live state the sweep surfaced,
together with the criteria in this file,
to decide whether a session-management recommendation applies.
This file's criteria decide the declaration,
not `wrap-up`'s own default assessment
--- e.g. this file permits a `/clear` recommendation
when the only open work belongs to another session,
a case `wrap-up`'s closing checklist does not carve out on its own.
If a recommendation applies,
prefix it with the `⚠️ **FLAG** ---` tag and present it.
Regardless of whether a recommendation applies,
report what the sweep found:
every open PR and issue, linked,
any uncommitted changes,
and any leftover branches or worktrees.
For a clean stopping point,
end the reply with the stopping-point declaration (subject to the CI exception above).
For a non-clean stopping point,
place the open questions and pending tasks after the declaration,
so they remain the final and most visible element of the reply,
per `wrap-up`'s instruction to end the reply with the open questions,
last and clearly visible.

- **Do:** run `wrap-up`'s state sweep when a session hits a natural stopping point.
- **Do:** prefix any recommendation with the flag, instead of offering to take on more tasks.
- **Don't:** ask "what next?" when you just finished a task.
- **Don't:** trust `wrap-up`'s raw stopping-point declaration when the only open item belongs to another session --- this file's criteria decide the declaration.

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
