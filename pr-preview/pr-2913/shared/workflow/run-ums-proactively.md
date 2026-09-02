Don't wait for `/clear` or the end of a task to run `ums` (Update Memories and Skills).
As soon as a learning worth saving shows up during a session --- a corrected mistake, a new preference, a tool quirk, a workflow gap --- run UMS right then, interleaved with the main work, rather than batching it for a wrap-up step at the end.

Still run UMS before `/clear` too, as a final catch-all for anything accumulated since the last proactive pass --- but treat that as a backstop, not the trigger to wait for.

**In a multi-PR/multi-issue session (GII-style), treat each PR merge as a concrete proactive-UMS checkpoint, not just "whenever a learning happens to surface."**
"As learnings accumulate" is easy to defer indefinitely during heads-down execution across several PRs, since no single moment feels like the obvious trigger --- a merge is a natural, unmissable boundary to pause at instead.

**A PR's clean review verdict is a proactive-UMS checkpoint in its own right, and it fires strictly earlier than the merge -- run the pass there rather than holding it until the PR lands.**
The bullet above picked the merge because it is unmissable, and it is; the problem is that it may never arrive on this session's clock.
Merging is human-gated: [`ardi`](ardi.md)'s terminal action is to report the PR ready, never to merge it.
So a clean-but-unmerged PR can sit for hours, for days, or across a `/clear`, and the review lifecycle's learnings sit with it in conversation state that may not survive the wait.
Waiting buys nothing either, because by the time the verdict is clean every finding has already been Addressed, Rebutted, or Deferred -- the review has taught everything it is going to teach, and the merge adds only whatever the merge itself surfaces.
So run UMS when the verdict comes back clean, and treat the merge-time pass as a top-up rather than the trigger.

**Offering to run UMS is not running it.**
Everything above rules out *deferring* the pass to a wrap-up step.
It has to rule out the adjacent move as well, because that one reads as compliance rather than evasion: surface the learning now, and run the pass once the user says go.

An offer to run UMS is worth exactly what an unrecorded learning is worth, since both live only in the conversation and both die with it.
The two asymmetries that decide it are already written down, for issues rather than for learnings, in [`report-mistakes-proactively`](report-mistakes-proactively.md)'s "Filing is not gated on approval" section: a redundant entry is cheap while a lost one is not, and only the user can say a thing is not worth keeping --- which they can do after it is written, not only before.
Read that section rather than re-deriving the argument here.
The pattern is identical, and only the artifact differs.

What stays genuinely worth asking is **where** a learning belongs when the destination is unclear, never **whether** to record it --- the same split that fragment draws around its own dupe-check step.
Write it down first, then ask.

**The offer also survives being phrased as a decision, and that form is harder to see.**
The bullet above rules out the question.
It does not rule out the sentence that states an intention and then hands the timing back: "I'll run it now unless you'd rather I do something else first."

That reads as a commitment rather than a request, which is exactly why it passes self-review.
It is not one.
The pass still does not start, the user still has to spend a turn, and the trailing clause is doing the same work the question did --- it just moved the gate from *whether* to *when*.
It usually appears at the end of a long status recap, where it reads as courtesy about sequencing rather than as a request for permission.

The test is mechanical, so apply it rather than judging the tone: **if the sentence about UMS contains a conditional referring to the user, it is an offer.**
"Unless you'd rather", "if that works", "let me know if" --- all of them.
Run the pass, then report it in the past tense, and put any genuine sequencing question in its own sentence about the *other* work.

- **Do:** run the pass and say "ran UMS; here is what it recorded".
- **Do:** ask about ordering the remaining work, once the pass is already done.
- **Don't:** attach a user-conditional to a stated intention to run it.
- **Don't:** read "I will" as sufficient --- the trailing clause is what decides it.

**A new instruction arriving at a checkpoint does not cancel the checkpoint.**
The bullet above covers the pass you *announce* and never run; this is the one you never announce at all, because something else arrived first.
A merge or clean verdict is usually the exact moment I report back, so it is also the moment the next request lands.
That request then reads as the live task, and the checkpoint silently evaporates -- never refused, never deferred out loud, just never performed.
Note the asymmetry with the deferral the earlier bullets describe: there no moment feels like the trigger, whereas here a moment *did* fire and was preempted.
The remedies differ, and the preempted case cannot be fixed by naming more checkpoints.

The fix is cheap, because the pass is short.
When a request arrives at a checkpoint, either run UMS first and then start the request, or say in the same reply that the pass is owed and when it will run -- the latter being a real commitment, per the bullet above, not an offer.

