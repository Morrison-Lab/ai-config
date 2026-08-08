Break lines in prose at major phrase and sentence boundaries — one clause
per line, roughly 60 to 80 characters — rather than wrapping at a fixed
column or writing one long line per paragraph. This matters most in files
under version control (Quarto `.qmd`, Markdown docs, and similar), since a
semantic break keeps a diff to the changed sentence instead of a whole
reflowed paragraph.

**When editing existing prose**, preserve the file's current line breaks
exactly — don't reflow to a single long line or a different wrap width.
**When writing new prose**, add breaks at phrase/sentence boundaries as you
go.

**When a review flags a semantic-line-break violation, fix every
over-length line in the touched section in one pass** — not just the
specifically-flagged ones. Review bots (`@claude` / Copilot) re-scan on
each push and flag the next batch of adjacent borderline lines the prior
round left alone, so fixing only what was named drags the PR through round
after round of the same finding (UCD-SERG/lab-manual#297 took five review
rounds this way). Doing the whole section in one pass is how you spend
fewer rounds --- not a reason to stop iterating, which is never on the
table (see [`ardi`](../../skills/ardi/SKILL.md)'s "Stopping conditions").

**URL-inflation exception:** a line that runs long *only* because of an
embedded `[text](long-url)` link — where the visible prose before the link
is well under 40 characters — is fine as-is. Don't force an awkward
mid-clause break just to shorten the raw line; review bots themselves
classify these as borderline / acceptable.

**When reviewing prose, suggest semantic-line-break fixes — don't insist on
them.** Flag lines that ignore clause/sentence boundaries as a style
suggestion, the same weight as a word-choice nit: worth raising, not worth
blocking approval over, and not worth re-raising if the author declines.
This is distinct from the rule above: that one governs how thoroughly to
fix violations once a review has flagged them; this one governs the
weight to give the finding when you are the reviewer in the first place.

**What CI actually enforces is one sentence per line, not a character
count -- don't reflow to 80 columns thinking the check demands it.**
The 60-to-80 range above is guidance for a human writing prose.
The automated check backing it (`check-new-line-breaks`, a reusable
workflow in [`d-morrison/gha`](https://github.com/d-morrison/gha); formerly
ai-config's own `scripts/check-new-line-breaks.py`, retired in ai-config#703)
tests something narrower: for each **newly added** prose line in the diff,
it flags the line only when that line holds more than one sentence.
Two consequences.
A single long line carrying exactly one sentence passes, so the URL-inflation
exception above needs no special casing in the check.
And a line that packs two short sentences fails even at 50 characters, which
is the violation to actually look for before pushing.
Fix a flagged line by breaking at the sentence boundary, not by rewrapping
the paragraph to a narrower column.
(ai-config#712: assuming an 80-character limit sent me measuring line lengths
against the wrong criterion; reading the retired script's own source settled
it, and the real check then found 7 multi-sentence lines a length check had
passed over.)

**That check is advisory: it warns and exits 0, so a green CI job does not
mean the diff is clean.**
It emits `::warning::` annotations and a `N line(s) pack more than one
sentence/clause` summary, then exits successfully, so the job it runs in
reports success either way.
Read its output rather than its color --- this is the same
green-check-does-not-mean-clean-content pattern
[`review-verdict-pitfalls`](../workflow/review-verdict-pitfalls.md) documents
for review jobs, and it is easy to miss precisely because nothing turns red.
Run it locally before pushing and fix what it names --- the script lives in a
[`d-morrison/gha`](https://github.com/d-morrison/gha) checkout, at
`check-new-line-breaks/check-new-line-breaks.py` relative to that repo's root:

```bash
NLB_BASE_REF=origin/main \
  python3 <gha-checkout>/check-new-line-breaks/check-new-line-breaks.py
```
(ai-config#725: a round of review fixes introduced 7 multi-sentence lines; the
check flagged all 7 while `validate` stayed green, and the review bot did not
catch them either --- they were found only by reading the check's own output.)

**Run it AFTER committing, not before: it diffs `<base>...HEAD`, so
uncommitted work is invisible to it and a pre-commit run reports clean
vacuously.**
This is a nastier version of the advisory-exit-0 trap above, because here
the output is a positive all-clear rather than a warning nobody reads.
With nothing committed yet, `HEAD` still equals the base ref, so the diff is
empty and the script says `No lines missing semantic breaks` --- a true
statement about an empty diff, easily misread as a verdict on the work in
the tree.
The tell is that it passes instantly on a diff you know is large.
So commit first, then run it, then amend or add a fixup for whatever it
names.
And when quoting the result as evidence (a PR body's verification section),
re-run it against the pushed head rather than reusing an earlier run's
output.
(ai-config#752, 2026-07-27: the pre-commit run reported clean and that claim
went into the PR body; the same content flagged 7 lines the moment it was
run again after committing.)

**On a branch that already has commits, the same mistake reports the opposite
symptom: the violations you just fixed, quoted in their pre-edit form.**
The case above assumes nothing is committed yet, so `HEAD` equals the base
and the diff is empty.
Fixing a *review* finding is the other situation, and the more common one:
the branch already carries commits, so the diff is not empty --- it is simply
the committed state, which still holds the long lines whose replacements sit
uncommitted in the tree.
The check duly reports them.

That inverts the misreading, and the inverted one is worse.
A vacuous all-clear at least invites suspicion, whereas this output looks
like a fix that did not work --- which invites re-editing prose that is
already correct, or doubting where the reviewer's finding actually pointed.
The tell from the case above, passing instantly on a large diff, does not
fire here, because the check runs normally and reports real lines.
The tell for this one is that the flagged text is the *old* wording of lines
you know you changed: if the report quotes a string no longer in the file, it
is describing `HEAD` rather than your tree.
One `grep` for a quoted fragment settles it.

So the rule is unchanged and only the failure looks different: commit first,
then measure.

- **Do:** re-run the check after committing whenever it flags lines you
  believe you already fixed, before touching the prose again.
- **Don't:** conclude a reflow failed because a pre-commit run still reports
  the old lines.

(Morrison-Lab/ai-config#835, 2026-07-30: a round-2 reflow was checked before
committing, and the scan returned the original 154- and 175-character lines
verbatim.
Re-running after the commit reported 0 multi-sentence lines and 1 over-80
line out of 38 added.)

**A rebase or cherry-pick expires the result, so re-run it after moving the
commit to a new base.**
The rule above covers a check that ran too early, against an empty diff.
This is its mirror: a check that ran correctly, and whose answer has since
stopped applying.
A diff-scoped check answers a question about `<base>...HEAD`, so changing the
base asks a different question, and the previous answer is about a diff that
no longer exists.

Cherry-picking onto a fresh `main` is the usual way this happens, and it is
the worst moment for it, because attention is on whether the *content*
survived the move.
The checks feel like settled history rather than like something the move
invalidated, so nothing re-runs them, and the PR opens carrying an all-clear
that was true of a different diff.

Treat any change of base as invalidating every diff-scoped result at once:
this check, the banned-punctuation scan in
[`ascii-punctuation-in-source`](../coding/ascii-punctuation-in-source.md),
and a repo's own `lint-changed-lines`.
The re-run is seconds; the alternative is a reviewer finding what your own
instrument already knew how to find.
(Morrison-Lab/ai-config#833 -> #836, 2026-07-29: #833 merged while a
follow-up commit was mid-push, so that commit was cherry-picked onto a fresh
branch off the new `main`.
The check had passed on the old branch and was not re-run against the new
head; review then flagged a two-sentence line, which the re-run reproduced on
the first try.)

**A reflow pass of your own expires it too, because the range has two ends and
a rebase only moves one of them.**
The section above states the mechanism generally --- a diff-scoped check
answers a question about `<base>...HEAD` --- and then narrows its conclusion to
the base.
The narrowing is what lets this through.
`HEAD` moves far more often than the base does, and it moves because of your
own edits, so a reformatting pass expires every line-scoped result taken before
it even when nothing rebased and every check ran at the right moment.

The mechanism is that a reformat changes **which lines are added**.
Splitting a long line at a sentence boundary retires one added line and creates
two, and neither of the new ones was in the set an earlier scan examined.
So the earlier answer is not merely old.
It is an answer about lines that no longer exist.

A reflow is the worst of the diff-mutating passes to run late, and the one a
pre-push sweep most encourages running late, because its findings arrive as
warnings to clear rather than as content to write.
Regenerating a generated tree and merging `main` do the same thing on a larger
scale.

The failure is silent and reads as verified, which is what separates it from an
ordinary stale result.
The earlier check genuinely passed, so its output is a true measurement --- and
a true measurement is exactly the kind of thing that gets quoted into a commit
message and a PR body's verification section, where a reviewer meets a specific
numeric claim with nothing in the diff to contradict it.

The remedy is ordering rather than vigilance: run every diff-mutating pass
first, and every line-scoped check afterwards, as one block at the end.
Ordering is checkable, and a resolution to remember is not.

- **Do:** run every diff-mutating pass --- a reflow, a rewrap, a re-sort, a
  generator re-run, a `main` merge --- before any line-scoped check, and run
  the checks last as one block.
- **Do:** re-run a line-scoped check after any pass that edited the diff,
  including one whose whole purpose was to satisfy a different check.
- **Don't:** treat a check's result as durable because it was taken after
  committing and with the three-dot range --- that range's `HEAD` end moves
  with every edit you make.
- **Don't:** quote a check's output in a commit message or PR body without
  re-running it at the head you are about to push.

(Morrison-Lab/ai-config#1259, 2026-08-07: `3c2cd225` moved 38 case records out
of `CLAUDE.md`, then converted em-dashes on the diff's added lines, verified
with `git diff | grep -c` for banned glyphs at 0, then reflowed long lines to
clear `check-new-line-breaks`, verified at 0 warnings, then pushed quoting the
punctuation result.
The reflow split a list item, so the line carrying an em-dash was not in the
set the punctuation pass had scanned, and that pass was never re-run.
Review found the surviving glyph at `CLAUDE.md:420` --- the only one left in
the whole diff --- and noted that it contradicted the commit message's own
claim.
Fixed in `a06aa88f`.
Both passes ran after committing and with the three-dot range, so every remedy
this file offered was already being followed.)

**Relocating prose makes its multi-sentence lines yours, for the same
diff-scoped reason.**
Moving a section between files edits none of its lines and still puts every one
of them in the diff as an added line, so a file split or extraction hands you
the whole moved body to reformat.
[`ascii-punctuation-in-source`](../coding/ascii-punctuation-in-source.md) owns
the full statement of this, including why the scope-creep caution does not apply
and why deferring to a corpus-wide sweep does not either --- read it there
rather than re-deriving it.

Two mechanics specific to this check when you do the pass.
Use the real `check-new-line-breaks` rather than a hand-rolled matcher: a local
heuristic disagrees with it in both directions, over-reporting on ordered-list
markers and under-reporting a boundary like `.)` where the period is not the
last character before the space.
And prove the reflow changed nothing else, by comparing whitespace- and
markup-normalized word lists against the pre-move version --- a mechanical
reflow is exactly the operation that can silently drop a marker or a clause.

**When hand-reformatting a line the check flagged, copy the raw line rather
than the check's own report of it.**
The script strips a bullet marker or blockquote prefix before handing the
text to its sentence splitter, which is right for counting sentences and
wrong for reproducing the line.
So a reformat built from that output quietly loses the `- ` or `> ` the
original carried: a changelog entry stops being a list item while every
sentence inside it stays intact.

Nothing catches that on its own.
Re-running the check passes, because it re-strips a marker that is no longer
there to strip, and the reformatted prose reads correctly to a human.
The one instrument that decides it is a word-level diff of the two texts with
whitespace normalized away --- a dropped marker shows up as a missing token,
and so does any punctuation the reformat rewrote in passing.
Treat both as real findings rather than noise, since the whole premise of a
reformat is that only line wrapping changed.
(ai-config#779, 2026-07-28: a demo reformat of one of gha's changelog
fragments dropped its leading `- ` and rewrote an em dash as `---`.
The check reported the result clean; the word diff found both.)

**Breaking a line just before an issue reference turns it into a malformed
heading.**
This corpus writes `#NNNN` references constantly and mandates one clause per
line, so the two conventions eventually collide: a clause beginning with an
issue number puts `#` in column 1, markdownlint reads it as an ATX heading with
no space after the hash, and `validate` fails MD018.

It is worth knowing because of *where* it surfaces.
The banned-punctuation and multi-sentence scans both pass, since neither looks
at column 1, and the line reads perfectly as prose --- so the first report comes
from CI, on a file whose content is entirely correct.
Nothing about writing the sentence suggests a formatting problem.

Reword so the clause opens with a word rather than the reference:
prefer "Round 2 on #1287 sharpens why" over the possessive form that leads with
the number.
Note that quoting the bad form in prose reproduces the fault whenever the quote
wraps onto a fresh line, which is how this very paragraph first failed.
Derive the class rather than fixing the reported line, since one collision
usually means others: `git diff <base>...HEAD | grep "^+" | sed 's/^+//' |
grep -nE '^#[^ #]'` returns every added line that opens with a bare `#`.

- **Do:** scan added lines for a column-1 `#` before pushing, with the same
  after-committing, three-dot discipline the other diff-scoped scans use.
- **Do:** reword the clause to open with a word, keeping the reference inline.
- **Don't:** rely on the punctuation or sentence-count scans to catch it ---
  neither reads column 1.
- **Don't:** fix only the line CI named; the same phrasing habit produces the
  collision wherever a clause happens to start with a reference.
