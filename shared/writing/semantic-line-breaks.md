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
tests something narrower, against each **newly added** prose line in the diff.
Its primary rule flags a line holding more than one sentence.
Since gha#336 it also carries a **clause** rule, on by default: a line whose
markup-stripped text reaches 80 characters and carries a mid-line semicolon.
Neither rule is a character count, and the clause rule is the only one that
looks at length at all.

Two consequences.
A single long line carrying exactly one sentence and no mid-line semicolon
passes, so the URL-inflation exception above still needs no special casing in
the check.
And a line that packs two short sentences fails even at 50 characters, which
is the violation to actually look for before pushing.
Fix a flagged line by breaking at the sentence boundary, not by rewrapping
the paragraph to a narrower column.
(ai-config#712: assuming an 80-character limit sent me measuring line lengths
against the wrong criterion; reading the retired script's own source settled
it, and the real check then found 7 multi-sentence lines a length check had
passed over.)

**This repo's own reformatter is not that check, and its output can fail it.**
`scripts/semantic-line-breaks.py` is the in-repo tool named for this
convention, so it is the obvious thing to reach for when a line-break warning
needs clearing.
It is not what CI runs, and the two disagree about what a good line is.

The reformatter implements one sentence per line and nothing else.
Its own docstring says as much --- "Never break a phrase mid-way at a column
boundary" --- so it has no width policy, and it **joins** a hand-wrapped
sentence back into a single line however long that line becomes.
Corpus practice is the clause-wrapped 60-to-80 range this file opens with,
which the reformatter undoes.

Nothing runs it in CI.
`grep -rn "semantic-line-breaks.py" --include=*.yml .` returns no workflow;
its only callers in the tree are its own test file and one docstring
reference.
`MD013` is off repo-wide in `.markdownlint-cli2.jsonc`, so no width gate
exists either.

Measured by copying two fragments out of `origin/main`, reformatting each
copy with `--all`, and classifying both versions with the gate's own
`classify_line`:

| fragment (at `origin/main`) | longest line | lines over 80 | clause-flagged |
| --- | --- | --- | --- |
| `semantic-line-breaks.md` before | 80 | 0 | 0 |
| `semantic-line-breaks.md` after | 387 | 97 | 10 |
| `grep-is-not-coverage.md` before | 79 | 0 | 0 |
| `grep-is-not-coverage.md` after | 411 | 59 | 5 |

So the reformatter clears the sentence rule and manufactures clause
violations the gate then reports, on files that had none.
The classifier was pinned in both directions first, per
[`fail-fast`](../principles/fail-fast.md)'s negative-control rule: it returns
`clause` on a padded semicolon line, `sentence` on a two-sentence line, and
`None` on a short clean one.

It still finds real violations, which is what makes it worth running --- the
same two fragments carry 5 and 0 genuine multi-sentence lines at
`origin/main`.
So use it as a **detector** and read its preview, which is its default when
no `--write` is passed.
Take the sentence splits it proposes, and break at a clause boundary yourself
rather than accepting the joins.

- **Do:** read the reformatter's preview and apply its sentence splits by
  hand, wrapping at a clause boundary.
- **Do:** re-run the gate after any reformat, since the joined lines are added
  lines and the gate is diff-scoped.
- **Don't:** treat `scripts/semantic-line-breaks.py` as the check CI runs ---
  no workflow invokes it, and its output is not what the gate wants.
- **Don't:** accept a join that puts a wrapped sentence back on one line; that
  is the direction that trips the clause rule.

(Morrison-Lab/ai-config, 2026-08-15, measured on this machine with the gate at
`Morrison-Lab/gha@da46419`, whose `_DEFAULT_CLAUSE_BREAKS` is `True` and
`_DEFAULT_CLAUSE_MIN_LENGTH` is 80.)

**Third dated recurrence, 2026-08-21, and the tell is the tool's name.**
An `ardia` sweep drove three PRs whose prose it had edited, ran
`scripts/semantic-line-breaks.py` on each, read its silence as the gate being
satisfied, and pushed.
The gate then failed on `memories/preferences.md:151` --- a 197-character line
with a mid-line semicolon, which the reformatter itself had produced by joining
two hand-wrapped lines.
A detector for the two documented rules, run afterwards across every branch that
sweep had pushed, found the same violation on two more of them.