The same skip has a second route worth checking, since several skills end in a UMS step ([`post-merge`](../../skills/post-merge/SKILL.md), [`ardi`](ardi.md), [`wrap-up`](../../skills/wrap-up/SKILL.md)).
Reporting one of those skills complete asserts that its final step ran, so before calling a merge wrapped up, confirm the UMS pass actually happened rather than only the steps before it.

**A merge you discover rather than perform is still a checkpoint, and it is the one that never feels like a moment.**
Every bullet above describes a checkpoint that *happens* while you are watching: you push, the verdict lands, the PR merges, you report back.
The merge someone else performs while you are away arrives differently --- as a row in a status table, hours later, alongside a dozen other rows.
Nothing about reading `MERGED` in a poll resembles the event the rule was written for, so the checkpoint passes without ever presenting itself as one.

The asymmetry is worth naming because it inverts the usual risk.
A checkpoint you witness is at least *available* to be skipped.
This one is never noticed to begin with, and the more of them arrive at once, the less any single one reads as an occasion to stop.
A status poll that flips several PRs from open to merged is therefore a strong UMS trigger, not a weak one.

So treat any transition **to** merged as the trigger, whoever performed it and whenever you learn of it.
The cheap check is the poll you are already running: if a PR you were driving reads merged now and did not last time you looked, the pass is owed.

- **Do:** run the pass when a status query first shows a PR merged, exactly as if you had merged it yourself.
- **Do:** treat a batch of merges discovered together as one checkpoint carrying all of their learnings, rather than as background news.
- **Don't:** require that you witnessed the merge for it to count.
- **Don't:** let a poll that reports several merges roll straight into the next task because no single row felt like an event.

**Recommending that the session end is itself a UMS trigger, and it is the one route where skipping the pass destroys the learnings rather than merely delaying them.**
The three bullets above all describe a pass that is *postponed*: no moment felt like the trigger, or a moment fired and was announced, or a moment fired and was preempted.
In each of those the material survives in the conversation, so a later pass can still recover it.
This route closes that door.
Proposing `/clear`, a fresh session, or a handoff while the pass is owed is proposing to discard exactly what the pass exists to save, and the recommendation reads as responsible precisely because it is framed as tidying up.

Disclosing the owed pass in the same message as the `/clear` flag is not enough either.
That is the *offer* failure one level up: it names the debt in the same breath as recommending the action that voids it, which leaves the user to notice the contradiction.
So invert the order.
Run the pass, then flag the stopping point.
A flag that has to mention an owed UMS is a flag raised too early.

