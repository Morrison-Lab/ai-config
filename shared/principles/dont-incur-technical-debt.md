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

## The one exception: an edit that would retire expensive evidence

Everything above says a diagnosed defect inside your own diff is yours to fix now,
and the discriminator is deliberately blunt: if the diff contains the thing you
diagnosed, it is the scope.
There is one case where deferring is nevertheless right, and it needs stating here
rather than being discovered as a plausible-sounding excuse later.

**The enabling fact is that a measurement is a function of the TREE, not the commit.**
`git rev-parse <commit>^{tree}` names content rather than history, so two commits
returning the same tree object have byte-for-byte identical checkouts, whatever their
SHAs, their parents, or what happened in between.
Any measurement that is a function of the working tree --- a test run, a benchmark, an
ops table, a scan of generated output --- therefore describes both commits **exactly**,
instead of merely being expected to still hold.
A comparison against a base reads two trees, so it carries over only when both match.

That makes a tree-identity proof a real asset, and it makes any edit to the tree a real
cost: the edit retires the proof, trading "the same object" for the weaker "identical
except for one comment".
Where the defect is trivial and the evidence is expensive, paying that cost to fix the
trivial thing is a net loss on a PR whose argument is that its measurements still apply.

**Three conditions, all of them, or this is just the excuse it resembles:**

- The defect is **non-behavioural** and its cost is bounded --- a weaker justification
  for a correct constant, a stale phrase in a comment.
  Never a wrong result.
- The evidence is **expensive to re-run** --- a bit-identity proof over a long
  simulation, a whole-catalog scan --- rather than a command you could simply repeat.
  Where re-running is cheap, re-run it and make the edit; the trade only exists because
  the evidence costs something.
- The deferral is **filed**, per [`issue-first`](../workflow/issue-first.md).
  "A tracking issue is not payment" above still governs: the issue records the debt, and
  what licenses it here is the evidentiary loss, not the filing.

Note the reason is **evidentiary**, where `issue-first`'s existing deferral licence is
about **scope**.
They are different reasons and neither implies the other.

**Two checks worth running before leaning on such a proof.**
Its mechanic already exists in this corpus for a different job:
[`claim-pr`](../workflow/claim-pr.md) compares `HEAD^{tree}` against
`origin/<branch>^{tree}` to decide whether a rejected push's remote commit is the *same
merge*, and requires identical tree **and identical parents**.
Here the parents differ by construction, so that check answers the wrong question ---
same command, opposite premise, per
[`check-purpose-before-reusing`](../workflow/check-purpose-before-reusing.md).
And [`memories/git.md`](../../memories/git.md) warns that a squash-merging repo leaves a
branch SHA unreachable, which would strand the citation.
A tree can outlive the commits that carried it, since a squash merge whose base has not
moved produces a commit on the default branch with the same tree as the branch head ---
but a squash after the base moved does not, so confirm rather than assume:

```bash
git rev-parse <merge-commit>^{tree} <branch-head>^{tree}   # equal => still checkable
```

- **Do:** compare tree objects before re-running a whole-tree measurement across a
  revert, restore, or rewrite --- changed SHAs do not mean changed content.
- **Do:** weigh an edit's evidentiary cost against the defect's, and file the deferral
  when the evidence wins.
- **Don't:** defer a behavioural defect on these grounds, or defer at all when the
  evidence is cheap to re-run --- the exception is bought by the re-run cost, not by
  owning a proof.
- **Don't:** read "same tree" as covering a comparison against a base unless both trees
  match; that measurement reads two.

(`Lacaedemon/sparta` #1255 -> #1256 -> #1257, 2026-08-13/15.
The central evidence in #1255 was a tree-identity proof: `7ac2901`, the head its
round-2 review verified, and `d243fb0`, its final head, are both tree
`cbfbc77f71e5ff0333434a606d240259383a9c5d`, so a bit-identity proof, an ops-counter
table and a demo-defect scan carried across without being re-run.
The intervening commit was a bot re-implementation, reverted --- not a rebase, which is
the route this reads as needing.
A stale phrase in a doc comment that same PR had authored was left unfixed for exactly
the reason above and filed as #1256; #1257 then fixed it **better** than the deferred
plan, adding a floating-point-contraction caveat for web exports that #1256 had not
considered.
The proof stayed checkable after the squash merge: `d8aaa03` on `main` carries the same
tree object, though none of the three branch SHAs is an ancestor of `main`.)


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

## De-duplication corrupts a test the same way, and that direction is invisible

The section above is the case everyone expects: two copies of one thing, so the
test checks the copies against each other rather than against reality.
The mirror runs the other way, and it arrives wearing this principle's own
vocabulary.

A test can assert two independent facts about a value that are each written as
a literal.
DRY says to name the value once and derive both from it, which is ordinarily
right.
When the two facts are *the fixture the test builds* and *the expectation it
checks*, deriving both from one constant makes them move together, so a wrong
constant satisfies both and the pair stops asserting anything about the world.

That inverts the usual reading of duplication.
Here the duplicated literals were the only thing holding the assertions apart,
so the refactor traded a real check for a self-consistency check, and it did so
in a commit whose message correctly says it removed a duplicate.

Nothing about the diff shows it.
The tests still pass, the constant is still correct, and the assertion still
names the property it always named.
Only a mutation reveals it: change the constant to something false and watch the
suite stay green.

So when a refactor pulls a literal out of a test, ask what the two sites were
*independently* claiming, and anchor whichever one made a claim about the world
against something the constant cannot move.
A filesystem check, a recorded output, or a value read from a different source
all work; another expression over the same constant does not.

The rule is not "leave duplication in tests".
It is that a **constant is not a source of truth**, so an assertion derived
entirely from one is a tautology however many steps separate the two.

- **Do:** mutate a named constant to a wrong value after de-duplicating a test,
  and require the suite to fail.
- **Do:** keep at least one assertion anchored outside the constant -- the
  filesystem, a fixture recorded elsewhere, an independently computed value.
- **Don't:** derive both a test's fixture and its expectation from the same
  constant and read the passing test as coverage.
- **Don't:** treat a DRY refactor of a test as behaviour-preserving because it
  changed no logic; it can change what the test is able to detect.

(`ucdavis/bcs#614`, 2026-08-09: `.github/scripts/detect-redaction-diff.py`'s
self-test asserted that the script's own path is excluded from its scan and
that the exclusion is reported.
Both were hard-coded literals.
Naming the path once as `SELF_PATH` made the fixture and the exclusion set both
derive from it, so a `SELF_PATH` naming a file that does not exist passed both
assertions -- verified by mutation, exit 0 -- while the pre-refactor duplicated
version would have caught it.
Repaired by adding a third assertion, `Path(SELF_PATH).exists()`, which the
constant cannot satisfy on its own.)

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
