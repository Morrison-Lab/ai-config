Don't incur technical debt.
When the right way to do the work in front of you needs a change you have not
made yet, make that change as part of the work, rather than shipping the
version that routes around it.

The rule bounds **new** work only: what you add is yours to get right, and the
un-migrated code you happened to land next to is not.
That bound is not a softening.
It is what makes the rule followable, since without it this reads as "refactor
everything adjacent", which nobody can comply with and everybody therefore
ignores.
"What this does not oblige" draws the line case by case.

## The case this comes from

Every section here refers to one incident, so it is worth stating once.

While adding a check to [`Morrison-Lab/gha`](https://github.com/Morrison-Lab/gha),
I needed a function mapping a unified diff to the new-file line numbers it
adds.
That function already existed in the same repository, as `added_lines()` in
`lint-changed-lines/added-lines.R`.
I did not reuse it, because cross-directory sourcing inside a composite action
is awkward, so I wrote a second copy.
My copy omitted the context-line branch, which silently misnumbers every
reported line after the first context line.

The offline test for my copy then reimplemented the same loop a third time, to
exercise it on a canned patch.
That third copy carried the identical omission, so it agreed with the code
under test and the test passed on wrong numbers.
It failed only because the expected values had been written out by hand.

Three copies of one function in one afternoon, two of them wrong, and the test
concealed the bug rather than catching it.

I then diagnosed the remedy correctly -- organize that repo's R code as a
package, filed as
[Morrison-Lab/gha#383](https://github.com/Morrison-Lab/gha/issues/383) -- and
recommended for deferral: land the new check as scripts now, package later.
That recommendation is what the directive corrected.

## Debt is incurred when you defer a fix you have already diagnosed

The dangerous moment is not the one where you fail to notice.
It is the one where you notice, name the remedy exactly, and decide it is out
of scope for the change in hand.

That moment is the most defensible-sounding one available, because three true
things converge on it.
The diagnosis is fresh, so you can state the remedy precisely and cheaply.
The scope argument is genuine -- the fix really is larger than the work you set
out to do.
And deferring reads as discipline rather than as a decision, which is the part
that does the damage: it feels like the mature call, so nothing prompts you to
weigh it as one.

None of the three changes what ships.
A defect you have named, in a diff you are about to push, ships as a defect
whose existence you documented.

Note the inversion against ordinary review triage, because the vocabulary
collides.
[`address-every-comment`](../workflow/address-every-comment.md)'s **Defer**
disposition and [`ardi`](../workflow/ardi.md)'s D step are both correct, and
neither licenses this.
Both concern a finding whose subject **already exists** and whose fix would
expand the PR.
Deferring here means writing the defect and the deferral into the same commit.

One question separates the two:

> Does the diff I am about to push contain the thing I just diagnosed as wrong?

If it does, the fix is not out of scope.
It is the scope.

## A tracking issue is not payment

Filing the issue is necessary, and it is not sufficient.

[`report-mistakes-proactively`](../workflow/report-mistakes-proactively.md)'s
"Filing is not gated on approval" section makes the neighbouring move for a
different artifact, and its reasoning holds here unchanged -- read it there
rather than re-deriving it here.

What differs is the direction of the error.
There, filing *is* the whole deliverable, and the failure is not filing.
Here filing is real work that ought to happen, and the failure is treating it
as the deliverable.
The issue records the debt; it does not pay it.

Filing also makes the deferral feel settled, which is worse than doing nothing
would have been.
An undocumented shortcut still nags.
A shortcut with an issue number attached has been converted into a plan, and a
plan does not nag.

Two consequences.
Do not let the act of filing terminate the decision -- file, then still ask
whether the fix belongs in this diff.
And when you do defer, say in the PR what ships broken because of it, rather
than only linking the issue, so a reviewer weighs a known defect instead of
reading a tidy cross-reference.

## What this does not oblige

Pre-existing un-migrated code is not debt *you* are incurring.
Encountering a module that should have been a package, a helper that should
have been shared, or two copies that predate you does not put their unification
in your scope.

The line is **authorship, not adjacency**: what you add, not what you happen to
be standing next to.

- Adding a second copy of a function that already exists -- yours, fix now.
- Editing one of two copies that already existed -- not yours to unify, though
  it is worth filing if nothing tracks it yet.
- Extending a pattern you judge wrong, in the shape it is already in -- a
  judgment call, and usually worth stating in the PR either way.
- Refactoring the surrounding module because you were in the file -- explicitly
  not required, and frequently the wrong call.

One clarification, because a neighbouring rule runs the opposite way and will
be generalized wrongly if left implicit.
[`ascii-punctuation-in-source`](../coding/ascii-punctuation-in-source.md) says
that editing a line makes its pre-existing violations yours.
That holds for a **diff-scoped lint**, where the unit is a line and the fix is
seconds.
It does not extend to structural debt, where the unit is a module and the fix
is a migration.
Touching a file does not make its architecture yours.

## Duplicated logic corrupts its own tests

This is a distinct failure from ordinary duplication, and the sharper half of
the incident above.

A test that reimplements the unit under test is not a test of that unit.
It is a test that two copies agree, and the two copies are not independent:
they were written minutes apart by the same author from the same mental model,
so they share its gaps exactly.
The test therefore reproduces whatever bug the code has, and reports it as a
pass.

That inverts what a test is for.
Ordinary duplication makes a bug *survive* in a second place; this makes the
instrument built to catch it vouch for it.

The tell is a test whose own setup or expectation logic mirrors the shape of
the code under test -- the same loop, the same branch structure, the same
parsing.
The remedy is that expected values must come from somewhere the implementation
cannot reach: hand-computed, a recorded real-world output, or an independent
tool.
In the incident above, the hand-written expectations were the only reason the
bug surfaced at all.

Distinct from
[`fixtures-are-not-evidence`](../workflow/fixtures-are-not-evidence.md), which
covers an inference drawn *from* a fixture back to the real system.
Here the fixture is fine and the defect is in the test's own logic.

## Relationship to the other principles

- **[DRW](dont-reinvent-wheel.md)** covers searching before building.
  This is the case one step later: you searched, you *found* the existing
  implementation, and you copied it anyway because reusing it was inconvenient.
  DRW's search step succeeded and the outcome was a duplicate regardless, which
  is why the two are not the same rule.
- **DRY** names what the duplicate violates.
  This rule names when the violation is committed -- at the moment of deferral,
  not at the moment of noticing.
- **KISS** is a live tension.
  The workaround is often simpler than the fix, considered as a single diff;
  KISS is about the construct, and this is about the sum, so a locally simple
  choice can still be the one that accumulates.

**YAGNI will look like a conflict, and is not one.**
YAGNI says do not build what you do not need; this says do not defer what you
have already found necessary.
The two never fire on the same object, because they differ in what is known.
YAGNI governs a **speculated future** requirement, and its whole content is
that you cannot yet tell whether it is real.
This governs a **present, diagnosed defect** -- something you have already
established is wrong, in code you are writing now.
A reader who feels the pull of both at once is usually holding a suspicion
rather than a diagnosis, and the way out is to settle which it is, not to
split the difference.

## Do / Don't

- **Do:** fix a defect you diagnosed while writing the code that carries it,
  in the same PR.
- **Do:** file the tracking issue *and* fix it -- the issue records the debt,
  it does not pay it.
- **Do:** state in the PR what ships broken when you genuinely must defer, not
  just the issue link.
- **Do:** derive a test's expected values from outside the implementation --
  by hand, from a recording, or with an independent tool.
- **Don't:** treat a fresh diagnosis plus a filed issue as grounds for
  shipping the workaround; that combination is where debt is incurred, not
  where it is managed.
- **Don't:** add a new copy of something that already exists because reusing
  it is awkward -- fix the awkwardness, or reuse it awkwardly.
- **Don't:** let a test reimplement the unit it tests.
- **Don't:** read this as an obligation to migrate pre-existing code you did
  not write; the bound is what you add.

## In review

Flag these with the same weight as the other standing review checks:

- A diff that adds a second copy of logic the same repository already has,
  where the PR or a linked issue acknowledges the duplication.
  The acknowledgement makes it worse, not better -- it establishes that the
  author knew.
- A PR that links a follow-up issue for a defect **inside its own diff**, as
  opposed to one in code it merely touches.
- A test whose expected values are produced by logic resembling the code under
  test.
- A "we will do this properly later" note with no statement of what ships
  wrong in the meantime.