**"I am low on context" does not exempt it, and that claim needs the same test any other asserted blocker does** (see [`ardi`](ardi.md)'s "Verify a blocker you assert").
It is the one blocker that is never tested, because it feels like introspection rather than a claim, and it is self-serving in a way the others are not: it excuses the work while sounding diligent.
The asymmetry also runs the wrong way for caution.
A pass that records the top three learnings in a few edits is worth far more than a thorough one that never runs, so shrink the pass rather than deferring it, and say what got left out.
If context genuinely runs out mid-pass, the entries already written are durable and the session ends having banked most of the value.

- **Do:** run the pass, then flag the stopping point, then let the user decide how to end the session.
- **Do:** shrink a pass you genuinely cannot finish, record the top items first, and say what was left out.
- **Don't:** recommend `/clear`, a fresh session, or a handoff while a pass is owed, however clearly the debt is disclosed alongside it.
- **Don't:** cite remaining context as a reason to defer, without having attempted the pass.

**"That would mean another open PR" is the same deferral wearing repo hygiene, and it is the one that sounds like good judgment.**
Every bullet above rules out a deferral whose stated reason is about *me* --- no moment felt like the trigger, a request preempted it, context is short.
This one's stated reason is about the **repo**, so it reads as restraint rather than avoidance: holding a fourth concurrent PR looks like consideration for the reviewer and the merge queue.

Three things dissolve it.
A UMS PR is *usually* disjoint --- it touches a memory file or a fragment nothing else in flight is editing --- so it usually costs no merge-order constraint and no conflict, which is exactly the case `CLAUDE.md`'s own merge-order section says to state plainly rather than manage.
Verify that rather than assuming it, because two UMS passes in one session land in the same few files and collide readily.
When they do, the answer is still to open the PR and resolve the collision, not to hold the pass.
The queue is durable and the learning is not: an extra open PR waits patiently, while an unrecorded learning dies with the session, so the two costs are not comparable.
And the deferral is usually announced in the same breath as reporting a PR ready, which is the moment the next instruction arrives --- so "once this lands" reliably becomes never.

The permission to announce a pass rather than run it, granted above, is for a **real** blocker.
Not wanting another PR is a preference, and a preference does not license the announcement.

- **Do:** open the UMS PR immediately, however many of yours are already open, and resolve any collision it turns out to have.
- **Do:** check whether its files overlap your other open PRs, and say either that it is disjoint or exactly where it collides, so the count does not read as a problem.
- **Don't:** defer a pass to keep the open-PR count down, or until an unrelated PR merges.
- **Don't:** treat "I will write it once #N lands" as a commitment --- it is the announced-and-never-run failure with a due date attached.

**"Don't start a new wave" is the same deferral wearing an instruction, and the instruction does not say what it is read to say.**
A `gii`/`gia` wave boundary, or a "finish the current wave but don't start a new one" from the user, caps *issue grabs*.
A UMS pass is not a grab: it records what the wave taught, and it is owed at the wave's own clean verdicts and merges by the bullets above.
So the pass runs, and its PR opens, inside the cap --- see [`gii`](../../skills/gii/SKILL.md)'s "A UMS pass is not a new wave" paragraph, which carries the user's directive.

- **Do:** run the owed pass under a no-new-wave instruction, exactly as under no instruction.
- **Don't:** hold the pass until the next wave is authorized, on the reading that its PR would be a new wave.

**Correcting your own understanding of a technical issue is itself a trigger, and it fires immediately rather than at the next checkpoint.**
Every trigger above is an event in the *work*: a verdict lands, a PR merges, a poll reports a merge, a stopping point gets proposed.
This one is an event in what you *believe*, and it leaves no artifact behind.
Nothing merges, no check turns green, and the only record is that you were wrong and then were not.

That absence is why it needs naming rather than being left to "as learnings accumulate".
A corrected misunderstanding feels resolved the moment it is corrected, so the correction reads as the completion when it is only the input.
Nothing is left outstanding, so nothing prompts the pass, and the learning evaporates with the conversation that produced it.
That puts it alongside the recommend-a-fresh-session route above, as a case where skipping the pass destroys the material rather than merely delaying it.
It is also unusually valuable material, because a correction names both the model that was wrong and the thing that displaced it -- which is exactly the pair `CLAUDE.md`'s ["Record both the pattern and the anti-pattern"](../../CLAUDE.md) section asks every entry to carry.

So run the pass at the correction, not at the end of whatever task the correction unblocked.
The task will still be there; what you believed ten minutes ago will not.

- **Do:** run the pass as soon as a technical belief is corrected, before resuming the work it was blocking.
- **Do:** record the belief that was wrong alongside the fact that replaced it, not just the fact.
- **Don't:** wait for the unblocked task to reach a checkpoint of its own -- that checkpoint carries the task's learnings, not the correction's.
- **Don't:** treat "I know the right answer now" as the pass having happened.

**A false claim about *state* is the same trigger, and it is the one you can be wrong about without ever holding a wrong belief.**
The bullet above covers a corrected *understanding* --- a model of how something works, which you held, and which turned out to be false.
The commoner failure has no belief in it at all.
You assert that a repository is public, that a PR is green, that a corpus lacks a feature, that a list has nine entries.
None of those were things you thought.
They are things you did not look up, or looked up once against a stale checkout and then repeated.

That absence is why the trigger above does not obviously fire here.
Nothing that feels like a belief gets corrected, so the discovery reads as a small factual fix rather than as the event this section is about.
It also arrives mid-task, at the moment the natural impulse is to repair the claim and carry on --- which is the opposite of a checkpoint, and is exactly when nothing prompts a pass.

Treat any discovery that you were wrong as the trigger, whatever kind of wrong it was.
The class matters for what you *record*, not for whether the pass runs: a corrected belief yields the belief and its replacement, while a false state claim yields the query you should have run, which is the more reusable of the two.

Two mechanisms make this survivable rather than merely mandated.
**Delegate the pass**, per [`use-subagents`](use-subagents.md)'s "Use subagents when helpful" section, which already pre-authorizes an owed UMS pass as sidecar work --- that is what keeps the pass from competing with the task the correction interrupted.
And **algorithmatize the trigger** rather than relying on noticing it, per [`algorithmatize-checks`](algorithmatize-checks.md): `hooks/remind-ums-after-error.py` detects a first-person admission in the transcript and injects a reminder on the next prompt when no memory, skill, or shared write followed it.
That hook only ever *adds context*.
An error admission must never be blocked, delayed, or suppressed --- see its own docstring, and the "Never activate a new hook before its PR merges" gate in [`README.md`](../../README.md).
Building such an instrument is itself delegable sidecar work, not a reason to postpone the pass.

- **Do:** run the pass the moment you discover any claim of yours was false, including one you never believed so much as asserted.
- **Do:** record the *query that settles it* for a state claim, not just the corrected value.
- **Do:** delegate the pass, and delegate the instrument, rather than queueing either.
- **Don't:** treat a factual correction as too small to record because no belief changed.
- **Don't:** wait for the task the correction interrupted to reach a checkpoint of its own.

**Scrutiny of your work is a UMS trigger, and a questioned claim that was wrong is the path that looks like a closed Q&A.**
The triggers above all fire on a discovery you made, or on a verdict, or on an admission.
They miss the moment someone else scrutinizes the work: you read a review, you take critical feedback, or a claim is questioned.
Nothing in those moments requires you to say "I was wrong", to Address a finding, or to wait for a clean verdict, so the existing checkpoints never see them.

Three surfaces, one pass.
They are not three rules.

1. **You read a review of your work.**
   The trigger is the read, not Address and not a clean verdict.
   Rebut and Defer still get a pass: the review taught something even if you disagree.
   A review with no findings still gets a short pass.
   [`learn-from-review-findings`](learn-from-review-findings.md) still attaches the record-the-class and algorithmatize steps to Address.
   This is the earlier bank, not a replacement for those steps.

2. **You receive critical feedback on the work.**
   Chat, a human PR comment, another agent's review, an adversarial-reviewer finding.
   Not only a formal `@claude review` round, and not only feedback phrased as a behaviour correction.

3. **A claim of yours is questioned, and the check shows it was wrong.**
   "Are you sure about that?" is the given example.
   Questioning is the prompt to check, not itself the recorded lesson.
   If the check shows the claim was right, answering is enough.
   If the check shows the claim was wrong, run UMS: answering with the corrected fact is not the pass.
   That path is what the first-person-admission trigger and `hooks/remind-ums-after-error.py` miss by construction --- you never said "I was wrong", you just updated the answer, and the Q&A reads as closed.

`hooks/remind-ums-on-scrutiny.py` is the decidable slice: a review-read, or a questioned claim followed by a correction, with no explicit UMS after it.
It injects on the next prompt and never blocks.

- **Do:** run UMS when you read a review of your work, before or as you start ARD, not after the verdict.
- **Do:** run UMS when critical feedback arrives, including feedback that is not a formal review round.
- **Do:** when a claim is questioned and the check shows it was wrong, run UMS as you correct the answer --- the discovery is the trigger, not a first-person admission.
- **Don't:** wait for Address, a clean verdict, or an admission phrasing before the pass is owed.
- **Don't:** treat answering "are you sure about that?" with the corrected fact as having banked the lesson.
- **Don't:** run UMS merely because someone asked.
  The questioning case fires if the claim was wrong.

See [`run-ums-proactively.cases.md`](run-ums-proactively.cases.md), "Are you sure about that?".

(Directive from the user, 2026-08-25, in four successive expansions:
run ums every time you read a review of your work,
then any critical feedback,
then every time your work or your claims are questioned,
then the worked example that questioning triggers UMS if the claim was wrong.
Tracked as [ai-config#2261](https://github.com/Morrison-Lab/ai-config/issues/2261).)

**Folding or pruning a finished record is a step of the pass, and which records are outstanding is a link-graph fact rather than something you remember.**
`CLAUDE.md`'s ["Keep a running on-disk session lab notebook"](../../CLAUDE.md) section already names the moment: fold a finished notebook into durable memory, or prune it, during UMS once its content is captured elsewhere.
It names no way to find the ones you have forgotten, so the set is left to recollection --- and recollection covers this session's notebook and nothing else.
A notebook from three sessions back, a `handoff` snapshot, a `.cases.md` companion nothing cites: each is invisible to the session that would have to remember it, which is exactly the blind spot [`flag-session-boundaries`](flag-session-boundaries.md) names for a state sweep.

So run the instrument as part of the pass:

```bash
python3 scripts/check-stale-records.py
```

It walks the same link graph `scripts/check-links.py` does, counts inbound links and `@`-imports per markdown file, and reports two buckets plus the count it examined.

**Orphans --- zero inbound references --- are a reading prompt rather than a defect.**
A slash command invoked by name, an index, a directory README: each is legitimately unlinked, so the question the bucket answers is whether a *new* orphan appeared, not whether the count is zero.

**Old but still referenced is the bucket the corpus was blind to**, and it is the harmful case: a live link to a stale record reads as current project state to every fresh agent walking the graph, where an orphan is merely unreachable.

**The age bucket carries no information under a shallow clone**, which is what the checker's own output says (`age_informative: false` in `--json`).
Re-run against a full clone (`git fetch --unshallow`) before reading it.

- **Do:** run the checker during the pass, and fold or prune whatever it reports that the pass has already captured elsewhere.
- **Do:** read a new orphan as a question about that file.
- **Don't:** decide which records are outstanding from memory --- that covers this session's own notebook and nothing else.
- **Don't:** read the age bucket at all from a shallow clone.

See [`run-ums-proactively.cases.md`](run-ums-proactively.cases.md), "Stale records checker baseline and shallow clones".
