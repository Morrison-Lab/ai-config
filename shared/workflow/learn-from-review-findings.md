A reviewer's valid finding is a mistake that reached the reviewer, so treat every one you accept as a first-push miss to learn from --- not merely an item to fix and close.
The goal is a review that comes back clean on the first push, and every finding a reviewer has to raise is that goal missed once.

Fixing the finding discharges the PR.
It does not discharge the *lesson*, and the two feel identical from the inside: the thread resolves, the round closes, and the class of mistake that produced the finding is still unrecorded and still free to recur on the next PR.

This is the external-correction counterpart to the "discovering you were wrong" triggers in `CLAUDE.md`'s "Run UMS proactively" section, which fire on a *first-person* admission ("I was wrong").
A reviewer catching your mistake is the commoner case and the one those triggers miss by construction: you never admit anything, you agree with a finding --- so `hooks/remind-ums-after-error.py`, which keys on a first-person admission and deliberately excludes correcting someone else, never fires.
The learning is exactly as real; only the surface that carried it is a review thread rather than a sentence of self-correction.

So when you Address a finding --- as opposed to Rebut or Defer it, per [`ardi`](ardi.md)'s ARD dispositions --- do two things beyond the fix:

1. **Record the class of mistake** --- what you overlooked or believed, and what the reviewer saw.
   This is `CLAUDE.md`'s "Run UMS proactively" rule reaching the review loop: record the lesson as the finding is accepted rather than deferring it, with [`ardi`](ardi.md)'s clean-verdict pass as the backstop that catches whatever slipped through, not the trigger to wait for.
   Delegate it to a subagent, per `CLAUDE.md`'s pre-authorized sidecar work, so it does not compete with the round.
2. **Ask whether it is algorithmatizable**, per [`algorithmatize-checks`](algorithmatize-checks.md).
   A finding with a decidable condition --- a banned token, a stale cross-reference, a missing test for new logic, a doc a diff falsified --- is one a pre-push check or a hook can catch every time thereafter, so the next reviewer never has to.
   That is the mechanism half of `hooks/no-mistake-without-a-hook.py`, one class of mistake over: the reviewer's finding is the incident, and the guard built from it is what turns "the reviewer keeps catching this" into "the reviewer never sees it again".

The UMS pass itself now fires earlier than Address: on *reading* the review,
and on critical feedback or a questioned claim that was wrong, per
[`run-ums-proactively`](run-ums-proactively.md).
This section's two steps still attach to Address.
The read-time pass is the bank.
Address is the class-of-mistake write-up.

The lever that actually delivers a clean first push is the pre-push self-review [`ardi`](ardi.md) already requires: the project's own review skills and checks applied to your own diff *before* pushing, so a finding you would have accepted is one you caught first.
Dispatch that pass rather than performing it --- a separate [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md) subagent, per [`adversarial-self-review`](adversarial-self-review.md) --- since the session that wrote the diff is the one party that reads it already knowing what it meant.
A finding a reviewer raises that your own stated conventions already covered is a self-review that did not run, not new information --- see [`copilot-review-before-human`](../vendored/copilot-review-before-human.md) for the same point about catching issues before a human sees them.