Nothing about that sequence felt like skipping a step, which is why the existing
Don't pair above did not fire.
The reformatter is named for the convention, lives in this repo's own `scripts/`,
and its silence is a positive-sounding all-clear --- so reaching for it reads as
having checked rather than as having substituted one tool for another.
That is [`verify-the-right-artifact`](../workflow/verify-the-right-artifact.md)'s
adjacent-artifact substitution, arriving through a tool whose name matches the
check it is not.

The laundering step is worth naming separately, because it is what let the error
reach a reviewer.
The sweep reported "`semantic-line-breaks.py` scoped to the added lines
(canonical)" in a PR comment, which reads as a gate result and is not one.
A verification sentence naming a tool is only as good as that tool's relationship
to the check being claimed, and here there is none.

**The same run corrected a false cause claim.**
The sweep had already diagnosed a different PR's failure on this gate as the
added line opening with `(`, and "fixed" it by joining the new text onto an
existing case record --- deleting 8 lines to add 1, and leaving the semicolon in
place, so the fix could not have worked.
The real cause was the clause rule both times.
Per [`metacognitive-monitoring`](../workflow/metacognitive-monitoring.md)'s
**cause** claim type, the question that would have caught it is what else
produces a red gate on a one-line diff --- and the rule is documented directly
above, so the answer was one read away.

- **Do:** name the check you actually ran when reporting a line-break result,
  and say whether it was the gate or the reformatter.
- **Don't:** read the reformatter's silence as a gate pass --- it has no width
  policy, so it is silent about precisely the violation it creates.

