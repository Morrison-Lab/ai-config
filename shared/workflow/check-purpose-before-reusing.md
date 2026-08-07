Never take shortcuts, and never copy-paste or pattern-match blindly.
Before reusing a structure --- a template, a working script, a
neighbouring file's shape, a pattern from another tool --- state what the
original was **for** and what the new one is **for**, and confirm those
are the same kind of thing.
When they differ, the template does not transfer, however well it fits
mechanically.

This is not an argument against reuse.
[`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md) and the
3Rs "recycle" lens both push toward adapting what exists, and they are
right.
This is the check that makes adaptation safe: structural fit is
necessary and is not sufficient.

## The tell: your checks confirm the mechanism, never the purpose

The reason this survives ordinary diligence is that every check you
naturally run after adapting a template asks whether the **mechanism**
works, and none asks whether the **purpose** survived the substitution.

Same interface, same event, same test convention, passing tests: all
green, and the thing now does the opposite of what it should.
Nothing fails, so nothing prompts the question.

Two properties make it invisible from the inside.

**A template you wrote yourself, recently, gets the least scrutiny.**
Reusing something you just built and verified feels like *consistency*
rather than like assuming.
A pattern borrowed from a stranger's repo would have prompted more
suspicion than one you authored ten minutes earlier, which inverts the
scrutiny the situation actually warrants.

**Structural validity reads as evidence.**
The verification confirmed that the mechanism functions, not that the
mechanism should exist --- the same shape
[`fixtures-are-not-evidence`](fixtures-are-not-evidence.md) describes for
a fixture that has been green so long it reads as a specification.

No instrument decides this, and that is not an oversight.
Structural sameness is mechanical; purpose sameness is not, so it lands
squarely in the judgment residue
[`algorithmatize-checks`](algorithmatize-checks.md)'s "Limits" section
reserves.

## Not the opposite failure

`memories/preferences.md` uses "pattern-matching" pejoratively for
reading an example **too literally** --- applying a rule only to the
case it illustrates instead of to the principle behind it.
This rule warns about reading a template **too loosely**, carrying its
structure into a case whose purpose differs.

Same phrase, opposite directions, and they do not conflict: generalize
the *principle* a rule teaches, and do not generalize the *structure* an
implementation happens to have.

## The check

Two sentences, written out rather than felt:

1. The original exists to do X.
2. This new one exists to do Y.

Then ask whether X and Y are the same kind of thing.
When they are not, keep the interface if it genuinely helps and rebuild
the behaviour from the new purpose --- do not carry over the parts you
have not justified.

- **Do:** name the original's purpose and the new one's, out loud, before
  adapting a structure.
- **Do:** treat a template you authored recently as needing *more*
  scrutiny than a borrowed one, not less.
- **Don't:** read a passing test suite as evidence that the borrowed
  shape belongs --- it establishes that the mechanism works, never that
  it should exist.
- **Don't:** infer a convention from a sibling tool's shape without
  checking that tool's own reference for it.

## A bulk copy has the same failure at the level of a whole file

The check above assumes you are adapting one template you can look at.
A "port the set of X from repo Y" task usually copies a **directory tree**
instead, and the failure mode shifts from *purpose mismatch* to *state
mismatch*: some files in the incoming tree are genuinely new to the
target, and others already exist there under a different path, with their
own history.
A wholesale `cp -R` (or equivalent) cannot tell the two apart, so a file
that should have been a pure rename gets silently replaced by the source
repo's own, possibly-diverged copy.

Run the same two-sentence check per file rather than once for the whole
tree: does this path already exist in the target, and if so, is the
source repo's version authoritative for it, or is the target's own
history?
When the file already exists, treat the operation as a **relocation**
--- write the target's own current content (`git show <old-ref>:<old-path>`)
at the new path --- not an import.
Reserve the source repo's copy for files genuinely new to the target.

- **Do:** before bulk-copying a directory tree, check each incoming path
  against the target repo for an existing equivalent.
- **Do:** relocate an existing file with its own content intact; import
  only what's actually new.
- **Don't:** let a directory-level copy operation decide, by omission,
  that the source repo's version of a shared file wins.

## In review

Flag a diff that introduces a structure closely mirroring an existing one
where the two serve different purposes, and ask for the purpose
comparison rather than for the mechanism to be re-tested.
This is the arrival path for the "correct-looking implementation of the
wrong strategy" case in
[`fact-check-code-logic`](../coding/fact-check-code-logic.md)'s strategic
correctness section: the wrong strategy usually got there by copying a
working neighbour.

Flag a "port/adapt from repo Y" diff that replaces an existing file's
content with Y's version and calls it a move --- check whether the diff
is a pure rename (no hunks) or carries an unexplained content change
riding along with it.

(Corrected 2026-07-30: "cai: never take shortcuts, never copy-paste or
pattern match blindly; always think twice and critically about what you
are doing and how it might be wrong."
A `Stop` hook that blocks a message had just been written and verified.
Minutes later, asked to make a different rule mechanical, the session
reused that shape and swapped the regex --- producing a hook that would
have blocked *error admissions*.
The existing hooks block messages that are wrong to send; an error
admission is right to send, so the copy inverted the purpose while
remaining structurally valid at every step, with passing tests.
An earlier instance of the same failure is already recorded narrowly in
`memories/r-quarto.md`: a `.jarlignore` invented by analogy to other
tools' ignore-file conventions, structurally plausible and silently
inert, because nobody checked that tool's own config reference.)

(Caught by review, 2026-08-07: `UCD-SERG/serocalculator#639` ported a set
of Quarto extensions from `Morrison-Lab/rpt`.
One of them, `slidebreak`, already existed in the target repo at a
different path.
A wholesale `cp -R` of rpt's whole extension tree overwrote it with
rpt's own, trivially-diverged copy --- an `author:` field changed and
two blank lines picked up trailing whitespace, neither mentioned in the
PR description or commit message.
The `@claude` review caught both as "unexplained side effects of a
rename"; the fix was `git show <old-ref>:<old-path>` at the new path
instead of the source repo's copy.)
