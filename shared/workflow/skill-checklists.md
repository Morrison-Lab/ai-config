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

Session-start freshness is Read-Do: `check-install.py` compares installed
copies against the checkout, so a report taken before the pull is not merely
early, it is measuring against stale reference content and can hide the
script itself.
A merge is Read-Do for the other reason -- nothing after it is a
confirmation, because the irreversible act already happened.

A pre-push sweep is Do-Confirm: its items are independent, so running the
test suite before or after the non-ASCII scan changes neither result.

- **Do:** state which kind a checklist is, in the heading or its first line,
  so a reader knows whether they may work ahead of it.
- **Do:** write Read-Do items as imperatives in execution order, and
  Do-Confirm items as past-tense confirmations of an observable fact.
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

## Mark the killer items

Gawande's term for the steps that are both most often skipped and most
costly to skip.
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

Five to nine items, ordered by execution.
Write each as an action plus its evidence, not a slogan.
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
