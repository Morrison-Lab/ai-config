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
