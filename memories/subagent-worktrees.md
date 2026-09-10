# Peer and subagent worktrees

Worktree behaviour where a **second session** is involved: a dispatched subagent, a peer Claude Code session, or a reviewer reading a tree you also write to.
Split out of [`git-worktrees.md`](git-worktrees.md) at the 1250-line memory-file gate (the ai-config#694 pattern).

That split is itself the fix for ai-config#3449: `git-worktrees.md` sat one line under the cap, so no satellite of it could carry the one-line "Moved to" stub the corpus convention requires, and every future satellite hit the same wall.

Single-session worktree mechanics --- `worktree add` and `worktree remove`, `checkout -B` in a linked worktree, pushing by refspec, where a `cd` lands --- stay in [`git-worktrees.md`](git-worktrees.md).

Write every cross-reference by name, never by position.
A section here and the section it answers now sit in different files, so "above" and "below" are false the moment either moves --- and they stay present while becoming false, which is why a content comparison cannot catch them.

## A quiet worktree is not evidence the session working it has stopped

Every worktree section in [`git-worktrees.md`](git-worktrees.md) assumes the
peer worktree is dead.
This one is about telling that apart from a peer worktree that only *looks*
dead, before you edit it, delete it, or reassign its branch.
The operative rule --- ask the agent, never infer --- is restated in
`CLAUDE.md`'s "Subagent worktrees are assigned" section; this section carries
the evidence and the case record behind it.

`git status --short` reporting nothing uncommitted, and `git log
origin/<branch>..HEAD` reporting nothing unpushed, both answer a question
about a **moment**: is anything sitting here right now that a snapshot would
show.
Neither answers "is anyone working here".
A session between edits, or paused mid-thought, produces the identical
snapshot to a session that finished and walked away, and nothing in either
command distinguishes the two.

`ListAgents` not naming a session is the same shape of gap, not a stronger
signal.
It reports what the harness currently tracks, and a session can be alive and
simply not be one the listing surfaces --- so absence there is not proof of
absence in fact, any more than a clean `git status` is.

**The `idle_notification` timestamp check is sound in form and only as good as
the timestamp you compare it against.**
Comparing a teammate's last `idle_notification` against your own most recent
message to it is the right check --- a notification timestamped before your
last message is stale, not evidence the teammate has gone quiet since.
But that check has an input you supply, and if the timestamp you are comparing
against is itself invented rather than read, the comparison inherits the
error: a fabricated "now" can make a live, recent notification look stale, and
the conclusion --- "this session has gone quiet" --- is then built on a number
nobody measured.
`Morrison-Lab/ai-config#1453` owns that defect and its fix (derive every
timestamp you reason about, don't extrapolate from one you derived earlier);
what matters here is the interaction, not the fix: a fabricated figure feeding
straight into a **liveness** decision is a sharper failure than feeding into
an ordinary status recap, because the decision it distorts is exactly the one
this section is about.

**One step earlier than the timestamp: the field's own semantics are not
established anywhere in this corpus, so a correct timestamp comparison still
does not settle liveness on its own.**
An `idle_notification` carries an `idleReason` such as `"available"`, and
reading that as "this session has stopped working" is an inference this
corpus has never verified.
`"available"` describes a session that is not currently blocked on a tool
call --- which is exactly what a session sitting on a backgrounded `gh run
watch` looks like from the outside, since the watch runs and reports without
occupying the foreground.
So the timestamp check above can be run correctly, against a real,
non-fabricated timestamp, and the result still says only when the notification
was sent --- never what sending it actually meant.
Read `idleReason` as an unglossed field rather than as a verdict, and treat a
liveness question it seems to answer as still open.

**Two more direct ways the same misreading arrives, both concluding "dead" on
evidence that only shows "quiet right now".**

- A worktree read clean via `git status --short`, with no unpushed commits and
  no `ListAgents` entry, was judged finished, and a second session began
  editing a file inside it.
  The Edit tool's own read-staleness guard refused: `File has been modified
  since read`.
  The worktree's owner had started editing between the read and the write.
  What actually prevented the clobber was that guard, not the judgment that
  produced the edit attempt --- worth naming plainly, since crediting your own
  care for a tool's backstop is how the next read of a clean worktree gets
  trusted a little more than it should.
- A worktree instead sat with real uncommitted work (38 insertions) for over
  nine hours, with no `ListAgents` entry for it, and was judged dead on that
  basis.
  It was alive, and replied within a minute once asked directly.

Both readings used the same evidence --- a snapshot plus an absent listing ---
and reached opposite, both wrong, conclusions.
That is the tell that the evidence does not discriminate: it produced "quiet
but alive" and "quiet and abandoned" from the identical two facts.

**A harness-reported failure is not a snapshot, and there the question is what
to salvage rather than whether the agent is alive.**
Everything above concerns evidence that cannot discriminate --- a quiet
worktree, an absent listing --- where the remedy is to ask.
A `task-notification` carrying `status: failed` is a different kind of signal.
It comes from the harness rather than from an inference of yours, so asking
buys nothing and costs an agent spin-up aimed at a process already gone.

The useful discovery is that a failed agent has often already pushed.
An agent that stalls during its verification or reporting phase can have
committed and pushed everything first, so the work sits safe on the remote
while the *report* about it is what was lost.
The report is also the only part that felt like the deliverable, which is why
the failure reads as total.
Reading it that way leads to redoing work that already landed, and a redo can
diverge from what was actually pushed.

Four reads settle what survived, before touching anything:

```bash
gh pr view <N> --json headRefOid --jq .headRefOid   # what the remote has
git -C <worktree> rev-parse HEAD                    # what the worktree has
git -C <worktree> status --short                    # uncommitted
git -C <worktree> log --oneline @{u}..HEAD          # committed, unpushed
```

A matching remote and local head, an empty status, and an empty unpushed range
together mean the work landed in full and only the reporting was lost.
Then finish the remainder yourself rather than resuming the agent, and verify
its changes against the tree rather than against its commit message --- the
verification step is precisely the one that did not run.

- **Do:** treat a harness `status: failed` as authoritative about the process,
  and check what was pushed rather than asking a dead agent.
- **Do:** re-verify a failed agent's work against the tree, since the checks it
  was about to run are the missing ones.
- **Don't:** redo work on the assumption a stalled agent lost it --- pushing
  early is the whole point, and it usually worked.
- **Don't:** apply the ask-don't-infer rule here.
  That rule governs evidence which cannot discriminate, and a harness failure
  signal discriminates.

(Morrison-Lab/ai-config#1696, 2026-08-19: an agent addressing six review
findings stalled on a 600s watchdog, its last line reading "Now the full check
suite before a single push".
It had already pushed --- remote head, worktree HEAD, and an empty unpushed
range all agreed --- so the six fixes were intact and only the check suite, the
disposition comment, and the re-review dispatch remained.
Those were finished directly, and the PR merged as `f5059a84` after a clean
second round.)

**Long-stalled uncommitted work in a container-local worktree is still a real
problem, and the fix is to ask, not to infer.**
Uncommitted state in a worktree survives nothing --- not a container
restart, not a reclaim, not the session that made it forgetting to push.
So a worktree sitting on real, unpushed edits for hours is genuinely worth
resolving rather than leaving alone indefinitely.
The tension is real: leaving it risks losing work if the container churns,
and touching it risks clobbering work in progress.
The resolution is not to infer an answer from indirect signals that cannot
support one --- it is to ask the session directly (`SendMessage` to its id, or
the equivalent for a peer Claude Code session) and act on the reply.
One message costs a round trip.
A clobbered edit costs another session's unpushed work outright, with no
recovery path once it is gone.

- **Do:** treat a clean, in-sync `git status` in another session's worktree as
  a statement about that instant, never as a statement about whether anyone is
  still working there.
- **Do:** treat `ListAgents` not naming a session as "not tracked here", not as
  "does not exist".
- **Do:** ask the session directly before editing or reclaiming a worktree
  that has sat with real uncommitted work for an extended stretch --- and
  before concluding it is dead just because it has sat quietly.
- **Don't:** derive an `idle_notification` staleness comparison from a
  timestamp you extrapolated rather than measured; see `#1453` for that half.
- **Don't:** read `idleReason` as a liveness verdict; a correct timestamp
  comparison still leaves the field's own meaning unestablished.
- **Don't:** credit your own judgment when a tool's built-in guard is what
  actually stopped a clobber --- name the guard, so the next read of a clean
  worktree gets checked rather than trusted.

(`Morrison-Lab/ai-config`, 2026-08-13, in the multi-teammate session that went
on to merge #1452 as `fcc09f00`: a dispatched teammate's `idle_notification`s
at `16:08:59Z` and `16:10:24Z` were judged stale against status recaps timestamped
roughly `16:13Z` and `16:20Z` --- timestamps that had themselves been
extrapolated rather than re-derived, per `#1453`.
Separately, that teammate's worktree read `git status --short` clean and
in-sync, with no `ListAgents` entry, and was judged finished; editing
`shared/workflow/fully-clean.md` inside it was refused by the Edit tool's
staleness guard mid-edit, because the teammate had started editing the same
file between the read and the write.
Later the same worktree sat with 38 uncommitted insertions for over nine
hours with no `ListAgents` entry, was judged dead, and replied within a
minute once asked --- it then reclaimed the PR itself.
A fourth instance came from a different source: the team-lead session's own
review message on the PR recording all this, which read the agent writing
this entry as idle roughly three minutes after it dispatched the review run
that produced round 1, on the strength of an `idleReason: "available"`
notification --- and named the notification's own semantics as unverified
only once the writer pointed out the watch had, in fact, been running the
whole time.
Recorded here as evidence about the field rather than about a worktree,
since nothing about it involved git state --- the mechanism is identical to
the first two instances, and the correction came from a message rather than
from a diff.)

**A `Claude-Session:` commit trailer names the exact session that authored a commit, which is the one instrument that identifies a peer rather than inferring one.**
The rule above says `ListAgents` silence means "not tracked here" rather than "does not exist".
That is right, and it leaves you with no way to say who *is* there.
Git history does.
A remote session's commits carried a `Claude-Session:` trailer holding that session's own URL in the one case observed here, so where the trailer is present, comparing it against your own settles authorship instead of suggesting it.
The trailer may be absent, which is why its ABSENCE settles nothing --- the third signature below is exactly that case.

```bash
git log -1 --format='author=%an <%ae>%n%b' origin/<branch> \
  | grep -E 'author=|Claude-Session|Co-Authored-By'
```

Three signatures, seen across four branches --- the first two measured, the third measured in its observables and inferred in its conclusion:

- **A `Claude-Session:` URL differing from yours** --- a concurrent *remote* session, named.
  Decisive, where `updated_at` movement is only a hint.
- **Your own `Claude-Session:` URL** --- your commit.
- **No trailer, authored by the human, with a `Co-Authored-By: Claude ...` line** --- consistent with a *local* Claude Code session, which commits under the human's git identity and injects no session trailer.
  This one prompts a question rather than settling it, unlike the other two: the same facts also fit a person typing the co-author line, or a remote session with the trailer suppressed.

The third signature misreads in both directions.
Read as human-authored it credits a person with an agent's work;
read as absent evidence it makes every local session invisible to a peer sweep.
The `Co-Authored-By:` line is what separates it from a genuinely hand-written commit, and it names the model too, so a `Claude Fable 5.1` co-author tells you a differently-configured session is active on that branch.

- **Do:** read the trailer off the branch tip before calling a PR yours, a peer's, or a human's.
- **Don't:** infer authorship from the GitHub login --- a local session, a remote session, and the person all push under the same account.
- **Don't:** read a missing `Claude-Session:` trailer as "not an agent";
  check for `Co-Authored-By:` before concluding that.

(Measured 2026-09-03 during a `gia` sweep on ai-config.
`ListAgents` reported no peers for the entire session while a peer demonstrably held ai-config#3023, whose tip carried a `Claude-Session:` URL differing from this session's.
ai-config#3089, #3100 and #3101 carried no trailer and the human's authorship, with `Co-Authored-By: Claude Opus 5` or `Claude Fable 5.1`.
An adversarial reviewer sent to settle the same question reported #3023 as human-authored with no trailer, which is why the query above names the trailer explicitly rather than leaving it to a general history read.)

## A subagent that has REPORTED COMPLETION can still be resumed, so its worktree is not yours to work in

The "A quiet worktree is not evidence the session working it has stopped"
section is entirely about concluding "dead" on evidence that shows
only "quiet" --- a clean `git status`, an absent `ListAgents` entry, an
`idleReason` nobody has glossed.
Its remedy is to ask the agent before touching its worktree.

This is the case where the agent has answered without being asked.
A dispatched subagent emits a completion notification, the orchestrator reads
it, and that is a far stronger signal than any of the above: it is the agent's
own report that it has stopped.
It is still not terminal.
The harness's own notification says so in as many words --- "the same task-id
may notify more than once", because the agent can be resumed and will then
notify again --- so a completion report bounds the past and promises nothing
about the future.

**The second-order effect is the expensive half, and it lands on the agent
rather than on you.**
Working in a completed agent's worktree puts your commits on its branch and in
its reflog.
When it resumes, it finds a commit it did not make, freshly pushed, on the PR
it claimed --- which is exactly the signature
[`claim-pr`](../shared/workflow/claim-pr.md)'s parallel-session check names,
and that check is sound.
So the agent applies a correct rule to a manufactured signal, concludes a live
session is racing it, stops pushing, and escalates a question to a user who is
not there.

Note which way this fails.
Nothing is corrupted and no work is lost, so there is no artifact to inspect
afterwards --- the cost is a stalled agent and a question nobody asked for,
which reads as the agent being cautious rather than as the orchestrator having
manufactured its evidence.

The fix is to keep the two working directories separate rather than to reason
harder about liveness.
Cut your own worktree off the branch and work there, and reclaim the agent's
only after deciding it will not be resumed.
Where you must work in its tree, say so **to the agent** before it resumes,
since a message is the one thing that can distinguish your commit from a
stranger's.

- **Do:** cut a separate worktree for your own commits on a dispatched agent's
  branch, rather than reusing the worktree it was given.
- **Do:** read a completion notification as "has produced a result", and nothing more.
  Not even that the agent is currently idle, which the second occurrence below measured it not to be.
- **Do:** tell the agent when one of its branch's commits is yours, so its
  parallel-session check has something to weigh.
- **Don't:** treat a completion report as licence to reclaim a worktree --- it
  is stronger evidence than silence and still not terminal.
- **Don't:** read the resulting "a parallel session is racing me" escalation
  as the agent malfunctioning; it is applying a correct rule to evidence you
  created.

(`Morrison-Lab/ai-config#1481`, 2026-08-15.
A sidecar UMS agent opened the PR and reported completion.
The orchestrator then addressed the review's one blocking finding from inside
that agent's own worktree, committing `4d8c6c7a` and pushing it.
The agent was resumed, found a commit it had not made --- correctly authored
`Claude <noreply@anthropic.com>`, already pushed, present in its own reflog ---
applied `claim-pr`'s parallel-session rule, declined to push, and asked which
of the two sessions should keep driving.
Its analysis was right at every step, including its verification that the commit it had not made was the better fix;
only its premise was false, and the orchestrator had supplied it.)

**Second occurrence, 2026-09-02, split out of the review of [ai-config#3023](https://github.com/Morrison-Lab/ai-config/pull/3023).**
The orchestrator dispatched a sidecar UMS agent, received its full final report, and treated that report as termination.
On the strength of that, it handed the agent's branch to a different session.
The agent then resumed and committed to that branch, which by then had an owner expecting to be its only writer.
`ListAgents` showed the agent `running` an hour after its report.

**The branch and the colliding commit were not recorded at the time, and that omission is the first lesson.**
The #1481 record above names `4d8c6c7a`, so a later reader can audit it;
this one has not been recovered, and no recovery was attempted while the reflog and `ListAgents` state were still live.
Capture the identifier while the incident is in front of you, because the narrative survives in memory and the sha does not.

It shares #1481's premise --- a completion report is not termination --- and inverts its actors.
There the orchestrator wrote into the agent's tree;
here the agent wrote into work the orchestrator had reassigned.
So the harm is not the one this section's heading names, and the entry sits here for the shared premise rather than for a shared shape.

The sharper reading of the tell is this.
This section says above that a completion report "bounds the past and promises nothing about the future", which is true and weaker than what was measured: the agent had not stopped at all.
So the report does not establish even that the agent is *currently* idle.

**Why no instrument was built is an OPEN QUESTION, not a settled negative, and two successive drafts of this entry got that wrong in the same way.**
The first draft claimed a hook "cannot enumerate live agents".
The second conceded that and then argued a `SubagentStop` ledger could not observe a resumption, which foreclosed the question again one step further in.
Both were caught in review, and the pattern is worth more than either claim: an entry explaining why something was not built is under steady pressure to sound decided, because "we considered it and it cannot work" reads as more rigorous than "we did not get to it".

What is actually known, as of 2026-09-02:

- The v2.1 hook schema SUPPORTS `SubagentStart`, `SubagentStop`, `TeammateIdle`, `TaskCreated` and `TaskCompleted`, per [`claude-code-hooks.md`](claude-code-hooks.md).
  Schema support is not an observation that they fire, and nothing here has observed one.
  That catalog labels itself a snapshot measured 2026-08 against Claude Code v2.1.236 and asks to be re-verified rather than treated as permanent, so re-run it before building on it.
- `hooks/hooks.json` registers only `PreToolUse`, `Stop` and `UserPromptSubmit`, and `.claude/settings.json` adds `SessionStart`.
  None of the subagent events is used.
  That is a choice this corpus has not revisited, not a limit it has hit.
- A `SubagentStart`/`SubagentStop` pair is the obvious ledger, and the obvious objection is resumption.
  Whether the objection holds is UNMEASURED: it turns on whether a resumed agent re-emits `SubagentStart`, and on whether the resuming session runs these hooks at all.
  Neither recorded occurrence names the resuming session, so neither settles it.

The measurement that would settle it has to vary the resuming session, or it answers only half the question.
Register a logger on all five subagent and task events --- they are keyed by name with no wildcard, so "log every event" is itself a step.
Dispatch an agent and let it report.
Resume it twice: once from the dispatching session, once from a SECOND session with its own hook configuration.
Record which session's log each event lands in.
Resuming only from the dispatcher holds the variable that both occurrences turned on constant.
Until someone runs that, "no instrument was built" is the honest sentence and "no instrument is possible" is not.

Meanwhile the decidable slice upstream of the failure is already built: `hooks/flag-unassigned-worktree.py` warns on a write-capable `Agent` launch with no `isolation`.
It makes a missing worktree a deliberate choice rather than an accident --- it warns and never denies, by its own docstring, so it bounds nothing.
It does not make a dispatched agent's tree safe to reclaim, and #1481 is the counter-example --- the orchestrator committed `4d8c6c7a` from inside an agent's own assigned worktree.

The one cheap check that works today is a message: `SendMessage` to the agent's id costs one call and answers the actual question, which is what the first `Do` bullet below says, and what the "Long-stalled uncommitted work in a container-local worktree" section says for a peer session.

- **Do:** ask the agent directly, rather than inferring liveness from a report, a quiet tree, or an absent `ListAgents` row.
- **Do:** record the branch and commit when a collision happens, so the case can be audited later rather than taken on trust.
- **Don't:** read a completion report as evidence the agent is even idle;
  measured twice, and the second time it was still running.
- **Don't:** write "no instrument is possible" when what is true is "none was built and the objection is unmeasured" --- two drafts of this entry made exactly that upgrade, and a durable record that forecloses a question stops anyone reopening it.

## Switching a shared worktree's branch under a live dispatched reviewer breaks its reads

The "A subagent that has REPORTED COMPLETION can still be resumed" section is about the orchestrator writing into an agent's own, separate worktree.
This is the case one door down: the orchestrator's **own** worktree, shared with a dispatched read-only reviewer subagent that is mid-review of it, and the orchestrator switches that worktree's checked-out branch to go address a *different* PR's finding while the review is still running.

"Read-only" describes what the reviewer is permitted to do to the tree, not what the tree is permitted to do to the reviewer.
A `git checkout <other-branch>` in the shared directory changes every file the reviewer might read next, mid-flight, with no notice to the reviewer at all -- the same worktree, the same paths, different content underneath them.
The reviewer did not open a stale file, and it did not race the orchestrator for a lock;
the ground it was standing on moved.

The failure is not silent here, which is what makes it recoverable rather than merely a near-miss: the reviewer noticed its reads no longer matched what it expected to be reviewing and fell back to `git show <pinned-sha>:<path>` reads, which are immune to a later checkout because they resolve a path against a fixed commit rather than the working tree.
A reviewer that does not notice -- one that trusts a plain file read over a long review -- would silently review a mix of two branches with no error at all.

- **Do:** brief every reviewer of a shared worktree with the exact commit SHA it is reviewing, and instruct it to read via `git show <sha>:<path>` (or an equivalent pinned read) rather than plain file reads, so a later checkout in the same directory cannot move its ground.
- **Do:** hold branch switches in a worktree until every dispatched reader of it has reported back, when a pinned-read briefing is not practical.
- **Don't:** treat a read-only subagent as immune to the orchestrator's own checkout churn -- read-only protects the tree from the agent, not the agent from the tree.
- **Don't:** assume a reviewer will notice and recover the way this one did;
  build the pinned read into the brief rather than relying on the reviewer to catch a moving target.

(Measured 2026-08-27, `Morrison-Lab/gha`: the orchestrating session ran `git checkout <other-branch>` in its own worktree to address a different PR's review finding while a dispatched read-only reviewer subagent was mid-review of the previous branch in that same directory.
The reviewer noticed the tree had changed mid-flight and fell back to `git show <pinned-sha>:<path>` reads to finish the round.)

**Second occurrence, 2026-09-09: the trigger is any write to the tree, not `git checkout`.**
Recorded in [`shared/workflow/adversarial-self-review.md`](../shared/workflow/adversarial-self-review.md), since the rule it yields binds the dispatcher rather than the worktree.

## An unisolated subagent's live edits get read by a dirty-tree check as YOUR uncommitted work

The rule to set `isolation` on every `Agent` call is stated in
[`CLAUDE.md`](../CLAUDE.md) and warned about by
[`hooks/flag-unassigned-worktree.py`](../hooks/flag-unassigned-worktree.py),
and its stated rationale is about agents organizing their own directories and
about the two directions of liveness misreading.
Neither names the consequence measured here, which is the one that can cause
damage rather than confusion.

A dispatched agent working in the session's **primary checkout** leaves its
in-flight edits in the tree the session's own tooling inspects.
A repo-wide dirty-tree check --- a `Stop` hook, a pre-push guard, a wrap-up
sweep --- cannot tell whose edits those are.
It reports uncommitted changes and prescribes the ordinary remedy: commit and
push them.

That remedy is correct for your own work and **actively harmful** for an
agent's.
The measured case: an adversarial reviewer was asked to confirm that each new
test fails when its corresponding fix is reverted, so it was doing exactly
that --- mutating the implementation --- when the `Stop` hook fired.
Committing and pushing on that instruction would have shipped the reverted fix
under a commit message claiming the opposite, and closed the issue with the
bug intact.

Three things make it hard to catch from the inside.
The hook's report is accurate: the tree *is* dirty.
The prescribed action is the one that is right almost every other time it
fires.
And the agent is behaving correctly --- running mutations is what it was asked
to do --- so nothing looks like a fault to investigate.

The tell is a diff you did not write.
Read it before acting on any dirty-tree report, and check
[`ListAgents`](../CLAUDE.md) for a live subagent before touching any path that
report flags:
a running agent's mutation must be left alone until it finishes and restores,
per this file's own "A quiet worktree is not evidence the session working it
has stopped".

- **Do:** read the actual diff on a dirty-tree report, rather than acting on
  the report's summary.
- **Do:** check for a live subagent before committing, reverting, or stashing
  anything you do not recognize.
- **Do:** decline the hook's instruction, and say why, when the uncommitted
  delta is another agent's scratch state.
- **Don't:** dispatch a write-capable agent into the primary checkout ---
  which is what puts its state where a whole-repo check will claim it.
- **Don't:** read "my own work is committed" as making a dirty tree safe to
  clear; the danger is the extra content, not the missing content.

(Measured 2026-08-30 on `Morrison-Lab/gha#755`.
The reviewer's mutation reverted `normalize_bullet_markers`'s fix --- one line
--- while the session's own three commits were already safe.
The hook fired on that single line.
The prior instance in [`CLAUDE.cases.md`](../CLAUDE.cases.md) records the same
unassigned-isolation slip with no harmful consequence available; this is the
consequence.)

## A read-only `cd` into a peer's worktree, or a REFUSED checkout, can arm `no-unshipped-commit.py`

Sibling to the "An unisolated subagent's live edits get read by a dirty-tree check as YOUR uncommitted work" section, same family (a repo scan drawing a conclusion from context that is not the session's own), different mechanism: `no-unshipped-commit.py` (unpushed commits, not uncommitted diffs) fired from inspecting a separate PEER worktree, not from working inside the primary one.

Measured 2026-09-04 on `ucdavis/hac.sap`: a session `cd`'d into a peer's worktree only to inspect it, exactly what [`CLAUDE.md`](../CLAUDE.md)'s "Subagent worktrees are assigned" section requires, and separately ran a `git checkout -B` that git refused (`fatal: ... already used by worktree`).
The hook then blocked `Stop`, reporting four of a live peer's unpushed commits (one a breaking `fix!:`) as this session's to push.

Filed as [ai-config#3272](https://github.com/Morrison-Lab/ai-config/issues/3272) (open; do not re-file).
Its own follow-up comment names the mechanism as it stood at filing time: a read-only visit and a failed checkout both registered as "touched."
**Do not cite that comment's function or variable names as current** --- `no-unshipped-commit.py` has since accumulated several unrelated attribution fixes per its own docstrings (ai-config#2422, #2737), so a name correct at filing time can already be stale;
re-derive from the live source before quoting internals, which is this entry's own near-miss on the first draft (an adversarial review caught fabricated names and a stale line range copied from the issue rather than re-checked against the code).
A re-read of the current `scan_transcript` found that a call containing only a `cd`/`checkout` with no `git commit` in it no longer contributes to the tracked branches or paths at all (the function's own docstring: "Visiting is not committing," ai-config#2422), so the plain read-only-`cd` trigger may already be closed.
Whether a *refused* checkout inside the same call as a real commit still registers (the command is read as text, with no exit-status check visible in that read) was not re-verified here.

Until the issue resolves, or its current state is re-checked:

- **Do:** inspect a peer worktree with `git -C <path>` reads (`status`, `log`, `rev-parse`), never a bare `cd`, as a general precaution regardless of this hook's current state.
- **Do:** re-read the hook's live source, not this entry or the issue comment, before asserting whether the bug still reproduces.
- **Don't:** comply with "push the branch" when the flagged worktree belongs to a peer confirmed live;
  publishing another session's unreviewed, possibly mid-amend commits is unsafe regardless of the trigger or whether the hook's report is accurate.

## An empty draft PR is not evidence that nothing was done

The "A quiet worktree is not evidence the session working it has stopped"
section is about whether you may **touch** a quiet worktree.
This is a step earlier: whether you should even **look**, and it can matter
even when the worktree's session has genuinely gone quiet.

`pr-on-claim` opens a draft PR from an empty commit at claim time (see
[`pr-on-claim`](../shared/workflow/pr-on-claim.md)), so a PR's own file and
line counts describe the branch **as last pushed**, not the branch as it
currently sits on disk.
Measured 2026-09-05 on `Morrison-Lab/ai-config#3168`: the PR showed 0 files
and 0 additions and had gone unupdated for 37 hours, which reads as
abandoned or not-yet-started.
Its branch's worktree, at a path outside any session's own scratchpad, held
**two unpushed commits totalling 366 insertions across 4 files** --- including
a security-relevant guard fix
(see the "An identity match with no id must poison rather than guess" section
of [`fail-fast`](../shared/principles/fail-fast.md)).
The owning session had exited without pushing.

So the forge's view of a PR and the working tree's view can diverge
completely, and the direction that matters is the dangerous one: real,
reviewed-or-not, security-relevant work can sit invisible to everyone reading
the PR, including a later session deciding whether that PR is safe to ignore
or safe to close.

The check that finds it costs two commands: `git worktree list` to find the
branch's worktree path, then `git log origin/<branch>..HEAD` and `git status
--short` run inside it.
An empty or stale-looking PR is a prompt to run that check, not a conclusion
that nothing is there.

- **Do:** run `git worktree list` and check the associated worktree's
  unpushed/uncommitted state before treating an empty or stale draft PR as
  abandoned, un-started, or safe to close.
- **Do:** treat a positive result from that check as the same magnitude of
  finding whether the PR looks empty or looks active --- the PR's own
  counters are the thing that was wrong, not a secondary signal.
- **Don't:** infer "nothing happened here" from a PR's file/line counts or
  its `updatedAt` alone; both describe the last push, not the branch.
- **Don't:** conflate this with the liveness question the "A quiet worktree
  is not evidence the session working it has stopped" section settles --- a worktree
  can hold real unpushed work whether or not the session that wrote it is
  still running, and this check is worth running either way.