Not every finding is a learnable pattern.
A true one-off --- a typo, a domain fact you could not have known, a judgment call that went the other way --- has no rule and no mechanism behind it, and inventing one produces a guard that misfires and gets switched off, taking the real cases with it ([`algorithmatize-checks`](algorithmatize-checks.md)'s "Limits").
Saying plainly that a finding is a one-off, and why, discharges the lesson as completely as recording it does.
What is not allowed is the silent third option: fix it, resolve the thread, and record nothing --- which is the default this fragment exists to displace.

- **Do:** on accepting a reviewer's finding, record the class of mistake and ask whether a pre-push check or hook could catch it next time, before calling the round done.
- **Do:** run the project's own review skills against your diff before pushing, so an accepted finding is the exception rather than the round.
- **Don't:** treat resolving the thread as the whole of the work --- the fix discharges the PR, not the lesson.
- **Don't:** invent a rule or a hook for a genuine one-off; say it is one, and why, then move on.

(Morrison-Lab/ai-config#1065: the standing goal that "every PR gets a clean review on the first push --- learn from your mistakes so you don't repeat them, and algorithmatize whenever possible (e.g. through hooks or other scripts)."
`hooks/remind-learn-from-review.py` is the trigger this fragment describes: it detects an accepted review finding in the transcript with no learning or mechanism recorded after it, and injects a reminder on the next prompt --- the external-correction sibling of `hooks/remind-ums-after-error.py`, which only ever adds context and never blocks.)

A finding class that RECURS is evidence about your instrument, not about its threshold.
Everything above treats findings one at a time: accept it, fix it, record the class, ask whether a check could catch it.
That is the right loop while the findings are different.
It says nothing about the case where the *same kind* of finding comes back, and that case wants the opposite response from the one the loop trains.

The reflex when a finding recurs is to widen or tighten whatever you built the first time --- add the case the reviewer just showed you, and the round goes green.
It always does.
A narrowed heuristic passes the tests written from the finding that prompted it by construction, so the artifact reports success and the class survives inside it.
That is what makes this invisible without a rule: nothing distinguishes "fixed the class" from "fixed the instance and re-armed the class", because both look like an accepted finding, a targeted patch, and a passing suite.

So use recurrence itself as the signal.
**The second time a reviewer raises the same class, stop asking what else the check should match and ask whether that kind of check can decide the question at all.**
Those are different questions, and only the first one has an obvious next move --- which is exactly why the second one gets skipped.

A reviewer's own wording is often the cheapest way to notice.
"The same underlying defect class recurring for the third time", "this is the same issue as before", "a residual instance of" --- each names a recurrence the individual finding does not, and each is easy to read past while attending to the concrete case attached to it.
Read the framing as a finding in its own right.

Note the direction of travel, since a suggested fix pulls the other way.
A reviewer who spots a recurrence still tends to propose a *narrowing*, because a narrowing is concrete and a redesign is not theirs to specify.
Taking that suggestion is the fourth patch, not the fix, and declining it is not a rebuttal --- accept the finding, decline the remedy, and say which you are doing.

The replacement is usually a different kind of evidence rather than a better pattern.
Ask what would settle the question directly, and whether you can observe it: an artifact instead of a description of one, a derived count instead of a claim about a count, a tool call instead of the prose announcing it.
Where no such evidence exists, say so and pick the failure direction deliberately, per [`fail-fast`](../principles/fail-fast.md) --- a bounded, nameable false positive beats a silent bypass, and both beat a heuristic nobody can characterize.

This is [`deterministic-tools`](../principles/deterministic-tools.md)'s recurrence bar pointed the other way, and the two thresholds differ on purpose.
That rule says the third time you do a judgment task by hand, build a tool.
This one fires a round earlier: the **second** time your tool draws the same finding, the tool is wrong --- and the fact that it keeps *almost* working is the reason it survives that long.
The asymmetry is the point rather than an oversight.
Waiting for a third instance costs a whole extra round spent narrowing something that cannot work, which is precisely the delay this section exists to prevent;
waiting for a third hand-run of a judgment call costs only that call.

- **Do:** treat the second instance of a finding class as a question about the instrument, and say in the round which of the two questions you are answering.
- **Do:** read a reviewer's "same issue as before" framing as a finding in its own right, separate from the case it arrives attached to.
- **Do:** look for evidence you can observe directly before reaching for a better pattern.
- **Don't:** apply a suggested narrowing just because the reviewer offered it --- a recurrence's proposed remedy is usually one more patch.
- **Don't:** read a passing suite after a narrowing as evidence the class is closed;
  the tests came from the instance.

(Morrison-Lab/ai-config#1733, from three review rounds on #1724.
Rounds 1 and 2 were answered by narrowing a wording heuristic, and round 3 found the same class again in bare nouns (`edit`, `update`, `record`, `author`, `patch`) that the round-2 verb pattern matched.
The fix that held was deleting the heuristic and observing a subagent's actual writes instead.
Both remedies the round-3 review suggested were a fourth narrowing, and each is defeated by a one-line rephrasing.)

A manual action by someone else, on a PR you claimed, is the same trigger with nothing labelled a finding.
The trigger above still needs a reviewer to state a defect.
This is the version where nobody states anything.
You claimed the PR --- posted the claim comment, per [`claim-pr`](claim-pr.md) --- and while you are driving it, another actor performs an action that was already yours to have taken.
A human requests the review you should have requested the moment the PR opened or went ready, per [`pr-on-claim`](pr-on-claim.md)'s "Request the external reviewer in the same stride".
A maintainer merges `main` in to clear a conflict [`sync-with-main`](sync-with-main.md) says you should have been watching for.
A bot resolves a thread [`address-every-comment`](address-every-comment.md) says you should have resolved on Address.

Nothing marks it as a correction.
A reviewer's finding is addressed to you and labelled a defect; a manual compensating action is just someone else doing their part, and it reads that way even when the part they did was yours.
The PR keeps moving, the gap closes, and there is no comment, no thread, no "not addressed" for anything to notice --- which is exactly what leaves this trigger unfired by default.
Treat the observation itself as the finding: someone else had to do the thing you own, which means you did not do it when you should have.

Two branches once you notice it, and they call for different lessons.
If a standing rule already required the action --- `pr-on-claim`'s review-request step is the given example --- this is an **execution** miss: run UMS to record why the rule did not fire (a timing you missed, a step your checklist didn't carry), and sharpen the checklist per [`skill-checklists`](skill-checklists.md) rather than merely re-reading the rule you already had.
If no rule covered the action, this is a **coverage** gap: write the rule now, the same way any other accepted finding gets encoded, per the "record the class of mistake" step above.

