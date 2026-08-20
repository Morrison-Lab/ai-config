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

The lever that actually delivers a clean first push is the pre-push self-review [`ardi`](ardi.md) already requires: run the project's own review skills and checks against your own diff *before* pushing, so a finding you would have accepted is one you caught yourself.
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
You claimed the PR --- posted the "paws off" comment, per [`claim-pr`](claim-pr.md) --- and while you are driving it, another actor performs an action that was already yours to have taken.
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
