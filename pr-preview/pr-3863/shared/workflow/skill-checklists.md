Use checklists in skills deliberately, not by default.

A checklist is not a summary of a procedure, and it is not a teaching
document.
It is a short list of items confirmed at one specific moment, chosen because
each one has been missed before and the miss was expensive.
The prose in a skill teaches; the checklist only reminds.

## When a checklist earns its place

Add one only when all three are true:

1. **Repeatable:** the same failure mode recurs across sessions.
2. **High-cost miss:** missing the step causes real churn (extra review
   rounds, broken CI, duplicate work, incorrect "clean" claims).
3. **Observable:** each item can be confirmed mechanically ("did we post the
   claim comment", "did we resolve every inline thread"), not by vague
   judgment.

The third condition is the one that does the work, and it is the same
standard [`algorithmatize-checks`](algorithmatize-checks.md) applies: an item
a reader can satisfy by feeling confident is not an item.

## Pick the type: Do-Confirm or Read-Do

Atul Gawande's *The Checklist Manifesto* splits checklists into two kinds.
The choice is not stylistic.
It follows from whether the steps are independent.

- **Do-Confirm.** Do the work from judgment and experience, then stop at a
  designated point and confirm every item actually happened.
  This is the default for our skills, because most of what they cover is
  reversible and the failure mode is an omission found later: a review round
  that missed a finding, a push that did not carry the fix, a wrap-up that
  skipped its own last step.
- **Read-Do.** Read each item and perform it in order, like a recipe.
  Reserved for work where the order is load-bearing, or where a step cannot
  be undone once taken.

The tell for Read-Do is that **reordering the steps changes the answer**.

Session-start freshness is Read-Do: `install-hooks.py` compares `settings.json`'s registered hooks against the checkout's own `hooks/hooks.json`, so a report taken before the pull is not merely early, it is measuring against stale reference content and can miss an entry that merged since.
A merge is Read-Do for the other reason -- nothing after it is a
confirmation, because the irreversible act already happened.

A pre-push sweep is mostly Do-Confirm: running the test suite before or after
the non-ASCII scan changes neither result.
Read that as a fact about *that pair* rather than about the sweep, because a
pre-push list usually holds items that edit the diff as well as items that
measure it --- and a reflow, a regeneration, or a `main` merge changes which
lines are added, so a scan taken before one of them is answering about lines
that no longer exist.
Those items are Read-Do by this section's own criterion, and
[`ardi`](ardi.md)'s checklist pins their order.

- **Do:** state which kind a checklist is, in the heading or its first line,
  so a reader knows whether they may work ahead of it.
- **Do:** write Read-Do items as imperatives in execution order.
- **Do:** in a Do-Confirm list, match the tense to what the item confirms ---
  past tense for an **action** that had to happen ("the whole test suite ran",
  "the changelog was re-read"), present tense for a **state** that has to hold
  right now ("every inline thread is resolved", "all check runs are green").
  An action written in the present tense reads as an aspiration rather than as
  something to look up, which is the slip this distinction prevents.
- **Don't:** write a Read-Do list for independent items -- it forces a
  serial order that buys nothing and invites working around the list.
- **Don't:** write a Do-Confirm list for an irreversible sequence, where
  "confirm the backup exists" after the migration is not a check at all.

## Name the pause point

Every checklist needs the moment it fires, stated explicitly, in the
checklist itself.
"Place it where the miss happens" is the design rule; naming the moment is
what makes it fire.

A good pause point is an observable event, not a phase: **before `git
push`**, **before posting the round summary**, **before reporting the PR
ready**, **before recommending the session end**.
A checklist headed only by a topic has no trigger, so it is read by whoever
was already going to be careful.

This matters most where the pause point is the *last* step of a skill, since
that is exactly where a new request tends to arrive and preempt it -- the
failure `CLAUDE.md`'s "A new instruction arriving at a checkpoint does not
cancel the checkpoint" describes.

### An item run before its pause point is banked, not discharged

The paragraph above covers a pause point preempted from *after*, by a request
that arrives and displaces it.
The mirror failure comes from *before*: you run one of the list's own checks
early, while the work is still in flight, and carry its result forward to a
pause point that then never happens.

That is worse than skipping the item outright, which is the whole reason it
needs naming.
A skipped item leaves you knowing it is outstanding.
An early-run one leaves you believing it is discharged -- and the belief rests
on a real command with real output, so nothing about it reads as a gap.

Diff-scoped checks are the ones this bites, because a diff is exactly the
input that *changes* between the moment you feel like running a check and the
moment the checklist fires.
A `<base>...HEAD` scan run mid-edit compares committed history against itself,
cannot see the working tree at all, and returns a clean zero that is true of
an empty diff and says nothing about the work.
That the corpus already states this three times over -- narrowly in
[`semantic-line-breaks`](../writing/semantic-line-breaks.md), generally in
[`address-every-comment`](address-every-comment.md), and as a checklist item
in [`ardi`](ardi.md) naming punctuation and the three-dot range outright --
is the evidence that restating it a fourth time is not the fix.
Knowing the rule is not what fails here; the item is skipped at the pause
point because it feels already done.

Two things actually help.
Put the *timing* inside the item, as `ardi`'s does ("run *after* committing
and with the three-dot range"), so an early run reads as not-yet-done rather
than as done.
And prefer a check that reports its denominator, per
[`fail-fast`](../principles/fail-fast.md)'s hand-check section: a scan
reporting `0 findings in N added lines` cannot be banked, because a premature
run visibly reports `N = 0`.

- **Do:** re-run a pause-point check at the pause point, however recently you
  ran it, whenever anything has been committed or edited since.
- **Do:** write the timing into the item itself, so running it early is
  visibly not running it.
- **Don't:** carry a diff-scoped check's result across a commit -- the commit
  is precisely what changes its answer.
- **Don't:** read a zero from a check you ran early as evidence about work you
  did afterwards.

(Morrison-Lab/ai-config#1178, 2026-08-06: four skill files were edited, and a
punctuation scan over `git diff -U0 origin/main...HEAD` reported "banned
punctuation in added lines: 0", which was then reported as verification.
Nothing was committed at that moment, so the scan compared committed history
and never saw a line the edit had written.
Commit `1edc5037` landed three em-dashes in `skills/ard/SKILL.md` and
`skills/merge-it/SKILL.md`; a parallel session fixed them in `ebd39ade`
(a PR-branch commit, squashed into `7a5b2ce0`).
`ardi`'s checklist item already named banned punctuation, the after-committing
timing, and the three-dot range, and was never run at the pause point --
running the same scan earlier had felt like discharging it.)

### An item a guard exempts is neither run nor skipped

The section above names two states an item can be in: skipped, where you know
it is outstanding, and run early, where you believe it is discharged on real
output.
A third sits between them and is commoner than either.
The item is never run and never skipped.
It is **exempted** --- a guard inside the procedure says the item does not
apply in this case --- and the belief that it is settled rests on the guard
rather than on any command.

That defeats the earlier section's own consolation.
"A skipped item leaves you knowing it is outstanding" is true of a skip and
false of an exemption, because an exemption is not experienced as omitting
anything.
It is experienced as the checklist not applying.

**A guard with two clauses is read by whichever clause is cheaper to satisfy.**
The failure needs no carelessness, only an asymmetry: one clause is a property
of the situation you can see at a glance, and the other takes work.
[`post-merge`](../../skills/post-merge/SKILL.md)'s recursion guard is the
worked example.
It skips the UMS step when the merged PR *was itself a UMS or learnings PR*
**and** *no new lessons emerged from its own review loop*.
The first clause is trivially true of every learnings PR, which is the only
kind of PR the guard ever fires on, so it is satisfied before you have read the
second.
Once a guard reads as satisfied, nothing prompts evaluating the rest of it, and
the conjunction quietly becomes its first conjunct.

Diagnosing this as an under-specified guard is the wrong repair, and it is the
repair that suggests itself.
That guard already spells its second clause out in as many words, and the
skill's own pause-point checklist already demands the skip be stated.
Both went unperformed together, which is the finding rather than a coincidence:
a guard that reads as satisfied suppresses the check written to catch it.

**So the guard's output is a sentence, and silence is the failure.**
An exemption that genuinely fires produces something like "skipped under the
recursion guard; the review loop raised nothing that is not already in the
diff", which names both clauses and is checkable by someone else.
An exemption nobody writes down is indistinguishable from an item nobody
reached, and only one of those is legitimate.
Write the sentence at the pause point, and treat being unable to write the
second clause's half of it as the guard not having fired.

The two rules this most resembles are scoped elsewhere, and the difference
decides the remedy.
[`fail-fast`](../principles/fail-fast.md)'s "A guard's discharge fires on
positive success, not the absence of failure" and
[`algorithmatize-checks`](algorithmatize-checks.md)'s "A reminder guard's
discharge condition is a second matcher" both govern a guard you **ship** ---
code, a hook, a matcher --- where the fix is to narrow the condition or gate it
on attributable evidence.
That file's AND-clause rule is nearer still, and its remedy is a mutation test,
which needs something executable to mutate.
Here the guard is prose and the reader is the runtime, so none of those
remedies reach it and the stated sentence is the whole instrument.

- **Do:** state a guard's outcome as a sentence naming every clause, at the
  pause point, whether it fired or not.
- **Do:** treat a clause you have not evaluated as the guard not having fired,
  rather than as a clause to assume.
- **Don't:** read a multi-clause exemption as satisfied by the clause that was
  already true before you looked at it.
- **Don't:** repair this by sharpening the guard's wording --- the operative
  clause is usually written down already, and rewriting it changes nothing
  about whether anyone reaches it.

(`Morrison-Lab/ai-config`, 2026-08-07/08: seven PRs merged in one session
--- #1255, #1240, #1260, #1271, #1273, #1281, and #1285, from `18:01:52Z` to
`05:47:31Z` --- and every one was a learnings PR, so the recursion guard's
first clause held for all seven.
Steps 1 to 3 of `post-merge` ran each time: branches deleted, worktrees
removed, the main checkout restored on `main` and clean.
Step 4 was never performed and never reported, and step 5's killer item, which
exists for exactly this and requires a skip to be stated, was not run either.
The second clause did not hold: #1281's own review cycle had produced a further
lesson about dispatch pre-checks, surfaced in conversation and left unrecorded
by the UMS PR that cycle did produce.
The user had to ask "did you run ums?".)

## Mark the killer items

The term *The Checklist Manifesto* uses for the steps that are both most often
skipped and most costly to skip.
Gawande relays it from Boeing's own checklist practice, via the veteran pilot
Daniel Boorman, rather than coining it --- so cite it as the book's usage, not
as his invention.
Mark them, because a flat list of equals gets triaged under time pressure and
the item that gets dropped is whichever looks most like bookkeeping -- which
is frequently the killer item, since the dangerous steps are often the
undramatic ones.

Mark at most one or two per list, with a **bold label**, and say what goes
wrong if it is skipped.
Two we already know empirically:

- **The UMS pass** at the end of `post-merge` and `ardi`.
  A run reported complete whose UMS step never executed is the recorded
  failure, and skipping it discards learnings rather than delaying them.
- **The state sweep** in `wrap-up`.
  Recollection covers only the PRs this conversation created, so the sweep is
  the entire value of the step.

## Keep it short

Nine items is the bound that matters, and it is not arbitrary: five to nine is
the range Boorman gives as ideal for a pause-point list, on the reasoning that
attention drifts after roughly a minute of reading and people start skipping
steps.

Treat nine as a ceiling, and **not** five as a floor.
A boundary with three genuine failure points wants a three-item list; padding
it to five adds items that have never caught anything, which is exactly the
harm the deletion rule below describes.

Order by execution, and write each item as an action plus its evidence, not a
slogan.
When a list outgrows nine items, the usual cause is that it has started
teaching -- move the explanation into the prose above it and leave the
reminder behind.

Reuse one canonical checklist per skill family; aliases should point at that
location rather than copy it.

## A checklist is a draft until it has been used

Gawande's point that survives translation to this corpus: a checklist written
from imagination fails in the field, and the only way to find out is to run
it on real work.

So treat every checklist here as provisional, and treat UMS as its revision
loop.
When a checklist was followed and the failure happened anyway, the finding is
about the checklist -- an item too vague to fail, a pause point that fires
after the damage, a killer item unmarked -- not only about the incident.
Add, sharpen, or delete the item in the same pass that records the incident.

Deleting is a real outcome.
An item that has never once caught anything is training readers to skim the
list it sits in.

## Where checklists do not belong

Skip checklist-izing skills that are mostly design judgment, exploratory
research, or one-off improvisation.
For those, rigid boxes add noise and slow good decisions without reducing
real failure risk.

The same caution applies to frequency: a checklist whose items pass every
single time is indistinguishable from one nobody reads, and it spends
attention that the lists carrying killer items need.

## In review

Flag these with the same weight as the other workflow rules:

- A checklist with no stated pause point, so nothing triggers it.
- A checklist item that cannot be confirmed mechanically, per condition 3.
- A Read-Do list whose items are independent, or a Do-Confirm list guarding
  an irreversible step.
- A skill that reports a terminal state ("clean", "ready", "wrapped up")
  while a recorded, repeatable failure sits at that exact boundary with no
  confirm list -- the gap this fragment exists to close.
- Conversely, a new checklist added to a judgment-heavy skill, or one whose
  items restate the procedure above them rather than reminding of its risky
  boundary.