A detector here is harder than `hooks/remind-learn-from-review.py`'s, and is deliberately not built alongside this fragment.
That hook keys on a review comment already sitting in the transcript.
This trigger needs the transcript compared against the PR's own timeline --- who actually took an action the session was supposed to take --- which is a real instrument to build later, not a reason to skip recording the rule now; see [`algorithmatize-checks`](algorithmatize-checks.md) on building the check once the judgment has recurred.

- **Do:** treat a manual compensating action by another actor on a PR you claimed as a first-push miss, exactly like an accepted review finding.
- **Do:** check first whether an existing rule already covered the action; a rule you had and skipped is a different lesson than a rule you never wrote.
- **Don't:** read the action as merely "someone else helping" and move on --- the absence of a comment naming you is not evidence there was nothing to learn.
- **Don't:** wait for a formal finding before recording the lesson; the action itself, unremarked, is the finding.

(Directive from the user, 2026-08-07: "if you see someone else do something manually on a PR you've claimed (like ask for a review), consider whether you should have done that yourself already, and learn/improve yourself accordingly.")

A fix for a defect class is where a fresh instance of that class hides.
The section above fires on the **second** time a reviewer raises a class, and asks whether your instrument can decide the question at all.
This one fires on the **first**, and asks a different question.
Where is the next instance going to be?
The answer is the fix.

[`ardi`](ardi.md)'s "Run that check over your own fix, too" already states the code half, and asks whether the fix's own new code instantiates the class it just closed.
That is posed per fix and answered yes or no.
The increment here is that the same exposure reaches **prose**, that the fix's new lines are members of a **population** rather than the subject of a yes-or-no question, that a residual you *name* asserts a survey nobody ran, and that the exposure runs in **both directions** --- a fix can silently remove a capability as easily as it can leave a bypass.