**Fourth dated recurrence, 2026-08-24, the same day as #2085.**
PR #2071 carried a memory entry whose added lines passed a deliberate scoped
run of the reformatter ("0 would change") and then failed the gate on three
lines, each flagged as a long line with a mid-line semicolon.
The fix wrapped two clauses at their semicolons and reworded a third
parenthetical so it needed none (heads `456a6c87` -> `57116043`).
[Issue #2085](https://github.com/Morrison-Lab/ai-config/issues/2085) records
the same root cause from PR #2073 hours earlier.

What this instance adds to the pairs above is that diligence did not help.
The author ran the local script on purpose, scoped to the added lines, and
read its clean result as clearance --- the substitution happened inside a real
check, not in place of one.
The second slip came at banking time: the failure was first written up as a
new `memories/github-actions.md` section forking a third record of this
lesson, until review consolidated it here instead.

- **Do:** search this fragment and the open issues for the root cause before
  banking a SemBr failure as a new memory entry.
- **Don't:** treat a clean scoped reformatter run on your own added lines as
  covering what the clause rule will read differently.

**A green check run named for this gate may never have run it, and both runs
carry the same name.**
The reformatter trap above is about the wrong *tool*.
This is about the right tool reporting success without measuring anything, and
it is harder to catch because there is nothing to notice: the check run is
green, its name is correct, and it sits in the same list as the real one.

The workflow's base-ref input is `github.event.pull_request.base.sha` on a
pull request and empty otherwise, which is deliberate --- it makes a push to
`main` skip cleanly instead of scanning the whole tree
(`.github/workflows/validate.yml`, the `new-line-breaks` job's own comment).
The consequence for a *branch* push is the part worth stating: that run has no
base ref either, so it skips the diff scan and concludes `success` having
examined nothing.

A PR therefore shows **two** check runs called
`new-line-breaks / check-new-line-breaks`.
Only the `pull_request`-triggered one is a verdict.
The `push`-triggered one is green unconditionally, so reading either one, or
reading "the check is green", answers a question it was never asked.

The asymmetry that makes this dangerous: the vacuous run can only ever say
success, so it never disagrees with a real failure loudly enough to notice ---
a red PR-triggered run and a green push-triggered run coexist in the same list,
and the green one is not evidence of anything.
Distinguish them by the triggering event rather than by the name, and prefer
the run whose `event` is `pull_request`.

- **Do:** read the triggering event of a `new-line-breaks` run before treating
  it as a verdict, since a PR carries one real run and one vacuous one under
  the same name.
- **Don't:** conclude the gate passed from a green check run alone --- confirm
  it was the `pull_request`-triggered one.

**The disagreement has a second, sharper form: the gate splits a boundary the
reformatter leaves whole.**
The clause case above is the reformatter doing too much, joining wrapped lines
the gate then flags.
This is the reformatter doing too little, leaving two sentences on one line that
the gate then flags as `Line packs more than one sentence`.
The two tools carry different sentence-boundary rules.
`scripts/semantic-line-breaks.py` has one break regex, `_SENT_BREAK_RE`, whose
lookahead demands an uppercase letter or markup after the period, so a sentence
ending in `.` before a lowercase word is no boundary to it.
The gate carries that same branch plus a second one the reformatter lacks,
`_SENT_BREAK_LOWER_RE` (reported in `d-morrison/gha` #389, added by gha#425), matching
`(?<=[a-z][a-z])([.!?])\s+(?=[a-z])` --- a period after two lowercase letters,
then a space, then a lowercase word.
So `...rules, or agents. opencode instead reads...` is one line to the
reformatter and two sentences to the gate, because the lowercased brand name
`opencode` follows the period after `agents`.
The reformatter does worse than fail to propose the split.
It **undoes** the split once you have made it.
`split_sentences()` collapses whitespace before applying `_SENT_BREAK_RE`, so a
hand-break at a lowercase-follower boundary is joined back onto one line ---
the reformatter reverts the very fix the gate is asking for.

That makes this case an exception to the remedy the section above gives.
"Read the reformatter's preview and apply its sentence splits by hand" is sound
for every boundary the reformatter can see, and silently destructive here,
because re-running it after a correct hand-break restores the violation.
The neighbouring guard rail does not cover it either: "don't accept a join that
puts a wrapped sentence back on one line" is framed around the **clause** rule,
and this is the **sentence** rule.

- **Do:** run the real `check-new-line-breaks.py` locally to catch a
  lowercase-follower boundary, and hand-break after the period.
- **Do:** treat a `.` before a lowercased package or brand name (`opencode`,
  `renv`) opening a sentence as a boundary the gate will split.
- **Don't:** read the reformatter leaving a line whole as evidence the gate
  passes it --- the reformatter has no lowercase-follower branch.
- **Don't:** re-run the reformatter over a hand-broken lowercase boundary.
  It will rejoin it, and the rejoin is silent.

(Both mechanisms verified by source, read on 2026-08-21:
the reformatter's single `_SENT_BREAK_RE` in `scripts/semantic-line-breaks.py`,
and the gate's `_SENT_BREAK_LOWER_RE` at `check-new-line-breaks.py:140` in a
fresh clone of `d-morrison/gha`, whose own `CLAUDE.md` records that gha#425
closed gha#389 by adding that branch.
The rejoin was reproduced directly rather than inferred: calling `reformat()`
on `"...or agents.\nopencode instead reads..."` returns the two lines joined
into one.)

**That check WAS advisory --- it warned and exited 0 --- and stopped being so
on 2026-08-18.**
`d-morrison/gha@e91b8bf` ("fail by default when violations are found",
gha#508/#509) flipped `_DEFAULT_FAIL` to `True`, and this repo's `validate.yml`
passes `NLB_FAIL: true` besides, so a violation now reddens the check rather
than annotating a green one.
Read this as a caution about the *file* as much as about the check: the
advisory claim was measured on 2026-08-15 and was wrong three days later,
which is the decay [`timestamp-volatile-claims`](timestamp-volatile-claims.md)
exists for.

The old advice --- read its output rather than its color --- is still worth
keeping, because it now points the other way.
A green **`pull_request`-triggered** job means the added lines passed.
Two other green results mean nothing was examined, and both come from the same
cause --- the script is diff-scoped, so a run against the wrong base, or against
no base at all, reports a clean exit over a diff it never looked at.
The local run does this when pointed at the wrong base ref.
The push-triggered CI job does it unconditionally, as the section above
records.

**The sentence rule has no minimum line length; only the CLAUSE rule does.**
`NLB_CLAUSE_MIN_LENGTH` (80) gates the mid-line-semicolon check alone, so a
SHORT line carrying two sentences is flagged all the same.
That asymmetry is the one worth remembering, because a hand-rolled pre-push
scan naturally applies one length floor to both and then passes a line the
gate rejects --- which is the specific way this was rediscovered, on the PR
that added this very paragraph.
Run it locally before pushing and fix what it names --- the script lives in a
[`d-morrison/gha`](https://github.com/d-morrison/gha) checkout, at
`check-new-line-breaks/check-new-line-breaks.py` relative to that repo's root:

```bash
NLB_BASE_REF=origin/main \
NLB_PATHS_IGNORE='codex-skills/**,docs/**,_site/**,.quarto/**' \
  python3 <gha-checkout>/check-new-line-breaks/check-new-line-breaks.py
```

**`NLB_PATHS_IGNORE` is the one input the local run needs and does not
default to**, so a command without it over-reports on generated files this
repo's workflow excludes --- the `codex-skills/` wrappers most of all, since
they are machine-written and nobody is going to line-break them.
Everything else the workflow passes is already the script's own default, so
setting it changes nothing: `NLB_GLOBS` defaults to `*.md`, `NLB_FAIL` and
`NLB_CLAUSE_BREAKS` to true, and `NLB_CLAUSE_MIN_LENGTH` to 80 (read off
`check-new-line-breaks.py` at `d-morrison/gha` `430393d`, and confirmed
against a passing job's own log, which prints every `NLB_*` value it used).
The practical consequence is worth stating in the safe direction: the clause
check that catches a long line with a mid-line semicolon **is** on by default
locally, so a local run cannot silently under-report that case.
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

**A third dirty-tree symptom, and the only one that flags a line you never
touched: the line NUMBERS come from the commit and the line CONTENT comes
from the tree.**
Both cases around this one describe the check reporting the *committed*
state --- vacuously clean, or stale.
This one reports a line that is unchanged in both states and appears in
neither's diff, which is why it reads as a checker bug rather than as the
run-after-committing rule firing again.

The mechanism is one function boundary.
`_added_line_numbers()` derives its line numbers from
`git diff --unified=0 <base>...HEAD`, so they are numbered against **HEAD**.
`find_violations()` then does `path.read_text()` and indexes
`lines[line_no - 1]`, which is the **working tree**.
An uncommitted insertion above shifts every later line, so the two
snapshots disagree by exactly that many lines and the check classifies a
neighbour it was never pointed at.

That is [`verify-the-right-artifact`](../workflow/verify-the-right-artifact.md)
inside a single instrument: an index from one artifact, content from
another.
It also explains why the flagged line is often a long pre-existing one ---
the corpus has many, and any of them can drift under the cursor.

- **Do:** commit, then re-run, before believing a flag on a line your diff
  does not contain.
- **Do:** check whether the reported line appears in `git diff -U0` at all;
  absent means the numbering is off, not that the checker is wrong about
  the line's contents.
- **Don't:** hand-edit the flagged line --- it is someone else's line, and
  editing it makes a pre-existing violation yours.
- **Don't:** file it as a checker bug; the check is documented to diff
  `<base>...HEAD` and never claimed to read the tree consistently.

(Measured 2026-08-21 on
[ai-config#1787](https://github.com/Morrison-Lab/ai-config/pull/1787).
A dirty-tree run flagged `skills/post-merge/SKILL.md:916`, an anti-pattern
bullet about force-pulling a diverged checkout, roughly 140 lines from the
nearest edit.
`git diff origin/main -- <path>` did not contain it and `git diff -U0` put
it outside every added hunk;
the merge base carried it verbatim.
Committing and re-running cleared it with no edit to that line.)

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

**Re-run markdownlint in that block too, even though it is not line-scoped ---
it is the only one of these that actually reddens `validate`.**
The rule above enumerates line-scoped checks, and a reader takes the
enumeration as the list: this check, the banned-punctuation scan,
`lint-changed-lines`.
Markdownlint is not on it, because it is whole-file rather than diff-scoped,
so nothing about the phrase "line-scoped check" reaches it.

Its scope and its severity run opposite to everything else in the block, which
is what makes the omission expensive.
`validate.yml` runs both `npx --yes markdownlint-cli2` and
`check-new-line-breaks` as blocking checks (each fails the job on a non-zero
exit).
Markdownlint is the one the ordering rule above leaves out, and a reflow can
introduce a rule violation none of the enumerated line-scoped scans can see ---
MD018 when a split lands an issue reference in column 1 (the section further
down owns that collision), and MD022 when it disturbs the blank line around a
heading.

- **Do:** run markdownlint last, alongside the line-scoped checks, after every
  diff-mutating pass.
- **Don't:** read "line-scoped checks" as the whole re-run list --- the
  whole-file one is the only one that can fail the build.

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

Run that diff in **both** directions, though, and not only in the
did-anything-go-missing direction its wording invites.
A token the move *added* is as much a violation of that premise as one it
dropped, and a one-sided comparison passes over it --- which is how a
`grep '^+'` extraction's own `++ b/<path>` diff header rode into merged prose
in ai-config#1290.
Note also what the normalization costs: a dropped blank line contributes no
words, so this instrument cannot see a paragraph boundary the move collapsed
either.
[`fail-fast`](../principles/fail-fast.md)'s third pattern direction owns both
halves.
(ai-config#779, 2026-07-28: a demo reformat of one of gha's changelog
fragments dropped its leading `- ` and rewrote an em dash as `---`.
The check reported the result clean; the word diff found both.)

**A third blind spot, and the one that survives running the diff both ways: a
defect BOTH sides share.**
The two above are differences the normalization cannot represent.
This one is a defect the normalization deliberately ERASES, so the comparison is
not merely silent about it --- it is silent in both directions at once, and the
both-ways rule just above buys nothing against it.

The reasoning is short.
A both-sides comparison validates the TRANSFORMATION, never the INPUT.
Whatever class of difference the normalization exists to ignore, whitespace and
inline markup here, is exactly the class it cannot report --- and a flaw already
present in the ORIGINAL text falls in that class as readily as one the reflow
would have introduced.
The check then passes with a reassuringly specific word count, and the defect
ships untouched.

The worked shape is a hyphenated compound the author split across a line break,
`close-` ending one line and `order foot.` opening the next.
Collapsing `\s+` to a single space turns the pre-reflow and the post-reflow text
alike into `close- order foot.`, so the word lists match exactly and the check
reports nothing lost and nothing added, while both versions render that stray
space.

So pair the transformation check with one aimed at the INPUT.
For a reflow the cheap one is a scan for a line ending in a hyphen, anchored on
an alphanumeric so this corpus's own `---` convention does not flood it:

```bash
grep -rnE '[[:alnum:]]-$' shared/
```

Run it against the PRE-reflow text as well, since its whole point is to judge
text the comparison has already agreed with itself about.
Do not answer this by widening the normalization instead, per
[`address-every-comment`](../workflow/address-every-comment.md)'s rule that
extending a normalizer can break a term the previous version matched.

- **Do:** name the class of difference a normalization erases, and add a check
  aimed at that class over the input.
- **Do:** run the input-side check on the pre-reflow text too --- a defect the
  comparison cannot see is one it never had an opinion about.
- **Don't:** read "identical, N words, nothing lost or added" as a statement
  about the text; it is a statement about the edit.
- **Don't:** widen the normalization to swallow such a defect --- that degrades
  the comparison it exists to make.

(2026-08-16: a design-doc reflow was verified this way and reported "identical,
6498 words, nothing lost or added", while `close-` / `order foot.` sat split
across a line break in both versions; it was caught by eye, reading the
reflowed output.
The detector above, run over `shared/` at `41d82611`, returns exactly four
pre-existing instances and no false positives from the `---` convention, so the
class is live in this corpus and the scan is precise enough to act on.)

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
usually means others: `git diff <base>...HEAD | grep '^+' | tail -n +2 |
sed 's/^+//' | grep -nE '^#[^ #]'` returns every added line that opens with a
bare `#`.
The `tail -n +2` is load-bearing whenever such a pipeline's output is *kept*
rather than filtered again --- the diff's own `+++ b/<path>` header starts with
`+` too, so it survives the first grep and the `sed` mangles it into
`++ b/<path>` instead of removing it.
Dropping it by position rather than by pattern is deliberate: no prefix
separates the header from an added line that itself begins with `++`, per
[`fail-fast`](../principles/fail-fast.md)'s third direction.
It is harmless in this particular pipeline only because the trailing `^#`
filter discards the mangled header anyway.

**`tail -n +2` strips exactly one header, so on a multi-file diff the
position trick under-corrects.**
A diff carries one `+++ b/<path>` header per file, all of them surviving the
`grep '^+'`, and `tail -n +2` removes only the first --- so a two-file diff
leaves one mangled `++ b/<path>` line in the stream, and an N-file diff
leaves N-1.
A trailing filter (the `^#` grep above) still discards them, but a pipeline
whose output is *counted* or *kept* silently inflates by N-1: an added-lines
count reads one high per extra file, and the phantom line reads as content.
For a count, skip the extraction entirely and sum
`git diff --numstat <base>...HEAD`'s first column, which has no headers to
strip.
For kept content, drop headers per file rather than by global position ---
`grep '^+' | grep -v '^+++ '` --- which is safe exactly when every `+++ `
line in the stream is a real header.
The dangerous class is an added source line beginning `++ ` (two pluses
then a space): git's own `+` prefix turns it into a raw `+++ ` line, which
no pattern can tell from a header, per the fail-fast caveat above.
So the precondition check is a per-line membership test, not a pattern and
not an aggregate: each `+++ ` line's target must be a changed file's
`b/<path>` or `/dev/null`, and any other target is a phantom.

```bash
git diff --name-only <base>...HEAD | sed 's|^|b/|' > /tmp/known
git diff -U0 <base>...HEAD | grep '^+++ ' | sed 's/^+++ //' |
  while read -r t; do
    [ "$t" = /dev/null ] && continue
    grep -qxF "$t" /tmp/known || echo "phantom: +++ $t"
  done
```

Any `phantom:` line means fall back to parsing the diff's hunk structure
instead of prefix-filtering.
An aggregate comparison --- the stream's `^+++ ` line count against
`--numstat`'s file count --- cannot serve here: a header-deflating file (a
binary, a mode-only change) and a `++ ` source line elsewhere in the same
diff cancel, leaving the totals equal over a stream that still carries a
phantom, while a per-item test has nothing to cancel.
Note the deflating files are irrelevant to the filter's own safety --- a
missing header drops nothing --- so the aggregate was also counting a
quantity the question never depended on.
The residual limit: a phantom whose text coincidentally names a changed
file's own `b/<path>` --- or is literally `/dev/null`, colliding with the
deletion-header sentinel the test skips --- is indistinguishable from a
real header by any stream inspection, so certainty past that point is
hunk-structure parsing.

- **Do:** count added lines from `--numstat`, not from a header-stripped
  extraction.
- **Do:** verify every `+++ ` line's target is a changed file's `b/<path>`
  or `/dev/null` before trusting a `^+++ ` header filter on kept content,
  and fall back to hunk-structure parsing on any phantom.
- **Don't:** reuse the single-`tail` pipeline on a multi-file diff when its
  output is counted or kept --- it was written for a one-file diff, and each
  extra file adds one phantom line.
- **Don't:** guard the header filter with a single-line pattern or an
  aggregate count --- a raw `+++ ` line matches every header pattern, and
  totals can cancel; only the per-line membership test decides it, up to
  the coincidental-path and `/dev/null`-sentinel limits above.

(Morrison-Lab/ai-config#1476, 2026-08-15, review round 1, finding 2: a PR
body claimed "13 added lines" over a two-file diff whose true count was 12
--- the extraction pipeline above had left the second file's `+++` header in
the stream, and the header was counted as an added line.
The reviewer derived 12 from the PR's own `additions` field; `--numstat`
confirms it.)

- **Do:** scan added lines for a column-1 `#` before pushing, with the same
  after-committing, three-dot discipline the other diff-scoped scans use.
- **Do:** reword the clause to open with a word, keeping the reference inline.
- **Don't:** rely on the punctuation or sentence-count scans to catch it ---
  neither reads column 1.
- **Don't:** fix only the line CI named; the same phrasing habit produces the
  collision wherever a clause happens to start with a reference.

**Repointing a citation to a longer filename can push an untouched
`memories/` file over its hard-gated size ceiling, with zero content added.**
The "Relocating prose" section above is about the *moved* content's own
lines growing.
The citing side has its own version, and it fires on a file you never meant
to touch beyond a one-word swap.
`memories/` files sit under a hard-gated ceiling --- the checker script
calls itself advisory, but `test_check_memory_file_size.py`'s own
regression test asserts the *live corpus* stays under it, which is a
different, non-advisory guarantee --- so a file already sitting exactly at
1200 lines has zero headroom.
Repointing one citation inside it to a longer replacement name rewraps the
sentence carrying it, and in this semantic-line-break corpus that rewrap can
add a whole line, pushing the file to 1201 and failing CI though not one
word of content changed.

- **Do:** after repointing a citation, `wc -l` any touched `memories/` file
  that was near 1200 lines, and re-wrap the sentence to recover the line if
  it crossed.
- **Do:** read `test_check_memory_file_size.py` itself, not just the
  checker script's docstring --- the docstring calls the check advisory,
  and the test suite hard-gates the live corpus anyway.
- **Don't:** assume a citation swap with no other content change cannot
  move a file's line count.

(Morrison-Lab/ai-config#1291, 2026-08-08: repointing citations from
`fully-clean.md` to the longer `review-verdict-pitfalls.md` inside
`memories/claude-bot-workflows.md` and `memories/github-actions.md` tipped
each from exactly 1200 to 1201 lines, failing `validate` with no content
change; fixed by re-wrapping the same sentences at a different clause
boundary, restoring both to 1200.)