Measured three times across four review rounds on [ai-config#1947](https://github.com/Morrison-Lab/ai-config/pull/1947), each time in the fix for the round before.

**The prose sweep that skipped its own new line.**
Round 1 named three pre-existing `Don't` bullets reading as a blanket ban on a case the PR was introducing an exemption for.
All three were correctly scoped.
Round 2 found that the bullet the same branch had itself added carried the identical contradiction, 11 lines from the prose it contradicted, and in the reviewer's own words at *closer range* than the more distant pre-existing bullets the fix had correctly scoped.
Proximity ran inverse to the catch rate, which is the tell that the sweep's population, rather than its pattern, was the defect.

**The residual paragraph that named the rarer case.**
Round 1 found a regex discharging on a mere mention of a path rather than an execution of it.
The fix added an execution anchor and a docstring paragraph headed "Residual, named rather than papered over", accepting `python3 -c "print(open('...').read())"` as contrived.
Round 2 found that `sh -c "cat ..."` --- an ordinary idiom, far commoner than the accepted residual --- walked past the new anchor untouched.
The paragraph performed the ritual of naming a residual while naming the wrong one, which is worse than naming none, because it reads as having surveyed the class.

**The rewrite that dropped a tolerance nobody had written down.**
Both instances above are fixes that left something *open* --- a contradiction the sweep did not reach, and a bypass the new anchor did not close.
Round 4 is the mirror, and it earns its own paragraph because it fails in the opposite direction.
Round 3 had stopped patching the regex and replaced it with a `shlex` tokenizer, which is the considered repair rather than a fourth narrowing.
Round 4 then found that the rewrite had silently removed something the regex could do:

```
python3 hooks/monitor-open-prs.py; echo done
```

`shlex.split` breaks on whitespace and quoting but not on shell operators, so the path token arrives carrying the trailing separator, and the new anchored match rejected it.
The old unanchored `re.search` had never cared about trailing punctuation.

Two things make this the sharpest of the three.
It landed in the round that deliberately **changed instruments**, the least reflexive fix available and chosen precisely because successive rounds had shown the pattern itself was wrong, so the mechanism is structural rather than a matter of care.
And a false negative **fails safe**, so it leaves no artifact behind.
A bypass is found by anyone who probes the guard, whereas a missed discharge inconveniences one author once and is never written down anywhere a later reader could find it.

The transferable tell is that **a rewrite inherits the old implementation's accidental tolerances as unstated requirements.**
The unanchored search tolerated trailing punctuation by accident, nothing ever recorded that as a requirement, and so the replacement dropped it without any test going red.

**Why the fix moment is the dangerous one.**
You would expect scrutiny to be highest right after a reviewer names a class.
It is the opposite, and the mechanism is worth stating rather than leaving to care.
Having just been shown the class, you feel calibrated to it, so the sweep feels complete the moment the *named instances* are handled.
The reviewer supplied a list, and the list quietly becomes the population.
That is [`derive-dont-enumerate`](derive-dont-enumerate.md)'s failure arriving through a review finding instead of a dispatch brief, and [`metacognitive-monitoring`](metacognitive-monitoring.md)'s scope-claim failure --- check the population, do not recall it.
Note what the substitution does to the existing remedy.
[`address-every-comment`](address-every-comment.md) already says to derive the site list by grepping "the whole diff", and that search space was fixed before the fix's own lines existed.
Re-running that sweep *after* the fix is what closes the gap, and nothing about writing a correction prompts a second run.

**This is not algorithmatizable in general, and saying so is the honest answer** rather than a gap to be filled later.
"Did the sweep cover the diff's own added lines?" has no decidable condition.
Deciding it needs the *class* the reviewer named, which lives in prose and differs every round, so any lexical proxy a hook could key on is uncorrelated with whether the sweep actually ran.
That is exactly [`algorithmatize-checks`](algorithmatize-checks.md)'s "Limits" case, where a guard that misfires gets switched off and takes the real cases with it.
No decidable slice was found worth building either.
The nearest candidate --- warn when a fix commit's added lines contain the literal string a reviewer flagged --- fails on all three instances measured here, since none of them repeated a flagged literal.
Step 2 above obliges you to *ask* whether a finding is algorithmatizable, not to answer yes, so an answered no carrying its reason discharges that step as completely as a guard would.
Read `hooks/remind-learn-from-review.py`'s own ONE-OFF discharge clause as the adjacent case rather than this one.
That clause covers a finding with no rule behind it at all, and this finding has a rule --- the section you are reading.
What this finding has no room for is a hook.

- **Do:** after fixing an instance of class C, re-derive the population of C over the whole diff **including the lines this branch added**, and report the pattern searched and the hit count --- your fix's new lines are the highest-risk members and the ones no reviewer has looked at yet.
- **Do:** enumerate the residual **class** and name its commonest member whenever you write down an accepted residual, since naming one is itself a claim that you surveyed them.
- **Do:** enumerate what an implementation **accepted** before you delete it, not only what it wrongly accepted, and carry both halves into the replacement's tests.
- **Don't:** treat the reviewer's enumeration as the population once you have fixed every member of it --- feeling calibrated to a class is not having swept for it.
- **Don't:** write a "residual, named rather than papered over" paragraph around the first exception that comes to mind, since the naming is what makes it read as surveyed.
- **Don't:** read a rewrite as immune because it replaced the thing that was wrong --- it inherits the old implementation's accidental tolerances as requirements nobody wrote down, and dropping one fails safe and so leaves no artifact.

(Morrison-Lab/ai-config#1959, from rounds 2 and 4 of review on #1947.
All three instances landed in one PR, each inside the fix for the round before it, and each was found by the reviewer rather than by the sweep that had just run.)

A review series that stops finding defects has narrowed its search, not finished it.
The three sections above each fire inside a single round --- a finding accepted, a class recurring, a fix carrying the next instance of the class it just closed.
This one fires on the shape of the whole **series**, and it fires at the moment the series ends, which is the moment nothing else is looking.

**A reviewer's exhaustion is a scope claim about the family it searched, not about the class.**
A verdict reporting that it spent substantial effort looking for another bypass and could not construct one reads as coverage.
It is a report of a search, and like every scope claim it names a population --- so [`metacognitive-monitoring`](metacognitive-monitoring.md)'s scope rule applies to it unchanged: check the population rather than recalling it.
The increment is that the population belongs to somebody else, and the reviewer never stated it as a choice, so nothing in the verdict marks it as one.
Such a sentence almost always lists what it probed, usually in a parenthesis.
Read that list and ask what its members have in common.
When they share one mechanism, the claim covers that mechanism and is silent about every other way the same effect can be produced.

**The series is what chose the family, which is why the last round is the least likely to escape it.**
Each round inherits its search space from the previous round's findings, because a reviewer shown a bypass in option parsing goes looking for the next one in option parsing.
So a converging series narrows onto whatever family it opened in, and the rounds that feel most thorough --- the late ones, where every probe comes back empty --- are the ones searching the smallest space.
Convergence is therefore evidence about the reviewer's attention rather than about the artifact.
Note how this differs from the recurrence rule above, which fires when the same finding class keeps returning and asks whether your instrument can decide the question at all.
Here the findings stop returning, and the question is whether the reviewer was still looking in more than one place.

**So convergence is the moment to enumerate families, not the moment to stop.**
When several consecutive rounds all find defects in one mechanism, ask what *other* ways the guarded action can be spelled, and probe those yourself.
For a command guard the list is short enough to write out: an alias, a wrapper or an interpreter, a shell function, an environment variable, a config key, and a different tool reaching the same effect without ever running the command.
[`least-flexible-tool`](../coding/least-flexible-tool.md) covers the wrapper-and-interpreter rung of that list and says to name the rung you stopped on, which is the same observation about one family rather than about the set.

**A clean verdict discharges the round, and it does not discharge your own probing.**
This is the half that has no other trigger behind it.
An accepted finding has [`ardi`](ardi.md)'s dispositions, a recurrence has the rule above, and a red check has CI --- whereas a clean verdict produces no artifact at all, closes the loop, and reads as permission to stop.
The probe is cheap and it is not one-sided: it returns validated coverage as often as it returns a defect, and a family confirmed already handled is worth as much to a later reader as a family found open.
Report both, per [`report-mistakes-proactively`](report-mistakes-proactively.md), and file whatever the probe finds before the verdict's apparent finality makes it feel like old news.

- **Do:** read a reviewer's "I could not find another" as a report of the space it searched, and derive that space from the probes it lists.
- **Do:** treat several consecutive rounds finding defects in one mechanism as evidence the reviewer has locked onto that mechanism, and enumerate the other spellings of the guarded action before accepting the verdict.
- **Do:** probe the unsearched families yourself once the verdict comes back clean, and record the families the probe confirms as well as the ones it breaks.
- **Don't:** read an exhaustion claim as coverage of the class --- it covers the family, and the previous rounds chose the family rather than any survey.
- **Don't:** treat convergence as the series having finished, when the late rounds are the ones searching the smallest space and so the ones likeliest to come back empty for the wrong reason.
- **Don't:** let a clean verdict end your own probing --- the round is discharged, and nobody at all is looking at the families it never searched.

(Measured 2026-08-22 on the pre-push guard `hooks/no-push-without-self-review.py`, across two stacked PRs.
[ai-config#1932](https://github.com/Morrison-Lab/ai-config/pull/1932) merged into [#1911](https://github.com/Morrison-Lab/ai-config/pull/1911)'s branch at 16:32Z, and its own body tabulates nine review rounds: rounds 1 through 8 each raised at least one finding, four of them raising a defect the previous round's fix had introduced, and round 9 raised none and returned **Ready for merge**.
Six further `claude-review` rounds then ran on #1911 between 17:55Z and 21:21Z, and the last of them returned **Ready for merge** on `51be639e` while reporting no new findings to post.
That PR, #1911, was still unmerged at the time of this reading.
That final round described the previous round's six findings as "all about a specific bypass class", and its own exhaustion sentence listed six probes --- option-abbreviation resolution, `-C` chaining, subshell depth tracking, wrapper-arg windows, deletion refspecs mixed with real ones, and stale-verdict-versus-fresh-SHA interactions.
Every one of the six is git option parsing.
The live bypass outside that family was found the same evening by probing rather than by any round: a git alias expanding to a push (`git config alias.p 'push --mirror'`, then `git p origin`) is not matched by the shared `_argv_push` detector at all, so neither push guard fires, filed as [#1993](https://github.com/Morrison-Lab/ai-config/issues/1993).
`alias.p = push` is among the commonest git aliases in ordinary use, so the unsearched family was more reachable than any spelling the searched one produced.
The same probe returned a confirmation as well as a defect, establishing that `GIT_CONFIG_GLOBAL` was already caught by the wholesale environment overlay added in `51be639e`.
A third family --- the GitHub MCP write tools, which reach a remote branch with no `git push` for the guard to see --- was found by a dispatched `adversarial-reviewer` subagent rather than by `claude-review`, and is filed as [#1929](https://github.com/Morrison-Lab/ai-config/issues/1929).
That one is worth reading as evidence for the rule rather than against it: a different reviewer searched a different family, which is what makes family coverage a property of who looked rather than of how hard.)

## A later round can find a defect in the FIX rather than in the original code

Every rule above treats a review round as scrutiny of the diff you set out to write.
A round can instead find that **the previous round's fix was the defect**, and that case reads differently from the inside: the code under review is code you wrote *in response to a finding*, so it arrives already feeling validated.

Two shapes, both measured on Morrison-Lab/ai-config#2007 over three rounds.

**The over-correction.**
A finding says a pattern matches too much, and the fix narrows it past the target.
Here a guard's deferral patterns were narrowed twice in one commit -- a `to` requirement was added *and* the verb `left` was dropped -- to kill one false positive.
The `to` alone was sufficient.
Dropping `left` on top of it removed a construction the guard was supposed to catch.
Two changes shipped together, one of them load-bearing and one of them a regression, and the false positive disappeared either way, so nothing in the outcome distinguished them.

The tell is a fix that changes more than one thing in service of one finding.
Ask which single change is sufficient, and drop the rest.

**It recurred on the same guard, in the commit immediately after this rule was written.**
Round 2's narrowing was itself over-narrowed: requiring the connector to sit immediately after the deferral verb dropped every phrasing with a real noun-phrase object between them ("leave this decision to the reviewer", "flagging this concern for the maintainer"), which round 3 had to restore.
Both corrections shared a root the first one did not name: I was testing **adjacency** when the discriminator was **order** -- in a deferral the connector precedes the party, and in the innocent construction the party is the verb's indirect object and arrives first.
So an over-correction is often a sign that the discriminator itself is wrong rather than merely mis-tuned, and re-tuning a wrong discriminator produces another one.

**The tell is mechanical: consecutive fixes that all adjust the same knob.**
Three rounds on that guard each changed the width of one wildcard -- connector adjacent to the verb, then a bare pronoun allowed, then a short gap -- and a fourth round found why none could work.
The two senses being separated had the identical surface shape, so no width of wildcard could ever distinguish them.
What separated them was the identity of one word, and the fix was to enumerate that word's allowed values rather than to match around it.
Count the knob rather than the rounds: two fixes turning the same dial is the signal to ask what the test is measuring, and three is the signal to stop tuning and change its shape.
That the rule was written, and then broken within the hour by its author, is the ordinary case rather than a surprising one: a rule is consulted at read time and violated at composition time.

**The probe that fired for the wrong reason.**
I checked the over-correction before shipping it, with two sentences of the shape I had just removed.
One fired and one did not, and I read that as coverage.
It was not: the one that fired matched a *different alternative* in the same list, incidentally, on a clause the sentence happened to contain.
So the hole was real and my own probe concealed it.

That is the same failure the mutation rules in [`algorithmatize-checks`](algorithmatize-checks.md) describe, arriving one level out: not a test that never ran, but a test that ran, passed, and proved something other than what it was written to prove.
A passing probe is evidence only once you know *which* clause made it pass.

**The tests written to prove a narrowing safe must VARY along the axis you narrowed.**
This is the coverage shape that lets an over-correction ship green, and it is separate from the probe problem above.
Ten new cases went in with round 2's narrowing, and every one of them used the same sentence shape the narrowing happened to preserve -- a bare pronoun object.
None used a noun-phrase object, which is precisely what the narrowing broke, so the suite could not see the regression and neither could the cross-vendor reviewer's own run, which passed at that head.
A suite that grows while staying inside one shape reports coverage and adds none.
So when a fix restricts what a pattern accepts, ask what the restriction excludes and write a case on the far side of it -- the far side is where the regression lives, by construction.

**A correct diagnosis is what licenses the unsafe edit, which is why a well-understood finding is the dangerous one.**
The over-correction and the mis-fired probe above are both about the *content* of a fix.
This is about its *speed*, and it is the condition that produces both of those.
When the cause is genuinely understood, the edit that follows feels settled before it is written --- there is nothing left to work out, so there is nothing left to check --- and that feeling is indistinguishable from the edit actually being safe.
An unclear finding gets a careful fix precisely because the confusion forces a pass over it.

Measured while drafting [#3101](https://github.com/Morrison-Lab/ai-config/pull/3101).
Four such fixes, each resting on a diagnosis that was correct.
The first two were caught before their commit, so nothing in that PR's history records them and they are described rather than cited:

- Adding `2>/dev/null` to a timing loop fixed stderr interleaving and silenced the only remaining failure signal, so a nonexistent command reported a plausible fast spread (`0.007 / 0.003 / 0.003`).
- Moving a hard-to-time probe in-process fixed a misattribution and made the guard hang rather than fail.
- Narrowing a regex branch to option tokens only fixed a false positive and silently dropped `git clean -fdx <root>`, a real destructive form the previous draft caught --- the surviving comment in `hooks/flag-config-deletion-without-ref-check.py` records it.
- Adding a not-exhaustive note to a catalog document fixed an underived count claim and severed the document's own purpose statement onto the wrong sentence (`eca210dbf`), which the next round had to restore (`d8c88486f`).

Read the list by column rather than by row.
Each fix did what it was for;
each also broke something the finding it answered never mentioned --- a hidden failure signal, a stranded purpose statement, a dropped destructive form, a hang in place of a failure.
Three questions cover those four, and none of the three is the question the finding asks.
So ask them explicitly once the edit is written: what does this fix now hide, what does it now let through, and how can it now fail in a way it could not before?
Then probe whichever one the edit exposes, before reporting the fix, rather than probing the finding again.

**Re-running the original failing case is the probe this list does not otherwise ask for.**
The far-side case the coverage rule above prescribes catches what a narrowing excluded.
It says nothing about whether the fix still does its own job, and a fix that hides a signal can pass a far-side case while quietly failing the case that prompted it.
The `2>/dev/null` fix is the cheapest illustration: it silenced the very failure it was added to tidy, so the original probe was the only one that could have caught it, and it was the one probe nobody thought to repeat.

- **Do:** ask what a fix now hides, what it now admits, and how it can now fail, and probe whichever of those the edit exposes before reporting the fix.
- **Do:** re-run the original failing case after a fix, alongside the far-side case, so the fix is shown still to do its own job.
- **Do:** ask which single change is sufficient for a finding, and ship only that one.
- **Do:** write at least one case on the far side of any restriction you add, varying the axis the restriction acts on.
- **Do:** check *which* alternative made a probe fire before reading it as coverage.
- **Don't:** treat code written in response to a finding as pre-validated --- it is a new diff and gets a new review.
- **Don't:** conclude a class is covered because one member of it fired.
- **Don't:** treat a correct diagnosis as evidence the edit implementing it is safe --- being right about the cause says nothing about the patch.

## A cosmetic pass over a paragraph is not a read of it

A round whose brief is narrow and mechanical -- a red formatting check, a lint fix, a rename -- edits lines without engaging their content.
That is efficient and correct as far as it goes, and it produces a specific blind spot: a **carried-over finding living in the very paragraph you just reformatted** survives the round, because the paragraph was processed rather than read.

It is worse than not touching the file at all.
Editing a paragraph creates a strong impression of having covered it, so the next round's re-raise reads as new rather than as repeated, and the reviewer has to say "carried over, unaddressed" to be believed.

Measured on Morrison-Lab/ai-config#2011: a round fixed CI-red semantic line breaks in a section, and left standing an already-raised finding one line away -- that the section's own worked example cited another repo's PRs as bare `#NNN`, the exact defect the section documents.
The reformat rewrote that line's neighbours and never engaged it.

- **Do:** re-read a whole paragraph you reformat, and check it against any open finding on that file.
- **Do:** treat a re-raised finding as evidence that the previous round's brief was too narrow, not that the reviewer is repeating itself.
- **Don't:** count a mechanical edit as coverage of the lines it touched.
